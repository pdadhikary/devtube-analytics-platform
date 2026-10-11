# AGENTS.md

DevTube Analytics Platform — a data engineering + AI platform that answers
"What is popular today in Dev YouTube?" Pipeline: batch ingestion → RustFS
(S3-compatible) raw lake + Parquet mirror → DuckDB/dbt warehouse (Bronze/
Silver/Gold) → trend scoring → RAG chat.

## Product goals

Each goal states a question the system should answer:

- **Trending topics**: What Tech YouTube topics are gaining attention today?
- **Creator momentum**: Which creators are gaining attention or publishing around emerging topics?
- **Video discovery**: Which videos are driving a trend?
- **Topic explanation**: Why is a particular topic trending?
- **Audience discussion**: What are viewers talking about or reacting to?
- **Interactive analysis**: Can a user ask follow-up questions and get evidence-grounded answers?

## Roles

The agent is the primary author for the whole project — backend, pipelines,
infrastructure, and the React app (`apps/devtube_web/`). It owns implementation,
refactors, fixes, and tests end to end, and keeps every layer consistent with the
platform's API contracts. The user remains the decision maker on scope and
direction.

## Working mode

- Diagnose from evidence first: reproduce the failure, identify the root cause,
  then fix it. Reference `file:line` in the explanation.
- Build each milestone as a working increment: finish batch ingestion and
  analytics before adding RAG, finish RAG before adding streaming, use the
  final days for hardening rather than new technologies.

## Tooling

- Type-check with `zuban`; it is the project's type checker and `ty` is being
  removed. `zuban check` needs source directories, not package roots, e.g.
  `uv run zuban check pipelines/devtube-pipeline/src orchestration/devtube_dagster/src`.

## Definition of done

- A fresh local environment can be created using Docker + Terraform against RustFS.
- The batch pipeline ingests curated Tech YouTube data into immutable S3-compatible raw storage (RustFS).
- A DuckDB data warehouse with Bronze/Silver/Gold layers (built by dbt) exists and
  can be queried reliably; a content-addressed Parquet mirror of the raw lake backs it.
- DuckDB contains analytical models suitable for trend analysis.
- dbt tests and data-quality checks catch invalid/duplicate data.
- A reproducible orchestrated batch job produces updated trend results.
- The system identifies trending topics, videos, and creators using more than raw lifetime views.
- Transcripts are used when available; descriptions provide a controlled fallback.
- Comments are treated as audience evidence, filtered/clustered rather than blindly trusted.
- Qdrant supports semantic retrieval with metadata/provenance.
- The chat interface uses hybrid retrieval and produces source-grounded answers.
- RAG retrieval and answer quality have a small documented evaluation set.
- A simulated streaming path demonstrates continuous event processing into the raw lake and DuckDB warehouse.
- Tests, CI, structured logging, configuration hygiene, and documentation are present.
