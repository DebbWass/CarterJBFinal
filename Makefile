# ─── Crater capstone project ────────────────────────────────────────────────
#
# Run from the project root. The scaffold ships only the upstream:
#   * data-init          — one-shot sidecar that downloads a window of
#                          gzipped hourly GH Archive JSONL files into a named
#                          docker volume. ~20-40 min on first run for the
#                          full 6-sim-day window (~14 GB). Idempotent — exits
#                          in <2s after that.
#   * gh-archive-vendor  — FastAPI service that serves
#                          GET /{YYYY-MM-DD-H}.json.gz gated by a simulated
#                          clock advancing at REPLAY_SECONDS_PER_HOUR pace.
#
# Everything else (probing, ingest, storage, normalisation, the analyst SQL
# surface) is yours to design. Add services to compose.yml as you need them.
# ────────────────────────────────────────────────────────────────────────────

.PHONY: run stop reset logs vendor-chaos vendor-calm help \
        pipeline-logs pipeline-status db-shell redis-shell migrate \
        test test-unit test-integration test-queries \
        query-1 query-2 query-3 query-4 query-5

help:
	@echo ""
	@echo "  ── Lifecycle ───────────────────────────────────────────────────────"
	@echo "  make run              Build and start all services (vendor + pipeline)"
	@echo "  make stop             Stop containers (keeps volumes)"
	@echo "  make reset            Stop + wipe all volumes (re-downloads window)"
	@echo ""
	@echo "  ── Observability ───────────────────────────────────────────────────"
	@echo "  make logs             Tail gh-archive-vendor logs"
	@echo "  make pipeline-logs    Tail pipeline logs"
	@echo "  make pipeline-status  Show pipeline metrics (curl /status)"
	@echo ""
	@echo "  ── Database / cache ─────────────────────────────────────────────────"
	@echo "  make db-shell         psql into the crater database"
	@echo "  make redis-shell      redis-cli into the watermark store"
	@echo ""
	@echo "  ── Analyst queries ──────────────────────────────────────────────────"
	@echo "  make query-1          Q1: top languages per actor"
	@echo "  make query-2          Q2: commit authors vs pushers"
	@echo "  make query-3          Q3: top collaborator pairs"
	@echo "  make query-4          Q4: star → fork → PR funnel"
	@echo "  make query-5          Q5: collaboration network (prompts for actor)"
	@echo ""
	@echo "  ── Testing ──────────────────────────────────────────────────────────"
	@echo "  make test             All tests"
	@echo "  make test-unit        Unit tests only"
	@echo "  make test-integration Integration tests"
	@echo "  make test-queries     Query contract tests"
	@echo ""
	@echo "  ── Chaos ────────────────────────────────────────────────────────────"
	@echo "  make vendor-chaos     Enable slow/late/truncated/drift/outage"
	@echo "  make vendor-calm      Disable all chaos modes"
	@echo ""
	@echo "  Vendor API:       http://localhost:18400/docs"
	@echo "  Pipeline API:     http://localhost:18401/healthz"
	@echo ""

run:
	docker compose up -d --build
	@echo ""
	@echo "=============================================================="
	@echo " Crater is starting."
	@echo "   First run downloads the configured GH Archive window."
	@echo "   Full 6-sim-day default = ~14 GB (~20-40 min). Watch progress:"
	@echo "     docker compose logs -f data-init"
	@echo "   Once gh-archive-vendor is healthy:"
	@echo "     curl http://localhost:18400/healthz"
	@echo "   Pipeline status:"
	@echo "     curl http://localhost:18401/status | python3 -m json.tool"
	@echo "=============================================================="

stop:
	docker compose down --remove-orphans

reset:
	docker compose down -v --remove-orphans

logs:
	docker compose logs -f gh-archive-vendor

pipeline-logs:
	docker compose logs -f pipeline

pipeline-status:
	@curl -s http://localhost:18401/status | python3 -m json.tool

db-shell:
	docker compose exec postgres psql -U crater -d crater

redis-shell:
	docker compose exec redis redis-cli

vendor-chaos:
	VENDOR_SLOW_FILE_RATE=0.10 \
	VENDOR_LATE_FILE_RATE=0.15 \
	VENDOR_LATE_FILE_DELAY_SECONDS=20 \
	VENDOR_TRUNCATED_FILE_RATE=0.10 \
	VENDOR_SCHEMA_DRIFT=on \
	VENDOR_OUTAGE_SCHEDULE=03:00-03:02 \
	docker compose up -d --no-deps --force-recreate gh-archive-vendor
	@echo "[chaos] gh-archive-vendor restarted with slow/late/truncated/drift/outage on."

vendor-calm:
	VENDOR_SLOW_FILE_RATE=0 \
	VENDOR_LATE_FILE_RATE=0 \
	VENDOR_TRUNCATED_FILE_RATE=0 \
	VENDOR_SCHEMA_DRIFT=off \
	VENDOR_OUTAGE_SCHEDULE= \
	docker compose up -d --no-deps --force-recreate gh-archive-vendor
	@echo "[calm] gh-archive-vendor restarted with chaos disabled."

# ─── Analyst queries (run against live database) ────────────────────────────

query-1:
	docker compose exec -T postgres psql -U crater -d crater \
	    -f /dev/stdin < src/crater/queries/q1_languages.sql

query-2:
	docker compose exec -T postgres psql -U crater -d crater \
	    -f /dev/stdin < src/crater/queries/q2_commit_vs_pusher.sql

query-3:
	docker compose exec -T postgres psql -U crater -d crater \
	    -f /dev/stdin < src/crater/queries/q3_collaborators.sql

query-4:
	docker compose exec -T postgres psql -U crater -d crater \
	    -f /dev/stdin < src/crater/queries/q4_funnel.sql

query-5:
	@read -p "Seed actor login: " ACTOR; \
	docker compose exec -T postgres psql -U crater -d crater \
	    -v seed_actor="'$$ACTOR'" \
	    -f /dev/stdin < src/crater/queries/q5_network.sql

# ─── Testing ─────────────────────────────────────────────────────────────────

test:
	docker compose run --rm --build --entrypoint python pipeline -m pytest tests/ -v --tb=short

test-unit:
	docker compose run --rm --build --entrypoint python pipeline -m pytest tests/unit/ -v --tb=short

test-integration:
	docker compose run --rm --build --entrypoint python pipeline -m pytest tests/integration/ -v --tb=short

test-queries:
	docker compose run --rm --build --entrypoint python pipeline -m pytest tests/queries/ -v --tb=short
