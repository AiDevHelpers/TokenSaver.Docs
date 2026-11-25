#!/usr/bin/env python3
"""gotcha-db validator — spec for the future `gotcha validate` command.

Checks: JSON Schema conformance, id<->path consistency, dangling refs
(snippets, gotchas, sub-patterns), regex syntax, tpl variable declarations,
and pattern placeholder <-> skeleton TODO(gotcha:...) marker consistency.
"""
import json, glob, os, re, sys
from jsonschema import Draft202012Validator

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

schemas = {n: json.load(open(f"metadata/schema/{n}.schema.json"))
           for n in ["gotcha", "snippet", "error-mapping", "pattern"]}
for s in schemas.values():
    Draft202012Validator.check_schema(s)

errors = 0
def fail(msg):
    global errors
    print(f"FAIL {msg}")
    errors += 1

def validate(path, schema):
    rec = json.load(open(path))
    for e in sorted(Draft202012Validator(schemas[schema]).iter_errors(rec), key=str):
        fail(f"{path}: {e.message}")
    expected = os.path.splitext(path)[0].replace("\\", "/")
    if rec.get("id") != expected:
        fail(f"{path}: id '{rec.get('id')}' != path '{expected}'")
    return rec

def check_regex(owner, pat):
    try:
        re.compile(pat)
    except re.error as e:
        fail(f"{owner}: bad regex '{pat}': {e}")

gotchas, snippets, patterns, mappings = [], {}, [], []
for p in glob.glob("languages/**/gotchas/**/*.json", recursive=True) + \
         glob.glob("platforms/**/gotchas/**/*.json", recursive=True) + \
         glob.glob("dependencies/**/*.json", recursive=True):
    gotchas.append(validate(p, "gotcha"))
for p in glob.glob("snippets/**/*.json", recursive=True):
    r = validate(p, "snippet")
    tpl_path = os.path.splitext(p)[0] + ".tpl"
    if not os.path.exists(tpl_path):
        fail(f"{p}: missing companion .tpl")
        continue
    tpl = open(tpl_path).read()
    used = set(re.findall(r"\{\{(\w+)\}\}", tpl))
    declared = set(r["variables"].keys())
    if used != declared:
        fail(f"{p}: tpl vars {sorted(used)} != declared {sorted(declared)}")
    snippets[r["id"]] = {"markers": set(re.findall(r"TODO\(gotcha:(\w+)\)", tpl))}
for p in glob.glob("patterns/**/*.json", recursive=True):
    patterns.append(validate(p, "pattern"))
for p in glob.glob("languages/**/errors/*.json", recursive=True) + \
         glob.glob("platforms/**/errors/*.json", recursive=True):
    mappings.append(validate(p, "error-mapping"))

gotcha_ids = {g["id"] for g in gotchas}
pattern_ids = {p["id"] for p in patterns}

for g in gotchas:
    if g.get("fix_snippet") and g["fix_snippet"] not in snippets:
        fail(f"{g['id']}: dangling fix_snippet {g['fix_snippet']}")
    for rel in g.get("related", []):
        if rel not in gotcha_ids | pattern_ids:
            fail(f"{g['id']}: dangling related {rel}")
    for sig in g.get("error_signatures", []):
        check_regex(g["id"], sig)
    if g.get("detection"):
        check_regex(g["id"], g["detection"]["pattern"])

for m in mappings:
    check_regex(m["id"], m["match"])
    for gid in m["gotchas"]:
        if gid not in gotcha_ids:
            fail(f"{m['id']}: dangling gotcha ref {gid}")

for pat in patterns:
    for ref in pat.get("gotchas", []):
        if ref not in gotcha_ids:
            fail(f"{pat['id']}: dangling pattern-level gotcha {ref}")
    for rel in pat.get("related", []):
        if rel not in pattern_ids:
            fail(f"{pat['id']}: dangling related {rel}")
    for comp in pat["components"]:
        where = f"{pat['id']}#{comp['role']}"
        if comp.get("uses") and comp["uses"] not in pattern_ids:
            fail(f"{where}: dangling uses {comp['uses']}")
        skel = comp.get("skeleton")
        if skel and skel not in snippets:
            fail(f"{where}: dangling skeleton {skel}")
        step_keys = {s["placeholder"] for s in comp.get("steps", [])}
        if skel and skel in snippets:
            markers = snippets[skel]["markers"]
            if not step_keys <= markers:
                fail(f"{where}: steps {sorted(step_keys - markers)} have no TODO(gotcha:...) marker in {skel}")
            if not markers <= step_keys:
                fail(f"{where}: skeleton markers {sorted(markers - step_keys)} have no step entry")
        for step in comp.get("steps", []):
            sp = step.get("starting_point")
            if sp and sp not in snippets:
                fail(f"{where}/{step['placeholder']}: dangling starting_point {sp}")
            for ref in step.get("gotchas", []):
                if ref not in gotcha_ids:
                    fail(f"{where}/{step['placeholder']}: dangling gotcha {ref}")

print(f"\n{len(gotchas)} gotchas, {len(snippets)} snippets, {len(patterns)} patterns, "
      f"{len(mappings)} error mappings — {'ALL VALID' if errors == 0 else f'{errors} errors'}")
sys.exit(1 if errors else 0)
