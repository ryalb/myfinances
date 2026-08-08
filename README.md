# MyFinances

Monorepo para consolidação e análise de patrimônio pessoal com:

- **Backend:** Django + Django REST Framework + GraphQL
- **Frontend:** Nuxt 3 + PrimeVue + Tailwind
- **Infra:** PostgreSQL + Redis + Celery + Docker Compose
- **Integração:** Pluggy (via Meu Pluggy, uso pessoal gratuito)

## Estrutura

```text
myfinances/
  backend/
    apps/finance/          # domínio, models, tasks, views, comandos
    config/                # settings, urls, celery, asgi
    PLUGGY_TROUBLESHOOTING.md
    PLUGGY_WEBHOOK_SETUP.md
  frontend/
  tmp/backups/             # dumps do banco (gitignored)
  docker-compose.yml
  mise.toml
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

```bash
mise install
mise run setup
cp backend/.env.example backend/.env   # preencha as credenciais do Pluggy
```

### Rodar o stack completo

```bash
mise run dev
```

Sobe API, Celery worker, frontend e túnel ngrok **em paralelo**. Note o `:::` na
definição da task: uma lista em `run` seria sequencial, e como cada processo é
long-running, o segundo nunca começaria. Pelo mesmo motivo o `ngrok` **não** pode
entrar em `depends` do `backend-dev` — `depends` espera a task terminar, e
`ngrok start --all` nunca termina.

### Tasks individuais

| Task | O que faz |
|---|---|
| `mise run setup` | Sobe os containers e instala dependências (backend + frontend) |
| `mise run dev` | Stack completo em paralelo (API, worker, frontend, ngrok) |
| `mise run backend-dev` | Django via Daphne (ASGI/WebSocket) na porta 8000 |
| `mise run backend-worker` | Celery worker |
| `mise run backend-migrate` | Aplica migrations |
| `mise run frontend-dev` | Nuxt dev server na porta 3000 |
| `mise run ngrok` | Túnel ngrok (necessário para receber webhooks em dev) |
| `mise run kill-port <porta>` | Mata processos numa porta |

### Banco de dados

| Task | O que faz |
|---|---|
| `mise run db-backup` | Dump em `tmp/backups/` (formato custom), reporta tamanho e nº de tabelas |
| `mise run db-backups` | Lista os backups, mais recente primeiro |
| `mise run db-restore <arquivo.dump>` | Restaura um dump. Pede confirmação digitada (`RESTORE`) |
| `mise run db-reset` | **Apaga o banco**, recria e roda migrations do zero. Faz backup antes e pede `RESET` |

O `db-reset` encerra as conexões abertas com `pg_terminate_backend` antes do
`DROP DATABASE` — sem isso o drop falha com o Daphne ou o worker rodando.

### Qualidade de código

```bash
mise run check          # lint + typecheck + testes (backend e frontend)
mise run backend-lint
mise run backend-format
mise run backend-typecheck
mise run backend-test   # pytest
mise run frontend-lint
```

Hooks de commit:

```bash
uv tool run prek install
uv tool run prek run --all-files
```

## Integração Pluggy

O projeto usa o **Meu Pluggy** (uso pessoal gratuito), não o fluxo de widget direto.

**Dois fatos que definem a arquitetura da integração:**

1. **Um item da Pluggy = uma conexão do Meu Pluggy.** A tela de consentimento em
   `meu.pluggy.ai` usa radio button: você autoriza **uma** conexão por vez. Nubank +
   Rico = dois itens, duas entradas "MeuPluggy" no Dashboard. Isso é o estado correto.
2. **A Pluggy não expõe listagem de items.** `GET /items` responde **401**; só
   `GET /items/{id}` funciona. Não existe "descobrir" items pela API — o `itemId`
   vem do Dashboard (**Itens Conectados**) ou do payload do webhook, e cabe à
   aplicação armazená-lo.

### Fluxo de configuração

```bash
# 1. Credenciais no backend/.env
PLUGGY_BASE_URL=https://api.pluggy.ai
PLUGGY_CLIENT_ID="..."
PLUGGY_CLIENT_SECRET="..."

# 2. Webhook (sem isto NÃO há sincronização automática)
PLUGGY_WEBHOOK_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
PLUGGY_WEBHOOK_URL="https://<sua-url>/api/v1/pluggy/webhook/?token=<o-mesmo-secret>"
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<host-do-tunel>   # senão o Django responde 400
```

```bash
# 3. Registrar o webhook na Pluggy
cd backend
uv run python manage.py pluggy_register_webhook --list   # confere
uv run python manage.py pluggy_register_webhook          # registra (event=all)

