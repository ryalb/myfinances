# Runbook: Webhook da Pluggy

Como configurar, registrar e validar o webhook que dispara a sincronização
automática das contas.

> **Sem webhook registrado não existe sincronização automática.** A Pluggy sincroniza
> os items sozinha (a cada 24/12/8h, conforme o plano) e avisa via webhook quando
> termina. Se o webhook não estiver registrado, os dados só entram no banco quando
> alguém clica em "Atualizar integrações" manualmente.

## As duas variáveis não vêm da Pluggy

| Variável | O que é | Origem |
|---|---|---|
| `PLUGGY_WEBHOOK_SECRET` | Segredo que **você gera**. O endpoint compara com o `?token=` da requisição e rejeita quem não bate. Não existe no Dashboard da Pluggy. | Você |
| `PLUGGY_WEBHOOK_URL` | A URL **pública do seu backend** + path do endpoint + o token. A Pluggy só precisa alcançá-la. | Seu túnel (dev) ou domínio (prod) |

O segredo na query string é uma decisão nossa, não requisito da Pluggy: não foi
confirmado na documentação oficial se a Pluggy assina os webhooks (ex. HMAC em
header). Se/quando isso for confirmado, prefira validar a assinatura e trate o
token como defesa secundária.

## Setup em dev

O ngrok deste projeto usa **domínio estático**, configurado em
`~/Library/Application Support/ngrok/ngrok.yml`:

```yaml
version: "3"
endpoints:
  - name: myfinances
    url: https://platonic-groin-basin.ngrok-free.dev
    upstream:
      url: http://127.0.0.1:8000   # NAO use "8000" nem "localhost:8000" — ver nota abaixo
```

> **Force IPv4 no upstream.** Se o upstream for `8000` ou `localhost:8000`, o ngrok
> resolve `localhost` e no macOS pega **`::1` (IPv6) primeiro**. O Daphne, como é
> iniciado aqui (`daphne config.asgi:application --port 8000`), abre socket
> **IPv4 apenas** — `lsof` mostra `TCP 127.0.0.1:8000 (LISTEN)` e nada em IPv6.
> Resultado: `ERR_NGROK_8012` com `dial tcp [::1]:8000: connect: connection refused`,
> mesmo com o backend rodando normalmente. Escrever `http://127.0.0.1:8000` elimina a
> resolução de nome e o problema.
>
> A alternativa é fazer o Daphne escutar em IPv6 (`daphne -b :: --port 8000`), mas
> fixar o upstream em IPv4 é mais simples e não mexe na task do `mise`.

Domínio estático significa que os passos abaixo são **feitos uma vez** — a URL não
muda entre reinícios.

### 1. Gere o segredo

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Preencha o `backend/.env`

```env
PLUGGY_WEBHOOK_SECRET="<o-que-o-passo-1-gerou>"
PLUGGY_WEBHOOK_URL="https://platonic-groin-basin.ngrok-free.dev/api/v1/pluggy/webhook/?token=<o-mesmo-segredo>"

# O host do túnel precisa estar aqui, senão o Django responde 400
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,platonic-groin-basin.ngrok-free.dev
```

O token tem que ser **idêntico** nas duas variáveis. O comando de registro valida
isso e recusa se não bater.

`DJANGO_ALLOWED_HOSTS` é o passo que falha silenciosamente: sem o host do túnel, o
Django devolve **400 antes de chegar na view**. A Pluggy conta como falha, tenta 9
vezes e desiste — e não aparece erro nenhum nos logs da aplicação.

### 3. Reinicie o backend

`config/settings.py` chama `load_dotenv()` na importação (linha 10), então mudança
no `.env` só vale depois de reiniciar.

```bash
mise run backend-dev    # já sobe o ngrok (task `ngrok` está em `depends`)
```

### 4. Registre o webhook

Os items do Meu Pluggy são criados fora do nosso widget, então o `webhookUrl` do
`connect_token` não os cobre. É preciso registrar a nível de aplicação:

```bash
cd backend
uv run python manage.py pluggy_register_webhook          # registra
uv run python manage.py pluggy_register_webhook --list   # confirma
```

Outras operações:

```bash
uv run python manage.py pluggy_register_webhook --delete <webhook-id>
uv run python manage.py pluggy_register_webhook --event item/updated   # evento específico
```

