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

## Offline release

Implemented manual vacancy entry, URL deduplication, explainable term ranking,
application stages and history, plus an isolated in-memory synthetic demo.
This local workflow does not enable remote discovery, ATS monitoring, scheduling,
notifications or outreach. Live collection remains conditional on verified
source-specific permission.
