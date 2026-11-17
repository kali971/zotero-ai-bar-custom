"""Restore one-line AI Bar input and retain content-driven multiline growth."""

import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "zotero_reader_ai_setup_20261107"
PLUGIN = (
    Path.home()
    / "Library/Application Support/Zotero/Profiles/xbd3ws3k.default"
    / "extensions/zaibar@fukeke.com.xpi"
)
CSS_PATH = "content/app.css"
JS_PATH = "content/scripts/zaibar.js"
OLD_CSS = re.compile(
    r"\n/\* (?:Roomier AI Bar composer input[^\n]*|"
    r"Content-sized AI Bar composer input[^\n]*) \*/\n"
    r'\.input-area textarea\[contenteditable="true"\] \{[^}]*\}\n?'
)
NEW_CSS = '''
/* Content-sized AI Bar composer input: one centered line, then grow. */
.input-area textarea[contenteditable="true"] {
  min-height: 1.5em !important;
  max-height: 160px !important;
  padding: 0 !important;
  line-height: 1.5 !important;
}
'''
JS_REPLACEMENTS = (
    ('Z.style.maxHeight="7rem"', 'Z.style.maxHeight="160px"'),
    ('Math.min(Z.scrollHeight,112)', 'Math.min(Z.scrollHeight,160)'),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    original_bytes = PLUGIN.read_bytes()
    with zipfile.ZipFile(PLUGIN) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Installed plugin archive is damaged")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["version"] != "1.6.10":
            raise RuntimeError("Review the new plugin version before applying this patch")
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]

    old_files = {info.filename: data for info, data in entries}
    css = old_files[CSS_PATH].decode("utf-8")
    if "Compact user-message bubbles:" not in css:
        raise RuntimeError("Expected compact user-message style is missing")
    css, removed = OLD_CSS.subn("\n", css)
    if removed != 1:
        raise RuntimeError("Expected one previous composer style block")
    css = css.rstrip() + "\n" + NEW_CSS

    js = old_files[JS_PATH].decode("utf-8")
    for old, new in JS_REPLACEMENTS:
        if js.count(old) == 1:
            js = js.replace(old, new, 1)
        elif js.count(new) != 1:
            raise RuntimeError(f"Expected a unique composer sizing expression: {old}")
    if 'B.classList.add("flex","items-center","justify-center","gap-1")' not in js:
        raise RuntimeError("Expected vertical centering in the input toolbar")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    backup = OUT_DIR / f"zaibar-before-composer-fix-{digest(original_bytes)[:12]}.xpi"
    if not backup.exists():
        backup.write_bytes(original_bytes)

    fd, temporary_path = tempfile.mkstemp(
        prefix="zaibar-composer-", suffix=".xpi", dir=PLUGIN.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_path)
    try:
        updated = {CSS_PATH: css.encode("utf-8"), JS_PATH: js.encode("utf-8")}
        with zipfile.ZipFile(temporary_path, "w") as archive:
            for info, data in entries:
                archive.writestr(info, updated.get(info.filename, data))
        with zipfile.ZipFile(temporary_path) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Patched plugin archive is damaged")
            changed = [
                name for name, old_data in old_files.items()
                if archive.read(name) != old_data
            ]
            if any(name not in updated for name in changed):
                raise RuntimeError("Unexpected plugin file changed")
            assert archive.read(CSS_PATH).decode("utf-8") == css
            assert archive.read(JS_PATH).decode("utf-8") == js
        os.chmod(temporary_path, PLUGIN.stat().st_mode & 0o777)
        temporary_path.replace(PLUGIN)
    finally:
        temporary_path.unlink(missing_ok=True)

    # Save the modified script for a syntax-only check; never execute plugin code.
    check_script = OUT_DIR / "zaibar-composer-syntax-check.js"
    check_script.write_text(js, encoding="utf-8")
    validation = {
        "plugin": str(PLUGIN),
        "plugin_version": manifest["version"],
        "backup": str(backup),
        "archive_integrity": "passed",
        "changed_files": changed,
        "short_input": "one line, vertically centered by the existing flex toolbar",
        "multiline_input": "height follows scrollHeight up to 160px, then scrolls",
        "shrinks_when_text_is_removed": 'Z.style.height="auto"' in js,
        "compact_user_bubbles_preserved": "Compact user-message bubbles:" in css,
        "requires_zotero_reload": True,
        "live_visual_check": "not performed",
        "patched_sha256": digest(PLUGIN.read_bytes()),
    }
    (OUT_DIR / "composer_layout_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
