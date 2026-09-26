#!/usr/bin/env python3
"""A job rename in a shared workflow must not drop a check another repository requires.

On 2026-09-26 the shared workflow's job was renamed from `Node 22` to
`Node 22 (${{ ...resolve mode... }})`. core-angular's develop requires `ci / Node 22` and
`ci / Node 24` by name, so those checks never arrived and every pull request there was
BLOCKED -- with every job green.

For each caller recorded in .github/required-checks.json (refreshed from branch protection by
.github/scripts/snapshot-required-checks.sh), this builds the check names the shared workflow
produces: the caller's job id, " / ", the job's `name:` with `matrix.node` over the caller's
Node versions. Any OTHER expression in a name is unknown here, so it stands for "any text":
- a required name no produced name can equal, whatever those expressions evaluate to: FOUND;
- a required name reachable only through an unknown expression: UNEVALUABLE;
- a required name produced exactly: CLEAR.

Exit: 0 CLEAR · 1 FOUND (named, with what is produced now) · 2 UNEVALUABLE (named) --
could-not-tell is never folded into CLEAR.
"""
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print('UNEVALUABLE: PyYAML is not installed, so the workflows cannot be read')
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / '.github' / 'required-checks.json'
EXPR = re.compile(r'\$\{\{\s*(.*?)\s*\}\}')


def produced(workflow_file: Path, caller_job: str, node_versions):
    """[(shown name, regex, exact)] one caller's job produces, or (None, why)."""
    wf = yaml.safe_load(workflow_file.read_text())
    on = wf.get('on') or wf.get(True) or {}
    inputs = ((on or {}).get('workflow_call') or {}).get('inputs') or {}
    versions = node_versions
    if versions is None:
        default = (inputs.get('node-versions') or {}).get('default')
        versions = json.loads(default) if default else None
    out = []
    for job_id, job in (wf.get('jobs') or {}).items():
        template = str((job or {}).get('name', job_id))
        uses_node = any(e == 'matrix.node' for e in EXPR.findall(template))
        if uses_node and not versions:
            return None, f'job `{job_id}` is named with matrix.node, and no Node versions are known'
        for v in (versions if uses_node else [None]):
            shown, pattern, exact, pos = '', '', True, 0
            for m in EXPR.finditer(template):
                literal = template[pos:m.start()]
                shown += literal
                pattern += re.escape(literal)
                if m.group(1) == 'matrix.node':
                    shown += str(v)
                    pattern += re.escape(str(v))
                else:
                    shown += '<' + m.group(1)[:40] + '>'
                    pattern += '.*'
                    exact = False
                pos = m.end()
            shown += template[pos:]
            pattern += re.escape(template[pos:])
            out.append((f'{caller_job} / {shown}', re.compile(re.escape(caller_job + ' / ') + pattern + r'\Z'), exact))
    return out, None


def main() -> int:
    if not SNAPSHOT.exists():
        print(f'UNEVALUABLE: no {SNAPSHOT.relative_to(ROOT)} -- nothing records what the callers require')
        return 2
    snapshot = json.loads(SNAPSHOT.read_text())
    callers = snapshot.get('callers', {})
    found, unevaluable, clear = [], [], 0
    for repo, entry in sorted(callers.items()):
        job = entry.get('caller_job', 'ci')
        names, why = produced(ROOT / '.github' / 'workflows' / entry['workflow'], job, entry.get('node_versions'))
        if names is None:
            unevaluable.append(f'{repo}: {why}')
            continue
        for required in entry.get('required', []):
            if not required.startswith(job + ' / '):
                continue  # a check from another workflow of that repository
            hits = [n for n in names if n[1].match(required)]
            if any(exact for _, _, exact in hits):
                clear += 1
            elif hits:
                unevaluable.append(f'{repo} requires `{required}`: produced only if '
                                   f'{", ".join(s for s, _, _ in hits)} evaluates to it')
            else:
                found.append(f'{repo} requires `{required}`; {entry["workflow"]} now produces '
                             f'{", ".join(s for s, _, _ in names)}')
    total = clear + len(found) + sum(1 for u in unevaluable if ' requires ' in u)
    print(f'{len(found)} of {total} required check(s) no longer produced, across {len(callers)} calling '
          f'repositor(ies) (snapshot {snapshot.get("taken", "?")})')
    for line in found:
        print(f'  FOUND: {line}')
    for line in unevaluable:
        print(f'  UNEVALUABLE: {line}')
    if found:
        return 1
    if unevaluable or total == 0:
        if total == 0:
            print('  UNEVALUABLE: no required check from these workflows is recorded -- nothing was compared')
        return 2
    print(f'  CLEAR: all {clear} still produced')
    return 0


if __name__ == '__main__':
    sys.exit(main())
