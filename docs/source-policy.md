# Source policy and assessment ledger

Assessed **2026-10-24 (Europe/Berlin)**. Evidence reviewed from primary sources.
This ledger records an engineering access decision, not a legal opinion or a
guarantee of GDPR compliance. Terms can change. Access assessments expire after
90 days, including local file assessments. Future-dated assessments fail closed.

## Decision rule

Only explicitly enabled PERMITTED sources with dated, high-confidence evidence,
license, field scope, robots assessment and rate settings pass the gate. UNKNOWN,
RESTRICTED, BLOCKED, disabled, stale and incomplete records fail. Assessments are
persisted in SQLite and are not reset by the next execution. Audit entries include
the full assessment snapshot effective at that event.

HTTP collection additionally requires assessed HTTPS endpoint/robots origin,
current successful robots rules allowing the request, and runtime checks. Missing,
unrecognized, redirected, unavailable or disallowing robots results do not grant
collection permission. No implicit permission from public visibility. No
alternative host, identity, proxy or browser route is used after denial.

401/403 or a detected CAPTCHA/challenge persist a denial latch. New processes
cannot retry a latched source. 429 and 503 with Retry-After save a cooldown, with
no immediate retry. HTTP-date and delay-seconds are supported; malformed headers
use 300 seconds. At most two attempts occur for transport failures or 502/503/504
without Retry-After. Redirects are never followed. Requests use a descriptive bot
User-Agent, finite timeouts, serialized per-source discovery leases and persistent
request spacing. Response size is capped at 2 MB. No live adapters are enabled,
so response caching/conditional requests are deferred until a source's cache
semantics are assessed. Local imports make no network requests.

## Wikidata Query Service — BLOCKED, disabled

- Official source: https://query.wikidata.org/
- Intended access: documented SPARQL GET; organization IDs/names, website and
  headquarters claims only. No personal profiles.
- [Data access](https://www.wikidata.org/wiki/Wikidata:Data_access) explicitly
  describes programmatic access; [licensing](https://www.wikidata.org/wiki/Wikidata:Licensing)
  assigns CC0 to structured data. Other wiki text has a different license.
- [Terms §12](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#12._API_Terms)
  incorporates API policies. [User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
  requires identifiable clients and contact information.
- [Service limits](https://www.mediawiki.org/wiki/Wikidata_Query_Service/User_Manual#Query_limits):
  60 processing seconds per 60 seconds, 30 error queries/minute, maximum five
  parallel queries. These are ceilings, not desired operating rates.
- Robots policy check actually performed: GET
  https://query.wikidata.org/robots.txt, HTTP 200; relevant response:

  ```text
  User-agent: *
  Disallow: /sparql
  Disallow: /bigdata
  ```

- Decision confidence: high for this project's BLOCKED decision. Despite
  documented API access, the user's stricter requirement to respect robots
  disallows the intended path. **No SPARQL data query was sent.**

## OpenStreetMap via FOSSGIS Overpass — BLOCKED, disabled

- Official source: https://overpass-api.de/
- Intended access: documented Overpass QL GET on `/api/interpreter`, organization
  names, OSM IDs, organization websites and locations only.
- [Operator guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
  describes the free shared service and approximately 10000 requests and 1 GB
  daily safety guidelines, with slot-based load shedding. Personal occasional
  queries would be small, but the robots restriction still blocks this adapter.
- [OSM copyright](https://www.openstreetmap.org/copyright): ODbL-1.0; attribution
  and share-alike obligations apply to distribution. The repository MIT license
  does not relicense OSM data. [Attribution guidance](https://osmfoundation.org/wiki/Attribution_Guidelines)
  distinguishes internal use and public produced works.
- Robots policy check actually performed: GET
  https://overpass-api.de/robots.txt, HTTP 200; relevant response:

  ```text
  User-agent: *
  Disallow: /api/
  Disallow: /munin/
  ```

- Decision confidence: high for BLOCKED. **No interpreter/data query was sent.**
  No alternate Overpass instance was tried to evade the restriction.

## Other sources

IHK Köln, KölnBusiness, LinkedIn, Indeed, StepStone and XING are UNKNOWN/disabled:
no source-specific automated collection authorization established. They were not
queried for employer/job data. The remaining universities, institutes, ATS
providers and recruitment platforms named in the project brief are unassessed
and unimplemented; mentioning them is not authorization.

`local-json` starts UNKNOWN/disabled. It supports only a local dataset whose exact
SHA-256 and actual rights evidence appear in a dated assessment. An assessment
cannot authorize arbitrary files or future file changes. Synthetic test grants
are confined to temporary test databases and are never seeded into production.

Only organization-level fields are accepted. No recruiter contacts, employee
profiles, email harvesting, applications or outreach. Field allowlists reduce
collection scope but cannot prove lawful data content: review datasets before
import. Local permissions depend on the user's real evidence; a manual assertion
does not itself establish rights.

M1 exposes no command to override remote BLOCKED states or clear runtime denial
latches. A future remote-source change requires new documented evidence, review
of robots and policy, code/config changes and tests. Do not edit SQLite merely to
bypass a denial. `sources disable ID` remains available for every source.
