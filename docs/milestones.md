# Milestones

## M0 — foundation and compliance

Implemented src layout, pinned dependencies/uv lock, permanent AGENTS.md rules,
zero-cost/local-first constraints, authorization registry, fail-closed gate,
auditable gated HTTP transport, responsible rate/denial handling and tests.

## M1 — employer registry

Implemented models, SQLite schema, aliases, normalization, conservative employer
deduplication, provenance, claim history, incremental local import, persistent
source controls, health/coverage counts and operational CLI commands.

**Conditional external source item remains unavailable:** Wikidata SPARQL and
FOSSGIS Overpass were evaluated and blocked because their robots rules disallow
the intended paths. No remote discovery adapter is enabled, no live employer
discovery smoke test ran and no genuine sample discovery results are claimed.
Synthetic offline fixtures verify functionality as authorized by the assignment's
fallback. This is a functioning registry/foundation with limited data acquisition.

## Stop point

M2–M8 have not been started. Next, after user authorization to continue: assess
permitted official employer/ATS feeds for M2, implement careers identification,
permission-scoped monitoring and vacancy lifecycle tests. Live adapters require
fresh source-specific evidence before any collection. Do not activate blocked
sources merely to increase coverage.
