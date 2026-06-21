# Crater — Python Project Structure

## Purpose

This document describes the complete package hierarchy, every module and class, and the design decisions behind the Crater GitHub Archive talent-intelligence pipeline.

---

## Top-Level Layout

```
carter/
├── src/crater/          ← The Python package (everything we wrote)
├── tests/               ← Unit, integration, and query tests
├── vendor/              ← Scaffold-provided vendor mock (do not modify)
├── data/                ← Local scratch (gitignored)
├── Dockerfile           ← Pipeline service image
├── compose.yml          ← All Docker Compose services
├── Makefile             ← Developer workflow commands
├── pyproject.toml       ← Python dependencies and project metadata
├── .env / .env.example  ← Runtime configuration
└── Python_Project_Structure.md  ← This file
```

---

## src/crater/ — Package Hierarchy

```
src/crater/
├── __init__.py
├── __main__.py                         Entry point: python -m crater
│
├── config/
│   └── settings.py                     PipelineSettings
│
├── domain/
│   ├── models.py                       RawEvent, NormalizedEvent, PushCommitRecord,
│   │                                   ContributionRecord, NormalizationResult
│   ├── watermark.py                    HighWaterMark
│   └── events/
│       ├── base.py                     AbstractEventNormalizer, EventNormalizerRegistry
│       ├── _helpers.py                 base_event(), is_bot_login()
│       ├── push.py                     PushEventNormalizer
│       ├── pull_request.py             PullRequestEventNormalizer
│       ├── watch.py                    WatchEventNormalizer
│       ├── fork.py                     ForkEventNormalizer
│       ├── issues.py                   IssuesEventNormalizer
│       ├── issue_comment.py            IssueCommentEventNormalizer
│       ├── create.py                   CreateEventNormalizer
│       ├── delete.py                   DeleteEventNormalizer
│       ├── release.py                  ReleaseEventNormalizer
│       └── unknown.py                  UnknownEventNormalizer
│
├── infrastructure/
│   ├── logging/
│   │   └── setup.py                    configure_logging()
│   ├── vendor/
│   │   ├── client.py                   VendorHttpClient
│   │   └── file_fetcher.py             FileFetcher
│   ├── postgres/
│   │   ├── connection.py               create_pool()
│   │   ├── schema.py                   DDL constants (ALL_DDL list)
│   │   ├── migrations.py               SchemaMigrator
│   │   └── repositories/
│   │       ├── base.py                 AbstractRepository[T]
│   │       ├── events.py               EventRepository
│   │       ├── push_commits.py         PushCommitRepository
│   │       └── contributions.py        ContributionRepository
│   └── redis/
│       ├── connection.py               create_redis_client()
│       └── watermark_store.py          AbstractWatermarkStore, RedisWatermarkStore,
│                                       InMemoryWatermarkStore
│
├── pipeline/
│   ├── errors.py                       CraterError, TruncatedResponseError, VendorOutageError,
│   │                                   GzipDecompressionError, WatermarkError, RepositoryError
│   ├── poller.py                       HourPoller
│   ├── ingestor.py                     FileIngestor
│   ├── normalizer.py                   NormalizationService
│   ├── writer.py                       PipelineWriter, FlushResult
│   └── coordinator.py                  PipelineCoordinator
│
├── monitoring/
│   ├── metrics.py                      MetricsCollector, InMemoryMetricsCollector
│   └── health.py                       HealthProbe, HealthReport, ComponentHealth
│
├── api/
│   ├── app.py                          create_app()
│   └── routes/
│       ├── health.py                   GET /healthz
│       └── status.py                   GET /status
│
└── queries/
    ├── q1_languages.sql
    ├── q2_commit_vs_pusher.sql
    ├── q3_collaborators.sql
    ├── q4_funnel.sql
    └── q5_network.sql
```

---

## Module and Class Reference

### config/settings.py

**`PipelineSettings(BaseSettings)`**

Single responsibility: typed, validated configuration from environment variables and `.env`. Every downstream class receives settings via constructor injection; nothing reads `os.environ` directly.

Key fields:
- `vendor_base_url` — URL of the gh-archive-vendor service
- `pg_dsn` — PostgreSQL connection string (psycopg3 format)
- `redis_url` — Redis connection URL
- `batch_size` — rows buffered before a flush to Postgres
- `poll_interval_seconds` — sleep between 404-probe retries
- `replay_window_start/end` — date range boundaries for the pipeline

---

### domain/models.py

**`RawEvent(BaseModel, extra="allow")`**

