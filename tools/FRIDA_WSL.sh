#!/usr/bin/env bash
# UNIVERSAL WSL launcher for tools/frida_capture.py.
# Stage-specific behavior lives ONLY in the JSON config, not in this wrapper.
set -euo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/.." && pwd)"
cd "$ROOT"

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  CYAN=$'\033[36m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; MAGENTA=$'\033[35m'; RED=$'\033[31m'; RESET=$'\033[0m'
  export FORCE_COLOR=1
else
  CYAN=''; GREEN=''; YELLOW=''; MAGENTA=''; RED=''; RESET=''
fi
msg() { local color="$1" tag="$2"; shift 2; printf '%s[%s]%s %s\n' "$color" "$tag" "$RESET" "$*"; }
fail() { msg "$RED" ERROR "$*"; exit 2; }
command -v wslpath >/dev/null || fail "WSL wslpath is required"
[[ -f "$ROOT/.venv/bin/activate" ]] || fail "WSL .venv missing"
source "$ROOT/.venv/bin/activate"

WINPY="${FRIDA_WINPY:-$ROOT/research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe}"
[[ -f "$WINPY" ]] || fail "Windows Frida Python missing: $WINPY (set FRIDA_WINPY)"
DLL="${FRIDA_ORIGINAL_DLL:-$ROOT/research/_LOCAL_FILES/vendor/5868USB.dll}"
if [[ ! -f "$DLL" && -z "${FRIDA_ORIGINAL_DLL:-}" ]]; then
  DLL="$ROOT/research/_LOCAL_FILES/5868USB.dll"
fi
[[ -f "$DLL" ]] || fail "Private original DLL missing: $DLL (set FRIDA_ORIGINAL_DLL)"

# Accept --config from any stage directory; preserve old FRIDA_CONFIG defaults.
CFG="${FRIDA_CONFIG:-htkpa_stage24c_stack.json}"
ARGS=()
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--config" ]]; then
    [[ $# -ge 2 ]] || fail "--config needs a JSON path"
    CFG="$2"
    shift 2
  else
    ARGS+=("$1")
    shift
  fi
done
if [[ ! -f "$CFG" ]]; then
  if [[ -f "$ROOT/$CFG" ]]; then
    CFG="$ROOT/$CFG"
  elif [[ -f "$ROOT/tools/frida_examples/$CFG" ]]; then
    CFG="$ROOT/tools/frida_examples/$CFG"
  else
    fail "Frida JSON config missing: $CFG"
  fi
fi
CFG="$(realpath "$CFG")"

# Read mode, never import or execute stage-specific Python.
MODE="$(python - "$CFG" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding="utf-8")).get("mode","scalar"))
PY
)"
msg "$CYAN" PROJECT "$ROOT"
msg "$CYAN" CONFIG "$CFG"
msg "$MAGENTA" MODE "$MODE"
msg "$GREEN" CHECK "Universal Frida Python self-test (offline)"
python "$ROOT/tools/frida_capture.py" --self-test
msg "$YELLOW" SAFETY "Exact DLL SHA checked before attachment (and loaded SHA before guarded hook)"
if [[ "$MODE" == "guarded_metadata" || "$MODE" == "guarded_f64_binary" || "$MODE" == "guarded_fractional_io" ]]; then
  if [[ "$MODE" == "guarded_metadata" ]]; then
    msg "$MAGENTA" HOOK "Guarded single-site metadata only; no audio read"
  elif [[ "$MODE" == "guarded_fractional_io" ]]; then
    INPUT_PROBE="$(python - "$CFG" <<'PY'
import json,sys
print(bool(json.load(open(sys.argv[1],encoding="utf-8")).get("input_probe")))
PY
)"
    COEFF_PROBE="$(python - "$CFG" <<'PY'
import json,sys
print(bool(json.load(open(sys.argv[1],encoding="utf-8")).get("coeff_probe")))
PY
)"
    LONG_PROBE="$(python - "$CFG" <<'PY'
import json,sys
print(bool(json.load(open(sys.argv[1],encoding="utf-8")).get("long_probe")))
PY
)"
    if [[ "$LONG_PROBE" == "True" ]]; then
      msg "$YELLOW" HOOK "Stage64: ONE fractional hook; capture 1067+114 output f64 = 9448 private bytes, original native first32 SHA required"
    elif [[ "$COEFF_PROBE" == "True" ]]; then
      msg "$YELLOW" HOOK "Stage58: ONE fractional hook; read only generated coefficient table 673x72 f64 (387648 private bytes), ZERO audio"
    elif [[ "$INPUT_PROBE" == "True" ]]; then
      msg "$YELLOW" HOOK "Stage54: ONE fractional hook; 3+256 input f64 at 96k + 32 output f64 at 48k (2328 private bytes)"
    else
      msg "$MAGENTA" HOOK "Fractional I/O metadata: ONE hook, at most 64 pairs, ZERO audio reads"
    fi
  else
    msg "$YELLOW" HOOK "Stage49-style opt-in: ONE output prefix, MAX 32 f64 / 256 bytes"
  fi
  LIFECYCLE_START="$(python - "$CFG" <<'PY'
import json,sys
print(json.load(open(sys.argv[1],encoding="utf-8")).get("lifecycle",{}).get("start","attach_only"))
PY
)"
  if [[ "$LIFECYCLE_START" == "fresh" ]]; then
    msg "$YELLOW" ACTION "CLOSE existing Manager first. Universal Frida will launch its own instance."
    msg "$GREEN" CLOSE "After experiment, gracefully close ONLY the tool-launched Manager PID."
  elif [[ "$LIFECYCLE_START" == "if_missing" ]]; then
    msg "$CYAN" TARGET "Reuses an existing Manager (leaves it open) or launches its own."
    msg "$GREEN" CLOSE "Only a tool-launched Manager is closed automatically."
  else
    msg "$YELLOW" ACTION "Open Manager first; attach-only mode."
  fi
  msg "$YELLOW" ACTION "After [HOOK], perform ONE normal conversion"
  msg "$CYAN" WATCH "CLO output path from JSON completion, unless FRIDA_WATCH_CLO supplied"
