#!/usr/bin/env bash
# Refresh .github/required-checks.json: for every coolms repository whose CI calls a workflow of this
# repository, the checks its develop branch REQUIRES (read from branch protection) and the caller's
# job id and Node versions (read from its .github/workflows/ci.yml). Needs a token that can read
# branch protection: GH_TOKEN of an organisation owner. Run it whenever a repository's protection,
# or its caller workflow, changes; commit the result.
set -euo pipefail
cd "$(dirname "$0")/../.."
out=.github/required-checks.json
repos=$(gh repo list coolms --limit 200 --json name,isArchived --jq '.[] | select(.isArchived | not) | .name')
python3 - "$out" $repos <<'PY'
import json, subprocess, sys, datetime
import yaml
out, repos = sys.argv[1], sys.argv[2:]
def gh(path):
    r = subprocess.run(['gh', 'api', path], capture_output=True, text=True)
    return json.loads(r.stdout) if r.returncode == 0 else None
callers = {}
for repo in sorted(repos):
    ci = gh(f'repos/coolms/{repo}/contents/.github/workflows/ci.yml?ref=develop')
    if not ci:
        continue
    import base64
    wf = yaml.safe_load(base64.b64decode(ci['content']))
    for job_id, job in (wf.get('jobs') or {}).items():
        uses = str((job or {}).get('uses', ''))
        if not uses.startswith('coolms/.github/.github/workflows/'):
            continue
        prot = gh(f'repos/coolms/{repo}/branches/develop/protection/required_status_checks')
        nv = ((job.get('with') or {}).get('node-versions'))
        callers[repo] = {
            'workflow': uses.split('/')[-1].split('@')[0],
            'caller_job': job_id,
            'node_versions': json.loads(nv) if nv else None,
            'required': (prot or {}).get('contexts', []),
            'protected': prot is not None,
        }
json.dump({'taken': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
           'callers': callers}, open(out, 'w'), indent=2, sort_keys=True)
open(out, 'a').write('\n')
print(f'{len(callers)} calling repositor(ies) recorded in {out}')
PY