Parses one JSONL line from a vendor file. `extra="allow"` silently absorbs schema-drift fields (extra `payload.crater_drift_marker`, etc.) without crashing.

**`NormalizedEvent(dataclass)`**

Flat, storage-ready representation of one event. Fields map 1:1 to `events` table columns. Type-specific fields (pr_author_login, pr_merged, fork_forkee_repo_id) are `None` for event types that don't populate them.

**`PushCommitRecord(dataclass)`**

One row in `push_commits` — a single commit extracted from `PushEvent.payload.commits[]`.

**`ContributionRecord(dataclass)`**

One (actor_login, repo_id, contribution_type) row for the `actor_repo_contributions` table — the backbone of Q3 and Q5.

**`NormalizationResult(dataclass)`**

The complete output of normalizing one RawEvent: the event itself plus any commits and contributions it produces.

---

### domain/watermark.py

**`HighWaterMark(dataclass, frozen=True)`**

Value object: wraps the last successfully ingested hour. Immutable — `advance()` returns a new instance rather than mutating. Key method: `next_filename()` returns the GH Archive filename for the next hour, correctly enforcing the non-zero-padded hour convention (`2024-01-15-3.json.gz`, not `2024-01-15-03.json.gz`).

---

### domain/events/base.py

**`AbstractEventNormalizer(ABC)`**

Strategy contract for per-event-type normalization. Three methods:
- `normalize(raw) -> NormalizedEvent` — required
- `extract_commits(raw) -> list[PushCommitRecord]` — default returns `[]`
- `extract_contributions(raw) -> list[ContributionRecord]` — default returns `[]`

**`EventNormalizerRegistry`**

Strategy dispatcher. Maps event type strings to normalizer instances. `get(event_type)` falls back to `UnknownEventNormalizer` if the type is unrecognized — no event is ever dropped. `build_default()` classmethod wires all 10 known normalizers and the fallback.

---

### domain/events — Concrete Normalizers

| Class | File | Key Logic |
|---|---|---|
| `PushEventNormalizer` | push.py | Extracts commits from `payload.commits[]`, sets `forced` flag, produces `commit_author` ContributionRecord |
| `PullRequestEventNormalizer` | pull_request.py | **PR author = `payload.pull_request.user.login`, NOT `actor`**; extracts merged flag, language, base repo id; produces `pr_author` ContributionRecord |
| `WatchEventNormalizer` | watch.py | Pass-through (star event, no extra fields) |
| `ForkEventNormalizer` | fork.py | Extracts `forkee.id` → `fork_forkee_repo_id` |
| `IssuesEventNormalizer` | issues.py | Pass-through |
| `IssueCommentEventNormalizer` | issue_comment.py | Pass-through |
| `CreateEventNormalizer` | create.py | Pass-through |
| `DeleteEventNormalizer` | delete.py | Pass-through |
| `ReleaseEventNormalizer` | release.py | Pass-through |
| `UnknownEventNormalizer` | unknown.py | Fallback: stores full `raw_payload` as JSONB, never raises |

---

### infrastructure/vendor/client.py

**`VendorHttpClient`**

HTTP transport only. Sends GET requests to the vendor API. Returns `(status_code, bytes | None)`. Raises `TruncatedResponseError` on Content-Length mismatches. Retries transient network errors with exponential backoff up to `max_fetch_retries`. Does NOT implement the 404/503 retry policy — that is FileFetcher's job.

---

### infrastructure/vendor/file_fetcher.py

**`FileFetcher`**

Fetch state machine on top of `VendorHttpClient`. States:
- **PENDING_CLOCK (404)** → sleep `poll_interval_seconds` → retry
- **OUTAGE (503)** → sleep exponential backoff (doubles up to 60s) → retry
- **TRUNCATED** (Content-Length mismatch or invalid gzip) → immediate retry (up to 5 attempts)
- **READY (200 + valid gzip)** → return bytes

Guarantees: `fetch_with_retry()` never returns truncated or invalid gzip bytes. Callers can pass the result directly to `FileIngestor.parse()`.

---

### infrastructure/postgres/schema.py

Constants holding all DDL: `EVENTS_TABLE`, `PUSH_COMMITS_TABLE`, `CONTRIBUTIONS_TABLE`, `FUNNEL_EVENTS_TABLE`, `PIPELINE_FILES_TABLE`, `INDEXES`. All use `IF NOT EXISTS`. `ALL_DDL` is the ordered list for `SchemaMigrator` to execute.

---

