# Authorized local import

No default source is PERMITTED. For useful local employer records, supply a JSON
file you created from your own organizational data or obtained with compatible
processing rights. Do not scrape prohibited platforms or include employee/contact
information. This importer never fetches a URL in the file.

Dataset shape (replace with genuine organization records; these names/URLs are
explicitly **synthetic examples**, not discovered employers):

```json
{
  "employers": [
    {
      "external_id": "your-stable-id",
      "name": "Synthetic Example Organization",
      "website": "https://organization.example",
      "source_url": "https://evidence.example/organization",
      "aliases": ["Synthetic Example"],
      "industry": "research",
      "location_evidence": "Describe your source's Cologne presence claim"
    }
  ]
}
```

Required: nonempty string external_id, name and source_url. Optional: website,
aliases (string list), industry, location_evidence, confidence. Imported confidence
is always stored as `source_claim`, even if a file attempts to claim verified
status. Unknown/contact fields are rejected; maximum size 2 MB, 10000 records.
Website URLs must be HTTP(S) with no embedded credentials. Canonical URLs preserve
schemes, meaningful paths and queries, normalize hosts/default ports and drop
fragments/trailing slash. Normalization does not validate website ownership.

1. Store your dataset outside Git, for example in an ignored `data/` directory.
2. Compute its exact checksum on macOS:

   ```bash
   shasum -a 256 /absolute/path/to/employers.json
   ```

3. Copy `config/local-assessment.example.json` to an ignored local location. Set:
   - `documentation`: actual permission/license evidence and a string
     `sha256:` immediately followed by the checksum (64 hex digits).
   - `license`: actual reuse rights, for example your own original data if true.
   - `restrictions`: actual scope/retention/privacy restrictions.
   - `assessed_on`: actual review date in `YYYY-MM-DD`.
   - `confidence`: `high` only after establishing permission.
   - `state`: `PERMITTED` only after establishing permission.
   - `enabled`: `true` to enable, or `false` to save then enable separately.
4. Register, import and inspect:

   ```bash
   cologne-jobs sources assess /absolute/path/to/local-assessment.json
   cologne-jobs sources enable local-json
   cologne-jobs discover --file /absolute/path/to/employers.json
   cologne-jobs employers
   cologne-jobs employers 1
   cologne-jobs status
   ```

If permission is unresolved, leave UNKNOWN/disabled. The software cannot certify
the truth of supplied rights evidence. `sources assess` supports local-json only
in M1; it cannot enable remote sources. The gate checks evidence before reading
the dataset. A changed file requires a new exact-file assessment. Multiple imports
do not delete existing employers. Only source-supplied stable IDs, or exact
name+website matches, consolidate records.

Synthetic examples exist only in test fixtures/documentation and are never
seeded into the normal application database.