### Registre apenas UM webhook, com `event=all`

Erros comuns ao cadastrar pelo Dashboard, todos já vistos neste projeto:

| Erro | Consequência |
|---|---|
| Porta na URL pública (`...ngrok-free.dev:8000/...`) | Não chega no túnel: o endpoint público do ngrok é 443. A `:8000` é o upstream local. |
| URL sem a barra final (`.../pluggy/webhook`) | A rota é `api/v1/pluggy/webhook/` e `APPEND_SLASH` é `True`: um POST sem barra vira 301 (ou `RuntimeError` com `DEBUG=True`), nunca 200. |
| URL sem `?token=` | 403 no endpoint. |
| Um webhook `all` **e** um `item/updated` | Entrega dupla do mesmo evento. A idempotência por `eventId` absorve se a Pluggy reusar o `eventId` entre subscriptions — não confirmado na doc. Na dúvida, mantenha só `all`. |

Qualquer resposta fora de 2XX é falha para a Pluggy: ela tenta 9 vezes e desiste,
sem erro visível nos seus logs de aplicação.

Prefira registrar pelo comando em vez do Dashboard — ele valida que o `?token=`
existe e bate com `PLUGGY_WEBHOOK_SECRET` antes de chamar a API.

### 5. Valide de ponta a ponta

```bash
cd backend
set -a && source .env && set +a

curl -i -X POST "$PLUGGY_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"event":"item/updated","itemId":"<item-id-real>","clientUserId":"1","eventId":"teste-1"}'
```

Esperado: `200 {"status":"queued"}`.

Confira também os caminhos de rejeição:

| Requisição | Esperado |
|---|---|
| Sem `?token=` | `403` |
| `?token=errado` | `403` |
| `PLUGGY_WEBHOOK_SECRET` vazio no ambiente | `503` |
| Evento desconhecido (ex. `item.update`) | `200 {"status":"ignored"}` |
| Mesmo `eventId` duas vezes | segunda é ignorada (idempotência) |

Troque o `eventId` a cada teste — repetir o mesmo é ignorado de propósito.

O worker precisa estar rodando para o job sair da fila:

```bash
mise run backend-worker
```

## Setup em produção

```env
PLUGGY_WEBHOOK_URL="https://api.seudominio.com/api/v1/pluggy/webhook/?token=<secret>"
DJANGO_ALLOWED_HOSTS=api.seudominio.com
```

- HTTPS é obrigatório: o token viaja na query string.
- O segredo vem do gerenciador de segredos do host, não de um `.env` em disco.
- Use credenciais Pluggy (`PLUGGY_CLIENT_ID`/`SECRET`) de uma aplicação separada da
  de desenvolvimento.

## Eventos tratados

Nomes usam **barra**, não ponto. `item.update` é ignorado pelo endpoint.

| Evento | O que o backend faz |
|---|---|
| `item/created`, `item/updated` | Busca o item via `GET /items/{id}`, e se `UPDATED` dispara sync completo |
| `item/error` | Marca a conexão como `ERROR` com a mensagem |
| `item/waiting_user_input` | Marca como `PENDING` (MFA pendente) |
| `item/login_succeeded` | Reavalia o status do item |
| `item/deleted` | Remove a `Connection` local |
| `transactions/created` | Usa `createdTransactionsLink` (ou `transactionsCreatedAtFrom`) para buscar só as novas |
| `transactions/updated` | Refaz o fetch dos `transactionIds` informados |
| `transactions/deleted` | Apaga os `transactionIds`, escopados à conexão do item |

Deleção de transações **só** acontece via `transactions/deleted`. O sync completo
nunca apaga por diferença — fazer isso destruía todo o histórico fora da janela de
`from_date`.

## Troubleshooting

### `502` com `ERR_NGROK_8012`

O túnel está de pé, mas o ngrok não conseguiu falar com o upstream. O corpo da
resposta traz um `data-payload` em base64 com o motivo exato:

```bash
echo '<conteudo-do-data-payload>' | base64 -d | python3 -m json.tool
```

Procure `errorText`. Os dois casos comuns:

