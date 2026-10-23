# M0/M1 implementation report — 2026-10-24

Scope: M0 and M1 only, local changes in `cologne-job-intelligence`. No M2–M8
implementation, deployment, paid service, Actions workflow, applications or outreach.

## M0 — implemented

- Modular Python package, installable `cologne-jobs` entry point, exact dependency
  pins and transitive `uv.lock`, pytest/Ruff development tools.
- Permanent `AGENTS.md` legal-access, zero-cost, privacy and milestone rules.
- Persistent source registry with PERMITTED, RESTRICTED, UNKNOWN, BLOCKED states;
  enable/disable controls; dated evidence and 90-day expiry; fail-closed gate.
- Central HTTPX transport with current robots enforcement, assessed endpoint
  allowlist, finite timeout/response limits, persistent pacing/cooldowns, bounded
  transient retries, no redirect/host-switch behavior and persistent denial latch.
- SQLite audit records include assessment snapshots, control changes, request
  fingerprints, responses, network errors, denials and successful/failed discovery.
- Source evidence, coverage definitions, architecture and operational documentation.

M0 verification: `.venv/bin/pytest -q tests/test_authorization_http.py`:
**32 passed in 0.15s**. These are synthetic MockTransport tests, not live API tests.
The unit suite explicitly prevents HTTPX's real transport from making requests.

## M1 — implemented

- SQLite v1 schema, transactions, constraints, employer identities, aliases,
  provenance, historical source claims and discovery run summaries.
- Unicode/name and HTTP(S) URL normalization; conservative deduplication by stable
  source ID or unambiguous exact normalized name plus website. No fuzzy/domain-only
  consolidation. Source changes preserve old observation payloads and first-seen.
- Local JSON discovery/import connector with explicit, file-hash-bound permission;
  input field validation and all-or-nothing persistence. No website visits.
- Operational CLI: `discover` (local file only), `employers`, `sources` with assess /
  enable / disable, `status`, `doctor`, `audit`.
- Separate-process persistence, repeated discovery and command/error tests.

M1 verification: `.venv/bin/pytest -q tests/test_discovery_storage_cli.py`:
**25 passed in 0.35s**. Synthetic fixtures only; normal database receives no demo
or invented employers. All imported employer facts remain source claims.

The first live connector/smoke-test item is **unavailable**, as allowed by the
assignment's fail-closed fallback. No suitable permitted live endpoint was enabled
after the two evaluated API paths failed robots policy checks. This deliverable
is a tested employer registry and import foundation, not live job discovery.

## Final checks actually executed

Environment: macOS, Python **3.13.5**, SQLite **3.45.3**. Python >=3.12 is declared;
Python 3.12 was not installed or tested here. Python 3.13.5 was available locally.

| Check | Actual result |
| --- | --- |
| `.venv/bin/pytest -q` | **57 passed in 0.48s** |
| `.venv/bin/ruff check .` | **All checks passed!** |
| `.venv/bin/ruff format --check .` | **11 files already formatted** |
| `git diff --check` | Exit 0; no whitespace errors |
| Installed console command `doctor` against temporary DB | integrity `ok`, 0 foreign-key errors, schema 1 |
| Installed command `status` against fresh temporary DB | 0 employers, 9 sources, 0 allowed |
| Explicit separate-process synthetic CLI smoke | first import: fetched 1, created 1, updated 0 |
| Same synthetic file, second console command | fetched 1, created 0, updated 1 |
| Inspect synthetic employer in third process | 1 employer, 1 provenance, source_claim |

The explicit CLI smoke used `/private/tmp/cologne-m1-smoke-fkhlvrch/smoke.sqlite3`.
It contains only a clearly named synthetic organization at a reserved `.example`
domain, with test-only permission. It is outside the default application database
and outside Git. No genuine discovery results were collected or claimed.

Installed using free dependency downloads with `uv sync`. The documented install
uses `--no-editable`: this environment marks files under `.venv` hidden, which
caused Python 3.13 to skip an editable install's `.pth` file. A normal wheel
installation was verified. Rebuild after source edits using the README's explicit
`--reinstall-package cologne-job-intelligence` command before running tests/CLI.

## Source authorization and live checks

| Source | State / enabled | Actual live activity and decision |
| --- | --- | --- |
| Wikidata SPARQL | BLOCKED / false | Official API/license/policy documentation reviewed; robots GET returned HTTP 200 with `Disallow: /sparql`. No data query. |
| FOSSGIS Overpass | BLOCKED / false | Official service/license documentation reviewed; robots GET returned HTTP 200 with `Disallow: /api/`. No interpreter query. |
| local-json | UNKNOWN / false by default | Only exact-file synthetic test grants were enabled in temporary test DBs. Genuine files require actual rights evidence. |
| IHK Köln, KölnBusiness, LinkedIn, Indeed, StepStone, XING | UNKNOWN / false | No authorization established; no collection attempted. |

No live employer discovery smoke test was run. Live policy/robots checks are not
a successful discovery integration. No alternate instance, proxy, identity,
credential or browser route was used to circumvent these rules. There are no
enabled PERMITTED remote sources. See [source-policy.md](source-policy.md) for
official links, rate guidance, exact robots excerpts and licensing obligations.

## Files created or modified

Modified: `README.md`. Preserved: existing MIT `LICENSE`.

Created: `AGENTS.md`, `pyproject.toml`, `uv.lock`, `.gitignore`, `.env.example`,
`config/local-assessment.example.json`; `src/cologne_jobs/` modules (`__init__`,
authorization, cli, discovery, http, models, normalization, storage);
`tests/conftest.py`, `tests/test_authorization_http.py`,
`tests/test_discovery_storage_cli.py`; architecture, source-policy, local-import,
operations, milestones and this report under `docs/`.

No credentials or personal contacts were added. The static secret-pattern test
and ignore checks passed; these do not constitute an exhaustive security audit.

## Operation

Installation and commands are documented in [README](../README.md). On macOS:

```bash
uv sync --frozen --no-editable
source .venv/bin/activate
cologne-jobs doctor
cologne-jobs status
cologne-jobs sources
```

Persistent database default:
`~/Library/Application Support/cologne-jobs/employers.sqlite3`.
Use `--db PATH` before a command or export `COLOGNE_JOBS_DB` to override.
The verification runs used temporary databases rather than write to the default
user Library directory. The default is created on first operational command.

Authorized local import: document rights using the
[local import workflow](local-import.md), then `sources assess FILE` and
`discover --file DATASET`. No external API credentials are needed for M0/M1.

## Limitations and next milestone

- Zero remote data collection currently available; no job listings or rankings.
- Manual rights assertions cannot prove actual permission. The program does not
  independently verify employer websites, presence, legitimacy or current status.
- Conservative deduplication may retain false negatives. No fuzzy identity merges.
- No external live adapter cache/pagination support, notification configuration,
  dashboard, scheduling or integrated update command yet.
- Audit/history storage grows without automated pruning. Backup is local/manual.
- No claim of exhaustive Cologne coverage or legal-compliance certification.

Stop at M0/M1 as requested. After authorization to proceed, M2 would assess
specific official employer/ATS feeds, implement permitted careers identification
and vacancy lifecycle tracking, and verify that source failures never remove jobs.
