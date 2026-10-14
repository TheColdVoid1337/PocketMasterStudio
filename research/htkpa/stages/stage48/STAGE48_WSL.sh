#!/usr/bin/env bash
# Stage48: zero-PID-typing Windows Frida console from WSL.
# One metadata hook only, never starts Manager or reads any waveform.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../../../.." && pwd)"
cd "$ROOT"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C=$'\033[36m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; M=$'\033[35m'; X=$'\033[0m'
  export FORCE_COLOR=1
else
  C=''; G=''; Y=''; R=''; M=''; X=''
fi
msg() { local color="$1" tag="$2"; shift 2; printf '%s[%s]%s %s\n' "$color" "$tag" "$X" "$*"; }
fatal() { msg "$R" ERROR "$*"; exit 2; }

command -v wslpath >/dev/null || fatal "Use WSL; wslpath not available"
[[ -f "$ROOT/.venv/bin/activate" ]] || fatal "Missing WSL .venv"
source "$ROOT/.venv/bin/activate"
WINPY="${FRIDA_WINPY:-$ROOT/research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe}"
[[ -f "$WINPY" ]] || fatal "Windows Frida Python missing: $WINPY"
DLL="${FRIDA_ORIGINAL_DLL:-$ROOT/research/_LOCAL_FILES/vendor/5868USB.dll}"
if [[ ! -f "$DLL" ]]; then
  DLL="$ROOT/research/_LOCAL_FILES/5868USB.dll"
fi
[[ -f "$DLL" ]] || fatal "Original DLL missing; set FRIDA_ORIGINAL_DLL to an ignored private file"

msg "$C" PROJECT "$ROOT"
msg "$C" VENV "WSL for preflight, Windows Python for Frida"
msg "$M" CHECK "Offline one-hook source self-test + original DLL SHA-256"
python "$HERE/metadata_probe.py" --self-test --dll "$DLL"

# This is a no-attach mode: it enumerates Windows PIDs only and stops.
for arg in "$@"; do
  if [[ "$arg" == "--list-processes" ]]; then
    msg "$C" DISCOVERY "Enumerating Windows processes only; no hook will be installed"
    "$WINPY" "$(wslpath -w "$HERE/metadata_probe.py")" --list-processes
    exit $?
  fi
done

# Normal path auto-detects the one Manager PID from Frida's process list.
# If FRIDA_WATCH_CLO is unset, derive the current Windows user's APPDATA
# in WINDOWS Python (not the WSL username). Never hardcode a username.
WATCH="${FRIDA_WATCH_CLO:-}"
if [[ -z "$WATCH" ]]; then
  WINWATCH="$("$WINPY" -c 'from pathlib import Path; import os; print(Path(os.environ["APPDATA"]) / "Sonicake" / "Sonicake Manager")' | tr -d '\r')"
  [[ -n "$WINWATCH" ]] || fatal "Could not obtain Windows APPDATA. Set FRIDA_WATCH_CLO."
  WATCH="$(wslpath -u "$WINWATCH")"
  msg "$C" WATCH "Auto-detected Windows APPDATA Sonicake folder"
fi
[[ -d "$WATCH" ]] || fatal "CLO watch folder absent: $WATCH (set FRIDA_WATCH_CLO explicitly)"
mkdir -p "$ROOT/research/_LOCAL_FILES/frida_captures"

msg "$G" READY "Original DLL SHA verified; existing Manager will be auto-detected"
msg "$M" HOOK "ONE metadata-only hook: original 5868USB.dll RVA 0x1190C"
msg "$Y" ACTION "After [HOOK], run ONE NAM-to-CLO conversion in Manager"
msg "$Y" NOTE "Press Ctrl+C to exit if needed; partial results will be preserved"
msg "$C" WATCH "$WATCH (recursive *.clo stat only; no CLO content read)"
msg "$C" OUTPUT "research/_LOCAL_FILES/frida_captures/stage48_*/"
"$WINPY" "$(wslpath -w "$HERE/metadata_probe.py")" \
  --dll "$(wslpath -w "$DLL")" \
  --completion-dir "$(wslpath -w "$WATCH")" \
  --out "$(wslpath -w "$ROOT/research/_LOCAL_FILES/frida_captures")" "$@"