**`dial tcp 127.0.0.1:8000: connect: connection refused`** — o backend não está
rodando. Confirme e suba:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN   # vazio = nada escutando
mise run backend-dev
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health/   # espera 200
```

**`dial tcp [::1]:8000: connect: connection refused`** — o upstream do ngrok está
resolvendo `localhost` para IPv6, e o Daphne só escuta em IPv4. Corrija o
`ngrok.yml` para `upstream.url: http://127.0.0.1:8000` (ver a nota na seção de
setup). Isso acontece **mesmo com o backend rodando**, então é fácil confundir com
"backend caiu".

Para diagnosticar qual dos dois é:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

- Sem saída → backend não está rodando (primeiro caso).
- Saída com `IPv4 ... TCP 127.0.0.1:8000 (LISTEN)` e o erro citando `[::1]` →
  problema de IPv6 (segundo caso).

### `fetch_items falhou: 401 Unauthorized` em `GET /items`

**Confirmado: a Pluggy não expõe listagem de items.** A autenticação passa
(`/auth` devolve 200 e um JWT), `GET /items/{id}` funciona, mas `GET /items` sem
`itemId` responde 401.

```
INFO   Pluggy auth returned apiKey_length=698 has_expiresIn=False
INFO   Pluggy request method=GET url=https://api.pluggy.ai/items
WARN   Pluggy request retrying after 401 for /items
ERROR  Pluggy 401 body for https://api.pluggy.ai/items: code=401 message=Unauthorized
```

Consequência: o endpoint `/pluggy/discover/` não funciona, porque depende de
`fetch_items()`. Use o comando que recebe os itemIds explicitamente:

```bash
python manage.py pluggy_import_item \
  --item <item-id-1> \
  --item <item-id-2> \
  --user-id 1
```

Os itemIds vêm do Dashboard da Pluggy (**Itens Conectados**, o UUID acima do nome)
ou do payload dos webhooks `item/created` / `item/updated`. Guarde-os — é
responsabilidade da aplicação, não algo que se consulta.

Lembre que **cada conexão do Meu Pluggy é um item separado**: a tela de
consentimento permite escolher uma conexão por autorização, então Nubank + Rico =
dois itemIds. Ver [`PLUGGY_TROUBLESHOOTING.md`](./PLUGGY_TROUBLESHOOTING.md).

## Backup e restore

Antes de qualquer `--reset` ou operação destrutiva:

```bash
mise run db-backup      # dump em tmp/backups/ (formato custom, restaurável)
mise run db-backups     # lista os backups, mais recente primeiro
mise run db-restore tmp/backups/myfinances-AAAAMMDD-HHMMSS.dump
```

O `db-restore` pede confirmação digitada (`RESTORE`) porque sobrescreve o banco com
`--clean --if-exists`. `tmp/` está no `.gitignore`, então os dumps não vão para o
git.

### Webhook registrado mas nada chega

Na ordem:

1. `pluggy_register_webhook --list` mostra a URL correta, com `?token=`?
2. O host do túnel está em `DJANGO_ALLOWED_HOSTS`? (400 silencioso)
3. O backend está de pé e escutando? `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/health/` → 200
4. O `curl` do passo 5 retorna `200`? Se sim, o problema está no caminho até você,
   não no código.
5. O ngrok está de pé? `mise run backend-dev` já sobe, mas confira em
   `http://localhost:4040` (inspector do ngrok) se as requisições chegam — e com que
   status saem.
6. O Celery worker está rodando? Sem ele o `200 {"status":"queued"}` acontece mas
   nada é processado.
7. Redis de pé? É o broker do Celery.

### `403` no meu próprio curl de teste

O `?token=` não bate com `PLUGGY_WEBHOOK_SECRET` do ambiente do processo. Lembre que
mudança no `.env` exige reiniciar o backend.

### `503 Webhook not configured`

`PLUGGY_WEBHOOK_SECRET` está vazio ou ausente no ambiente do backend. É proposital:
o endpoint recusa operar sem segredo em vez de aceitar qualquer requisição.

## Referências

- [`PLUGGY_TROUBLESHOOTING.md`](./PLUGGY_TROUBLESHOOTING.md) — diagnóstico geral da
  integração (discover, SSL, clientUserId)
- Testes de regressão: `apps/finance/tests/test_pluggy_webhook.py`
- Endpoint: `apps/finance/views.py` → `PluggyWebhookAPIView`
- Processamento: `apps/finance/tasks.py` → `process_pluggy_webhook`
