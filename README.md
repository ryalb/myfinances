# MyFinances

Monorepo inicial para consolidação e análise de patrimônio pessoal com:

- **Backend:** Django + Django REST Framework + GraphQL
- **Frontend:** Nuxt 3 + PrimeVue + Tailwind
- **Infra:** PostgreSQL + Redis + Celery + Docker Compose

## Estrutura

```text
myfinances/
  backend/
  frontend/
  docker-compose.yml
```

## Subir com Docker

```bash
docker compose up --build
```

Serviços:

- Backend API: `http://localhost:8000`
- GraphQL: `http://localhost:8000/graphql/`
- Frontend: `http://localhost:3000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`

## Ambiente com mise

Na raiz do projeto:

```bash
mise install
mise run setup
```

## Backend (local)

```bash
cp backend/.env.example backend/.env
mise run backend-migrate
mise run backend-dev
```

Celery worker:

```bash
mise run backend-worker
```

## Frontend (local)

```bash
mise run frontend-dev
```

## Endpoints principais do backend

- `POST /api/v1/auth/register/` cria usuário
- `POST /api/v1/auth/token/` autentica e retorna JWT
- `POST /api/v1/connections/{id}/sync/` dispara sincronização manual
- `GET /api/v1/summary/` consolidação de patrimônio
- `GET /api/v1/cash-flow/?year=YYYY&month=MM` fluxo de caixa mensal
- `POST /api/v1/net-worth/snapshot/` recalcula snapshot de patrimônio

## Qualidade de código

```bash
mise run backend-lint
mise run backend-typecheck
mise run backend-test
mise run frontend-lint
```

Hooks de commit:

```bash
uv tool run prek install
uv tool run prek run --all-files
```
