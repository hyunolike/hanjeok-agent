# Contract: Hanjeok Export

The only way Hanjeok data enters this repository (constitution, Constraints).
Produced on the Hanjeok side; consumed by `guide refresh`. Format version 1.

## Layout

```text
hanjeok-export-<YYYYMMDD>/
├── manifest.json
├── places.jsonl
├── related.jsonl
├── festivals.jsonl
└── exhibitions.jsonl
```

One JSON object per line, UTF-8, no trailing commas, `null` for absent values.

## `manifest.json`

```json
{
  "format_version": 1,
  "exported_at": "2026-10-13T02:00:00Z",
  "source": "hanjeok",
  "files": {
    "places.jsonl":      {"rows": 0, "sha256": "…"},
    "related.jsonl":     {"rows": 0, "sha256": "…"},
    "festivals.jsonl":   {"rows": 0, "sha256": "…"},
    "exhibitions.jsonl": {"rows": 0, "sha256": "…"}
  }
}
```

`guide refresh` recomputes every hash and row count before loading and stops
with a named cause on any mismatch. The manifest's own SHA-256 is recorded on
the `Corpus` node as `export_sha256` and stamped on every report.

## Files

Columns are an allow-list. A column not named here is not exported, including
any added to these tables later.

### `places.jsonl`

From `derived_attraction` joined to `raw_attraction` on `content_id`.

| Field | Source | Notes |
| --- | --- | --- |
| `id` | `derived_attraction.id` | Integer. The id Hanjeok's API uses |
| `name` | `derived_attraction.name` | |
| `region_code` | `derived_attraction.signgu_cd5` | 5 digits |
| `region_label` | `derived_attraction.area_label` | |
| `content_type` | `derived_attraction.content_type_id` | |
| `category_mid`, `category_small` | `derived_attraction.lcls_systm2`, `lcls_systm3` | |
| `summary` | `derived_attraction.summary` | |
| `overview` | `raw_attraction.overview` | |
| `address` | `raw_attraction.addr1` | |
| `lat`, `lng` | from `derived_attraction.location` | Decimal degrees |
| `has_congestion_data` | `derived_attraction.has_congestion_data` | |

Rows: places with `has_congestion_data = true`, and places that are the
`related_attraction_id` of such a place.

Deliberately not exported: `tel`, `homepage`, `rest_date`, `use_time`, images,
bus-stop fields. The agent does not answer contact, hours or transport
questions (spec, Out of Scope), and data it must not answer from is better not
held.

### `related.jsonl`

From `derived_related`.

| Field | Source |
| --- | --- |
| `base_id` | `base_attraction_id` |
| `related_id` | `related_attraction_id` |
| `rank` | `relation_rank`, nullable |
| `score` | `relation_score` |
| `distance_km` | `distance_km` |
| `travel_minutes` | `travel_minutes` |

Rows: those whose `base_id` and `related_id` are both in `places.jsonl`.

### `festivals.jsonl`

From `derived_festival`: `id`, `name`, `start_date`, `end_date`, `lat`, `lng`.
Rows whose `end_date` is on or after the export date.

### `exhibitions.jsonl`

From `derived_exhibition`: `id`, `name`, `start_date`, `end_date`, `place`,
`lat`, `lng`, `attraction_id`. Same date rule.

## Never exported

`community_member`, `place_photo`, `photo_like`, `photo_report`,
`attraction_view`, `daily_view_stat`, `course`, `course_item`,
`congestion_feedback`, `attraction_light_feedback`, `attraction_visit`,
`congestion_coverage_miss`, and the operational tables `batch_run`,
`load_metric_snapshot`, `event_publication`, `shedlock`.

`derived_congestion` and `derived_weather_daily` are also not exported. They
are date-bound and the agent fetches them live (FR-011).

## Producing it

`scripts/guide-agent-export.sh` in the Hanjeok repository (branch
`chore/guide-agent-export`, written 2026-10-14 at the author's request). It
reads the four sources inside one read-only `REPEATABLE READ` transaction, so
a batch replacing relatedness rows mid-export cannot leave a link whose end is
missing from the places file. Each query names its columns one by one.

It does not use `\copy`: COPY's text format escapes backslashes a second time
and corrupts JSON strings. Rows are printed with `psql -At` and split into
files on the client.

Checked against a throwaway PostGIS container built from Hanjeok's own table
definitions, with rows chosen to be awkward: quotes, a backslash, a newline and
a tab in a description; a link Hanjeok left unranked; a place that is neither
covered nor a related target; links to that place; an event already over. The
output passed `guide refresh --check`. **It has not been run against the
production database**, and nothing in this repository connects to it.

## Synthetic export

`bench/tests/fixtures/hanjeok-export/` holds a hand-written export in this
format: about forty invented places in two regions, with relatedness links, a
few events, one place with no congestion data and two places sharing a name.
All tests and the local demo use it. It contains no real Hanjeok data.
