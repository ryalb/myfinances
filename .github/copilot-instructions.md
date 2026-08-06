# Copilot Instructions for MyFinances

## Build, test, and lint commands

### Use mise first (repo root)

```bash
mise install
mise run setup
```

Primary task runner for this repo is `mise.toml`. Prefer `mise run <task>` over ad-hoc commands.

### Backend (Django + uv)

Run from repository root:

```bash
cp backend/.env.example backend/.env
mise run backend-migrate
mise run backend-dev
```

Celery worker:

```bash
mise run backend-worker
```

Backend quality commands:

```bash
mise run backend-lint
mise run backend-typecheck
mise run backend-test
```

Single Django test:

```bash
cd backend && uv run python manage.py test apps.finance.tests.test_views.ConnectionViewSetTests.test_create_connection
```

### Frontend (Nuxt 3 + Bun + ESLint)

Run dev/build:

```bash
mise run frontend-dev
mise run frontend-build
```

Lint frontend:

```bash
mise run frontend-lint
mise run frontend-lint-fix
```

### Docker Compose (full stack)

Run from repository root:

```bash
docker compose up --build
```

Exposed services:

- Frontend: `http://localhost:3000`
- Backend REST: `http://localhost:8000/api/v1/`
- GraphQL: `http://localhost:8000/graphql/`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

### Commit hooks (prek)

```bash
uv tool run prek install
uv tool run prek run --all-files
```

## High-level architecture

This repository is a two-app monorepo:

1. `backend/`: Django app with DRF + GraphQL + Celery
2. `frontend/`: Nuxt 3 app consuming REST and GraphQL endpoints

Backend architecture centers around `apps.finance`:

- **Domain models** in `apps/finance/models.py` represent institutions, user connections, accounts/cards/transactions, investments, goals, and snapshots.
- **REST API** is built with DRF viewsets in `apps/finance/views.py` and routed under `/api/v1/` in `config/urls.py`.
- **GraphQL API** is defined in `apps/finance/graphql.py` and composed in `config/schema.py`, exposed at `/graphql/`.
- **Async sync flow**:
  - creating a `Connection` via REST triggers `perform_create`
  - a `SyncJob` row is created
  - Celery task `sync_connection_data` is enqueued (`apps/finance/tasks.py`)
  - task pulls account data from Pluggy (`apps/finance/services.py`) and updates local models

Frontend architecture:

- Runtime endpoints are configured in `frontend/nuxt.config.ts` via:
  - `NUXT_PUBLIC_API_BASE_URL` (defaults to `/api/v1` backend URL)
  - `NUXT_PUBLIC_GRAPHQL_ENDPOINT`
- Pages currently use server-side `useFetch` calls and an auth cookie (`access_token`) to call backend endpoints.
- Dashboard metrics are aggregated client-side in `composables/useDashboardMetrics.ts` from `/accounts/` and `/transactions/`.
- Icons should use Iconify (`@iconify/vue`) instead of introducing custom icon assets.

## Key conventions in this codebase

- **Tooling defaults**:
  - backend dependencies and tools are managed via `uv` (`backend/pyproject.toml`)
  - backend lint/typecheck uses `ruff` + `ty`
  - Git hooks use `prek.toml`
  - frontend lint uses ESLint flat config (`frontend/eslint.config.mjs`)
  - environment/tool versions and standard tasks are centralized in `mise.toml`
- **User-scoped data access is enforced at queryset level** in DRF viewsets (`filter(...user=self.request.user)` patterns) rather than broad global querysets for mutable/user-owned resources.
- **Connection sync is job-driven**: avoid direct data fetch on request thread; queue work through `SyncJob` + Celery.
- **Provider integration boundary** lives in `apps/finance/services.py` (`PluggyClient`), while task orchestration/persistence lives in `tasks.py`.
- **Status fields use Django `TextChoices` enums** (`ConnectionStatus`, `SyncJobStatus`, etc.); preserve these enum classes when adding new states.
- **API defaults are authenticated** (`REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = IsAuthenticated`), with explicit `AllowAny` only for health check.
- **Monorepo local dev defaults to Docker-friendly env vars** (`POSTGRES_HOST`, `REDIS_URL`, and Nuxt public endpoints); keep new services configurable through env vars and `.env.example`.
