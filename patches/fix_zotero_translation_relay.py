"""Use AI Bar's validated JSON-text translation path for custom relays."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/zotero_translation_fix_20261109"
PLUGIN = Path.home() / "Library/Application Support/Zotero/Profiles/xbd3ws3k.default/extensions/zaibar@fukeke.com.xpi"
JS_PATH = "content/scripts/zaibar.js"
OLD = 'async function wV(e){let t=LV(e.modelSelection);if(xV.has(t))'
NEW = 'async function wV(e){let t=LV(e.modelSelection);if(e.modelSelection.providerId.startsWith("custom-")||zV(e.modelSelection)===!1||xV.has(t))'

TEST_HARNESS = r'''
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(process.argv[2], "utf8");
const start = source.indexOf("async function wV(");
const end = source.indexOf("async function lIe(", start);
let structuredCalls = 0;
let textCalls = 0;
let failure;
const context = vm.createContext({
    LV: (selection) => `${selection.providerId}::${selection.modelId}`,
    zV: (selection) => selection.supported,
    xV: new Set(), En() {}, si: (error) => error.message,
    uIe: (error) => /response_format.*unsupported/.test(error.message),
    Zotero: {debug() {}},
    async lIe() { structuredCalls++; if (failure) throw failure; return "structured"; },
    async IV() { textCalls++; if (failure) throw failure; return "text-json"; },
});
vm.runInContext(source.slice(start, end), context);
const request = (providerId, supported) => ({modelSelection: {providerId, modelId: "test", supported}});
assert.equal(await context.wV(request("custom-relay", true)), "text-json");
assert.equal(structuredCalls, 0, "custom relays must never issue the failing schema request");
assert.equal(await context.wV(request("official", false)), "text-json");
assert.equal(await context.wV(request("official", true)), "structured");
assert.equal(await context.wV(request("unknown", undefined)), "structured");
context.xV.add("cached::test");
assert.equal(await context.wV(request("cached", true)), "text-json");
for (const message of ["401 unauthorized", "429 rate limit", "Upstream request failed"]) {
    failure = new Error(message);
    await assert.rejects(context.wV(request("custom-relay", true)), new RegExp(message));
}
console.log(JSON.stringify({routing_cases: 5, error_propagation_cases: 3, status: "passed"}));
'''


def main():
    original = PLUGIN.read_bytes()
    with zipfile.ZipFile(PLUGIN) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Plugin archive integrity check failed")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest["version"] != "1.6.10":
            raise RuntimeError("Review this patch for the installed plugin version")
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    files = {info.filename: data for info, data in entries}
    js = files[JS_PATH].decode()
    if js.count(OLD) == 1:
        patched = js.replace(OLD, NEW, 1)
    elif js.count(NEW) == 1:
        patched = js
    else:
        raise RuntimeError("Expected a unique translation entry point")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    check = OUT_DIR / "zaibar-relay-syntax-check.js"
    check.write_text(patched, encoding="utf-8")
    harness = OUT_DIR / "translation_relay_routing_test.mjs"
    harness.write_text(TEST_HARNESS, encoding="utf-8")
    node = shutil.which("node")
    subprocess.run([node, "--check", str(check)], check=True, capture_output=True)
    tests = subprocess.run([node, str(harness), str(check)], check=True, capture_output=True, text=True)
    backup = OUT_DIR / ("zaibar-before-relay-fix-" + hashlib.sha256(original).hexdigest()[:12] + ".xpi")
    changed = []
    if patched != js:
        if not backup.exists():
            backup.write_bytes(original)
        fd, name = tempfile.mkstemp(prefix="zaibar-relay-", suffix=".xpi", dir=PLUGIN.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                for info, data in entries:
                    archive.writestr(info, patched.encode() if info.filename == JS_PATH else data)
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("Patched archive integrity check failed")
                changed = [name for name, data in files.items() if archive.read(name) != data]
                if changed != [JS_PATH]:
                    raise RuntimeError("Unexpected changes to plugin files")
            os.chmod(temporary, PLUGIN.stat().st_mode & 0o777)
            temporary.replace(PLUGIN)
        finally:
            temporary.unlink(missing_ok=True)
    report = {
        "plugin_version": manifest["version"],
        "backup": str(backup),
        "changed_files": changed,
        "syntax_check": "passed",
        "routing_tests": json.loads(tests.stdout),
        "installed_sha256": hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
    }
    (OUT_DIR / "relay-fix-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
