# 5868USB reverse-engineering moved to re5868USB

The public-safe HTKPA / 5868USB.dll investigation is maintained in [re5868USB](https://github.com/TheColdVoid1337/re5868USB), not this application repository.

**Migration proof:** 613 source files were copied with exact Git blob SHA equality against source commit [9d52cf0b7c1601bbcea50d00f3bd773c9cd65210](https://github.com/TheColdVoid1337/PocketMasterStudio/commit/9d52cf0b7c1601bbcea50d00f3bd773c9cd65210). [Full migration ledger](https://github.com/TheColdVoid1337/re5868USB/blob/main/MIGRATION_MANIFEST.json).

The original historical Git commits remain in PocketMasterStudio. Research files were removed from the current working tree *after* verifying the new copies. Read [current state](https://github.com/TheColdVoid1337/re5868USB/blob/main/docs/CURRENT_STATUS.md) and [all stages](https://github.com/TheColdVoid1337/re5868USB/blob/main/docs/STAGE_INDEX.md) at the new location.

**Intentionally still here:** browser app, production `tools/nam_js/`, `src/`, builds, preset data and vendor-independent product tests, plus original SonicMaster license notice. None was removed.

**Local ignored assets:** files under `research/_LOCAL_FILES/` are not in Git and are not moved by GitHub commits. Use the existing private Google Drive [RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK) and, if relevant, copy local ignored research inputs to the new repository's corresponding ignored directory manually. Do not commit DLL/NAM/WAV/CLO/raw Frida or private reports to either public tree.
