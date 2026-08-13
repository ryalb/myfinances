# MyFinances AGENTS.md

## Toolchain
- **Task runner**: `mise.toml` is the source of truth. Prefer `mise run <task>` over ad-hoc commands.
- **Backend**: `uv` (Python 3.12, Django 5.1, DRF, Graphene, Celery 5.4, Redis, PostgreSQL 16).
- **Frontend**: `bun` (Nuxt 3.13, PrimeVue 4, Tailwind, Pinia, Apollo, Iconify).
- **Lint/format/typecheck**: `ruff` + `ty` (backend), ESLint flat config (frontend).
- **Pre-commit**: `prek.toml` runs ruff, ty, and eslint. Install once with `uv tool run prek install`.

### Python execution — `uv` only, no exceptions
- This repo has **no Poetry, no Pipenv, no bare venv**: there is a `uv.lock` in `backend/` and nothing else. `poetry.lock` / `requirements.txt` do not exist and must not be introduced.
- **ALWAYS** run backend Python through `uv run ...` (e.g. `cd backend && uv run python manage.py test`, `uv run pytest`, `uv run ruff check .`). **NEVER** invoke `python`, `python3`, `pip`, `pip3`, `poetry`, or `pipenv` directly — those bypass the locked, project-scoped environment in `backend/.venv`.
- Adding a dependency: `uv add <pkg>` (or `uv add --group dev <pkg>`) from `backend/`, not `pip install`.
- Installing tools that aren't project deps (e.g. `prek`): `uv tool run <tool>` / `uv tool install <tool>`.
- If a command seems to need a bare `python`/`pip`/`poetry` invocation, that's a sign to find the `uv run` or `uv tool` equivalent instead — not to fall back to the bare command.

## Setup
```bash
mise install
mise run setup
cp backend/.env.example backend/.env
```

## Commands
- **Full dev stack**: `mise run dev` (backend + frontend concurrently).
- **Backend only**: `mise run backend-dev` (auto-runs migrations first).
- **Celery worker**: `mise run backend-worker`.
- **Backend tests**: `cd backend && uv run python manage.py test`.
- **Backend quality**: `mise run backend-lint`, `mise run backend-typecheck`, `mise run backend-test`.
- **Frontend dev**: `mise run frontend-dev`.
- **Frontend build**: `mise run frontend-build`.
- **Frontend lint**: `mise run frontend-lint`, `mise run frontend-lint-fix`.
- **All checks**: `mise run check` (backend lint + typecheck + test + frontend lint).
- **Docker**: `docker compose up --build` from repo root. Services: frontend `:3000`, backend `:8000`, postgres `:5432`, redis `:6379`.

## Architecture
- **Monorepo**: `backend/` (Django) and `frontend/` (Nuxt). No shared packages.
- **Backend entrypoint**: `backend/manage.py` → `config.settings`. Single Django app `apps.finance`.
- **Domain**: `apps/finance/models.py` (institutions, connections, accounts, transactions, investments, goals, snapshots).
- **REST**: DRF viewsets in `apps/finance/views.py` under `/api/v1/`.
- **GraphQL**: `apps/finance/graphql.py` composed in `config/schema.py` at `/graphql/`.
- **Async**: Connection creation enqueues `SyncJob`; Celery task `sync_connection_data` in `apps/finance/tasks.py` pulls data via `PluggyClient` in `apps/finance/services.py`.
- **Frontend entrypoint**: `frontend/app.vue` → `frontend/layouts/default.vue`.
- **Frontend state**: Pinia stores; auth via `access_token` cookie.
- **Frontend data**: Server-side `useFetch` in pages; dashboard metrics aggregated client-side in `composables/useDashboardMetrics.ts`.

## Conventions
- **Icons**: use `@iconify/vue` (e.g. `mdi:chart-line`). Do not add custom SVG assets.
- **Auth**: Backend defaults to `IsAuthenticated`. Frontend middleware redirects unauthenticated users to `/login`.
- **User data**: DRF querysets filter by `user=self.request.user`; do not rely on global mutable querysets for user-owned resources.
- **Enums**: Status fields use Django `TextChoices`; preserve enum classes when adding states.
- **Env**: Backend reads `.env` via `python-dotenv`. Frontend reads `NUXT_PUBLIC_*` env vars.

## Frontend Layout Quirks
- `frontend/layouts/default.vue` uses a custom sidebar provider pattern.
- The layout component **must** call `useSidebarProvider()` before `useSidebar()`.
- Auth pages (`pages/login.vue`, `pages/register.vue`) set `definePageMeta({ layout: false })` to skip the sidebar.

## CI
- GitHub Actions runs on PR/push to `main`.
- Steps: `mise install` → `mise run setup` → `mise run check` → `mise run frontend-build` → `uv tool run prek run --all-files`.
- CI brings up Postgres and Redis as services; no Docker Compose for the app containers in CI.

## Docker Compose
- `docker-compose.yml` only defines `db`, `redis`, and `worker`. Backend/frontend containers are commented out; local dev runs them directly via `mise`.
