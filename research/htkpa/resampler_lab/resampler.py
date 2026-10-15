#!/usr/bin/env python3
"""Small, auditable WAV/f64le frontend for the Stage66 C++ native-compat bridge.

Supported ONLY:
  reverse = 96000 -> 44100: fractional-only DSP (24-tap/673 phase)
  forward = 44100 -> 48000: full r8brain FIR+fractional DSP chain

WAV input: uncompressed PCM 8/16/24/32-bit mono/stereo. WAV output: PCM24.
Raw f64le input/output: interleaved IEEE754 little-endian, no WAV header.
No arbitrary sample-rate conversion, no latency removal, no hidden tail flush.
This is a lab, NOT the NAM-to-CLO converter.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import wave

import build

bridge = build.bridge
MODELS = {
    "reverse": (bridge.MODE_REVERSE, 96000, 44100),
    "forward": (bridge.MODE_FORWARD, 44100, 48000),
}
ALIAS = {"96000-to-44100": "reverse", "44100-to-48000": "forward"}
CHUNK_MAX = 2680


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decode_pcm(data: bytes, width: int) -> list[float]:
    if width not in (1, 2, 3, 4) or len(data) % width:
        raise ValueError("Unsupported/truncated PCM sample")
    if width == 1:
        return [(v - 128) / 128.0 for v in data]
    if width == 2:
        return [x[0] / 32768.0 for x in struct.iter_unpack("<h", data)]
    if width == 3:
        nums = []
        for p in range(0, len(data), 3):
            value = data[p] | data[p+1] << 8 | data[p+2] << 16
            if value >= 0x800000:
                value -= 0x1000000
            nums.append(value / 8388608.0)
        return nums
    return [x[0] / 2147483648.0 for x in struct.iter_unpack("<i", data)]


def encode_pcm24(values: list[float]) -> tuple[bytes, int]:
    data = bytearray()
    clipped = 0
    for x in values:
        if not math.isfinite(x):
            raise ValueError("Non-finite output from C++ DSP")
        integer = round(x * 8388608.0)
        if integer < -8388608:
            clipped += 1
            integer = -8388608
        elif integer > 8388607:
            clipped += 1
            integer = 8388607
        data.extend(integer.to_bytes(3, "little", signed=True))
    return bytes(data), clipped


def decode_f64le(data: bytes) -> list[float]:
    if len(data) % 8:
        raise ValueError("Raw Float64 data must be a multiple of 8 bytes")
    values = [v[0] for v in struct.iter_unpack("<d", data)]
    if any(not math.isfinite(v) for v in values):
        raise ValueError("Raw Float64 data contains NaN or infinity")
    return values


def encode_f64le(values: list[float]) -> bytes:
    if any(not math.isfinite(v) for v in values):
        raise ValueError("Non-finite Float64 output")
    return struct.pack("<" + str(len(values)) + "d", *values)


class AudioReader:
    """Stream PCM WAV or raw f64le without loading the entire audio file."""
    def __init__(self, filename: Path, rate: int | None, channels: int):
        self.path = Path(filename)
        self.extension = self.path.suffix.lower()
        self._file = None
        if self.extension == ".wav":
            try:
                self._file = wave.open(str(self.path), "rb")
                if self._file.getcomptype() != "NONE":
                    raise ValueError("Only uncompressed PCM WAV is supported")
                self.rate = self._file.getframerate()
                self.channels = self._file.getnchannels()
                self.width = self._file.getsampwidth()
                self.frames = self._file.getnframes()
                if self.width not in (1, 2, 3, 4) or self.channels not in (1, 2):
                    raise ValueError("WAV input must be mono/stereo PCM 8/16/24/32-bit")
                if rate is not None and rate != self.rate:
                    raise ValueError("Provided --rate contradicts WAV header")
            except (wave.Error, EOFError) as exc:
                self.close()
                raise ValueError("Invalid WAV or unsupported WAV encoding; use PCM WAV") from exc
            except Exception:
                self.close()
                raise
        elif self.extension == ".f64le":
            if rate is None or rate <= 0 or channels not in (1, 2):
                raise ValueError("Raw .f64le input requires --rate and --channels 1 or 2")
            self.rate, self.channels, self.width = rate, channels, 8
            total = self.path.stat().st_size
            if total % (8 * channels):
                raise ValueError("Interleaved Float64 file length is not divisible by channels")
            self.frames = total // (8 * channels)
            self._file = self.path.open("rb")
        else:
            raise ValueError("Input must end in .wav or .f64le")

    def read(self, frames: int) -> list[float]:
        if not 1 <= frames <= CHUNK_MAX:
            raise ValueError("Block size outside 1..2680")
        if self.extension == ".wav":
            values = decode_pcm(self._file.readframes(frames), self.width)
        else:
            values = decode_f64le(self._file.read(frames * self.channels * 8))
        if len(values) % self.channels:
            raise ValueError("Malformed input channel data")
        return values

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class AudioWriter:
    def __init__(self, filename: Path, rate: int, channels: int):
        self.path = Path(filename)
        self.extension = self.path.suffix.lower()
        self.clipped_samples = 0
        if self.extension == ".wav":
            self._file = wave.open(str(self.path), "wb")
            self._file.setnchannels(channels)
            self._file.setsampwidth(3)
            self._file.setframerate(rate)
        elif self.extension == ".f64le":
            self._file = self.path.open("wb")
        else:
            raise ValueError("Output must end in .wav or .f64le")

    def write(self, values: list[float]):
        if self.extension == ".wav":
            samples, clipped = encode_pcm24(values)
            self.clipped_samples += clipped
            self._file.writeframesraw(samples)
        else:
            self._file.write(encode_f64le(values))

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def resolve_mode(label: str, source_rate: int) -> tuple[str, int, int, int]:
    selected = (("forward" if source_rate == 44100 else
                 "reverse" if source_rate == 96000 else None)
                if label == "auto" else ALIAS.get(label, label))
    if selected not in MODELS:
        raise ValueError("Only 44100->48000 and 96000->44100 are verified; select --mode")
    mode_id, expected_input, output_rate = MODELS[selected]
    if source_rate != expected_input:
        raise ValueError(
            f"{selected} expects {expected_input} Hz input, got {source_rate} Hz")
    return selected, mode_id, expected_input, output_rate


def write_json_atomic(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    scratch = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", dir=path.parent, prefix=".htkpa_report_",
                suffix=".tmp", encoding="utf-8", delete=False) as f:
            scratch = Path(f.name)
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(scratch, path)
    finally:
        if scratch is not None:
            scratch.unlink(missing_ok=True)


def convert(source: Path, destination: Path, *, mode: str = "auto",
            rate: int | None = None, channels: int = 1,
            chunk: int = 1024, pad_input: int = 0,
            overwrite: bool = False, library_dir: Path | None = None,
            stream_factory=None) -> dict:
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output cannot be the same file")
    if destination.exists() and not overwrite:
        raise FileExistsError("Output exists; use --overwrite to replace")
    if not 1 <= chunk <= CHUNK_MAX:
        raise ValueError("--chunk must be within 1..2680")
    if not 0 <= pad_input <= 16384:
        raise ValueError("--pad-input must be within 0..16384")
    if not source.is_file():
        raise FileNotFoundError(source)

    with AudioReader(source, rate, channels) as reader:
        selected, mode_id, input_rate, output_rate = resolve_mode(mode, reader.rate)
        if stream_factory is None:
            lib, manifest = build.verify_library(library_dir)
            library = bridge.bind_abi(lib)
            stream_factory = lambda: bridge.Stream(library, mode_id)
            binary_sha = manifest["shared_object_sha256"]
        else:
            binary_sha = "TEST_DOUBLE_NO_NATIVE_BINARY"
        destination.parent.mkdir(parents=True, exist_ok=True)
        scratch = None
        sent_frames = 0
        output_frames = 0
        clipped = 0
        streams = []
        try:
            for _ in range(reader.channels):
                streams.append(stream_factory())
            with tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix=".htkpa_audio_",
                    suffix=destination.suffix, delete=False) as f:
                scratch = Path(f.name)
            with AudioWriter(scratch, output_rate, reader.channels) as writer:
                while True:
                    values = reader.read(chunk)
                    if not values:
                        break
                    if len(values) % reader.channels:
                        raise ValueError("Malformed multichannel frame")
                    frames = len(values) // reader.channels
                    sent_frames += frames
                    out = []
                    for channel in range(reader.channels):
                        raw = streams[channel].process(values[channel::reader.channels])
                        out.append(decode_f64le(raw))
                    if len({len(x) for x in out}) != 1:
                        raise ValueError("C++ streams returned inconsistent channel lengths")
                    writer.write([value for frame in zip(*out) for value in frame])
                    output_frames += len(out[0])
                if sent_frames != reader.frames:
                    raise ValueError(
                        f"Truncated audio: header/stat says {reader.frames} frames "
                        f"but read {sent_frames}")
                remaining = pad_input
                while remaining > 0:
                    n = min(remaining, chunk)
                    out = [decode_f64le(stream.process([0.0] * n))
                           for stream in streams]
                    if len({len(x) for x in out}) != 1:
                        raise ValueError("Channel lengths differ during explicit zero padding")
                    writer.write([value for frame in zip(*out) for value in frame])
                    output_frames += len(out[0])
                    remaining -= n
                clipped = writer.clipped_samples
            os.replace(scratch, destination)
        finally:
            for stream in streams:
                stream.close()
            if scratch is not None:
                scratch.unlink(missing_ok=True)
    result = {
        "tool": "HTKPA Resampler Lab",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "mode": selected,
        "input_hz": input_rate,
        "output_hz": output_rate,
        "channels": reader.channels,
        "real_input_frames": sent_frames,
        "pad_input_zeros": pad_input,
        "output_frames": output_frames,
        "input_sha256": sha_file(source),
        "output_sha256": sha_file(destination),
        "format": "PCM24 WAV (quantized)" if destination.suffix.lower() == ".wav" else "f64le (unquantized)",
        "clipped_samples": clipped,
        "block_frames": chunk,
        "bridge_sha256": binary_sha,
        "scope": "two verified modes only; no automatic filter tail flush or latency compensation",
    }
    return result


def compare(actual: Path, reference: Path) -> dict:
    actual, reference = Path(actual), Path(reference)
    if actual.resolve() == reference.resolve():
        raise ValueError("Compare needs independent actual and reference files")
    def is_float64(filename: Path) -> bool:
        return filename.name.lower().endswith((".f64le", ".f64le.bin"))
    if not is_float64(actual) or not is_float64(reference):
        raise ValueError("Exact comparison accepts only raw .f64le or .f64le.bin, not WAV")
    if (actual.stat().st_size != reference.stat().st_size or
            actual.stat().st_size % 8):
        raise ValueError("f64le file sizes must match and be a multiple of 8")
    if actual.stat().st_size == 0:
        raise ValueError("Cannot compare empty f64le files")
    digest_a, digest_b = hashlib.sha256(), hashlib.sha256()
    sumsq, native_sq, max_abs, equal, count = [], [], 0.0, 0, 0
    with actual.open("rb") as left, reference.open("rb") as right:
        while True:
            a, b = left.read(65536), right.read(65536)
            if not a:
                break
            digest_a.update(a)
            digest_b.update(b)
            x, y = decode_f64le(a), decode_f64le(b)
            delta = [v - w for v, w in zip(x, y)]
            sumsq.append(math.fsum(z*z for z in delta))
            native_sq.append(math.fsum(z*z for z in y))
            max_abs = max(max_abs, max(abs(z) for z in delta))
            equal += sum(a[k:k+8] == b[k:k+8] for k in range(0, len(a), 8))
            count += len(x)
    rms = math.sqrt(math.fsum(sumsq)/count) if count else 0.0
    reference_rms = math.sqrt(math.fsum(native_sq)/count) if count else 0.0
    return {
        "status": "COMPARED_SAME_INDEX_NO_SHIFT",
        "f64": count, "bit_equal": equal,
        "rms_error": rms, "max_abs_error": max_abs,
        "reference_rms": reference_rms,
        "relative_rms_error": rms/reference_rms if reference_rms else None,
        "actual_sha256": digest_a.hexdigest(),
        "reference_sha256": digest_b.hexdigest(),
    }
