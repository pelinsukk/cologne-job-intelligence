# Cologne Job Intelligence

A finished offline tool for organizing a Cologne job search. Save vacancies
you find, rank your shortlist by keywords, and keep a history of application
stages in a local SQLite database. The command-line interface returns JSON.

- **Shortlist:** manually add vacancy links; duplicate links return the existing record.
- **Ranking:** see which of your search terms matched each vacancy.
- **Application history:** record stages and review their history.
- **Employer registry:** import authorised local JSON with source evidence.

**Release scope:** live data collection is intentionally outside this project.
There is no automated employer or vacancy discovery, site monitoring,
scheduling, or outreach. The tool does not visit saved links, contact employers,
or submit applications. The demo runs offline with synthetic data.

## Try the offline workflow

After installation, `cologne-jobs jobs demo` runs a labelled synthetic example
in memory without opening your personal database. For a real workflow, enter
only a listing you found and are authorised to use. The URL below is a placeholder.

```bash
cologne-jobs jobs demo
cologne-jobs jobs add --employer "Example" --title "Climate data analyst" \
  --url https://example.invalid/listing --location Cologne
cologne-jobs jobs list --term Python --term climate
cologne-jobs jobs stage 1 applied
cologne-jobs jobs history 1
```

Use the ID returned by `add` in the stage and history commands. The same
normalised URL returns the existing listing. Ranking counts distinct whole
terms or phrases found in the title, location and notes; the matched terms
are returned alongside the score. The stage is a personal record of what
you did outside the tool.

## Install on macOS

Use an existing Python 3.12+ interpreter and [uv](https://docs.astral.sh/uv/).
Python 3.13.5 was available locally and used for verification; 3.12 is supported by
the package requirement but has not been tested in this environment.

```bash
git clone https://github.com/pelinsukk/cologne-job-intelligence.git
cd cologne-job-intelligence
uv sync --frozen --no-editable
source .venv/bin/activate
cologne-jobs doctor
cologne-jobs status
cologne-jobs sources
```

`uv.lock` pins direct/transitive dependencies and hashes. Installation downloads
free packages; no credentials, API keys, cards or paid accounts are required.
Dependencies are development tools and HTTPX, not a subscription or hosted service.

## Commands

```bash
cologne-jobs --help
cologne-jobs sources
cologne-jobs sources disable local-json
cologne-jobs sources assess /absolute/path/to/local-assessment.json
cologne-jobs sources enable local-json
cologne-jobs discover --source local-json --file /absolute/path/to/employers.json
cologne-jobs employers --limit 50 --offset 0
cologne-jobs employers 1
cologne-jobs audit --limit 20
cologne-jobs status
cologne-jobs doctor
```

`sources enable` succeeds only for an assessed PERMITTED source. It cannot override
a runtime denial latch or an expired assessment. `discover` defaults to local-json
and fails closed until rights to the exact file have been assessed. Exit code 0
means command success; errors emit JSON on stderr with exit code 1 (usage errors 2).
`doctor` performs local checks and sends no network requests. `--db PATH` goes
**before** the command. Output is JSON; no unfinished commands are advertised.

## Local dataset workflow

See [local import instructions](docs/local-import.md). Permission belongs to a
specific dataset, not to JSON as a format. You must own the data or establish
compatible processing rights. Copy the [assessment template](config/local-assessment.example.json)
outside the repository, document actual rights evidence and the exact file SHA-256,
then assess and enable it. The template is UNKNOWN and disabled deliberately.
Do not use it to launder data collected from restricted websites. Imported data
remains a source claim: Cologne presence, official website and current employer
status are not independently verified. No linked website is visited.

## Data and coverage

Default database on macOS:
`~/Library/Application Support/cologne-jobs/employers.sqlite3`.
Override with `COLOGNE_JOBS_DB` or `--db`. `.env.example` documents configuration;
`.env` is not automatically loaded. Other systems use `$XDG_DATA_HOME/cologne-jobs`
or `~/.local/share/cologne-jobs`.

The database is created on the first operational command. Records, aliases, source
observations and first/last seen timestamps persist across manual runs. Updates
never delete employers. Changed claims remain in observation history. Identical
repeat imports refresh timestamps without extra employers or observation copies.
Missing records are not treated as removed. Database files and collected data are
ignored by Git. Local logs contain source IDs/statuses, not response bodies or
credentials. Do not publish a database without checking its source licenses.

Coverage is measured by registered/allowed/disabled sources, discovered unique
employers, successful/failed runs, records fetched/created/updated and per-source
last success. There is no reliable total number of relevant Cologne employers:
coverage percentages or exhaustive discovery claims would be misleading. Imported
names are potential employers, not verified vacancies or matching recommendations.

## Verification

```bash
uv sync --frozen --no-editable --reinstall-package cologne-job-intelligence
uv run --frozen --no-editable pytest -q
uv run --frozen --no-editable ruff check .
uv run --frozen --no-editable ruff format --check .
```

The non-editable install avoids Python 3.13 skipping hidden `.pth` files observed
in this macOS environment. After code changes, repeat the reinstall command above
before running tests or the CLI so that the installed wheel matches current source.

The offline demo and all 59 tests passed in the last verification on Python 3.13.5.
Unit tests prohibit real HTTP transport and use synthetic fixtures. See
[verification report](docs/implementation-report.md) for executed results and the
distinction between policy checks and live collection. This software is not a
legal-compliance certification.

Further documentation: [architecture](docs/architecture.md),
[source policy and evidence](docs/source-policy.md), [milestones](docs/milestones.md),
[backup and recovery](docs/operations.md).
