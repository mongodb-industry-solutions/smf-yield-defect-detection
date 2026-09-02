# AGENTS.md

Guidance for AI coding agents working in this repository.

This is a FastAPI (Python, async Motor driver) + Next.js 15 demo that detects semiconductor
yield excursions from time-series sensor data and runs a LangGraph agent for root cause
analysis. MongoDB Atlas is the only datastore — time series collections, Change Streams,
Atlas Vector Search, and Atlas Search all live in one cluster (database `smf-yield-defect`).

## Build and test commands

```bash
make install-uv                        # install the uv package manager, if missing
make install                           # install-frontend (npm) + install-backend (uv sync)
cd backend && uv sync                  # backend deps only, from backend/pyproject.toml / uv.lock
cd frontend && npm install --legacy-peer-deps  # frontend deps only

make dev                               # run backend (uvicorn --reload, :8000) and frontend (next dev, :3000) in background
make dev-fg                            # same, in the foreground (Ctrl+C to stop both)
make dev-backend                       # backend only: cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
make dev-frontend                      # frontend only: cd frontend && npm run dev
make stop                              # kill anything on :3000 / :8000
make dev-logs                          # tail .logs/backend.log and .logs/frontend.log (from `make dev`)
```

Supporting scripts:

```bash
make build            # docker compose build + up (full containerized stack)
make up / make down   # start/stop containers without rebuilding
make logs-backend / make logs-frontend  # follow container logs
make lint              # currently just lint-frontend: cd frontend && npm run lint (next lint)
cd backend && uv run python scripts/mdb_document_coll_creator.py     # create wafer_defects/process_context/historical_knowledge collections + indexes
cd backend && uv run python scripts/mdb_timeseries_coll_creator.py   # create the process_sensor_ts time series collection
cd backend && uv run python scripts/mdb_vector_search_idx_creator.py # create the wafer_defects_vector_search Atlas Vector Search index
```

**There is no automated test suite in this repository.** There is no `test`/`pytest` target in
`make`, `backend/pyproject.toml`, or `frontend/package.json`. To verify a change, run
`make lint`, then exercise the affected page or endpoint directly (see Smoke check below). Do
not claim tests pass — there are none.

Smoke check after a change:

1. `make dev-fg`
2. Open `http://localhost:3000` — the dashboard should auto-seed via `/seed/initialize` on
   first load (sensor telemetry, wafer defects, knowledge base, process context).
3. `curl http://localhost:8000/` — should return `{"message": "Server is running"}`.
4. `curl http://localhost:8000/docs` — FastAPI Swagger UI should render, confirming the router
   you touched still imports cleanly.

## Project structure

```
backend/
  main.py              # FastAPI app: startup wiring, service/router dependency injection
  db/mdb.py             # MongoDBConnector — shared PyMongo client wrapper (reads MONGODB_URI)
  config/
    config.json          # collection names, thresholds, agent profile, workflow graph — source of truth for names
    config_loader.py      # ConfigLoader reads config.json
    demo_config.py         # DEMO_EXCURSION_PROBABILITY env override
    thresholds.py           # excursion threshold definitions
  routers/              # FastAPI routers, one per domain (alerts, wafers, sensors, equipment,
                          # kpi, monitoring, websockets, dashboard, search, chat, collections, demo_mode)
  services/             # business logic: alert_manager, excursion_detector, sensor_data_writer,
                          # wafer_generator, embedding_service, embedding_pipeline,
                          # unified_search_service, rca_chat_tools, monitoring_service,
                          # demo_mode_service, websocket_manager, vector_index_manager
  scripts/               # one-off / setup scripts: collection + index creators, data loaders,
                          # cleanup and maintenance utilities
  data_generation/        # synthetic data generators (sensor data, wafer images, process
                          # context, historical knowledge, scenarios) + sample_data/*.json
  bedrock/                 # AWS Bedrock client wrapper for Claude chat completions
frontend/                # Next.js 15 App Router + React 19, LeafyGreen UI, Chart.js, Socket.IO client
assets/                  # architecture diagrams referenced from README.md
environments/            # deployment environment config
makefile                 # all local dev / Docker / lint entry points
docker-compose.yml, Dockerfile.backend, Dockerfile.frontend  # containerized stack
```

Notable files:

- `backend/db/mdb.py` — every MongoDB read/write goes through `MongoDBConnector`, which reads
  `MONGODB_URI`, `MDB_DATABASE_NAME` (via `ConfigLoader`), and `APP_NAME`. Extend this class
  rather than instantiating raw `pymongo.MongoClient` elsewhere.
- `backend/config/config.json` — the single source of truth for collection names
  (`MDB_EMBEDDINGS_COLLECTION`, `MDB_TIMESERIES_COLLECTION`, `MDB_VS_INDEX`, etc.), the demo
  agent profile, and the LangGraph workflow graph definition. `alerts`, `alert_history`,
  `sensor_events`, and `embedding_cache` are the exceptions — those collection names are
  hardcoded in their owning service files (see EDD.md).
- `backend/scripts/mdb_vector_search_idx_creator.py` — creates the `wafer_defects_vector_search`
  Atlas Vector Search index. There is no equivalent script for the
  `historical_knowledge_vector_search` index; it must be created manually (see README and
  EDD.md "Known inconsistencies").
- `backend/services/vector_index_manager.py` — defines a second, apparently unused set of
  vector index definitions with different names and the deprecated `knnVector` mapping syntax.
  Do not treat it as the current index contract; see EDD.md.
