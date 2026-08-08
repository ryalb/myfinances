# Troubleshooting: Pluggy Meu Pluggy

> Para configurar e registrar o webhook (o que habilita a sincronização automática),
> veja [`PLUGGY_WEBHOOK_SETUP.md`](./PLUGGY_WEBHOOK_SETUP.md).

## Como o Meu Pluggy se encaixa (leia primeiro)

**Um item da Pluggy = uma conexão do Meu Pluggy.** A tela de consentimento em
`meu.pluggy.ai/oauth/authorize` usa *radio button* ("SELECIONE A CONTA"): você
autoriza **uma** conexão por vez. Se você tem Nubank e Rico no Meu Pluggy, precisa
autorizar duas vezes, e o Dashboard vai mostrar **duas** entradas "MeuPluggy". Isso
é o estado correto — não é duplicação.

**A Pluggy não expõe listagem de items.** `GET /items` responde **401
Unauthorized**; só `GET /items/{id}` funciona. Consequência: não é possível
"descobrir" items pela API. O `itemId` vem de duas fontes:

1. O Dashboard da Pluggy, em **Itens Conectados** (o UUID acima do nome).
2. O payload do webhook (`item/created`, `item/updated`).

Por isso o endpoint `/pluggy/discover/` **não funciona** — ele depende de
`fetch_items()`. Para importar, use o comando que recebe os itemIds:

```bash
python manage.py pluggy_import_item \
  --item <item-id-1> \
  --item <item-id-2> \
  --user-id 1
```

Com `--reset --yes` ele apaga os dados Pluggy do usuário antes de reimportar.
**Faça backup primeiro:** `mise run db-backup`.

## Sintomas comuns

### 1. Só uma das minhas conexões aparece

Cada conexão exige uma autorização separada (ver a seção acima). Confira no
Dashboard, em **Itens Conectados**, se há um item por conexão. Se falta uma:
Dashboard → **+ Conectar Conta** → MeuPluggy → escolha a conexão que falta →
**Autorizar**. Depois importe o novo itemId com `pluggy_import_item`.

### 2. `GET /items` retorna 401 / `discover` retorna 0 items

Esperado — a Pluggy não expõe listagem de items. Use `pluggy_import_item` com os
itemIds do Dashboard. O `--no-filter` do comando de debug abaixo também vai falhar
com 401 pelo mesmo motivo.

**Diagnóstico passo a passo (para outros problemas de credencial):**

1. **Rode o comando de debug para ver o que a API retorna:**
   ```bash
   # Tenta buscar items filtrando por clientUserId
   python manage.py pluggy_test_meu_pluggy --user-id 1

   # Busca TODOS os items sem filtro, para ver o clientUserId real
   python manage.py pluggy_test_meu_pluggy --user-id 1 --no-filter
   ```

2. **Interpretando os resultados:**

   **Cenário A: `--no-filter` retorna 0 items**
   - Causa: A aplicação no Dashboard não tem nenhum item conectado
   - Solução: No Dashboard, abra sua aplicação, adicione o conector "Meu Pluggy" e faça login com `meu.pluggy.ai`

   **Cenário B: `--no-filter` retorna items, mas `connectorId != 200`**
   - Causa: Os items pertencem a outro conector (não é Meu Pluggy)
   - Solução: Verifique se você conectou o conector correto no Dashboard

   **Cenário C: `--no-filter` retorna items com `connectorId=200`, mas `clientUserId` diferente de `1`**
   - Causa: O `clientUserId` no Dashboard não é o ID do usuário Django
   - Solução: Verifique no Dashboard qual é o `clientUserId` da aplicação e ajuste o código se necessário

   **Cenário D: `--no-filter` retorna items com `connectorId=200` e `clientUserId=1`, mas a busca filtrada retorna 0**
   - Causa: Possível bug na API da Pluggy com filtro de clientUserId
   - Solução: `/pluggy/discover/` já tenta automaticamente `fetch_items()` sem filtro quando a busca filtrada retorna 0

3. **Credenciais corretas?**
   - `PLUGGY_BASE_URL` deve ser `https://api.pluggy.ai` (produção)
   - `PLUGGY_CLIENT_ID` e `PLUGGY_CLIENT_SECRET` devem ser da aplicação no Dashboard, não do sandbox
   - O comando de debug mostra o `client_id` usado — verifique se é o mesmo do Dashboard

4. **Usuário conectou bancos no Meu Pluggy?**
   - Acesse `https://meu.pluggy.ai` e confira se há contas conectadas
   - Cada banco conectado lá vira um item com `connectorId = 200`

5. **Aplicação no Dashboard está conectada ao Meu Pluggy?**
   - No Dashboard, abra sua aplicação
   - Verifique se o conector **"MeuPluggy"** aparece na lista de conectores
   - Se não aparecer, clique em adicionar e faça login com `meu.pluggy.ai`
   - **Importante**: uma mesma conta do Dashboard pode ter múltiplas aplicações; verifique se você está usando as credenciais da aplicação correta

6. **clientUserId no Dashboard**
   - O endpoint `/items` da Pluggy usa `clientUserId` para filtrar items
   - No nosso código, enviamos sempre `str(request.user.id)` (ex: `"1"`), derivado do
     usuário autenticado. Isso **não** é configurável pelo cliente: aceitar um
     `clientUserId` arbitrário permitiria importar as conexões de outro usuário.
   - No Dashboard, verifique se o `clientUserId` da aplicação corresponde a esse valor
   - Se no Dashboard o `clientUserId` for outro valor (ex: email, UUID), o filtro não
     retorna nada e o `discover` cai no fallback sem filtro
   - Use `--no-filter` no comando de debug para ver o `clientUserId` real dos items

