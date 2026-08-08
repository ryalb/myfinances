# Plano de Produto e Desenvolvimento

## Objetivo

Criar uma aplicação para consolidar e analisar o patrimônio financeiro pessoal com foco em planejamento de liberdade financeira, integrando dados de instituições via Pluggy e oferecendo uma experiência moderna com Django REST + GraphQL no backend e Nuxt + PrimeVue + Tailwind no frontend.

## Escopo do Produto

A aplicação deve organizar e analisar:

- Conta corrente
- Cartões de crédito
- Aplicações de renda fixa
- Investimentos de renda variável
- Previdência privada
- Assinaturas e pagamentos recorrentes (água, energia, internet, telefone, etc.)
- Fluxo de caixa e patrimônio consolidado
- Projeções para liberdade financeira

## Princípios do Produto

- Fonte única da verdade para consolidar dados financeiros
- Integração automática com instituições financeiras via Pluggy
- Interface clara para acompanhamento de patrimônio, dívidas e rentabilidade
- Camadas bem separadas: ingestão, processamento, análise, apresentação
- Segurança e privacidade como premissas desde o início

## Arquitetura Proposta

### Backend
- Django
- Django REST Framework para APIs operacionais
- GraphQL para consultas flexíveis do frontend e análises avançadas
- PostgreSQL como banco principal
- Redis para cache e filas
- Celery para processamento assíncrono
- Integração com Pluggy para sincronização de dados financeiros

### Frontend
- Nuxt 3
- PrimeVue para componentes
- Tailwind CSS para layout e design system
- Apollo Client ou equivalente para GraphQL
- Pinia para estado local, quando necessário

### Integrações
- Pluggy para agregação de contas, transações, saldos e investimentos
- Possível integração futura com provedores de mercado, inflação, CDI, IPCA, Selic e cotações

## MVP

### Objetivo do MVP
Entregar uma visão consolidada da vida financeira com sincronização automática via Pluggy e indicadores básicos para planejamento.

### Funcionalidades do MVP
- Autenticação de usuário
- Cadastro e vínculo de instituições via Pluggy
- Importação de contas, cartões, saldos e transações
- Consolidação de patrimônio por categoria
- Visão de fluxo de caixa mensal
- Dashboard com indicadores básicos:
  - patrimônio total
  - saldo líquido
  - gastos mensais
  - taxa de poupança
  - evolução patrimonial
- Separação entre ativos, passivos e patrimônio líquido
- Primeira versão de metas de liberdade financeira
- Histórico de sincronizações e status das integrações
- Gestão de assinaturas e pagamentos recorrentes com vencimento e status de pagamento

### Fora do MVP
- Simuladores avançados
- Metas multiobjetivo sofisticadas
- Alertas inteligentes
- Automação fiscal
- Otimização de carteira
- Planejamento de aposentadoria detalhado

## Fases de Desenvolvimento

### Fase 0 - Descoberta e Setup
**Status:** Concluída

- Definir domínios financeiros principais
- Definir modelo de dados inicial
- Preparar ambientes de desenvolvimento
- Configurar backend, frontend, banco e jobs assíncronos
- Estruturar observabilidade e logging

### Fase 1 - Fundação da Plataforma
**Status:** Concluída

- Criar autenticação e autorização
- Criar infraestrutura Django, DRF e GraphQL
- Criar base Nuxt com PrimeVue e Tailwind
- Criar layout principal e navegação
- Estruturar entidades principais:
  - usuário
  - instituição
  - conta
  - cartão
  - transação
  - investimento
  - posição
  - objetivo financeiro

### Fase 2 - Integração Pluggy
**Status:** Concluída

- Implementar conexão com Pluggy
- Criar fluxo de consentimento e vínculo de instituição
- Sincronizar contas e transações
- Sincronizar cartões, saldos e investimentos quando disponíveis
- Persistir status de sincronização e erros
- Criar reprocessamento e atualização incremental
- Importar items por `itemId` via `POST /api/v1/pluggy/items/` e
  `manage.py pluggy_import_item`
- Receber webhooks do Pluggy para criação/atualização de items, com segredo
  compartilhado e idempotência por `eventId`
