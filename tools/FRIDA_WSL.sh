#!/usr/bin/env bash
# Launch Windows Frida Python from WSL using explicit Windows paths.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/.." && pwd)"
cd "$ROOT"
printf '\033[36m[PROJECT]\033[0m %s\n' "$PWD"
if [[ ! -f .venv/bin/activate ]]; then
  printf '\033[31m[ERROR]\033[0m Missing WSL .venv/bin/activate\n' >&2
  exit 2
fi
# This shell venv is for git/WSL utilities only; native Frida uses Windows Python.
source .venv/bin/activate
printf '\033[32m[VENV]\033[0m WSL environment activated (NOT used to run Frida)\n'
command -v wslpath >/dev/null || { echo '[ERROR] wslpath unavailable'; exit 2; }
WINPY="$ROOT/research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe"
[[ -f "$WINPY" ]] || { echo "[ERROR] Windows Python missing: $WINPY" >&2; exit 2; }
CFG="$ROOT/tools/frida_examples/${FRIDA_CONFIG:-htkpa_stage24c_stack.json}"
DLL="$ROOT/research/_LOCAL_FILES/vendor/5868USB.dll"
[[ -f "$CFG" && -f "$DLL" ]] || { echo '[ERROR] Config or original DLL missing' >&2; exit 2; }
SCRIPT_WIN="$(wslpath -w "$ROOT/tools/frida_capture.py")"
CFG_WIN="$(wslpath -w "$CFG")"
DLL_WIN="$(wslpath -w "$DLL")"
printf '\033[35m[FRIDA]\033[0m Launching Windows Python from WSL: %s\n' "$WINPY"
printf '\033[33m[ACTION]\033[0m Perform one NAM -> CLO conversion; Frida detaches after %s quiet seconds. Manager stays open.\n' "${FRIDA_AUTO_QUIET:-12}"
WATCH_ARGS=()
if [[ -n "${FRIDA_WATCH_CLO:-}" ]]; then
  [[ -d "$FRIDA_WATCH_CLO" ]] || { echo "[ERROR] CLO watch directory missing: $FRIDA_WATCH_CLO" >&2; exit 2; }
  WATCH_ARGS=(--completion-dir "$(wslpath -w "$FRIDA_WATCH_CLO")")
  printf '[WATCH] New/changed stable CLO in %s\n' "$FRIDA_WATCH_CLO"
fi
"$WINPY" "$SCRIPT_WIN" --config "$CFG_WIN" --module-file "$DLL_WIN" --auto-quiet "${FRIDA_AUTO_QUIET:-12}" "${WATCH_ARGS[@]}" "$@"
