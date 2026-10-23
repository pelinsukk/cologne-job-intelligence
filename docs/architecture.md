# Architecture — implemented M0/M1

Python >=3.12, verified on the available Python 3.13.5. Python 3.13 is a supported
alternative to installing 3.12 just for this milestone. The only runtime third-party
library is HTTPX. Standard-library argparse, dataclasses and sqlite3 keep the local
tool small. pytest/Ruff are development dependencies. A hash-pinned uv lock records
reproducible dependencies. LICENSE remains MIT for software, not collected data.

```text
CLI -> persistent source registry -> fail-closed authorization
    -> local dataset hash check -> JSON field validation
    -> normalization -> deduplication -> transactional SQLite persistence
                             -> source observations + provenance + run/audit records

Future remote adapter -> AuthorizedHTTP -> registry/runtime gate
    -> current robots check -> persistent pacing -> bounded HTTPX request
    -> audit / denial latch / cooldown / safe error
```

There is no network activity on import, startup, status or doctor. There is no
enabled live discovery adapter. The transport is implemented and tested for future
use, but neither tests nor its existence establish a live source permission.

## Modules

- `authorization.py`: explicit states, required assessment evidence, 90-day expiry,
  bundled blocked/unknown source ledger.
- `http.py`: centralized gated HTTPX transport, timeout/body bounds, robots checks,
  no redirects, no circumvention, bounded transient retries, persistent cooldowns.
- `models.py`: employer records, authorization states and safe errors.
- `normalization.py`: Unicode/name canonicalization and conservative HTTP(S) URL
  normalization. Website normalization never fetches a website.
- `storage.py`: schema v1, transactions, source/control state, audit snapshots,
  identities, aliases, provenance, historical claims, discovery runs and pacing.
- `discovery.py`: exact-file-authorized local JSON connector, batch validation,
  transactional import, success/failure tracking.
- `cli.py`: operational commands and JSON inspection/diagnostics.

No empty future milestone modules, credentials, schedulers or cloud integration.

## Identity and incremental changes

An exact `(source_id, external_id)` is authoritative for repeated observations.
Otherwise, merge only a unique exact normalized name AND exact normalized website
match. Domains or similar names alone never establish identity. This intentionally
misses some duplicates rather than merging unrelated organizations. Shared URLs
with distinct names remain distinct. Names alone without websites remain distinct.

Canonical name/website/industry may be refreshed for stable source identities;
prior claims survive in observations. Initial and current names are aliases.
First-seen survives updates, last-seen advances. The updated count means observed
existing records, including unchanged records; it is not a vacancy-change count.
Every distinct source/external ID retains its own provenance. Changed observations
are retained; identical payloads update last-seen rather than append duplicate rows.
Missing imported records never remove employers. Source-provided Cologne location
evidence and website URLs remain claims, not independent verification.

## Coverage and health metrics

- Unique employer count, alias/observation/provenance records available by inspection.
- Sources registered, effectively permitted, disabled/denied, with reasons.
- Per-source last successful import and per-run start/end, fetched/created/updated,
  success/failure and safe error reason. Epoch timestamps are UTC seconds.
- Audit trail of control changes, authorization refusals, requests, response status,
  robots decisions, cooldowns and successful/failed discovery.
- No denominator for all relevant employers; no implied completeness percentage.
- No monitoring/careers success is claimed before M2. Employer monitoring status
  starts `not_started`; careers/ATS/scan fields remain null.

Schema creation is atomic; unsupported schema versions fail rather than overwrite
data. Future migrations must be explicit, incremental and backed up. Short SQLite
transactions and a ten-minute source lease prevent parallel discovery for one
source; an interrupted process may require waiting for lease expiry. A crashed run
may remain `running` in historical run output and is not a successful scan.

## Boundaries

No global market coverage, geographic eligibility, language suitability or
employment compatibility is inferred. Employer registry imports are not vacancy
recommendations. There is no verification against company websites. The transport
does not guarantee exhaustive CAPTCHA detection; unexpected content fails the
JSON/robots checks. Defense relies on centralized transport and code review, not
a Python sandbox capable of preventing arbitrary new code from opening sockets.