- Derivar o nome da instituição real a partir das contas sincionizadas

#### Restrições descobertas na integração

Duas descobertas mudaram o desenho original e valem registro, porque contrariam a
suposição inicial de "descobrir integrações existentes":

**1. Um item da Pluggy = uma conexão do Meu Pluggy.**
A tela de consentimento em `meu.pluggy.ai/oauth/authorize` usa radio button
("SELECIONE A CONTA"): autoriza-se **uma** conexão por autorização. Ter Nubank e
Rico significa dois items e duas entradas "MeuPluggy" no Dashboard — estado correto,
não duplicação.

**2. A Pluggy não expõe listagem de items.**
`GET /items` responde **401 Unauthorized**; só `GET /items/{id}` funciona. Não é
possível "descobrir" items pela API. O `itemId` vem do Dashboard (Itens Conectados)
ou do payload do webhook, e armazená-lo é responsabilidade da aplicação.

Consequência: o endpoint `/pluggy/discover/`, que dependia de `fetch_items()`, foi
**removido** e substituído por `POST /api/v1/pluggy/items/`, que recebe o `itemId`.

**3. Items do Meu Pluggy não identificam o banco.**
Todos chegam com `connectorId=200` e `connector.name="MeuPluggy"`. Sem tratamento,
todas as conexões colapsam numa instituição só e a UI mostra cards idênticos. O nome
real é derivado dos nomes das contas e cartões (`INSTITUTION_KEYWORDS` em
`domain.py`), com `provider_id` namespaced (`200:nubank`, `200:rico`) e fallback pelo
nome da conta bancária. É heurística de string, não campo estruturado — se o payload
do item passar a expor o banco, vale trocar por leitura de campo.

**4. Sincronização automática depende de webhook registrado.**
A Pluggy sincroniza os items sozinha (24/12/8h conforme o plano) e avisa via webhook.
Sem webhook registrado, os dados só entram no banco por ação manual. Não se deve
implementar polling nem `PATCH /items` agendado — isso duplica o auto-sync e dispara
`ITEM_CREATION_LIMIT_EXCEEDED`.

**5. Remoção de transações vem só do evento `transactions/deleted`.**
Deletar por diferença contra a janela de `from_date` apaga todo o histórico anterior
a ela. O evento entrega os `transactionIds` exatos; a deleção é escopada à conexão do
item.

Detalhes operacionais: [`backend/PLUGGY_WEBHOOK_SETUP.md`](backend/PLUGGY_WEBHOOK_SETUP.md)
e [`backend/PLUGGY_TROUBLESHOOTING.md`](backend/PLUGGY_TROUBLESHOOTING.md).

### Fase 3 - Consolidação Financeira
**Status:** Concluída

- Normalizar transações e categorias
- Consolidar saldos por conta e por tipo de ativo
- Calcular patrimônio líquido
- Unificar dados de múltiplas instituições
- Criar regras de classificação entre:
  - caixa
  - investimentos
  - previdência
  - dívidas
  - cartões
- Consolidar assinaturas e pagamentos recorrentes no fluxo de caixa
- Reconciliar pagamentos recorrentes com transações importadas
- Motor de regras de categorização (`CategorizationRule`)
- Snapshots de patrimônio líquido no tempo

### Fase 4 - Dashboard e Análises
**Status:** Não iniciada (há apenas dashboard base)

- Criar dashboard principal
- Evolução patrimonial no tempo
- Fluxo de caixa mensal
- Percentual de poupança
- Distribuição por classe de ativo
- Visão de passivos e compromissos futuros
- Visão de assinaturas: vencimento, status de pagamento e valor total recorrente
- Indicadores para liberdade financeira:
  - renda passiva estimada
  - despesas mensais médias
  - runway financeiro
  - meta de patrimônio-alvo

### Fase 5 - Planejamento de Liberdade Financeira
**Status:** Não iniciada

- Definir metas financeiras personalizadas
- Calcular projeções com taxa de aporte e retorno esperados
- Simular cenários conservador, base e agressivo
- Acompanhar distância até a independência financeira
- Identificar gargalos de consumo e concentração de risco

