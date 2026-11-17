"""Apply an explicit conversation budget independently of model metadata."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs/zotero_compaction_budget_20261109"
PLUGIN = Path.home() / "Library/Application Support/Zotero/Profiles/xbd3ws3k.default/extensions/zaibar@fukeke.com.xpi"
JS_PATH = "content/scripts/zaibar.js"
PREF_PATH = "prefs.js"

OLD_NF = 'function nf(e){let t=e.contextLimit??0,n=jL(e.messages,e.tools),a=Math.max(0,e.outputAllowance??0),o=t>0?Vy(Math.round(t*.15),4096,2e4):0,i=t>0?Math.max(0,t-Math.max(a,o)):Number.POSITIVE_INFINITY;return{estimatedInputTokens:n,outputAllowance:a,bufferTokens:o,thresholdTokens:i,shouldCompact:t>0&&n>i}}'
NEW_NF = '''function ZAIBarCompactionPolicy(){let e=st("chat.compactionTriggerTokens"),t=st("chat.compactionTargetTokens"),n=typeof e==="number"&&Number.isFinite(e)&&e>=8192?Math.floor(e):256000,a=typeof t==="number"&&Number.isFinite(t)&&t>=4096?Math.floor(t):32000;return{triggerTokens:n,targetTokens:Math.min(a,Math.floor(n/2))}}function nf(e){let t=e.contextLimit??0,n=jL(e.messages,e.tools),a=Math.max(0,e.outputAllowance??0),o=t>0?Vy(Math.round(t*.15),4096,2e4):0,s=ZAIBarCompactionPolicy(),i=Math.min(s.triggerTokens,t>0?Math.max(0,t-Math.max(a,o)):Number.POSITIVE_INFINITY);return{estimatedInputTokens:n,outputAllowance:a,bufferTokens:o,policyTriggerTokens:s.triggerTokens,thresholdTokens:i,shouldCompact:n>=i}}'''
OLD_YL = 'function YL(e,t){let n=Aoe(e[0]),a=n?e.slice(1):e,o=t.mode==="agent"?Noe(a,Vy(Math.round((t.contextLimit??64e3)*.18),8e3,24e3)):Ooe(a,t.contextRounds??8);if(!(o<=0||o>=a.length))return{head:a.slice(0,o),tail:a.slice(o),previousSummary:n}}'
NEW_YL = '''function YL(e,t){let n=Aoe(e[0]),a=n?e.slice(1):e,s=Math.max(4096,ZAIBarCompactionPolicy().targetTokens-4096),o=t.mode==="agent"?Noe(a,Math.min(s,Vy(Math.round((t.contextLimit??64e3)*.18),8e3,24e3))):Math.max(Ooe(a,t.contextRounds??8),Noe(a,s));if(!(o<=0||o>=a.length))return{head:a.slice(0,o),tail:a.slice(o),previousSummary:n}}'''
OLD_DI = 'function di(){let e=addon.data.userProviderConfigV2,t=e?.active;if(!t)return;let a=(addon.data.commonProviders?.[t.providerId]?.models[t.modelId]??e?.addedModels.find(o=>o.providerId===t.providerId&&o.id===t.modelId))?.limit?.context;return typeof a=="number"&&a>0?a:void 0}'
NEW_DI = '''function di(){let e=addon.data.userProviderConfigV2,t=e?.active;if(!t)return;let a=(addon.data.commonProviders?.[t.providerId]?.models[t.modelId]??e?.addedModels.find(o=>o.providerId===t.providerId&&o.id===t.modelId))?.limit,n=[a?.context,a?.input].filter(o=>typeof o==="number"&&Number.isFinite(o)&&o>0);return n.length?Math.min(...n):void 0}'''
PREFS = '''\n// Local conversation budget; model capability metadata remains unchanged.\npref("extensions.zotero.${addonRef}.chat.compactionTriggerTokens", 256000);\npref("extensions.zotero.${addonRef}.chat.compactionTargetTokens", 32000);\n'''

TEST_HARNESS = r'''
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(process.argv[2], "utf8");
const values = {};
const context = vm.createContext({st: (key) => values[key], addon: {data: {}}});
function extract(name) {
    const start = source.indexOf(`function ${name}(`);
    assert.ok(start >= 0, name);
    const match = /(?:async )?function \w+\(/g;
    match.lastIndex = start + `function ${name}(`.length;
    const end = match.exec(source);
    return source.slice(start, end.index);
}
for (const name of ["ZAIBarCompactionPolicy", "nf", "YL", "jL", "Hy", "Ri", "Noe", "Ooe", "VL", "di"]) {
    vm.runInContext(extract(name), context);
}
vm.runInContext(`
function Vy(value,min,max){return Math.max(min,Math.min(max,value))}
function Aoe(message){return message?.checkpoint}
`, context);
function request(size, limit=1050000, extra={}) {
    // ASCII is estimated at four characters/token; each message costs twelve tokens.
    return {messages:[{role:"user",content:"a".repeat((size-12)*4)}],contextLimit:limit,outputAllowance:4096,...extra};
}
assert.equal(context.nf(request(255999)).shouldCompact, false);
assert.equal(context.nf(request(256000)).shouldCompact, true);
assert.equal(context.nf(request(256001)).thresholdTokens, 256000);
assert.equal(context.nf(request(256000, 0)).shouldCompact, true, "unknown metadata must not disable compaction");
assert.equal(context.nf(request(50000, 64000)).thresholdTokens, 54400, "smaller windows still reserve model headroom");
assert.equal(context.nf(request(50000, 64000,{outputAllowance:20000})).thresholdTokens, 44000);
values["chat.compactionTriggerTokens"]=128000;
assert.equal(context.nf(request(128000)).shouldCompact,true);
values["chat.compactionTriggerTokens"]=NaN;
assert.equal(context.nf(request(256000)).thresholdTokens,256000);
delete values["chat.compactionTriggerTokens"];
const config={active:{providerId:"relay",modelId:"m"},addedModels:[{providerId:"relay",id:"m",limit:{context:1000000,input:128000}}]};
context.addon.data.userProviderConfigV2=config;
assert.equal(context.di(),128000);
config.addedModels[0].limit.input=0;
assert.equal(context.di(),1000000);
const turns=[];
for(let i=0;i<20;i++) turns.push({role:"user",content:`Question ${i}: `+"x".repeat(20000)},{role:"assistant",content:"y".repeat(20000)});
turns.push({role:"user",content:"Explain the evidence on page 8."});
for(const mode of ["normal","full-text","agent"]){
    const split=context.YL(turns,{mode,contextRounds:8,contextLimit:1000000});
    assert.ok(split.head.length>0);
    assert.equal(split.tail.at(-1),turns.at(-1), "current question must survive");
    assert.ok(context.jL(split.tail)<=27904, "recent history must respect the target for ordinary sized turns");
    assert.equal(split.tail[0].role,"user", "do not split an assistant/tool turn");
}
const small=[];
for(let i=0;i<12;i++)small.push({role:"user",content:`q${i}`},{role:"assistant",content:`a${i}`});
small.push({role:"user",content:"current"});
const split=context.YL([{role:"assistant",checkpoint:"Existing evidence summary"},...small],{mode:"normal",contextRounds:8});
assert.equal(split.previousSummary,"Existing evidence summary");
assert.equal(split.tail.filter(x=>x.role==="user").length,9,"keep eight completed rounds plus current question when they fit");
assert.equal(context.YL([{role:"user",content:"Only current question"}],{mode:"normal"}),undefined,"never summarize away the sole current question");
assert.equal(context.nf({messages:[{role:"system",content:"a".repeat(256000*4)}],contextLimit:1000000}).shouldCompact,true,"full document admission must use the same budget");
console.log(JSON.stringify({threshold_and_limit_cases:11,mode_retention_cases:3,checkpoint_and_round_cases:3,status:"passed"}));
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
    patched = js
    for old, new in [(OLD_NF, NEW_NF), (OLD_YL, NEW_YL), (OLD_DI, NEW_DI)]:
        if patched.count(old) == 1:
            patched = patched.replace(old, new, 1)
        elif patched.count(new) != 1:
            raise RuntimeError("Expected a unique compaction function")
    prefs = files[PREF_PATH].decode()
    if 'chat.compactionTriggerTokens' not in prefs:
        prefs += PREFS
    elif PREFS not in prefs:
        raise RuntimeError("Review existing compaction defaults")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    check = OUT_DIR / "zaibar-compaction-syntax-check.js"
    check.write_text(patched, encoding="utf-8")
    harness = OUT_DIR / "compaction_budget_test.mjs"
    harness.write_text(TEST_HARNESS, encoding="utf-8")
    node = shutil.which("node")
    subprocess.run([node, "--check", str(check)], check=True, capture_output=True)
    tests = subprocess.run([node, str(harness), str(check)], check=True, capture_output=True, text=True)
    replacement = {JS_PATH: patched.encode(), PREF_PATH: prefs.encode()}
    backup = OUT_DIR / ("zaibar-before-budget-fix-" + hashlib.sha256(original).hexdigest()[:12] + ".xpi")
    changed = []
    if any(replacement[name] != files[name] for name in replacement):
        if not backup.exists():
            backup.write_bytes(original)
        fd, name = tempfile.mkstemp(prefix="zaibar-budget-", suffix=".xpi", dir=PLUGIN.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            with zipfile.ZipFile(temporary, "w") as archive:
                for info, data in entries:
                    archive.writestr(info, replacement.get(info.filename, data))
            with zipfile.ZipFile(temporary) as archive:
                if archive.testzip() is not None:
                    raise RuntimeError("Patched archive integrity check failed")
                changed = [name for name, data in files.items() if archive.read(name) != data]
                if set(changed) != set(replacement):
                    raise RuntimeError("Unexpected archive changes")
            os.chmod(temporary, PLUGIN.stat().st_mode & 0o777)
            temporary.replace(PLUGIN)
        finally:
            temporary.unlink(missing_ok=True)
    report = {
        "plugin_version": manifest["version"],
        "trigger_input_tokens": 256000,
        "target_history_tokens": 32000,
        "backup": str(backup),
        "changed_files": changed,
        "syntax_check": "passed",
        "tests": json.loads(tests.stdout),
        "installed_sha256": hashlib.sha256(PLUGIN.read_bytes()).hexdigest(),
        "limitations": ["Token counts are estimated.", "The target applies to summary and retained history; fixed document/system content is additional.", "The latest two user turns are preserved even if they exceed the target."],
    }
    (OUT_DIR / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
