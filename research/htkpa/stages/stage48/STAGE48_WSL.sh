#!/usr/bin/env bash
# Stage48 WSL handoff to Windows-x64 Frida with only ONE guarded metadata hook.
# Does NOT launch Manager, read waveform, install arbitrary agents or edit production.
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../../../.." && pwd)"
cd "$ROOT"

command -v wslpath >/dev/null || { echo "[ERROR] This wrapper is WSL-only" >&2; exit 2; }
[[ -f "$ROOT/.venv/bin/activate" ]] || { echo "[ERROR] Missing WSL .venv" >&2; exit 2; }
source "$ROOT/.venv/bin/activate"

WINPY="${FRIDA_WINPY:-$ROOT/research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe}"
[[ -f "$WINPY" ]] || { echo "[ERROR] Windows Frida Python not found: $WINPY" >&2; exit 2; }

DLL="${FRIDA_ORIGINAL_DLL:-$ROOT/research/_LOCAL_FILES/vendor/5868USB.dll}"
if [[ ! -f "$DLL" ]]; then
    DLL="$ROOT/research/_LOCAL_FILES/5868USB.dll"
fi
[[ -f "$DLL" ]] || { echo "[ERROR] Original ignored 5868USB.dll missing; set FRIDA_ORIGINAL_DLL" >&2; exit 2; }

: "${FRIDA_WATCH_CLO:?Set FRIDA_WATCH_CLO to the EXISTING WSL-visible Windows folder where new or updated CLO files are written.}"
[[ -d "$FRIDA_WATCH_CLO" ]] || { echo "[ERROR] CLO folder missing: $FRIDA_WATCH_CLO" >&2; exit 2; }

mkdir -p "$ROOT/research/_LOCAL_FILES/frida_captures"

printf '[CHECK] Python source self-test and SHA256 verification (WSL, no Frida)\n'
python "$HERE/metadata_probe.py" --self-test --dll "$DLL"

printf '[SAFETY] ONE Windows Frida hook, RVA 0x1190C, metadata only, no f64 reads.\n'
printf '[SAFETY] Manager must ALREADY be open. Wait for [HOOK] then perform ONE normal NAM->CLO conversion.\n'
printf '[SAFETY] A successful capture requires an observed valid fraction-stage vtable AND stable new/changed CLO.\n'
printf '[WATCH] %s\n' "$FRIDA_WATCH_CLO"

"$WINPY" "$(wslpath -w "$HERE/metadata_probe.py")" \
    --dll "$(wslpath -w "$DLL")" \
    --completion-dir "$(wslpath -w "$FRIDA_WATCH_CLO")" \
    --out "$(wslpath -w "$ROOT/research/_LOCAL_FILES/frida_captures")" "$@"
