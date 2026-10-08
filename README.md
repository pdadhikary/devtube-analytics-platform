# DevTube Analytics Platform

> **What is popular today in Dev YouTube?**

A production-oriented Data Engineering + AI platform for answering what is popular
right now in the YouTube developer space. DevTube is a deliberately scoped data
platform that continuously collects content from a curated set of technology
YouTube channels, computes what topics, creators, videos, and products are gaining
attention, and provides an evidence-grounded chat interface for deeper questions.

Core product thesis: **data engineering determines what is happening; AI
engineering helps explain why it is happening**, using the underlying evidence.

The project is built as a 15-day learning-by-doing project at roughly 3–4 hours
per day (45–60 hours total, deadline September 15). It prioritizes
production-grade engineering practices over feature count.

## Product goals

Each goal states a question the system should answer:

| Goal | Question |
|------|----------|
| **Trending topics** | What Tech YouTube topics are gaining attention today? |
| **Creator momentum** | Which creators are gaining attention or publishing around emerging topics? |
| **Video discovery** | Which videos are driving a trend? |
| **Topic explanation** | Why is a particular topic trending? |
| **Audience discussion** | What are viewers talking about or reacting to? |
| **Interactive analysis** | Can a user ask follow-up questions and get evidence-grounded answers? |

## Scope

**Dataset** — 20–30 curated Tech YouTube channels spanning consumer technology,
software development, AI/ML, Linux, programming, developer tooling, and SaaS.
Enough videos to make the analytics meaningful; historical backfill is
deliberately not the project itself.

**MVP** — batch ingestion, S3-compatible raw storage (RustFS) with a Parquet
mirror, DuckDB data warehouse, dbt, orchestration, trend scoring,
transcript/description enrichment, Qdrant vector search, hybrid retrieval, RAG
with citations, and a simulated streaming path.

**Out of scope** — Kubernetes, Spark clusters, sophisticated Flink deployments,
model fine-tuning, custom LLMs, advanced computer vision, authentication,
multi-tenancy, feature stores, and a large production UI.

## Architecture

### Component architecture

How the Python packages in the uv workspace fit together:

```
                        ┌─────────────┐
                        │   common    │
                        └──────┬──────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
devtube_ingestion   devtube_transformations   devtube_embeddings
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
                       devtube_dagster
                               │
                   ┌───────────┴───────────┐
                   ▼                       ▼
                 batch                 streaming

                          devtube_rag
                               │
                     ┌─────────┴─────────┐
                     ▼                   ▼
                  Qdrant                LLM
                     │
                     ▼
                  FastAPI
```

- `common` — shared models, configuration, and utilities
- `devtube_ingestion` — YouTube API clients and raw data collection
- `devtube_transformations` — Polars JSON→Parquet conformance (the Parquet mirror)
- `devtube_embeddings` — chunking and embedding models
- `devtube_rag` — hybrid retrieval and LLM answer synthesis
- `devtube_dagster` — orchestration of the batch job and simulated streaming path
- `devtube_api` — the FastAPI service (`/trends`, `/videos`, `/creators`, `/search`, `/chat`)
- `apps/devtube_web` — React frontend (dashboard + chat)

### Data flow

End-to-end, from the YouTube API to the dashboard and chat:

```
                             ┌─────────────────────┐
                             │     YouTube API     │
                             │  Videos / Channels  │
                             │  Stats / Comments   │
                             └──────────┬──────────┘
                                        │
                                        │ Batch ingestion (httpx)
                                        ▼
                             ┌─────────────────────┐
                             │  devtube_ingestion  │
                             └──────────┬──────────┘
                                        │
                                        │ Raw API responses (JSON)
                                        ▼
                    ┌─────────────────────────────────────────┐
                    │                 RustFS                  │
                    │            DATA LAKE (S3 API)           │
                    │                                         │
                    │  raw/      immutable JSON responses     │
                    │            videos/ channels/ comments/  │
                    │            transcripts/ metrics/        │
                    │                                         │
                    │  parquet/  conformed Parquet mirror     │
                    │            (Polars, content-addressed)  │
                    └────────┬─────────────────────┬──────────┘
                             │                     │
                             │ load Parquet        │ transcripts /
                             ▼                     │ descriptions /
                    ┌────────────────┐             │ comments
                    │     DuckDB     │             │
                    │   WAREHOUSE    │             ▼
                    │                │  ┌─────────────────────┐
                    │  ┌──────────┐  │  │ Content Processing  │
                    │  │  Bronze  │  │  │  Transcript         │
                    │  └────┬─────┘  │  │  Description        │
                    │       ▼        │  │  Comments           │
                    │  ┌──────────┐  │  └─────────┬───────────┘
                    │  │  Silver  │  │            │
                    │  └────┬─────┘  │            ▼
                    │       ▼        │  ┌─────────────────┐
                    │  ┌──────────┐  │  │    Chunking     │
                    │  │   Gold   │  │  │ + normalization │
                    │  └────┬─────┘  │  └────────┬────────┘
                    │       ▼        │           │
                    │  ┌──────────┐  │           ▼
                    │  │  Trend   │  │  ┌─────────────────┐
                    │  │  marts   │  │  │   Embeddings    │
                    │  └──────────┘  │  └────────┬────────┘
                    │                │           │
                    │  built by dbt  │           ▼
                    └────────┬───────┘  ┌─────────────────┐
                             │          │     Qdrant      │
                             │          │   Vector DB     │
                             │          │                 │
                             │          │ vectors +       │
                             │          │ metadata        │
                             │          └────────┬────────┘
                             │                   │
                             ▼                   ▼
                    ┌─────────────────────────────────────────┐
                    │                 FastAPI                 │
                    │                                         │
                    │  /trends    /videos    /creators        │
                    │  /search    /chat                       │
                    └────────────────────┬────────────────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          │                             │
                          ▼                             ▼
                   ┌──────────────┐              ┌──────────────┐
                   │  Dashboard   │              │  Chat / RAG  │
                   │              │              │              │
                   │ Trending     │              │ "Why is      │
                   │ topics       │              │ Claude Code  │
                   │ creators     │              │ trending?"   │
                   │ videos       │              │              │
                   └──────────────┘              └──────┬───────┘
                                                        │
                                                        ▼
                                                 ┌──────────────┐
                                                 │     LLM      │
                                                 │              │
                                                 │ Synthesize   │
                                                 │ retrieved    │
                                                 │ evidence     │
                                                 └──────────────┘
```

After the raw data lake, the flow splits into two paths:

- **Analytics path**: a Dagster op reads the raw JSON, conforms it with Polars,
  and writes a content-addressed Parquet mirror back to RustFS. A load step
  brings the mirror into DuckDB, where dbt builds Bronze → Silver → Gold
  (dimensions + `video_daily_metrics`) and the trend marts.
- **Content path**: transcripts, descriptions, and comments are chunked,
  normalized, embedded, and stored in Qdrant with full provenance metadata.

Both paths converge on FastAPI, which serves the trend dashboard and the chat
interface. The LLM synthesizes retrieved evidence into source-grounded answers.
Trend scores combine velocity, recency, engagement, and cross-channel spread —
never raw lifetime views alone.

## Technology stack

| Area | Technology |
|------|------------|
| Language | Python 3.13 (uv workspaces) |
| Containers | Docker + Docker Compose |
| Infrastructure | Terraform + Docker Compose (RustFS object storage) |
| Object storage | RustFS (S3-compatible) |
| Data lake | RustFS (S3-compatible): raw JSON + Parquet mirror |
| Data warehouse | DuckDB (embedded), Bronze/Silver/Gold + marts via dbt |
| Transformations | dbt (dbt-duckdb) |
| Batch processing | Polars |
| Orchestration | Dagster |
| Vector database | Qdrant |
| Embeddings | sentence-transformers |
| LLM | DeepSeek V4 Flash (via opencode) |
| API | FastAPI |
| Frontend | React (`apps/devtube_web`) |
| Testing | pytest + dbt tests |
| CI | GitHub Actions |