else
  if [[ "$MODE" == "invocation_trace" ]]; then
    msg "$YELLOW" HOOK "Stage96: EIGHT pinned read-only entry/exit hooks, bounded same-thread nesting IDs, NO audio or model reads"
    msg "$YELLOW" ACTION "Close Manager first, then perform ONE ordinary conversion after [HOOK]"
    msg "$CYAN" SAFETY "Native invocation capture is diagnostic; no CLO completion or fitting success is implied"
  else
    msg "$MAGENTA" FRIDA "Legacy scalar/binary capture mode, original config preserved"
  fi
fi

WATCH_ARGS=()
if [[ -n "${FRIDA_WATCH_CLO:-}" ]]; then
  [[ -d "$FRIDA_WATCH_CLO" ]] || fail "CLO folder missing: $FRIDA_WATCH_CLO"
  WATCH_ARGS=(--completion-dir "$(wslpath -w "$FRIDA_WATCH_CLO")")
  msg "$CYAN" WATCH "Override: $FRIDA_WATCH_CLO"
fi
QUIET_ARGS=()
if [[ "$MODE" != "guarded_metadata" && "$MODE" != "guarded_f64_binary" && "$MODE" != "guarded_fractional_io" ]]; then
  QUIET_ARGS=(--auto-quiet "${FRIDA_AUTO_QUIET:-12}")
fi
msg "$CYAN" OUTPUT "research/_LOCAL_FILES/frida_captures/frida_*.tar.gz"
"$WINPY" "$(wslpath -w "$ROOT/tools/frida_capture.py")" \
  --config "$(wslpath -w "$CFG")" \
  --module-file "$(wslpath -w "$DLL")" \
  "${QUIET_ARGS[@]}" "${WATCH_ARGS[@]}" "${ARGS[@]}"
