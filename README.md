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

**MVP** — batch ingestion, S3 raw storage, Iceberg lakehouse, Redshift, dbt,
orchestration, trend scoring, transcript/description enrichment, Qdrant vector
search, hybrid retrieval, RAG with citations, and a simulated streaming path.

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
                       devtube_pipeline
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
- `devtube_transformations` — Polars-based cleaning and conformance
- `devtube_embeddings` — chunking and embedding models
- `devtube_pipeline` — batch and (simulated) streaming entrypoints
- `devtube_rag` — hybrid retrieval and LLM answer synthesis
- `devtube_dagster` — orchestration of the batch job
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
                                        │ Batch ingestion
                                        ▼
                             ┌─────────────────────┐
                             │  Python Ingestion   │
                             │       Polars        │
                             └──────────┬──────────┘
                                        │
                                        │ Raw API responses
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │                   S3                    │
                   │              RAW DATA LAKE              │
                   │                                         │
                   │  videos/  channels/  comments/          │
                   │  transcripts/  metrics/                 │
                   └────────────────────┬────────────────────┘
                                        │
                                        ▼
                   ┌─────────────────────────────────────────┐
                   │             APACHE ICEBERG              │
                   │                                         │
                   │  ┌──────────┐  ┌──────────┐  ┌───────┐  │
                   │  │  Bronze  │→ │  Silver  │→ │  Gold │  │
                   │  └──────────┘  └──────────┘  └───────┘  │
                   │                                         │
                   │  Schema evolution / snapshots / ACID    │
                   └────────────────────┬────────────────────┘
                                        │
                             ┌──────────┴──────────┐
                             │                     │
                             ▼                     ▼
                     ┌────────────────┐  ┌────────────────────┐
                     │      dbt       │  │ Content Processing │
                     │ Transformations│  │                    │
                     └───────┬────────┘  │ Transcript         │
                             │           │ Description        │
                             ▼           │ Comments           │
                     ┌────────────────┐  └─────────┬──────────┘
                     │    Redshift    │            │
                     │                │            ▼
                     │ Analytics      │   ┌─────────────────┐
                     │ Trend metrics  │   │    Chunking     │
                     │ Dimensions     │   │ + normalization │
                     │ Facts          │   └────────┬────────┘
                     └───────┬────────┘            │
                             │                     ▼
                             │            ┌─────────────────┐
                             │            │   Embeddings    │
                             │            └────────┬────────┘
                             │                     │
                             │                     ▼
                             │            ┌─────────────────┐
                             │            │     Qdrant      │
                             │            │    Vector DB    │
                             │            │                 │
                             │            │ vectors +       │
                             │            │ metadata        │
                             │            └────────┬────────┘
                             │                     │
                             ▼                     ▼
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

- **Analytics path**: Iceberg Bronze → Silver → Gold, then dbt transformations
  into Redshift, producing the dimensions, facts, and trend metrics.
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
| Infrastructure | Terraform + Floci (local AWS emulation) |
| Object storage | S3 (via Floci) |
| Lakehouse | Apache Iceberg + Parquet |
| Warehouse | Redshift (via Floci) |
| Transformations | dbt |
| Batch processing | Polars |
| Orchestration | Dagster |
| Vector database | Qdrant |
| Embeddings | sentence-transformers |
| LLM | DeepSeek V4 Flash (via opencode) |
| API | FastAPI |
| Frontend | React (`apps/devtube_web`) |
| Testing | pytest + dbt tests |
| CI | GitHub Actions |
