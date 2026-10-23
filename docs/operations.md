# Local operations

All commands are manually executed. No task, launchd job, GitHub Actions workflow,
cloud runtime or notification service is activated. No software service cost is
authorized. Internet access is needed only to download free installation packages;
M0/M1 operational commands themselves have no enabled remote collection adapter.

Use `cologne-jobs --db /absolute/path/to/employers.sqlite3 status` or export
`COLOGNE_JOBS_DB` to override the macOS default. Keep the database outside Git.
The source registry and audit history are in the same SQLite file. `.gitignore`
also covers SQLite journals, WAL/SHM files, data, backups, logs and `.env*`.

## Backup and restore

For this manual local tool, finish all commands before making a copy of the SQLite
file. Copy it to a private local backup directory. Alternatively use SQLite's
online backup command with the actual path if sqlite3 CLI is installed:

```bash
sqlite3 "/absolute/path/to/employers.sqlite3" ".backup '/absolute/path/to/backup.sqlite3'"
```

Restore by choosing the backup with `--db` first and running `doctor`, `status`,
`sources` and `employers` before using it. Do not overwrite a newer database until
you have made a separate copy. An unsupported schema version fails closed.
Do not treat a backup as a way to bypass a denial or cooldown; those are safety
state and must be preserved/reviewed. Local data is not encrypted by this program;
use existing macOS account/file protection for private records.

## Failures and limits

`audit` and `status` report failed discovery and source denials. A nonzero command
exit must not be interpreted as an empty successful scan. No failure removes
employers. Unexpected malformed data rolls back the full import. JSON and local
filesystem failures are reported without arbitrary raw dataset contents in logs.
The HTTP transport audits all actual attempts; it does not log query values,
credentials or response bodies. Audit/observations currently grow without pruning.

Authorization expires after 90 days. Renew only with real evidence and a new date.
Runtime 401/403/CAPTCHA/robots denial latches are intentionally not clearable by a
normal CLI command. Reassessment and implementation review are required before
any future remote access. An interrupted source lease expires after ten minutes.

The CLI is sequential. One source lease serializes discovery; SQLite transactions
protect uniqueness and persistence. The framework is for personal manual use,
not a multiuser server. Bulk/live caching, paging, careers scans and automated
retention are outside M0/M1.