- `backend/services/excursion_detector.py` — watches the `sensor_events` collection (not the
  `process_sensor_ts` time series collection) via Change Streams, because time series
  collections have limited change stream support.

## Environment variables and configuration

| Name | Required | Example | Description |
| --- | --- | --- | --- |
| `MONGODB_URI` | Yes | `mongodb+srv://...` | Atlas connection string; read by `backend/db/mdb.py` and every service/script. Flex or dedicated tier needed for Vector Search + Search indexes. |
| `MDB_DATABASE_NAME` | No (default `smf-yield-defect`) | `smf-yield-defect` | Database name, read via `ConfigLoader` in `backend/db/mdb.py`. |
| `DATABASE_NAME` | No (default `smf-yield-defect`) | `smf-yield-defect` | Same database name, referenced separately in `.env.example`; keep in sync with `MDB_DATABASE_NAME`. |
| `APP_NAME` | No (default `devrel-fastapi-smf-yield-defect-detection`) | `devrel-fastapi-smf-yield-defect-detection` | Client `appName` reported to Atlas; set on the `MongoClient`/`AsyncIOMotorClient` in `backend/db/mdb.py` and `backend/main.py`. |
| `AWS_REGION`, `AWS_DEFAULT_REGION` | No (default `us-east-1`) | `us-east-1` | AWS region for Bedrock. |
| `AWS_PROFILE` | Recommended | `default` | AWS SSO/credentials profile with Bedrock access. Alternative to static keys. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | No | — | Static AWS credentials, only if not using `AWS_PROFILE`. |
| `COMPLETION_MODEL_ID` | No | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` | Bedrock cross-region inference profile for chat/RCA. |
| `HAIKU_MODEL_ID` | No | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock inference profile for lighter-weight completions. |
| `VOYAGE_API_KEY` | Yes (for embeddings) | — | Voyage AI key for `voyage-multimodal-3` embeddings used on `wafer_defects` and `historical_knowledge`. |
| `S3_BUCKET_URI` | No | `s3://ist-manufacturing-semiconductor` | Bucket for full-size generated wafer defect images; `ink_map.full_image_url` points here. |
| `DEMO_MODE_ENABLED` | No (default `true`) | `true` | Enables synthetic demo data generation. |
| `AUTO_START_DEMO` | No (default `true`) | `true` | Seeds data and starts demo mode automatically on backend startup (`main.py` `startup_event`). |
| `DEMO_INTERVAL_SECONDS` | No (default `10`, `.env.example` suggests `5`) | `5` | Interval between synthetic demo events. |
| `DEMO_EXCURSION_PROBABILITY` | No (default `0.0`) | `0.1` | Random excursion injection rate in demo mode; read in `backend/config/demo_config.py`. |
| `USE_CENTRALIZED_THRESHOLDS` | No | `true` | Toggles `backend/config/thresholds.py` centralized excursion thresholds. |
| `EMBEDDING_BATCH_SIZE` | No | `10` | Batch size for `services/embedding_service.py`. |
| `EMBEDDING_CACHE_SIZE` | No | `100` | Max entries in the `embedding_cache` collection. |
| `NODE_ENV` | No (default `prod` in `main.py`) | `development` | Gates whether the monitoring loop auto-starts (`prod`/`staging` only, to avoid duplicate alerts across instances). |
| `NEXT_PUBLIC_API_URL` | Yes (frontend) | `http://localhost:8000` | Backend base URL for the Next.js app. |
| `NEXT_PUBLIC_WS_URL` | Yes (frontend) | `ws://localhost:8000` | Backend WebSocket URL. |
| `INTERNAL_API_URL` | No | `http://localhost:8000` | Server-side (SSR) backend URL, used for single-pod deployments. |
| `NEXT_PUBLIC_ATLAS_CHART_METRICS_URL` / `..._PARTICLE_URL` / `..._RFPOWER_URL` / `..._TEMPERATURE_URL` | No | — | Embedded MongoDB Atlas Charts URLs for the dashboard. |

Constraints worth knowing before you debug a failure:

- **Atlas is required, not optional.** `mdb_vector_search_idx_creator.py` calls
  `collection.create_search_index()`, which only exists on Atlas (M10+ per the README).
  Against a local/self-hosted `mongod`, collections and documents insert fine but vector index
  creation fails.
- **`sensor_events` and `process_sensor_ts` are dual-written from the same reading** by
  `services/sensor_data_writer.py`. If you add a new metric field, update both write paths or
  they silently diverge.
- **Only `prod`/`staging` (`NODE_ENV`) auto-start the monitoring and RCA loops.** Other
  instances receive alert broadcasts over WebSocket but do not run detection themselves — this
  prevents duplicate alerts when multiple backend instances share one database.
- **Config values in `backend/config/config.json` take precedence over env vars for names**
  (e.g. collection and index names) — env vars mostly control credentials, tuning knobs, and
  feature flags. See EDD.md for the full list of config-driven collection names.

## MongoDB Skills

Use the official MongoDB agent skills from https://github.com/mongodb/agent-skills
whenever the task is MongoDB-specific and a matching skill exists.

## When To Use EDD.md

Use [EDD.md](./EDD.md) as the source of truth for the MongoDB data model in this repository.

Consult [EDD.md](./EDD.md) before making changes that touch:

- MongoDB collections, document structure, or field names
- FastAPI routes (`backend/routers/`) that read or write database records
- Validation, form fields, API payloads, or UI that depend on persisted data
- Schema documentation, Mermaid diagrams, or entity modeling discussions