# 4. Importar os items
uv run python manage.py pluggy_import_item --item <item-id-1> --item <item-id-2>
```

Detalhes e troubleshooting em
[`backend/PLUGGY_WEBHOOK_SETUP.md`](backend/PLUGGY_WEBHOOK_SETUP.md) e
[`backend/PLUGGY_TROUBLESHOOTING.md`](backend/PLUGGY_TROUBLESHOOTING.md).

### Comandos de gestão

Todos em `backend/`, via `uv run python manage.py <comando>`.

| Comando | O que faz |
|---|---|
| `pluggy_import_item` | Importa items por `itemId` e sincroniza. Substitui o antigo `/pluggy/discover/` |
| `pluggy_register_webhook` | Registra/lista/remove o webhook da aplicação |
| `pluggy_refine_institutions` | Re-deriva o nome da instituição a partir das contas sincronizadas |
| `pluggy_test_meu_pluggy` | Diagnóstico: autenticação, aplicações, webhooks, items |
| `fix_duplicated_credit_accounts` | Corrige contas de crédito gravadas como `Account` **e** `Card` |
| `seed_data` | Limpa o banco e insere dados fake para teste local |

**`pluggy_import_item`** — o principal:

```bash
# Importa e sincroniza (sync inline)
uv run python manage.py pluggy_import_item --item <uuid> --item <uuid>

# Escolha explícita do dono (obrigatória quando há mais de um usuário ativo)
uv run python manage.py pluggy_import_item --item <uuid> --user-id 1
uv run python manage.py pluggy_import_item --item <uuid> --email você@exemplo.com

# Apaga os dados Pluggy do usuário antes de reimportar
uv run python manage.py pluggy_import_item --item <uuid> --reset --yes

# Enfileira no Celery em vez de rodar inline
uv run python manage.py pluggy_import_item --item <uuid> --async

# Transfere posse de um item que pertence a outro usuário (só na CLI)
uv run python manage.py pluggy_import_item --item <uuid> --user-id 1 --claim
```

O comando **não escolhe usuário por você**: com mais de um usuário ativo ele aborta
e lista as opções. Vincular as contas ao usuário errado causa `409` ao importar pela
UI. Para saber com qual usuário você está logado no frontend:
`GET /api/v1/auth/me/`.

**`pluggy_refine_institutions`** — items do Meu Pluggy chegam todos como
`connectorId=200` / "MeuPluggy", então o nome do banco real é derivado dos nomes das
contas e cartões (`Nu Pagamentos S.A. …` → Nubank). Rode se uma conexão aparecer
como "MeuPluggy" em vez do banco:

```bash
uv run python manage.py pluggy_refine_institutions --dry-run
uv run python manage.py pluggy_refine_institutions
```

**`pluggy_register_webhook`**:

```bash
uv run python manage.py pluggy_register_webhook --list
uv run python manage.py pluggy_register_webhook --delete <webhook-id>
uv run python manage.py pluggy_register_webhook --event item/updated
```

Registre **um** webhook com `event=all`. Ele valida que a URL contém
`?token=<PLUGGY_WEBHOOK_SECRET>` antes de chamar a API.

## Endpoints principais do backend

### Autenticação

- `POST /api/v1/auth/register/` cria usuário
- `POST /api/v1/auth/token/` autentica e retorna JWT
- `POST /api/v1/auth/token/refresh/` renova o access token
- `GET /api/v1/auth/me/` usuário autenticado

### Pluggy

- `POST /api/v1/pluggy/items/` importa um item por `itemId` (corpo: `{"itemId": "<uuid>"}`)
- `POST /api/v1/pluggy/webhook/?token=<secret>` recebe eventos da Pluggy
- `POST /api/v1/pluggy/regenerate-auth/` revalida a apiKey (apenas staff; **nunca** retorna a chave)
- `POST /api/v1/connections/{id}/sync/` dispara sincronização manual

### Dados

- `GET /api/v1/summary/` consolidação de patrimônio
- `GET /api/v1/cash-flow/?year=YYYY&month=MM` fluxo de caixa mensal
- `POST /api/v1/net-worth/snapshot/` recalcula snapshot de patrimônio
- `POST /api/v1/ai/portfolio-report/` relatório de portfolio via RAG + LLM local
- `GET /health/` health check

## Segurança

Decisões que valem conhecer antes de mexer:

- **A apiKey do Pluggy nunca sai do backend.** Ela dá acesso total aos dados
  financeiros. O endpoint de revalidação não a retorna, e o frontend não a recebe.
- **O webhook exige segredo compartilhado** (`?token=`), responde `403` sem ele e
  `503` se `PLUGGY_WEBHOOK_SECRET` não estiver configurado. Sem isso, qualquer um
  poderia apagar transações via `transactions/deleted`.
- **O `clientUserId` é derivado do usuário autenticado**, nunca aceito do request.
- **Conexões nunca trocam de dono pela API.** Só a CLI transfere posse, com `--claim`.
- **Verificação TLS sempre ativa.** Se der erro de SSL, a URL está errada — não é
  certificado a contornar.

## Testes

```bash
mise run backend-test        # ou: cd backend && uv run pytest
```

Os testes usam `pytest` + `pytest-django` com fakes em memória para o
`PluggyClient` (sem mock de biblioteca). Cobrem, entre outros, regressões de:
sincronização que abortava por campo inexistente, deleção de histórico fora da
janela incremental, webhook aberto, exposição de credencial, e derivação de
instituição.
