// SonicMaster DSP is copied from Skyggedans/SonicMaster (MIT), pinned in
// docs/third_party/SONICMASTER_LICENSE.txt. Input: .nam JSON on stdin;
// output: exactly 8840 binary bytes on stdout; errors/progress on stderr.
mod generator;
use std::io::{Read, Write};
use std::path::Path;

const DI_BYTES: usize = 12_348_000;
const SIZE: usize = 8840;
const BIQUAD: [f64; 5] = [
  0.9963043928146362,
  -1.9926087856292725,
  0.9963043928146362,
  -1.9925950765609741,
  0.9926224946975708,
];
fn crc16(bytes: &[u8]) -> u16 {
    let mut crc: u16 = 0xffff;
    for &b in bytes {
        crc ^= b as u16;
        for _ in 0..8 {
            crc = if crc & 1 == 1 { (crc >> 1) ^ 0xa001 } else { crc >> 1 };
        }
    }
    crc
}
fn encode(arrays: generator::CloArrays) -> Result<Vec<u8>, String> {
    if arrays.array_a.len() != 128 || arrays.array_b.len() != 2048 || arrays.gains.len() != 4 {
        return Err("Unexpected DSP array sizes".into());
    }
    if arrays.array_a.iter().chain(arrays.array_b.iter()).chain(arrays.gains.iter()).any(|v| !v.is_finite()) {
        return Err("Non-finite DSP coefficients; no CLO will be emitted".into());
    }
    let mut b = vec![0u8; SIZE];
    b[0..4].copy_from_slice(b"VTSI");
    b[4..8].copy_from_slice(&(SIZE as u32).to_le_bytes());
    b[20..24].copy_from_slice(&8704u32.to_le_bytes());
    b[24..32].copy_from_slice(&1.0f64.to_le_bytes());
    for (i, &v) in BIQUAD.iter().enumerate() {
        b[64 + i * 8..72 + i * 8].copy_from_slice(&v.to_le_bytes());
    }
    for (i, &v) in arrays.gains.iter().enumerate() {
        b[104 + i * 4..108 + i * 4].copy_from_slice(&v.to_le_bytes());
    }
    b[124..128].copy_from_slice(&128u32.to_le_bytes());
    b[128..132].copy_from_slice(&128u32.to_le_bytes());
    b[132..136].copy_from_slice(&2048u32.to_le_bytes());
    for (i, &v) in arrays.array_a.iter().enumerate() {
        b[136 + i * 4..140 + i * 4].copy_from_slice(&v.to_le_bytes());
    }
    for (i, &v) in arrays.array_b.iter().enumerate() {
        b[648 + i * 4..652 + i * 4].copy_from_slice(&v.to_le_bytes());
    }
    let crc = crc16(&b[12..]);
    b[8..10].copy_from_slice(&crc.to_be_bytes());
    Ok(b)
}
fn run() -> Result<(), String> {
    let args: Vec<_> = std::env::args().collect();
    if args.len() != 3 || args[1] != "--reference" {
        return Err("Usage: pocketmaster_nam_dsp --reference path/to/nam_reference_di_44100.f32 < model.nam > model.clo".into());
    }
    let src = std::fs::read(Path::new(&args[2])).map_err(|e| format!("Cannot read DI fixture: {e}"))?;
    if src.len() != DI_BYTES { return Err(format!("Reference DI size mismatch: {}", src.len())); }
    let di: Vec<f32> = src.chunks_exact(4)
        .map(|ch| f32::from_le_bytes(ch.try_into().unwrap())).collect();
    let mut nam = String::new();
    std::io::stdin().take(32 * 1024 * 1024 + 1).read_to_string(&mut nam)
        .map_err(|e| format!("Cannot read .nam: {e}"))?;
    if nam.len() > 32 * 1024 * 1024 { return Err(".nam is too large".into()); }
    let decoded: serde_json::Value = serde_json::from_str(&nam).map_err(|e| format!("Invalid .nam JSON: {e}"))?;
    let arch = decoded.get("architecture").and_then(|v| v.as_str()).unwrap_or("");
    if arch != "WaveNet" && arch != "SlimmableContainer" {
        return Err(format!("Unsupported NAM architecture: {arch}"));
    }
    let arrays = generator::generate_clo_arrays(nam, di);
    let out = encode(arrays)?;
    std::io::stdout().write_all(&out).map_err(|e| format!("CLO write failed: {e}"))?;
    Ok(())
}
fn main() {
    if let Err(err) = run() {
        eprintln!("NAM conversion failed: {err}");
        std::process::exit(1);
    }
}
#[cfg(test)]
mod codec_tests {
    use super::*;
    #[test]
    fn encodes_valid_vtsi_header_crc_and_finite_arrays() {
        let data = encode(generator::CloArrays {
            array_a: vec![0.0; 128], array_b: vec![0.0; 2048], gains: vec![1.0; 4]
        }).unwrap();
        assert_eq!(data.len(), 8840);
        assert_eq!(&data[..4], b"VTSI");
        assert_eq!(u16::from_be_bytes(data[8..10].try_into().unwrap()), crc16(&data[12..]));
    }
    #[test]
    fn non_finite_output_is_rejected() {
        let mut gains = vec![0.0; 4];
        gains[0] = f32::NAN;
        assert!(encode(generator::CloArrays {
            array_a: vec![0.0; 128], array_b: vec![0.0; 2048], gains
        }).is_err());
    }
}
