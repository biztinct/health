#!/usr/bin/env node
/* =============================================================================
   Step 1 of the content pipeline (PHASE1_DESIGN §6).

   Loads the prototype's two content files in a bare VM context and dumps a
   normalised JSON tree on stdout. Parsing JS with a Python regex was the
   obvious alternative and it is the wrong one: these files contain nested
   template literals, HTML with braces, and Vietnamese text with quotes. The
   only parser guaranteed to agree with the browser is the one the browser uses.

   Usage:  node tools/dump_content.js > /tmp/content.json
   ========================================================================== */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");

const sandbox = { console, window: {}, document: undefined };
vm.createContext(sandbox);

for (const f of ["practice-data.js", "data.js"]) {
    const src = fs.readFileSync(path.join(ROOT, f), "utf8");
    // The files declare top-level `const`s. In a VM script those are scoped to
    // the script, not the context — so evaluate each file as the body of a
    // function that hands its declarations back explicitly.
    vm.runInContext(src, sandbox, { filename: f });
}

/* Two blocks of genuine teaching PROSE ended up in app.js rather than data.js:
   the morph before/after captions and the lifecycle stage names. In the module
   they belong in learn.step.line, where the .po workflow can reach them — so
   slice them out and evaluate them in the same sandbox (both only need B and
   CASE, which are already defined). Sliced rather than imported because the
   rest of app.js needs a DOM. */
const appSrc = fs.readFileSync(path.join(ROOT, "app.js"), "utf8");
for (const name of ["MORPHS", "CHAINS"]) {
    const start = appSrc.indexOf(`const ${name} = {`);
    if (start === -1) throw new Error(`app.js no longer defines ${name}`);
    const end = appSrc.indexOf("\n};", start);
    if (end === -1) throw new Error(`cannot find the end of ${name} in app.js`);
    vm.runInContext(appSrc.slice(start, end + 3), sandbox, { filename: `app.js:${name}` });
}

// `const` at the top level of runInContext lands in the context's lexical
// scope, which is reachable by evaluating the name — but not by property
// lookup on the sandbox object. Pull each one out by evaluation.
function grab(name) {
    try {
        return vm.runInContext(name, sandbox);
    } catch (e) {
        throw new Error(`content file does not define ${name}: ${e.message}`);
    }
}

const out = {
    schemaVersion: grab("PRACTICE_META").schemaVersion,
    tenantDefaults: grab("TENANT_DEFAULTS"),
    glossary: grab("GLOSSARY"),
    stations: grab("STATIONS"),
    lessons: grab("LESSONS"),
    missions: grab("MISSIONS"),
    m1Steps: grab("M1_STEPS"),
    m2Steps: grab("M2_STEPS"),
    screenCtx: grab("SCREEN_CTX"),
    qa: grab("QA"),
    qaFallback: grab("QA_FALLBACK"),
    qaSuggest: grab("QA_SUGGEST"),
    i18n: grab("I18N"),
    menu: grab("MENU"),
    retired: grab("RETIRED"),
    statusLabels: grab("STATUS_LABELS"),
    practice: grab("PRACTICE"),
    caseData: grab("CASE"),
    morphs: grab("MORPHS"),
    chains: grab("CHAINS"),
    columns: grab("COLUMNS"),
    opsStations: grab("OPS_STATIONS"),
    ops: grab("OPS"),
    opsScreenCtx: grab("OPS_SCREEN_CTX"),
    opsLessons: grab("OPS_LESSONS"),
    opsMissions: grab("OPS_MISSIONS"),
    opsM1Steps: grab("OPS_M1_STEPS"),
    opsColumns: grab("OPS_COLUMNS"),
    opsQa: grab("OPS_QA"),
    opsQaSuggest: grab("OPS_QA_SUGGEST"),
};

process.stdout.write(JSON.stringify(out, null, 1));