### 2. Erro SSL `UNEXPECTED_EOF_WHILE_READING`

**Causa:** `PLUGGY_BASE_URL` com host de sandbox inválido. O host correto do sandbox é
`https://api.sandbox.pluggy.ai` — `https://sandbox.pluggy.ai` (sem o `api.`) causa esse erro.

**Solução:**
```env
PLUGGY_BASE_URL="https://api.pluggy.ai"
```

O código força produção automaticamente quando usa `?meu_pluggy_only=1`, mas se o `.env` ainda estiver com sandbox, reinicie o backend após alterar.

> A verificação de TLS **não** é mais desabilitada para sandbox. Se você vê erro de SSL,
> a URL está errada — não é um problema de certificado a ser contornado.

### 3. Conexões aparecem mas não sincronizam

**Verifique:**
1. O item tem `status = UPDATED`? Se está `UPDATING`, a sincronização ainda está rodando na Pluggy.
   (`UPDATED` é o status de sucesso da Pluggy — não existe `ACTIVE` na API. `ACTIVE` é o
   nosso `ConnectionStatus` interno, não o do item.)
2. Existe webhook registrado? **Sem webhook não há sincronização automática:**
   ```bash
   python manage.py pluggy_register_webhook --list
   ```
   Se a lista vier vazia, registre:
   ```bash
   python manage.py pluggy_register_webhook
   ```
3. Clique em **Atualizar integrações** na página `/integrations` para forçar
4. Verifique os logs do Celery worker se estiver rodando:
   ```bash
   mise run backend-worker
   ```
5. Verifique se o Redis está rodando (broker do Celery)

### 4. Webhook não funciona

**Configuração obrigatória no `.env`:**
```env
PLUGGY_WEBHOOK_SECRET="<gere com: python -c 'import secrets; print(secrets.token_urlsafe(32))'>"
PLUGGY_WEBHOOK_URL="https://<sua-url>/api/v1/pluggy/webhook/?token=<PLUGGY_WEBHOOK_SECRET>"
```

O endpoint rejeita qualquer chamada sem o `?token=` correto (HTTP 403), e responde
HTTP 503 se `PLUGGY_WEBHOOK_SECRET` não estiver configurado.

**Se estiver testando localmente:**
- Use um túnel como `ngrok` ou `cloudflared` para expor a porta 8000
- Registre a URL com o comando (ele valida que o token está presente):
  ```bash
  python manage.py pluggy_register_webhook
  ```
- Os eventos usam **barra**, não ponto: `item/created`, `item/updated`, `item/error`,
  `transactions/created`, `transactions/updated`, `transactions/deleted`

**Teste manual do webhook:**
```bash
curl -X POST "https://<sua-url>/api/v1/pluggy/webhook/?token=$PLUGGY_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"event":"item/updated","itemId":"<item-id-real>","clientUserId":"1","eventId":"teste-1"}'
```

Note que o `eventId` é usado para idempotência: reenviar o mesmo `eventId` é ignorado.
Use um valor novo a cada teste.

## Comando de debug

```bash
# Lista items do Meu Pluggy para um usuário específico (filtra por clientUserId)
python manage.py pluggy_test_meu_pluggy --user-id 1

# Busca TODOS os items sem filtro, mostra o clientUserId de cada um
python manage.py pluggy_test_meu_pluggy --user-id 1 --no-filter

# Mesmo que o primeiro, mas mostra também items que não são Meu Pluggy
python manage.py pluggy_test_meu_pluggy --user-id 1 --all-items
```

**Quando usar cada flag:**
- Sem flags: diagnóstico rápido — busca items do Meu Pluggy para o usuário
- `--no-filter`: use quando o diagnóstico rápido retornar 0 items — mostra todos os items da aplicação e o `clientUserId` de cada um
- `--all-items`: use para ver todos os items, incluindo conectores que não são Meu Pluggy

## Fallback automático

O endpoint `/pluggy/discover/?meu_pluggy_only=1` agora tenta automaticamente buscar todos os items sem filtro se a busca filtrada retornar 0. Isso ajuda a diagnosticar se o problema é o `clientUserId` ou se realmente não há items conectados.

## Estrutura esperada de um item Meu Pluggy

```json
{
  "id": "uuid-do-item",
  "connectorId": "200",
  "institutionId": "uuid-da-instituicao",
  "status": "UPDATED",
  "executionStatus": "SUCCESS",
  "clientUserId": "1",
  ...
}
```

- `connectorId` deve ser exatamente `"200"` (string)
- `institutionId` é o ID da instituição no catálogo da Pluggy
- `status` de sucesso é `UPDATED`; os demais são `CREATING`, `UPDATING`,
  `LOGIN_ERROR`, `WAITING_USER_INPUT` e `OUTDATED`
- `executionStatus` detalha a execução (`SUCCESS`, `PARTIAL_SUCCESS`, ...)

## Diferença: Sandbox vs Meu Pluggy

| Aspecto | Sandbox | Meu Pluggy |
|---------|---------|------------|
| URL base | `https://api.sandbox.pluggy.ai` | `https://api.pluggy.ai` |
| Dados | Fictícios/mockados | Seus dados reais |
| Conexão | Via widget direto | Via `meu.pluggy.ai` + Dashboard |
| Conector | Qualquer | Apenas `connectorId=200` |
| Custo | Gratuito (dev) | Gratuito (uso pessoal) |