### Fase 6 - Refinamento e Escala
**Status:** Não iniciada

- Alertas e notificações
- Categorização assistida por regras
- Importação manual complementar
- Exportação CSV/Excel
- Relatórios periódicos
- Auditoria e trilha de mudanças
- Performance, cache e otimização de consultas GraphQL

### Fase 7 - Análise Inteligente de Portfolio com IA
**Status:** Não iniciada

- Stack validada:
  - Vector store: `pgvector` (extensão do Postgres 18 via imagem `pgvector/pgvector:0.8.6-pg18-trixie`)
  - Embeddings: `nomic-embed-text` via Ollama — roda localmente, sem custo de API
  - LLM: `qwen2.5:14b` via Ollama — bom equilíbrio qualidade/velocidade para análise financeira e JSON estruturado
  - Alternativa futura: modelo maior (`qwen2.5:32b`) se precisar de análises mais profundas
- Pipeline RAG:
  - Vetorizar transações, contas, investimentos, metas, histórico de sync e regras de categorização
  - Indexar em tabelas `DocumentChunk` + `Embedding` no Postgres via pgvector
  - Busca por similaridade por usuário, filtrando por domínio financeiro
- LLM para relatórios:
  - Relatório de saúde financeira com pontos fortes/fracos fundamentados nos dados
  - Sugestões de ajustes em aplicações financeiras existentes
  - Recomendações de novas aplicações/investimentos alinhadas ao perfil
  - Simulações de cenários baseadas no comportamento histórico
- Interface:
  - Backend: endpoint REST `/api/v1/ai/portfolio-report/`
  - Frontend: página/assistant integrada ao dashboard
- Critérios de qualidade:
  - Respostas fundamentadas nos dados reais do usuário (sem alucinação)
  - Rastreabilidade das fontes usadas pela LLM
  - Moderação de conteúdo financeiro sensível
  - Custos controlados por requisição/usuário
  - 100% offline/local sem envio de dados para APIs externas

## Modelo de Dados Inicial

### Entidades principais
- User
- FinancialInstitution
- Connection
- Account
- Card
- Transaction
- Investment
- InvestmentPosition
- PensionPlan
- NetWorthSnapshot
- FinancialGoal
- SyncJob
- CategorizationRule
- Subscription
- SubscriptionPayment
- ProcessedWebhookEvent
- DocumentChunk
- Embedding

### Relações importantes
- Um usuário possui várias conexões com instituições
- Uma conexão possui várias contas e cartões
- Uma conta possui várias transações e saldos históricos
- Uma transação pertence a uma conta **ou** a um cartão, nunca aos dois
  (`Transaction` não tem FK direta para `Connection`)
- Um investimento pode ter várias posições e histórico de valuation
- Um usuário pode ter várias metas financeiras
- Um usuário possui várias assinaturas/pagamentos recorrentes, cada uma com histórico de pagamentos mensais (status: pago/pendente)

### ProcessedWebhookEvent

Registro de `eventId` já processado. A Pluggy reentrega webhooks até 9 vezes (3
tentativas imediatas, 3 após 1h, 3 após 2h); sem isso cada reentrega reprocessaria o
evento. Também absorve a entrega dupla quando há mais de um webhook registrado
cobrindo o mesmo evento.

### Assinaturas e Pagamentos Recorrentes

Gerenciar despesas fixas recorrentes (água, energia, internet, telefone, streaming, etc.) com controle de vencimento e status de pagamento.

**Subscription** (assinatura/cobrança recorrente):
- name: nome descritivo (ex.: "Conta de água")
- category: tipo de serviço (água, energia, internet, telefone, streaming, etc.)
- amount: valor mensal esperado
- due_day: dia de vencimento (1-31)
- payment_account: conta/banco de pagamento (opcional)
- is_active: se a assinatura continua vigente

**SubscriptionPayment** (histórico de pagamentos por mês):
- subscription: referência à assinatura
- due_date: data de vencimento do mês
- paid_date: data efetiva do pagamento (null se pendente)
- status: pago / pendente / atrasado
- paid_amount: valor efetivamente pago (pode divergir do esperado)

