# AGENTS.md

DevTube Analytics Platform — a data engineering + AI platform that answers
"What is popular today in Dev YouTube?" Pipeline: batch ingestion → RustFS
(S3-compatible)/Iceberg lakehouse → DuckDB/dbt analytics → trend scoring →
RAG chat.

## Product goals

Each goal states a question the system should answer:

- **Trending topics**: What Tech YouTube topics are gaining attention today?
- **Creator momentum**: Which creators are gaining attention or publishing around emerging topics?
- **Video discovery**: Which videos are driving a trend?
- **Topic explanation**: Why is a particular topic trending?
- **Audience discussion**: What are viewers talking about or reacting to?
- **Interactive analysis**: Can a user ask follow-up questions and get evidence-grounded answers?

## Roles

This is a learning project: the user writes the backend by hand and learns by doing.

- **Backend, pipelines, infrastructure** (everything outside `apps/devtube_web/`):
  advisory only. Read any file to review or explain it, but make no edits without
  the user's explicit permission for that specific task. Feedback should reference
  `file:line` and explain the reasoning so the user can implement it themselves.
- **Frontend React app** (`apps/devtube_web/`): the agent is the primary author.
  It owns this code end to end — implementation, refactors, fixes, and tests —
  and keeps it consistent with the platform's API contracts.

## Working mode

- Advisory answers first: diagnose, review, propose. The user decides.
- Suggestions state the change and why; the user applies them unless the agent
  owns the file or holds explicit permission for the task.
- Build each milestone as a working increment: finish batch ingestion and
  analytics before adding RAG, finish RAG before adding streaming, use the
  final days for hardening rather than new technologies.

## Definition of done

- A fresh local environment can be created using Docker + Terraform against RustFS.
- The batch pipeline ingests curated Tech YouTube data into immutable S3-compatible raw storage (RustFS).
- Iceberg Bronze/Silver/Gold layers exist and can be queried reliably.
- DuckDB contains analytical models suitable for trend analysis.
- dbt tests and data-quality checks catch invalid/duplicate data.
- A reproducible orchestrated batch job produces updated trend results.
- The system identifies trending topics, videos, and creators using more than raw lifetime views.
- Transcripts are used when available; descriptions provide a controlled fallback.
- Comments are treated as audience evidence, filtered/clustered rather than blindly trusted.
- Qdrant supports semantic retrieval with metadata/provenance.
- The chat interface uses hybrid retrieval and produces source-grounded answers.
- RAG retrieval and answer quality have a small documented evaluation set.
- A simulated streaming path demonstrates continuous event processing into Iceberg.
- Tests, CI, structured logging, configuration hygiene, and documentation are present.