### infrastructure/postgres/migrations.py

**`SchemaMigrator`**

Runs all DDL idempotently at startup via `run(pool)`. Safe to call on every restart.

---

### infrastructure/postgres/repositories/base.py

**`AbstractRepository[T](Generic[T], ABC)`**

Generic contract: `bulk_insert(records) -> int`, `exists(key) -> bool`.

---

### infrastructure/postgres/repositories/events.py

**`EventRepository(AbstractRepository[NormalizedEvent])`**

Bulk-inserts `NormalizedEvent` rows using psycopg3 `COPY FROM STDIN` for maximum throughput (targets 150k+ rows/sec). Falls back to batched `INSERT ON CONFLICT DO NOTHING` if COPY is unavailable. Primary key `event_id` deduplicates on restart.

---

### infrastructure/postgres/repositories/push_commits.py

**`PushCommitRepository(AbstractRepository[PushCommitRecord])`**

Batched `executemany` INSERT for `push_commits`. Uses `ON CONFLICT DO NOTHING`.

---

### infrastructure/postgres/repositories/contributions.py

**`ContributionRepository(AbstractRepository[ContributionRecord])`**

Two responsibilities (kept together because they share the same table dependency pattern):
1. `bulk_insert()` → `actor_repo_contributions` via `ON CONFLICT DO NOTHING` on PK `(actor_login, repo_id, contribution_type)`
2. `bulk_insert_funnel_events()` → `funnel_events` (filters to WatchEvent, ForkEvent, PullRequestEvent) for Q4

---

### infrastructure/redis/watermark_store.py

**`AbstractWatermarkStore(ABC)`** — `get()`, `set()`, `set_if_greater()`

**`RedisWatermarkStore`** — Redis `HSET crater:hwm` backend. `set_if_greater()` uses a Lua script for atomic compare-and-set, preventing races if multiple processes start simultaneously.

**`InMemoryWatermarkStore`** — In-process test double. Not safe for concurrent use.

---

### pipeline/errors.py

Custom exception hierarchy rooted at `CraterError`:
- `TruncatedResponseError` — Content-Length mismatch from vendor
- `VendorOutageError` — 503 received
- `GzipDecompressionError` — gzip validation failed after max retries
- `WatermarkError` — Redis read/write failure
- `RepositoryError` — Database write failure

---

### pipeline/poller.py

**`HourPoller`**

Computes the next hourly filename to fetch based on the current watermark and the vendor's `simulated_now`. Returns `None` if the sim clock hasn't reached the next hour's close yet. Contains no I/O other than reading the watermark and calling `get_simulated_now()`.

---

### pipeline/ingestor.py

**`FileIngestor`**

Decompresses gzip bytes and yields `RawEvent` objects line by line. Design invariants:
- Partial gzip (truncated files that slip past FileFetcher) → decompresses available bytes, discards the rest
- Malformed JSON lines → log + skip (never drop the whole file)
- Pydantic validation failures → log + skip
- Schema drift (extra payload fields) → absorbed by `RawEvent(extra="allow")`

---

### pipeline/normalizer.py

**`NormalizationService`**

Routes `RawEvent` objects through the `EventNormalizerRegistry` (Strategy pattern). If normalization fails, falls back to `UnknownEventNormalizer` so no event is ever lost. Tracks `unknown_event_types` and `normalization_errors` metrics.

---

### pipeline/writer.py

**`PipelineWriter`**

Buffers `NormalizationResult` objects in memory. Flushes when `batch_size` is reached (or on explicit `flush()` call). One flush = writes to `events`, `push_commits`, `actor_repo_contributions`, and `funnel_events` in sequence. Returns `FlushResult(events_written, commits_written, contributions_written, funnel_events_written)`.

**`FlushResult(dataclass)`** — Row counts from a single flush.

---

### pipeline/coordinator.py

**`PipelineCoordinator`**

Top-level async orchestration loop. The only class that knows the full pipeline shape — wires poller → fetcher → ingestor → normalizer → writer → watermark advance. Contains no business logic; each step is fully delegated. Handles graceful shutdown on SIGTERM/SIGINT (flushes pending writes before exiting).

Main loop:
```
await _wait_for_vendor()      # polls /healthz until ready=true
while not shutdown_event:
    filename = await poller.next_filename()  # None → sleep(poll_interval)
    gz_bytes = await fetcher.fetch_with_retry(filename)
    for raw in ingestor.parse(gz_bytes):
        result = normalizer.process(raw)
        await writer.add(result)             # auto-flushes when batch full
    await writer.flush()                     # final flush for this file
    await watermark_store.set_if_greater(hour)  # advance HWM
```

