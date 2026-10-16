# coolms/.github

Shared GitHub Actions workflows for the CoolMS package set.

## `angular-library.yml`

A reusable workflow for the ng-packagr Angular libraries. All of them have
byte-identical `scripts`, so their CI lives here once rather than as a file per
package: with only two copies in existence they had already drifted to 53 and 71
lines, differing in the Node matrix, the install command, and whether lint ran at
all.

```yaml
# packages/<name>/.github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    - cron: '0 6 * * 1'

jobs:
  ci:
    uses: coolms/.github/.github/workflows/angular-library.yml@develop
    with:
      node-versions: '["22","24"]'
      bundle: dist/fesm2022/coolms-<name>.mjs   # optional
```

| input | default | purpose |
|---|---|---|
| `node-versions` | `["22","24"]` | JSON array of Node majors to run |
| `bundle` | `''` | fesm2022 bundle path; when given, asserts the framework stayed external. Empty skips that step. |

The steps are install, typecheck, lint, build, and two positive assertions — that
the build produced a package, and that Angular did not end up inside the bundle.
Beside them, an `advisories` job holds the committed lockfile's advisories against
the package's `.github/advisories.txt` (`npm-advisories.yml`, below).

## Who can call it today

Only the packages that can install standalone. The rest declare `@coolms/*` peer
dependencies, npm auto-installs peers, and none of those packages is published to
npm — so `npm install` fails in a clean checkout and every step behind it is
skipped. A workflow added before that is a red check that says nothing about the
code.

Publishing the `@coolms/*` libraries to npm is what unblocks them, in dependency
order: `core-angular` and `document-engine` first, then `editor-angular`,
`ui-angular`, `document-viewer-angular`, then `pdf-angular`, `image-editor-angular`
and `sheet-editor-angular`.

## `npm-advisories.yml`

Advisories may only fall. `npm audit` reads the committed `package-lock.json`, and
every advisory it reports must be on the repository's list, `.github/advisories.txt`,
at or above the severity it was accepted at. The job fails on a new advisory, on a
listed one that is no longer reported (so the list only shrinks), on an advisory
rated higher than its line records, on a `package.json` with no lockfile beside it,
and on any npm error. A check that could not evaluate does not pass: when the
registry is out of reach, the audit is retried with backoff and then fails as
`UNEVALUABLE: registry unreachable`; a rerun clears it.
A repository calls it as a job:

```yaml
jobs:
  advisories:
    uses: coolms/.github/.github/workflows/npm-advisories.yml@develop
    with:
      working-directory: angular   # optional, default '.'
```

```text
# .github/advisories.txt -- <package> <advisory id> <severity accepted at> <why it stays>
source-map-js  GHSA-68fv-2mgg-jv7q  high  build tool only; the update waits for its dependents
```

## `basic-files.yml`

Does a public package repository (composer.json or package.json at its root) carry
`README.md`, a `LICENSE` whose text is the license its manifests declare, and
`CHANGELOG.md`? A license is recognised by a phrase only its own text holds. A
declared license the check cannot compare, or a `LICENSE` it does not recognise,
fails the job as UNEVALUABLE: a check that could not evaluate is not a pass.

The check is a byte-for-byte copy of the one release-tools keeps, rendered there
and compared there with this file at the commit callers pin to. Do not edit it
here. The job reads the repository's contents and nothing else: no inputs, no
secrets, a checkout that keeps no credentials, and no network call after it.

**Call it pinned to a commit of this repository, never `@develop` or a tag**, so a
change here cannot change a caller's CI unseen. When the check changes, every
caller's pin is moved in one sweep, and each repository's next run proves it.

```yaml
jobs:
  basic-files:
    uses: coolms/.github/.github/workflows/basic-files.yml@<40-character commit>
```

Archived repositories are not checked. An empty repository is checked once it has
content.
