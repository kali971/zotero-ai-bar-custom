"""Enable AI Bar's existing translation fallback for rejected output schemas."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "zotero_translation_fix_20261109"
PLUGIN = (
    Path.home()
    / "Library/Application Support/Zotero/Profiles/xbd3ws3k.default"
    / "extensions/zaibar@fukeke.com.xpi"
)
JS_PATH = "content/scripts/zaibar.js"
OLD = '''function uIe(e){let t=si(e).toLowerCase(),n=t.includes("response_format")||t.includes("json_object"),a=t.includes("not supported")||t.includes("unsupported")||t.includes("unavailable")||t.includes("not available")||t.includes("not valid")||t.includes("invalidparameter")||t.includes("must contain the word 'json'");return n&&a}'''
NEW = OLD.replace(
    'n=t.includes("response_format")||t.includes("json_object")',
    'n=t.includes("response_format")||t.includes("json_object")||t.includes("json_schema")',
).replace(
    'a=t.includes("not supported")',
    'a=t.includes("invalid schema")||t.includes("invalid_json_schema")||t.includes("not supported")',
)

TEST_HARNESS = r'''
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(process.argv[2], "utf8");
function between(start, end) {
    const offset = source.indexOf(start);
    assert.ok(offset >= 0);
    const next = source.indexOf(end, offset + start.length);
    assert.ok(next > offset);
    return source.slice(offset, next);
}
const screenshotError = "[HTTP 400] AI_APICallError: Invalid schema for response_format 'translation_result': In context=('anyOf', '0'), 'required' is required to be supplied and to be an array including every key in properties. Missing 'explanation'.";
let structuredCalls = 0;
let fallbackCalls = 0;
let failure = new Error(screenshotError);
const context = vm.createContext({
    si: (error) => error.message ?? String(error),
    LV: (selection) => selection,
    xV: new Set(),
    En() {},
    Zotero: {debug() {}},
    async lIe() { structuredCalls++; throw failure; },
    async IV() { fallbackCalls++; return "validated streamed translation"; },
});
vm.runInContext(
    between("function uIe(", "function dIe(") +
    between("async function wV(", "async function lIe("),
    context,
);
const cases = [
    [screenshotError, true],
    ["Invalid schema for response_format: required explanation", true],
    ["invalid_json_schema for json_schema", true],
    ["response_format is not supported", true],
    ["json_object unsupported", true],
    ["401 unauthorized", false],
    ["429 rate limit exceeded", false],
    ["Upstream request failed", false],
    ["Network connection closed", false],
    ["Invalid schema for unrelated input", false],
    ["401 unauthorized while using response_format", false],
];
for (const [message, expected] of cases) {
    assert.equal(context.uIe(new Error(message)), expected, message);
}
assert.equal(await context.wV({modelSelection: "relay-model"}), "validated streamed translation");
assert.equal(structuredCalls, 1);
assert.equal(fallbackCalls, 1);
assert.equal(await context.wV({modelSelection: "relay-model"}), "validated streamed translation");
assert.equal(structuredCalls, 1, "cached model must use fallback directly");
assert.equal(fallbackCalls, 2);
failure = new Error("401 unauthorized");
await assert.rejects(context.wV({modelSelection: "another-model"}), /401 unauthorized/);
assert.equal(fallbackCalls, 2, "unrelated failures must propagate");
console.log(JSON.stringify({predicate_cases: cases.length, automatic_fallback: "passed", session_cache: "passed", unrelated_error_propagation: "passed"}));
'''


def main():
    original = PLUGIN.read_bytes()
    with zipfile.ZipFile(PLUGIN) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Installed plugin archive is damaged")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["version"] != "1.6.10":
            raise RuntimeError("Review this patch for the installed plugin version")
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    files = {info.filename: data for info, data in entries}
    js = files[JS_PATH].decode("utf-8")
    if js.count(OLD) == 1:
        patched = js.replace(OLD, NEW, 1)
    elif js.count(NEW) == 1:
        patched = js
    else:
        raise RuntimeError("Expected a unique compatibility predicate")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    check_path = OUT_DIR / "zaibar-translation-syntax-check.js"
    check_path.write_text(patched, encoding="utf-8")
    harness_path = OUT_DIR / "translation_compat_test.mjs"
    harness_path.write_text(TEST_HARNESS, encoding="utf-8")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node is required for verification before installation")
    subprocess.run([node, "--check", str(check_path)], check=True, capture_output=True)
    tests = subprocess.run(
        [node, str(harness_path), str(check_path)],
        check=True, capture_output=True, text=True,
    )

    backup = OUT_DIR / ("zaibar-before-translation-fix-" + hashlib.sha256(original).hexdigest()[:12] + ".xpi")
    if patched != js and not backup.exists():
        backup.write_bytes(original)
    changed = []
    if patched != js:
        fd, name = tempfile.mkstemp(prefix="zaibar-translation-", suffix=".xpi", dir=PLUGIN.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                for info, data in entries:
                    archive.writestr(info, patched.encode("utf-8") if info.filename == JS_PATH else data)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("Patched archive failed integrity check")
                changed = [key for key, data in files.items() if archive.read(key) != data]
                if changed != [JS_PATH]:
                    raise RuntimeError("Unexpected archive changes")
            os.chmod(temporary, PLUGIN.stat().st_mode & 0o777)
            temporary.replace(PLUGIN)
        finally:
            temporary.unlink(missing_ok=True)
    report = {
        "plugin_version": manifest["version"],
        "backup": str(backup) if backup.exists() else "already patched",
        "changed_files": changed,
        "syntax_check": "passed",
        "offline_tests": json.loads(tests.stdout),
        "live_api_test": "not performed",
        "requires_zotero_restart": True,
        "installed_sha256": hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
    }
    (OUT_DIR / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
