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

Sobe API, Celery worker, Celery beat e frontend **em paralelo**. Note o `:::` na
definição da task: uma lista em `run` seria sequencial, e como cada processo é
long-running, o segundo nunca começaria. Pelo mesmo motivo o `ngrok` **não** pode
entrar em `depends` do `backend-dev` — `depends` espera a task terminar, e
`ngrok start --all` nunca termina. Para receber webhooks da Pluggy use
`mise run dev-tunnel`, que adiciona o túnel.

### Tasks individuais

| Task | O que faz |
|---|---|
| `mise run setup` | Sobe os containers e instala dependências (backend + frontend) |
| `mise run dev` | Stack completo em paralelo (API, worker, beat, frontend) |
| `mise run dev-tunnel` | Idem + túnel ngrok |
| `mise run backend-dev` | Django via Daphne (ASGI/WebSocket) na porta 8000 |
| `mise run backend-worker` | Celery worker |
| `mise run backend-beat` | Celery beat — agendador das tasks diárias |
| `mise run backend-migrate` | Aplica migrations |
| `mise run frontend-dev` | Nuxt dev server na porta 3000 |
| `mise run ngrok` | Túnel ngrok (necessário para receber webhooks em dev) |
| `mise run kill-port <porta>` | Mata processos numa porta |

### Tasks periódicas

O beat agenda duas tasks diárias (`CELERY_BEAT_SCHEDULE` em `config/settings.py`):

| Task | Horário | O que faz |
|---|---|---|
| `snapshot_all_users` | 03:10 | Snapshot patrimonial de todo usuário com conexão |
| `reconcile_all_subscriptions` | 03:30 | Gera pendências do mês e marca atrasados |

**Sem o beat rodando nada disso dispara** — o worker só executa o que alguém
enfileira. O sintoma é silencioso: buraco no gráfico de evolução patrimonial em
meses sem sync, e assinatura vencida que nunca vira `overdue`. As duas são
idempotentes por dia, então reexecutar não duplica nada.

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
| `pluggy_dump_investments` | Mostra os investimentos crus da Pluggy e se cada um seria classificado como previdência |
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
- `GET /api/v1/export/transactions.csv?start_date=&end_date=` exporta transações
  (streaming, sem paginação, com BOM para o Excel ler UTF-8)
- `POST /api/v1/categorization-rules/reapply/` reaplica as regras ao histórico e
  devolve `{updated: N}`
- `POST /api/v1/ai/portfolio-report/` relatório de portfolio via RAG + LLM local
  (aceita `{"query": "..."}` opcional; responde `503` se o Ollama estiver fora e
  `422` se não houver dado indexável)
- `GET /health/` health check

## Análise com IA (RAG local)

Roda 100% local via Ollama, sem enviar dado financeiro para fora.

**Os dois modelos precisam ser baixados antes do primeiro relatório.** Sem isso o
Ollama responde `404 model "X" not found` e o endpoint devolve `503`:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull nomic-embed-text   # embeddings (768 dim)
docker compose exec ollama ollama pull qwen2.5:14b        # geração do relatório