**Comportamento esperado:**
- Geração automática de pagamentos pendentes ao longo do tempo com base em `due_day`
- Reconciliação automática com transações importadas (Pluggy) quando o pagamento é detectado
- Marcação manual de pago/pendente para contas não conectadas
- Alerta de vencimento próximo e pagamentos atrasados

## API e Contratos

### REST
Usar REST para:
- autenticação
- gerenciamento de integrações
- execução de sync jobs
- ações operacionais
- upload/importação manual
- gerenciamento de assinaturas e pagamentos recorrentes
- administração

Endpoints Pluggy atuais:
- `POST /api/v1/pluggy/items/` — importa um item por `itemId`
- `POST /api/v1/pluggy/webhook/?token=<secret>` — recebe eventos
- `POST /api/v1/pluggy/regenerate-auth/` — revalida a apiKey (staff; não a retorna)
- `POST /api/v1/connections/{id}/sync/` — sincronização manual

### GraphQL
Usar GraphQL para:
- dashboard
- análises agregadas
- consultas profundas e compostas
- detalhamento de patrimônio
- projeções financeiras
- visualizações por período e categoria

### Operações que ficam fora da API

Algumas ações são exclusivas de CLI, por serem privilegiadas ou destrutivas:

- **Transferir posse de uma conexão** (`pluggy_import_item --claim`). A API nunca
  reatribui dono: aceitar isso permitia a um usuário autenticado assumir as contas
  bancárias de outro.
- **Registrar/remover webhooks** (`pluggy_register_webhook`).
- **Reset e reimportação** (`pluggy_import_item --reset`, `mise run db-reset`).

## Segurança e Privacidade

- Autenticação segura
- Tokens com expiração e rotação
- Criptografia de dados sensíveis em repouso
- Segregação de credenciais do Pluggy
- Auditoria de acesso e sincronização
- Minimização de dados armazenados
- Validação forte de entrada e proteção contra abuso

### Invariantes implementadas

- **A apiKey do Pluggy nunca chega ao frontend.** Ela dá acesso total aos dados
  financeiros de todos os items da aplicação.
- **`clientId`/`clientSecret` só no backend**, lidos de variáveis de ambiente.
- **O webhook exige segredo compartilhado**, responde `403` sem token e `503` se o
  segredo não estiver configurado. Deleções de transação são escopadas à conexão do
  item — nunca por `external_id` global.
- **`clientUserId` é derivado do usuário autenticado**, nunca aceito do request.
- **Conexões nunca trocam de dono pela API** (`409` quando o item pertence a outro).
- **Verificação TLS sempre ativa** em todas as chamadas à Pluggy.
- **Sem endpoint de debug que emita token** — removido.

## Observabilidade

- Logs estruturados
- Métricas de sincronização
- Rastreamento de falhas de integração
- Monitoramento de jobs assíncronos
- Alertas para integrações quebradas ou dados desatualizados

## Operação

Comandos e tasks documentados em detalhe no [README](README.md). Resumo do que existe:

### Tasks mise

| Task | Uso |
|---|---|
| `mise run dev` | Stack completo em paralelo (API, worker, frontend, ngrok) |
| `mise run check` | lint + typecheck + testes |
| `mise run db-backup` | Dump em `tmp/backups/` |
| `mise run db-backups` | Lista backups |
| `mise run db-restore <dump>` | Restaura (confirmação digitada) |
| `mise run db-reset` | Apaga, recria e migra do zero (backup automático antes) |

Duas armadilhas de `mise` já encontradas, registradas em comentário no `mise.toml`:
processos long-running não podem entrar em `depends` (o `depends` espera terminar), e
uma lista em `run` é sequencial — paralelismo exige `:::`.

### Comandos de gestão

| Comando | Uso |
|---|---|
| `pluggy_import_item` | Importa items por `itemId` e sincroniza |
| `pluggy_register_webhook` | Registra/lista/remove webhook da aplicação |
| `pluggy_refine_institutions` | Re-deriva o nome da instituição das contas sincronizadas |
| `pluggy_test_meu_pluggy` | Diagnóstico da integração |
| `fix_duplicated_credit_accounts` | Corrige conta de crédito duplicada como `Account`+`Card` |
| `seed_data` | Dados fake para teste local |