---

### monitoring/metrics.py

**`MetricsCollector(ABC)`** — `increment(name, value=1)`, `gauge(name, value)`, `get_all()`

**`InMemoryMetricsCollector`** — Thread-safe dict-backed implementation. Exposed via `/status`. Drop-in replaceable with a Prometheus exporter by implementing the ABC.

---

### monitoring/health.py

**`HealthProbe`** — Checks vendor (`/healthz`), Postgres (`SELECT 1`), and Redis (`PING`). Returns `HealthReport` which serialises to a dict for the `/healthz` API response.

**`HealthReport(dataclass)`** — `healthy: bool`, `components: list[ComponentHealth]`

**`ComponentHealth(dataclass)`** — `name`, `healthy`, `detail`

---

### api/app.py

**`create_app(coordinator, metrics, health_probe) -> FastAPI`**

FastAPI application factory. Lifespan context starts `coordinator.run()` as an asyncio background task. The pipeline and the HTTP API share one event loop and one process — no extra service needed.

Routes:
- `GET /healthz` — full health report (200 if all components healthy, 503 otherwise)
- `GET /status` — pipeline metrics snapshot

---

## Design Patterns

| Pattern | Where Used | Why |
|---|---|---|
| **Strategy** | `EventNormalizerRegistry` + 10 normalizers | Each event type has a unique payload shape. Dispatch without `if/elif` chains; extend by registering a new class. |
| **Repository** | `AbstractRepository[T]` + 3 concrete repos | Isolates storage technology from pipeline logic. In-memory fakes make unit tests trivial. |
| **High-Water Mark** | `AbstractWatermarkStore` + Redis impl | Idempotent restart: advance only after successful DB commit. At-least-once fetch + idempotent inserts = effective exactly-once. |
| **Factory Method** | `EventNormalizerRegistry.build_default()`, `create_app()` | Centralises object graph wiring. Tests substitute fakes at any layer. |
| **Template Method** | `AbstractEventNormalizer` no-op defaults | Only Push and PR override `extract_commits`/`extract_contributions`; others inherit safe no-ops. |
| **Dependency Injection** | Constructor injection throughout | No class reads `os.environ` or imports infrastructure it uses. Test doubles pass in through `__init__`. |
| **Backoff State Machine** | `FileFetcher.fetch_with_retry()` | Explicit named states for 404/503/truncated/ready chaos modes. No implicit retry logic scattered across modules. |

---

## Database Schema

### events
Core event store. Primary key on `event_id` provides deduplication on restart. Type-specific columns are `NULL` for other event types. `raw_payload JSONB` stores the full payload for unknown types and future queries.

### push_commits
One row per commit in a PushEvent. Separate from `events` to support per-commit authorship queries (Q2) without exploding the main events table. `forced BOOLEAN` lets Q2 exclude force-push commits from authorship attribution.

### actor_repo_contributions
Pre-materialized (actor, repo, contribution_type) pairs. PK `(actor_login, repo_id, contribution_type)` with `ON CONFLICT DO NOTHING` ensures idempotent ingestion. This table powers Q3 (co-contributor pairs via self-join) and Q5 (distance-2 network via two-CTE join). Pre-materialisation is necessary: a live join over 34M events for Q5 at demo time would take 30+ seconds; a join over this ~2–5M-row table returns in under 5 seconds.

### funnel_events
Subset of events for WatchEvent, ForkEvent, and PullRequestEvent — the three types needed for Q4's star→fork→PR funnel. Kept separate from `events` to avoid scanning the full table for Q4's time-window joins. PK includes `occurred_at` to allow multiple events of the same type per (actor, repo) pair.

### pipeline_files
Records each ingested file (filename, sim_hour, event_count, status). Supplements the Redis watermark with a durable per-file audit trail in Postgres.

---

## Storage Decision Rationale

**PostgreSQL 16 + Redis 7. No Kafka. No Spark.**