# Confirme:
curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"'
```

Configuração por variável de ambiente: `OLLAMA_URL`, `OLLAMA_EMBEDDING_MODEL`
(default `nomic-embed-text`), `OLLAMA_CHAT_MODEL` (default `qwen2.5:14b`).

**Inferência remota é recusada por padrão.** O contexto enviado ao modelo inclui
saldos, transações, instituições e metas — um `OLLAMA_URL` apontando para fora
exportaria tudo isso em silêncio. Host não-local responde `503` com a razão; use
`AI_ALLOW_REMOTE_INFERENCE=true` se o envio for intencional.

O índice vetorial usa `pgvector` no próprio Postgres. Três coisas que importam:

- **A dimensão da coluna é fixa em 768** (`EMBEDDING_DIMENSIONS` em `models.py`), que
  é o que `nomic-embed-text` produz. Trocar por um modelo de outra dimensão exige
  alterar a constante e gerar migration — o serviço confere o tamanho antes de gravar
  e falha com mensagem explícita em vez de erro do banco.
- **A indexação é incremental.** Cada domínio financeiro (contas, cartões,
  investimentos, previdência, metas, assinaturas, regras, histórico de sync, e um
  documento por mês de transações) vira um `DocumentChunk` com hash do conteúdo. Só o
  que mudou é reembedado, então gerar o relatório duas vezes seguidas não custa
  chamada de embedding nenhuma.
- **O índice é dado derivado.** Apagar `DocumentChunk` é seguro: o próximo relatório
  reconstrói. A migration `0009` faz exatamente isso, e troca a coluna por
  `RemoveField` + `AddField` em vez de `AlterField` — o Postgres não converte `jsonb`
  em `vector` nem com a tabela vazia, porque a rejeição é do cast em si.

## Paginação

`/transactions/` e `/sync-jobs/` vêm paginados (`{count, next, previous, results}`,
100 por página, `?page_size=` até 500). São as coleções que crescem sem limite.

### Filtros de transações

`GET /api/v1/transactions/` aceita `search` (descrição, `icontains`), `category`
(exato), `type` (`credit`/`debit`), `account`, `card`, `start_date`, `end_date`,
`min_amount`, `max_amount`. Parâmetro vazio ou inválido é ignorado, não vira 400.

`GET /api/v1/transactions/categories/` lista as categorias existentes para o filtro.

`GET /api/v1/export/transactions.csv` aceita **os mesmos** parâmetros, pelo mesmo
helper (`apps/finance/filters.py`) — dois lugares aplicando os filtros separadamente
divergiriam, e o sintoma seria um CSV que não corresponde à tela.

As demais listas — contas, cartões, investimentos, previdência, assinaturas,
conexões — continuam como array puro **de propósito**: são naturalmente pequenas, e
paginar tudo mudaria a forma da resposta em oito telas sem ganho nenhum. Há teste
travando as duas decisões, então mudar de ideia quebra a suíte em vez de quebrar a UI
em silêncio.

## Alertas

O sino no cabeçalho mostra alertas **derivados do estado atual**, não registros
persistidos: pagamento atrasado, vencimento em 7 dias, conexão com erro e conexão sem
sincronizar há mais de 3 dias. Vêm do campo GraphQL `alerts`.

Não há tabela de notificações de propósito — um alerta derivado desaparece quando a
condição se resolve. Como `useRealtimeSync` já chama `refreshNuxtData()` a cada evento
de sync, os alertas se atualizam pelo WebSocket sem polling.

## Categorização

A ordem de precedência ao categorizar uma transação:

1. Regra do usuário (`CategorizationRule`, menor `priority` decide primeiro)
2. `provider_category` vindo da Pluggy
3. Palavras-chave conhecidas (`CATEGORY_KEYWORDS`)
4. Padrão por tipo (`income` / `expenses`)

A regra do usuário vem **antes** da categoria do provedor: era o contrário, e isso
fazia uma regra "uber → transporte" nunca se aplicar, porque a Pluggy manda "Travel".

As regras rodam no import. Para o histórico já gravado, use "Reaplicar ao histórico"
na tela `/rules` (ou `POST /api/v1/categorization-rules/reapply/`). Criar uma regra
**não** recategoriza nada sozinha — a tela avisa isso ao salvar.

### Por que as categorias apareciam em inglês

O categorizador da Pluggy usa taxonomia em inglês (`Bookstore`, `Vehicle maintenance`),
e o texto ia direto para a tela. Agora `apps/finance/categories.py` traduz na entrada:
`provider_category` guarda o valor cru da Pluggy como trilha de origem, e `category`
guarda o texto em pt-BR que a UI, o export e o relatório de IA usam.

O mapa cobre a árvore documentada (níveis 1–3). Categoria fora do mapa **passa
intacta** em vez de virar "Outros" — aparece em inglês, o que é visível e corrigível.

A fonte canônica seria `descriptionTranslated` do `GET /categories` da Pluggy, mas
usá-la exige gravar o `categoryId` da transação e sincronizar a árvore; não feito.

Dados já gravados: clique em **"Reaplicar ao histórico"** em `/rules` — ele recalcula
`category` de todo o histórico, inclusive traduzindo.

### `amount` é magnitude, não valor com sinal

A Pluggy assina `amount` e **a convenção difere por produto**: em conta bancária a
saída é negativa; em cartão a compra é positiva e o pagamento da fatura é negativo.
O indicador confiável de direção é `type` (`DEBIT` = saída, `CREDIT` = entrada), que é
obrigatório.

Por isso o valor é gravado como magnitude. Guardar com sinal produzia três sintomas de
uma vez: `Sum(amount)` das despesas dando negativo (taxa de poupança acima de 100%), o
prefixo `-` da tela virando `--`, e reconciliação de assinatura que nunca casava
porque filtra `amount__gt=0`. A migration `0010` normaliza as linhas antigas.

## Segurança

Decisões que valem conhecer antes de mexer:

- **A apiKey do Pluggy nunca sai do backend.** Ela dá acesso total aos dados
  financeiros. O endpoint de revalidação não a retorna, e o frontend não a recebe.
- **O webhook exige segredo compartilhado** (`?token=`), responde `403` sem ele e
  `503` se `PLUGGY_WEBHOOK_SECRET` não estiver configurado. Sem isso, qualquer um
  poderia apagar transações via `transactions/deleted`.
- **O `clientUserId` é derivado do usuário autenticado**, nunca aceito do request.
- **Conexões nunca trocam de dono pela API.** Só a CLI transfere posse, com `--claim`.
- **FK gravável é sempre escopada ao usuário.** O `ModelSerializer` valida FK contra
  a tabela inteira, então `UserScopedPrimaryKeyRelatedField` filtra pelo dono. Sem
  isso dava para pendurar a própria assinatura na conta bancária de outro usuário.
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