### Rotina de troubleshooting

1. Webhook registrado? `pluggy_register_webhook --list`. Sem webhook não há sync automático.
2. Túnel de pé e host no `DJANGO_ALLOWED_HOSTS`? Sem o host, o Django responde 400
   antes da view e a falha não aparece nos logs de aplicação.
3. Backend escutando? `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health/`
4. Worker do Celery rodando? Sem ele o webhook enfileira e nada é processado.
5. Conexão com nome "MeuPluggy"? `pluggy_refine_institutions`.
6. `409` ao importar pela UI? O item pertence a outro usuário — confira com
   `GET /api/v1/auth/me/` qual usuário está autenticado.

## Critérios de Sucesso do MVP

- Usuário consegue conectar instituições via Pluggy
- Dados financeiros aparecem consolidados no dashboard
- Patrimônio líquido é calculado corretamente
- Fluxo de caixa mensal é visível
- Assinaturas e pagamentos recorrentes são visíveis com status de pagamento por mês
- O sistema mostra progresso rumo à liberdade financeira
- Sincronização é estável e reexecutável

## Riscos e Pontos de Atenção

- Qualidade e disponibilidade dos dados retornados pelo Pluggy
- Normalização de categorias entre instituições diferentes
- Diferenças entre saldo contábil e saldo disponível
  (`classify_account_balance` usa `available_balance`, não `balance`)
- Tratamento de investimentos com estrutura complexa
- Privacidade e compliance com dados financeiros
- **Derivação de instituição por heurística de string.** Funciona para os bancos em
  `INSTITUTION_KEYWORDS`, com fallback pelo nome da conta bancária. Um banco novo
  exige uma linha no dict. Substituir por leitura de campo se o payload do item
  passar a expor o banco real.
- **Paginação de `/v2/transactions` não verificada contra a doc oficial.** O código
  segue cursor `next`/`after`; a documentação de referência descreve `page`/`pageSize`
  para `/transactions`. Confirmar antes de mexer — errar aqui perde transações
  silenciosamente.
- **Contas de crédito podem duplicar como `Account` e `Card`.** Prevenido pelo filtro
  `type=BANK` na busca de contas; dados antigos se corrigem com
  `fix_duplicated_credit_accounts`, que re-aponta as transações antes de remover a
  `Account` — deletar direto faria CASCADE e apagaria o histórico.

## Dívida técnica conhecida

- `config/asgi.py` tem `E402` (imports após `get_asgi_application()`), que é o padrão
  exigido pelo Channels. Ignorado deliberadamente.
- `pluggy-sdk` está em `pyproject.toml` mas não é usado — a integração fala com a API
  via `requests` direto. Avaliar remover ou migrar.
- Cobertura de testes concentrada na integração Pluggy e na consolidação; o restante
  do domínio (metas, GraphQL, serializers, IA) segue sem testes.
- `mise run setup` roda `docker compose up -d --force-recreate` e a task `dev` depende
  de `setup`. Verificar se o volume do Postgres é persistente, para não zerar o banco
  a cada `mise run dev`.
- Um episódio de derivação de instituição que falhou silenciosamente não teve causa
  raiz identificada. O modo de falha provável (o início do sync sobrescrever a
  instituição derivada) foi corrigido com teste, e o `refine` agora loga o resultado
  para tornar uma recorrência diagnosticável.

## Próximos Passos

1. Definir o escopo exato do MVP. ✅
2. Desenhar o modelo de dados inicial. ✅
3. Criar a base do backend Django com REST e GraphQL. ✅
4. Estruturar o frontend Nuxt com layout e design system. ✅
5. Implementar a primeira integração com Pluggy. ✅
6. Construir o dashboard inicial com métricas principais.
7. Implementar Fase 4 - Dashboard e Análises.
8. Implementar Fase 5 - Planejamento de Liberdade Financeira.
9. Implementar Fase 6 - Refinamento e Escala.