# ROADMAP

Sequencing for the DevTube Analytics Platform, Milestone 0 → 8. Each milestone is
a working increment: it produces something you can run and verify before moving on.
Finish batch ingestion and analytics before RAG; finish RAG before streaming; use
the final days for hardening rather than new technologies.

Working agreement: the user implements the backend by hand (agent advises, reviews
with `file:line` feedback). The agent is the primary author of the React app in
`apps/devtube_web/`.

## Milestone 0 — Repo hygiene + environment bootstrap (~1 day)

Nothing downstream works without local object storage (RustFS), so this comes first.

1. Initial `git` commit of the scaffold.
2. Harden `.gitignore`: `.env`, secrets, Terraform state/plan files, dbt artifacts.
3. `docker-compose.yml`: RustFS (S3-compatible object storage), Qdrant, Postgres
   (Dagster metadata).
4. terraform against rustfs: the object storage bucket.
5. `.env` with `YOUTUBE_API_KEY` (never committed).
6. Config hygiene: one place for credentials/endpoints, documented.

**Verify:** a smoke test writes a file to object storage and reads it back; the
same for a DuckDB analytics check. Definition of done: *a fresh local
environment can be created using Docker + Terraform against RustFS.*

## Milestone 1 — Batch ingestion → raw object storage (~2–3 days)

1. `devtube_ingestion`: YouTube Data API client — channels, videos, statistics,
   comments, transcripts.
2. Pydantic validation models in `common` (IDs, timestamps, counts, relationships).
3. Idempotent, immutable raw writes: deterministic object keys, no overwrites;
   keep the original API response byte-for-byte.
4. `devtube_dagster`: minimal Dagster job running ingestion; structured logs
   (`run_id`, duration, records written/failed).
5. pytest unit tests (mocked HTTP) + integration test against local object storage (RustFS).

**Verify:** running the job twice produces no duplicate logical records; raw data
is intact under `videos/`, `channels/`, `comments/`, `transcripts/`, `metrics/`.
Definition of done: *batch pipeline ingests curated Tech YouTube data into
immutable S3-compatible raw storage (RustFS).*

## Milestone 2 — Parquet mirror + DuckDB Bronze/Silver (~2–3 days)

1. Parquet mirror: a Dagster op reads the raw JSON, conforms it with Polars
   (`devtube_transformations`), and writes content-addressed Parquet back to
   RustFS (`parquet/`). Idempotent: unchanged input → identical keys, zero new
   objects.
2. Determinism check: run the mirror twice; Parquet output must be
   byte-identical (required for the sha256 keying).
3. DuckDB warehouse: `duckdb/devtube.duckdb`; a load op brings the Parquet
   mirror into DuckDB tables.
4. dbt project (`dbt/`): sources over the loaded tables → Bronze (thin landing)
   → Silver (dedupe, conform schema, standardize timestamps, validate
   relationships).
5. Incremental processing: the mirror is append-only; dbt models from Silver up
   materialize incrementally keyed on `snapshot_date` — watermark-based, no full
   recompute per run.

**Verify:** the mirror double-run creates zero new objects and byte-identical
files; Bronze/Silver are queryable in DuckDB; dbt runs green. Definition of done:
*DuckDB Bronze/Silver layers exist and can be queried reliably; the Parquet
mirror is idempotent.*

## Milestone 3 — dbt Gold + trend scoring (~2–3 days)

1. Gold: analytics-ready dimensions (`channels`, `videos`, `dates`, `topics`)
   and the fact table `video_daily_metrics`.
2. dbt tests + data-quality checks: `not_null`, `unique`, `relationships`,
   `accepted_values`; catch invalid/duplicate data.
3. Trend scoring — not raw lifetime views: velocity × recency × engagement ×
   cross-channel spread; derived metrics (views/day, engagement rate, velocity
   change, distinct creators/videos per topic, comment velocity).
4. Trend output tables/marts for topics, videos, creators.
5. dbt snapshots for slowly-changing entities — the time-travel substitute now
   that the warehouse is DuckDB.

**Verify:** dbt tests fail on bad data; a reproducible orchestrated batch job
produces updated trend results. This closes the *batch ingestion + analytics*
phase — the next phase depends on a solid analytics layer.

## Milestone 4 — Content processing + embeddings + Qdrant (~2–3 days)

1. Content pipeline with an explicit evidence hierarchy: transcripts (primary),
   descriptions (controlled fallback), comments (filtered/deduped, summarized or
   clustered before embedding — never treated as creator evidence).
2. Chunking + normalization with full provenance: `video_id`, `source_type`,
   timestamps.
3. `devtube_embeddings`: sentence-transformers → Qdrant with metadata.
4. Hybrid retrieval (BM25 + vector).

**Verify:** Qdrant returns semantically relevant chunks with provenance intact;
`source_type` is explicit and reported. Definition of done: *Qdrant supports
semantic retrieval with metadata/provenance; transcripts/descriptions/comments
handled per the source hierarchy.*

## Milestone 5 — FastAPI + RAG chat (~2–3 days)

1. `devtube_api`: `/trends`, `/videos`, `/creators`, `/search`, `/chat`.
2. Chat: hybrid retrieval → DeepSeek synthesis with citations; answers grounded
   in retrieved evidence.
3. Small documented evaluation set for retrieval and answer quality.

**Verify:** chat answers cite their sources; the eval set is committed and
documented. Definition of done: *hybrid retrieval + source-grounded answers;
documented evaluation set.*

## Milestone 6 — Streaming simulation (~1–1.5 days)

1. A simulated continuous event source (e.g. fake view/comment events).
2. Continuous event processing into the raw lake and DuckDB warehouse.

**Verify:** the path demonstrates incremental event ingestion into the lake and
warehouse without re-running the batch. Definition of done: *a simulated
streaming path demonstrates continuous event processing into the raw lake and
DuckDB warehouse.*

## Milestone 7 — React frontend (~2–3 days)

Agent-authored, against the `devtube_api` contracts from Milestone 5.

1. Dashboard: trending topics, creators, videos.
2. Chat UI with sources/citations rendered per answer.

**Verify:** the app consumes real API data end to end (trends + chat).

## Milestone 8 — Hardening + CI (~1–2 days)

1. GitHub Actions: lint, type checks, pytest, Terraform validate, dbt test.
2. Logging/config hygiene audit; docs pass over the repo.
3. Final run-through of the Definition of done in `AGENTS.md`.

## Parallel tracks

- The frontend can start earlier with mocked API data if a stable contract is
  agreed upfront; otherwise start after Milestone 5.
- Embedding-model selection and chunking experiments can be prototyped in
  isolation during Milestone 4 without blocking the analytics layer.

## Notes

- Today's date: 2026-09-04. Deadline September 15 → ~14–16 working days at
  3–4h/day, which fits the 15-day plan if each milestone ships on schedule.
- If a milestone slips, cut scope in the milestone itself (drop a table, a
  metric) rather than skipping a verification step.
- The local stack uses RustFS (S3-compatible) for object storage and DuckDB
  (embedded, via dbt-duckdb) for analytics. These replace the Floci AWS
  emulator, whose Redshift `DescribeClusters` response omits fields the
  Terraform provider requires (https://github.com/floci-io/floci/issues/3098).
- The medallion architecture lives in DuckDB (built by dbt); RustFS holds the
  immutable raw JSON plus a content-addressed Parquet mirror. Iceberg was
  dropped as overkill for a single-node project.
