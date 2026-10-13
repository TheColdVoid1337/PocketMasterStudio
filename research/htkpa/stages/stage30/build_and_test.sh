#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../../../.." && pwd)"
UPSTREAM_COMMIT="cb2abb9977efe2471979b380ed95daa56ab4fdb9"
LOCAL="$ROOT/research/_LOCAL_FILES/r8brain_src"
BIN="$ROOT/research/_LOCAL_FILES/r8brain_stage30/r8b_probe"
mkdir -p "$(dirname "$BIN")"
if [[ ! -d "$LOCAL/.git" ]]; then git clone https://github.com/avaneev/r8brain-free-src.git "$LOCAL"; fi
git -C "$LOCAL" fetch --depth 1 origin "$UPSTREAM_COMMIT"
git -C "$LOCAL" checkout --detach "$UPSTREAM_COMMIT"
ACTUAL="$(git -C "$LOCAL" rev-parse HEAD)"
[[ "$ACTUAL" == "$UPSTREAM_COMMIT" ]] || { echo "[ERROR] upstream mismatch" >&2; exit 2; }
printf "[R8B] Pinned upstream: %s\n" "$ACTUAL"
c++ -std=c++17 -O2 -fno-fast-math -I"$LOCAL" "$HERE/r8b_probe.cpp" -o "$BIN"
python3 "$HERE/check_r8b_stream.py" "$BIN"
printf "[PASS] Stage30 public r8brain synthetic streaming gate\n"
printf "[BIN] %s\n" "$BIN"