- **PostgreSQL** handles all 5 analyst queries natively. Q1–Q4 are relational aggregations. Q5 (distance-2 network) uses a 2-CTE join on the pre-materialised `actor_repo_contributions` table.
- **Redis** stores the high-water mark. The probe loop runs every 0.5s; a Postgres write on every 404 probe would be unnecessary load. Redis `HGET` is sub-millisecond; the watermark key survives `docker compose restart` via `appendonly yes`.
- **No Kafka**: the vendor is pull-based, serving one file per 2 wall-seconds. There is no fan-out consumer use case. A broker would double infrastructure for zero gain.
- **No Spark**: psycopg3 `COPY FROM STDIN` achieves 150k–250k rows/sec. The requirement is ~113k rows/sec (34M events / 300s). Spark's JVM overhead is unnecessary at this scale.
- **No Neo4j**: Q5 at distance-2 is solved with two CTEs. The adjacency table has ~2–5M rows (estimated), indexed on `actor_login` and `repo_id`. Neo4j would add a second query language and storage technology without enabling queries that are impossible in SQL.

---

## tests/ Structure

```
tests/
├── conftest.py                        Shared fixtures: RawEvent factory, fake watermark,
│                                      fake registry, in-memory metrics
├── unit/
│   ├── domain/
│   │   ├── test_watermark.py          HighWaterMark.advance(), next_filename() non-zero-padding
│   │   └── test_normalizers/
│   │       ├── test_push.py           Commit extraction, forced=True flag
│   │       ├── test_pull_request.py   PR author vs actor, merged detection, language extraction
│   │       ├── test_watch.py
│   │       ├── test_fork.py           forkee_repo_id extraction
│   │       └── test_unknown.py        No crash on novel fields, verbatim storage
│   ├── infrastructure/
│   │   ├── test_watermark_store.py    InMemoryWatermarkStore, set_if_greater semantics
│   │   └── test_file_fetcher.py       404→sleep, 503→backoff, truncation retry, gzip validation
│   └── pipeline/
│       ├── test_ingestor.py           Valid JSONL, malformed line skip, partial gzip
│       ├── test_normalizer_service.py  Unknown type fallback, normalization error recovery
│       ├── test_writer.py             Batch threshold, flush on shutdown, FlushResult counts
│       └── test_poller.py             Hour sequence, non-zero-padded filenames, window end
├── integration/
│   ├── conftest.py                    Real Postgres + Redis (docker-compose or testcontainers)
│   ├── test_schema_migration.py       Idempotent DDL (run twice, no error)
│   ├── test_event_repository.py       COPY insert, event_id conflict deduplication
│   ├── test_contribution_repo.py      ON CONFLICT DO NOTHING, funnel event insertion
│   ├── test_full_file_ingest.py       Single .json.gz fixture → assert row counts in all tables
│   └── test_chaos_recovery.py         Mock vendor: 503×3 then 200; truncated then valid retry
└── queries/
    ├── fixtures/
    │   └── seed_data.sql              Minimal deterministic dataset for all 5 queries
    ├── test_q1_languages.py
    ├── test_q2_commit_vs_pusher.py
    ├── test_q3_collaborators.py
    ├── test_q4_funnel.py
    └── test_q5_network.py
```

---

## Developer Workflow

```bash
make run                  # Start all services (vendor + postgres + redis + pipeline)
make pipeline-logs        # Tail pipeline logs
make db-shell             # psql into crater database
make redis-shell          # redis-cli into watermark store

make query-1              # Run Q1 against live data
make query-2              # Run Q2
make query-3              # Run Q3
make query-4              # Run Q4
make query-5              # Run Q5 (prompts for seed actor login)

make test-unit            # pytest tests/unit/
make test-integration     # pytest tests/integration/ (requires running postgres+redis)
make test-queries         # pytest tests/queries/ (requires seeded data)

make vendor-chaos         # Enable all chaos modes
make vendor-calm          # Disable all chaos modes
make pipeline-status      # curl http://localhost:18401/status | jq
make reset                # Wipe all volumes and restart fresh
```

---

## SOLID Principles Applied

| Principle | How Applied |
|---|---|
| **Single Responsibility** | Every class has one reason to change. `VendorHttpClient` handles HTTP transport only. `FileFetcher` handles the retry state machine only. `PipelineWriter` handles buffering and flushing only. |
| **Open/Closed** | New event types: register a new `AbstractEventNormalizer` subclass with the registry — no existing code changes. |
| **Liskov Substitution** | `InMemoryWatermarkStore` is a drop-in substitute for `RedisWatermarkStore` in all unit tests. |
| **Interface Segregation** | `AbstractRepository` exposes only `bulk_insert` and `exists` — callers don't depend on methods they don't use. |
| **Dependency Inversion** | `PipelineCoordinator` depends on `AbstractWatermarkStore`, `FileFetcher`, etc. — not on concrete Redis/HTTP implementations. Test doubles inject through constructors. |
