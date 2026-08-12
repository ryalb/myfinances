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

#### O PrimeVue precisa ser configurado, não só instalado

O preset Aura entrava sem customização, e dois defaults dele brigavam com o tema:

**1. `darkModeSelector` default é `"system"`**, que resolve para
`@media (prefers-color-scheme: dark)`. Com o SO em modo escuro o Aura emitia
`color-scheme: dark` no `:root` — e é `color-scheme`, não classe de Tailwind, que faz
o navegador desenhar **controle nativo** (`<input>`, `<select>`, `<textarea>`) com o
estilo escuro do sistema. O sintoma era input preto numa página clara, sem nenhuma
regra de CSS na aplicação apontando para preto.

O app é claro por design (`body` fixo em `#faf6f1`), então seguir o SO nunca foi a
intenção: `darkModeSelector: false`. E `color-scheme: light` no `:root` do
`theme.css` como defesa em profundidade — não depende do que o PrimeVue emite.

**2. A paleta `primary` default é emerald.** Todo componente PrimeVue sem override
saía verde: botão preenchido, anel de foco, seleção. O preset agora define `primary`
com a mesma escala do `sepia` do `tailwind.config.ts`.

Consequência prática: `<Button>` do PrimeVue **é preenchido por padrão**. Um botão
secundário ("Cancelar", "Reaplicar ao histórico") precisa de `!bg-transparent` ou
`!bg-white` explícito, senão vira um bloco de cor ao lado do botão primário.

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

**6. Previdência privada não é `type: "PENSION"`.**
Na Pluggy é `type: "SECURITY"` com `subtype` em `RETIREMENT | PGBL | VGBL` — o enum de
tipos é `FIXED_INCOME`, `SECURITY`, `MUTUAL_FUND`, `EQUITY`, `ETF`, `COE`, e `PENSION`
não existe ([doc](https://docs.pluggy.ai/docs/investments)). O filtro era
`type in ("pension", "previdencia")`, que nunca casava: a previdência simplesmente não
aparecia.

Dois efeitos colaterais do mesmo erro de campo adivinhado:

- **Contagem dupla latente.** O laço de investimentos criava um `Investment` para tudo
  que a Pluggy devolve, previdência incluída. Corrigir só o filtro faria o mesmo ativo
  somar duas vezes no patrimônio (`InvestmentPosition.market_value` **e**
  `PensionPlan.balance`). Previdência agora sai do laço genérico.
- **`provider` não existe no payload.** O código lia esse nome e gravava string vazia
  sempre. A seguradora (`institution.insurer.name`) é o dado preciso, com fallback
  para `institution.name` e depois para a instituição da conexão.
- **`unit_price` era sempre zero.** Lia `price`; o valor da cota está em `value`.

Lição: os três eram nomes de campo plausíveis que não existem. `.get(campo, default)`
transforma nome errado em valor default silencioso — não em erro.

**7. A Pluggy não expõe previdência para todo conector.**
Depois de corrigir o filtro, a previdência da Rico continuou ausente. O
`pluggy_dump_investments` mostrou o motivo: a Rico devolve `FIXED_INCOME/DEBENTURES`,
`FIXED_INCOME/CRA`, `EQUITY/STOCK` e `MUTUAL_FUND/STOCK_FUND` — e **nenhum
`SECURITY`**.

A [tabela de cobertura](https://docs.pluggy.ai/docs/investments-coverage) confirma: a
Rico não está listada, e `Security` só existe em Caixa Econômica, Safra, Caixa
Previdência, Banco do Brasil Previdência (Brasilprev), XP, BTG, XP-Wealth, BTG-Advisor
e EQI.

Consequência de produto: previdência que não esteja num desses conectores só entra por
cadastro manual. `PensionPlan.connection` é FK obrigatória hoje, então cadastro manual
exige tornar a conexão opcional e apontar o plano direto ao usuário.

Também visível no dump: várias posições com `balance=0` (`TRXF12`, `XPML12`, `RECR12`).
São provavelmente `status: TOTAL_WITHDRAWAL` (vendidas/transferidas), e o sync grava
todas — a lista de investimentos acumula linhas zeradas. O `status` documentado
(`ACTIVE` / `PENDING` / `TOTAL_WITHDRAWAL`) é o sinal para filtrar; não feito.

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
**Status:** Em andamento

- Criar dashboard principal ✅
- Evolução patrimonial no tempo ✅
- Fluxo de caixa mensal ✅ (12 meses via `GET /api/v1/cash-flow/` sem query params)
- Percentual de poupança ✅
- Distribuição por classe de ativo ✅
- Visão de passivos e compromissos futuros — parcial: `LiabilitiesBreakdown` separa
  cartões de dívidas e a visão de assinaturas mostra os vencimentos dos próximos 30
  dias. Falta unificar num calendário único com os vencimentos de fatura de cartão.
- Visão de assinaturas: vencimento, status de pagamento e valor total recorrente ✅
  (`subscriptionOverview` + `SubscriptionsOverview.vue`: total recorrente, pago e
  pendente no mês, atrasados em destaque, próximos vencimentos)
- Indicadores para liberdade financeira ✅ (`financialFreedomProjection`)
  - renda passiva estimada
  - despesas mensais médias
  - runway financeiro
  - meta de patrimônio-alvo

Os gráficos (`NetWorthChart`, `CashFlowChart`) são `div`s com `height` em
porcentagem — sem eixos, escala ou tooltip real. Suficiente para ler a tendência,
insuficiente para análise.

#### Um `immediate: false` esconde a fase inteira

O card de liberdade financeira nunca renderizou: o `useFetch` em `dashboard.vue`
tinha `immediate: false` e nada chamava `execute()`. O dashboard sempre caía no
empty state "Calcule suas projeções conectando instituições", mesmo com dados
sincronizados — o que fez a fase parecer não iniciada. Corrigido usando o
composable `useFinancialFreedom`, que já existia e nunca era importado.

### Fase 5 - Planejamento de Liberdade Financeira
**Status:** Em andamento

- Definir metas financeiras personalizadas — `FinancialGoal` existe com CRUD e UI,
  mas **não alimenta a projeção**
- Calcular projeções com taxa de aporte e retorno esperados — parcial: o cálculo
  existe, mas as premissas são fixas no código
- Simular cenários conservador, base e agressivo ✅ (4% / 8% / 12% a.a. hardcoded)
- Acompanhar distância até a independência financeira ✅
- Identificar gargalos de consumo e concentração de risco — **falta**

Premissas embutidas em `resolve_financial_freedom_projection` que o usuário ainda
não controla: alvo fixo em 25× as despesas anuais (regra dos 4%), retornos fixos,
médias apuradas sobre 3 meses. As médias usam `now - timedelta(days=30 * i)` como
"mês anterior", o que erra as bordas — a mesma aproximação aparece em
`estimated_retire_date` (`months_to_freedom * 30` dias).


### Fase 6 - Refinamento e Escala
**Status:** Em andamento

- Alertas e notificações ✅ in-app, derivados do estado atual (sino no cabeçalho)
- Categorização assistida por regras ✅ (tela `/rules` com CRUD, ativar/desativar e
  reaplicação ao histórico)
- Importação manual complementar — **falta**
- Exportação CSV ✅ (`GET /api/v1/export/transactions.csv`). Excel — **falta**
- Relatórios periódicos — **falta**. Depende de persistir notificação: um resumo
  gerado pelo beat às 03:30 não tem onde esperar o usuário. Fica junto da auditoria,
  que também mexe em models.
- Auditoria e trilha de mudanças — **adiada** por decisão
- Performance, cache e otimização de consultas GraphQL ✅ paginação, N+1 e
  memoização por requisição. Cache em Redis — ver abaixo.

#### Alertas derivados, sem model de notificação

Quatro fontes: pagamento atrasado (`danger`), vencimento em 7 dias (`info`), conexão
com erro (`danger`) e conexão sem sincronizar há mais de 3 dias (`warning`).
Ordenados por gravidade, porque o contador no cabeçalho mostra os primeiros — aviso
informativo antes de conexão quebrada esconderia o que precisa de ação.

**Não há tabela de notificações de propósito.** Um alerta derivado desaparece quando
a condição se resolve (pagamento marcado como pago, conexão reconectada). Uma tabela
precisaria de marcação de lido, expiração e limpeza — e ainda assim mostraria alerta
de problema que já passou.

A entrega em tempo real saiu de graça: `useRealtimeSync` já chama `refreshNuxtData()`
a cada evento de sync, então a consulta de alertas (um `useAsyncData`) se refaz sozinha
pelo WebSocket, sem polling.

Duas calibragens que evitam ruído: a janela de vencimento próximo é de 7 dias e não
30 (a visão de assinaturas já mostra 30; alerta com a mesma janela dispararia sempre,
porque há sempre algo vencendo no mês), e conexão `PENDING` não conta como sync
atrasado — ela ainda não sincronizou por definição.

#### Cache: memoização por requisição, não Redis

`financialSummary` e `financialFreedomProjection` recalculavam o resumo patrimonial
cada um por conta, e o dashboard pede os dois na mesma query — iterando as contas
duas vezes por carga de tela. Agora o resultado é memoizado no objeto da requisição.

Redis ficou de fora deliberadamente: é o único nível que precisa de invalidação, e
cache de saldo com invalidação errada mostra **dinheiro errado**, o que é pior que
mostrar devagar. O gancho natural existe (fim do sync), mas cada caminho de escrita
precisaria ser coberto — transação, assinatura, snapshot, webhook de deleção.

#### Regra do usuário perdia para a categoria do provedor

`normalize_transaction_category` checava `provider_category` **antes** das regras.
Uma regra "uber → transporte" nunca se aplicava, porque a Pluggy manda "Travel" —
intenção explícita do usuário perdendo para heurística do provedor. A ordem foi
invertida: regra do usuário primeiro, depois `provider_category`, depois
palavras-chave, depois o padrão por tipo.

**É mudança de comportamento**: transações reimportadas ou reprocessadas podem
trocar de categoria em relação ao que estava antes.

E as regras rodavam somente no import, então criar uma regra não mexia em nada já
gravado — a tela ficaria sem efeito visível. Daí `POST
/api/v1/categorization-rules/reapply/`, que devolve quantos lançamentos mudaram.
Síncrono de propósito: quem clica quer o número, e uma task Celery obrigaria a UI a
ficar consultando status. As regras são lidas uma vez e a gravação é em lote, então
o custo não cresce por transação.

#### Paginação: só onde a coleção não tem teto

Transações e sync jobs crescem sem limite e passaram a vir paginados
(`{count, next, previous, results}`, 100 por página, teto de 500 via `page_size`).
Sem o teto, `?page_size=999999` derrota a paginação.

Contas, cartões, investimentos, previdência, assinaturas e conexões continuam como
array puro, de propósito: são coleções naturalmente pequenas, e paginar tudo mudaria
a forma da resposta em oito telas sem ganho. Há teste travando as duas decisões.

Antes disso `/transactions/` devolvia o histórico inteiro e o frontend cortava as 100
primeiras no cliente — o resto viajava pela rede só para ser descartado.

**Ligar paginação quebra todo consumidor que espera array.** `useDashboardMetrics`
somava as transações do mês no cliente e passou a receber `{count, results}` —
`transactions.filter is not a function`. A correção não foi ler `.results`: somar
`.results` daria só os 100 primeiros lançamentos do mês, errado em silêncio. Os cards
agora leem `/cash-flow/?year=&month=`, que o backend agrega no banco. Efeito colateral
bom: os cards e o gráfico de fluxo de caixa passaram a usar a mesma fonte — antes
podiam divergir, porque a soma no cliente ignorava as assinaturas.

#### `/cash-flow/` muda o tipo conforme os parâmetros

Sem `year`/`month` a view monta o dicionário à mão com `float(...)` e devolve
**números**. Com `year`/`month` passa pelo `MonthlyCashFlowSerializer`, e
`DecimalField` do DRF serializa como **string** (`COERCE_DECIMAL_TO_STRING=True`, o
default, não sobrescrito). O mesmo endpoint devolve `5000` ou `"5000.00"` dependendo
da query.

Todo consumidor no frontend envolve em `Number()`, então funciona — mas é armadilha
para o próximo. Uniformizar exige decidir entre `COERCE_DECIMAL_TO_STRING=False`
(muda a forma de toda resposta com decimal) ou converter na view.

#### N+1 encontrados

- `SyncJobSerializer` expõe `connection.institution.name`, mas o viewset fazia
  `select_related("connection")` — uma query por job para buscar a instituição.
- `InvestmentPositionType` expõe `investment` no GraphQL sem `select_related`.
- `resolve_financial_freedom_projection` chamava `build_monthly_cash_flow` **seis
  vezes** para os mesmos três meses: um laço para a média de poupança, outro para a
  de despesa. Agora é `build_recent_month_averages`, uma leitura por mês.

Os três só aparecem em contagem de query — N+1 não muda a resposta, só a fatura.

#### Aritmética de mês, de novo

Ao deduplicar a projeção, os dois usos de `timedelta(days=30 * n)` que estavam
registrados como risco foram substituídos por aritmética de calendário
(`previous_month_keys` e `add_months`):

- `hoje - 30 dias` a partir de 31/03 cai em 01/03 — o mesmo mês. A média de 3 meses
  podia contar março duas vezes e pular fevereiro.
- `estimated_retire_date` usava `meses * 30 dias`, o que em 120 meses erra ~52 dias.


### Fase 7 - Análise Inteligente de Portfolio com IA
**Status:** Concluída

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
  - Backend: endpoint REST `/api/v1/ai/portfolio-report/` ✅
  - Frontend: página/assistant integrada ao dashboard ✅ (`/ai-report` renderiza
    resumo, pontos fortes/fracos, ajustes, sugestões, projeções e fontes; aceita um
    foco de análise opcional)
- Critérios de qualidade:
  - Respostas fundamentadas nos dados reais do usuário (sem alucinação) — o prompt
    proíbe inventar valores e instituições, e o contexto vem só do índice do próprio
    usuário; sem avaliação sistemática ainda
  - Rastreabilidade das fontes usadas pela LLM ✅ A resposta traz `sources` com
    tipo/id/similaridade do que foi **recuperado**, não do que a LLM diz ter usado,
    e a UI exibe isso.
  - Moderação de conteúdo financeiro sensível ✅ Ver abaixo.
  - Custos controlados por requisição/usuário ✅ na prática: reindexa só o que mudou,
    então um relatório repetido não regera embedding nenhum
  - 100% offline/local sem envio de dados para APIs externas ✅ **agora garantido em
    código**, não só por convenção

#### Moderação: o que foi decidido

Três medidas, em ordem de importância:

**1. Inferência remota é recusada por padrão.** A promessa de "100% local" não era
garantida por nada: um `OLLAMA_URL` apontando para fora exportaria saldos,
transações, instituições e metas em silêncio — é o dado mais sensível da aplicação
saindo por configuração. `assert_local_inference` recusa host não-local no `__init__`
dos dois serviços, e a resposta é `503` com a razão. `AI_ALLOW_REMOTE_INFERENCE=true`
libera, para o caso de o envio ser intencional.

**2. Disclaimer não negociável pelo modelo.** A resposta sempre carrega
`REPORT_DISCLAIMER` (não é recomendação de investimento nem consultoria), aplicado
**depois** dos campos vindos da LLM — se o modelo devolver a chave `disclaimer`, ela
é sobrescrita.

**3. Contrato de saída fechado.** A LLM devolve JSON livre, e `normalize_report`
força a forma que a UI renderiza: campos de texto viram texto (lista é unida), campos
de lista viram lista (parágrafo é quebrado por linha, `[{...}]` é achatado), e chave
fora do contrato é descartada. Sem isso a tela quebrava na primeira variação de
formato e o usuário via painel vazio sem saber por quê.

Fica de fora, e vale registrar: não há verificação de que os números citados no texto
existem no contexto. Uma checagem ingênua marcaria como inventado todo valor derivado
(percentual, soma) que o modelo calcula corretamente — e um alerta que dispara em caso
legítimo treina o usuário a ignorá-lo.

#### A stack de vetores agora é a descrita acima

As três lacunas registradas antes estão fechadas. O que valeu aprender:

**1. `pgvector` estava na imagem, não no código.** `Embedding.vector` era `JSONField`
e a similaridade era cosseno em Python varrendo todos os chunks do usuário. Agora é
`VectorField(dimensions=768)` com índice HNSW e busca via `CosineDistance` no
Postgres. Três detalhes que silenciam se errados:

- `CREATE EXTENSION vector` precisa rodar **antes** de qualquer coluna `vector`. A
  imagem `pgvector/pgvector` traz a extensão disponível, mas habilitar por banco é
  responsabilidade da migration (`VectorExtension()`), e o `makemigrations` não emite
  isso.
- O índice HNSW tem de usar a mesma classe de operador da busca
  (`vector_cosine_ops` para `CosineDistance`). Com a classe errada o índice é
  simplesmente ignorado pelo planner — sem erro, só lento.
- **`jsonb` não converte para `vector`, nem com a tabela vazia.** O `AlterField` que
  o `makemigrations` gera emite `ALTER COLUMN ... TYPE vector(768) USING
  vector::vector(768)`, e o Postgres rejeita esse cast no planejamento: não existe
  coerção entre os tipos. Apagar as linhas antes não ajuda — o erro é na expressão,
  não na conversão de linha. A migration faz `RemoveField` + `AddField`, o que só é
  aceitável porque a coluna guarda dado derivado.

**2. O índice duplicava a cada relatório.** `index_user_context` fazia `create()` e a
view chamava a cada POST. Agora é `update_or_create` com constraint única em
(`user`, `source_type`, `source_id`), e só reindexa o documento cujo `content_hash`
mudou — ou que foi embedado por outro modelo, porque vetor de outro modelo vive em
outro espaço e comparar daria similaridade sem significado. Domínio que deixou de
existir sai do índice, senão a LLM cita cartão que foi removido.

**3. Existia um único chunk.** Todo o contexto virava um documento
`financial_summary`, o que torna `top_k` inútil: os cinco resultados eram o mesmo
texto. Agora há um documento por domínio (contas, cartões, investimentos,
previdência, metas, assinaturas, regras, histórico de sync) mais **um por mês** de
transações — a pergunta sobre transação costuma ser temporal, e um bloco único com
todo o histórico venceria a busca por tamanho, não por relevância.

O resumo patrimonial entra sempre no contexto do relatório, fora da disputa de
similaridade: um mês de transações tem muito mais texto sobre qualquer assunto
específico e ganharia dele.

**Dimensão é fixa na coluna.** `nomic-embed-text` produz 768. Trocar
`OLLAMA_EMBEDDING_MODEL` por um modelo de outra dimensão exige migration; o
`RAGService` confere o tamanho antes de gravar para a falha aparecer como mensagem
acionável em vez de erro de inserção do Postgres.

**Ollama fora do ar responde 503, não 500.** Rodando local, "esqueci de subir o
Ollama" é o caso comum, e a mensagem diz qual URL e qual modelo falharam.

**O corpo do erro do Ollama precisa chegar ao usuário.** `raise_for_status()` produz
`404 Client Error` e descarta o corpo — mas é o corpo que diz o que fazer: modelo não
baixado responde `404 {"error": "model \"X\" not found, try pulling it first"}`,
indistinguível de endpoint inexistente se a mensagem for perdida. `_ollama_post`
repassa a mensagem e acrescenta o comando de pull quando o erro é de modelo ausente.


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
- Geração automática de pagamentos pendentes ao longo do tempo com base em `due_day` ✅
  (`_reconcile_subscriptions`, janela de -3 a +6 meses, agora também no beat diário)
- Reconciliação automática com transações importadas (Pluggy) quando o pagamento é detectado ✅
- Marcação manual de pago/pendente para contas não conectadas ✅
  (PATCH em `/subscription-payments/{id}/`, botão na página `/subscriptions`)
- Alerta de vencimento próximo e pagamentos atrasados — parcial: o dashboard destaca
  atrasados e lista os próximos 30 dias; não há notificação fora da tela (Fase 6)

`due_day` tem validators de 1 a 31 no modelo. Sem eles um dia fora do calendário não
estourava: `_due_date_for` cai no dia 28 e o vencimento virava outro em silêncio —
irrelevante enquanto o dado vinha só de seed, e importante com input de usuário.

Marcação manual sobrevive ao sync seguinte: `_reconcile_subscriptions` só promove a
`overdue` o que está `pending`, e nunca rebaixa um `paid`. Sem isso o recurso não
serviria justamente para a conta que não vem de instituição conectada.


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

O schema é somente leitura: não há `Mutation` nem `Subscription`. Toda escrita
passa por REST, e o tempo real por WebSocket (Channels).

#### O endpoint estava inalcançável pelo navegador

`GraphQLView` é uma view Django comum, e isso quebrava de duas formas com um cliente
que autentica por JWT:

1. **CSRF.** Sem `csrf_exempt`, todo POST do navegador levava `403 CSRF cookie not
   set`. A API não usa cookie de sessão, então não existe token de CSRF a enviar.
2. **Autenticação.** `request.user` vinha do `AuthenticationMiddleware`, que lê sessão
   e **ignora o header `Authorization`**. Mesmo sem o CSRF, todo resolver veria
   anônimo e devolveria vazio — com status 200, sem sinal de erro.

`JWTGraphQLView` (`apps/finance/graphql_view.py`) resolve os dois. Token inválido
responde `401` de propósito: cair para anônimo devolveria 200 com dados vazios, e o
cliente trataria sessão expirada como "usuário sem dados". Sem header, mantém o que o
middleware resolveu, o que preserva o GraphiQL para quem está logado no `/admin`.

**Rever quando existir `Mutation`:** com CSRF desligado e a sessão ainda válida como
fallback, uma escrita futura ficaria exposta a CSRF via cookie do `/admin`. Hoje não
há mutation, e o CORS impede leitura cross-origin da resposta.

#### A lacuna de teste que deixou isso passar

`test_graphql_schema.py` chama `schema.execute()` direto e atribui `request.user` à
mão. Isso valida resolver e isolamento entre usuários, e **não passa perto da camada
HTTP** — então um schema inteiro correto ficou atrás de um endpoint que respondia 403.

`test_graphql_endpoint.py` cobre o buraco, com dois cuidados que o próprio teste
exige:

- `Client()` do Django **desliga CSRF por padrão**. Sem `enforce_csrf_checks=True` o
  teste passaria com o bug presente.
- Verificar só o status não basta: "autenticado como anônimo" devolve 200. O teste
  compara o conteúdo com o dado esperado do usuário.

Campos expostos hoje: `institutions`, `accounts`, `netWorthHistory`,
`financialSummary`, `monthlyCashFlow`, `investmentDistribution`,
`financialFreedomProjection`, `subscriptions`, `subscriptionPayments`,
`categorizationRules`, `pensionPlans`, `investmentPositions`,
`subscriptionOverview`, `alerts`.

A agregação vive em `consolidation.py` (`build_subscription_overview` ao lado de
`build_user_financial_summary` e `build_monthly_cash_flow`); o resolver só converte
`Decimal` e `date` para os tipos do GraphQL. Sem essa conversão o graphene
serializa o `repr` (`Decimal('55.00')`) — há teste travando isso.

#### Um resolver sem campo declarado desaparece em silêncio

Cinco resolvers (`resolve_subscriptions`, `resolve_subscription_payments`,
`resolve_categorization_rules`, `resolve_pension_plans`,
`resolve_investment_positions`) existiam em `graphql.py` sem o campo
correspondente na classe `Query`. Em graphene isso não gera erro de import nem de
execução: o resolver é ignorado, o campo não entra no schema, e a falha só aparece
no cliente. Os `DjangoObjectType` correspondentes ficavam órfãos junto.

`test_graphql_schema.py` trava a lista completa de campos do `Query` justamente
porque esse modo de falha é invisível — um resolver novo sem campo derruba o teste.

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
- **FK gravável é sempre escopada ao usuário autenticado.** O `ModelSerializer`
  valida FK contra a tabela inteira: qualquer id existente passa. Como
  `SubscriptionPayment.subscription`, `Subscription.connection` e
  `Subscription.payment_account` são graváveis, isso permitia pendurar a própria
  assinatura na conta bancária de outro usuário, ou criar pagamentos dentro da
  assinatura de outro. `UserScopedPrimaryKeyRelatedField` filtra pelo dono e falha
  fechada sem request autenticado no contexto.

  O teste que trava isso é uma varredura, não um caso: percorre todo viewset com
  rota de escrita e falha se qualquer FK gravável aceitar a tabela inteira. Rodar
  sem banco é de propósito — a inspeção é do `where` do queryset, que é lazy.
  Viewsets somente-leitura ficam de fora porque não expõem a FK.

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
| `mise run dev` | Stack completo em paralelo (API, worker, beat, frontend) |
| `mise run dev-tunnel` | Idem + túnel ngrok (necessário para webhooks) |
| `mise run backend-beat` | Agendador das tasks diárias (Celery beat) |
| `mise run check` | lint + typecheck + testes |
| `mise run db-backup` | Dump em `tmp/backups/` |
| `mise run db-backups` | Lista backups |
| `mise run db-restore <dump>` | Restaura (confirmação digitada) |
| `mise run db-reset` | Apaga, recria e migra do zero (backup automático antes) |

Duas armadilhas de `mise` já encontradas, registradas em comentário no `mise.toml`:
processos long-running não podem entrar em `depends` (o `depends` espera terminar), e
uma lista em `run` é sequencial — paralelismo exige `:::`.

### Tasks periódicas

`CELERY_BEAT_SCHEDULE` em `config/settings.py`:

| Task | Horário | O que faz |
|---|---|---|
| `snapshot_all_users` | 03:10 | Snapshot patrimonial de todo usuário com conexão |
| `reconcile_all_subscriptions` | 03:30 | Gera pendências do mês e marca atrasados |

Antes disso nada rodava sozinho: `recompute_user_snapshot` e
`_reconcile_subscriptions` só disparavam dentro de um sync (webhook ou ação
manual). Consequências observáveis: um mês sem sync deixava buraco no gráfico de
evolução patrimonial, e uma assinatura vencida nunca virava `overdue` — pior
justamente para contas fora de instituição conectada, que são as que dependem do
controle manual.

Três decisões que valem registro:

- **Exige `mise run backend-beat`.** O worker só executa o que alguém enfileira.
  Sem o beat de pé, o `CELERY_BEAT_SCHEDULE` é decorativo.
- **Ambas são idempotentes por dia** (`update_or_create` por data,
  `bulk_create(ignore_conflicts=True)`). Um beat que ficou fora do ar só perde os
  pontos do período; reexecutar não duplica nada.
- **Uma falha por usuário não aborta o lote.** As tasks rodam uma vez por dia e não
  há retry por usuário: um registro ruim derrubaria o snapshot de todos os outros.
  O horário (03:10) fica depois da janela de auto-sync noturna da Pluggy, para o
  snapshot pegar saldos já atualizados.

Usuário sem conexão fica fora do snapshot de propósito — um registro zerado por dia
seria ruído no gráfico.

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
5. Beat do Celery rodando? Sem ele não há snapshot diário nem reconciliação de
   assinaturas — o gráfico patrimonial fica com buraco e nada vira `overdue`.
6. Conexão com nome "MeuPluggy"? `pluggy_refine_institutions`.
7. `409` ao importar pela UI? O item pertence a outro usuário — confira com
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
- **`new Date('2026-08-10')` renderiza 09/08 em São Paulo.** Uma string ISO sem hora
  é parseada como UTC meia-noite, e o fuso (UTC-3) puxa um dia para trás. Numa tela
  de vencimentos isso é erro de conteúdo, não de formatação. `formatDueDate` em
  `useSubscriptionLabels` quebra a string em partes em vez de construir um `Date`;
  qualquer data vinda do backend como `YYYY-MM-DD` precisa do mesmo cuidado.


## Dívida técnica conhecida

- `config/asgi.py` tem `E402` (imports após `get_asgi_application()`), que é o padrão
  exigido pelo Channels. Ignorado deliberadamente.
- `pluggy-sdk` está em `pyproject.toml` mas não é usado — a integração fala com a API
  via `requests` direto. Avaliar remover ou migrar.
- A indexação do RAG é síncrona dentro do `POST /api/v1/ai/portfolio-report/`. Na
  primeira geração isso são N chamadas de embedding em sequência antes de a LLM
  começar. Candidato natural a task Celery, com a view respondendo 202.
- Cobertura de testes concentrada na integração Pluggy, na consolidação, no schema
  GraphQL e nas tasks periódicas; o restante do domínio (metas, serializers, IA)
  segue sem testes. O frontend não tem nenhum teste.
- `mise run setup` roda `docker compose up -d --force-recreate` e a task `dev` depende
  de `setup`. Verificar se o volume do Postgres é persistente, para não zerar o banco
  a cada `mise run dev`.
- Um episódio de derivação de instituição que falhou silenciosamente não teve causa
  raiz identificada. O modo de falha provável (o início do sync sobrescrever a
  instituição derivada) foi corrigido com teste, e o `refine` agora loga o resultado
  para tornar uma recorrência diagnosticável.
- `pages/login.vue:40` tem erro de parsing no ESLint (`x-invalid-end-tag`), o que
  deixa `mise run check` vermelho independentemente das outras mudanças.
- Sem paginação em nenhum endpoint de lista. `/api/v1/transactions/` devolve o
  histórico inteiro e o frontend faz `.slice(0, 100)` no cliente.
- APIs completas sem UI: nenhuma pendente.
- `useApi.get` engole todo erro e devolve `null`, o que faz uma falha de rede virar
  lista vazia — a página mostra "nenhum registro" em vez de "erro ao carregar". As
  escritas (`post`/`patch`/`del`) já propagam; a leitura continua tolerante de
  propósito, para não derrubar o dashboard num erro transitório.
- Sem cache em Redis nas consultas do dashboard. A memoização por requisição já
  elimina o recálculo duplicado do resumo patrimonial dentro de uma query, mas cargas
  sucessivas recomputam tudo. O Redis já é dependência; falta cobrir cada caminho de
  escrita na invalidação (transação, assinatura, snapshot, webhook de deleção).
- `/api/v1/cash-flow/` devolve número sem `year`/`month` e string com — ver a seção
  da Fase 6. Funciona porque o frontend usa `Number()`, mas é armadilha.
- O frontend não tem nenhum teste. Dois bugs desta rodada (403 do GraphQL e
  `transactions.filter is not a function`) passaram por `bun run build` sem
  reclamação: o build compila, não executa. Um smoke test que carregue o dashboard
  autenticado pegaria os dois.



## Próximos Passos

1. Definir o escopo exato do MVP. ✅
2. Desenhar o modelo de dados inicial. ✅
3. Criar a base do backend Django com REST e GraphQL. ✅
4. Estruturar o frontend Nuxt com layout e design system. ✅
5. Implementar a primeira integração com Pluggy. ✅
6. Construir o dashboard inicial com métricas principais. ✅
7. Expor os cinco resolvers GraphQL órfãos e destravar o card de liberdade
   financeira. ✅
8. Agendar snapshot patrimonial e reconciliação de assinaturas no Celery beat. ✅
9. Fechar a Fase 4: assinaturas no dashboard (total recorrente, próximos
   vencimentos, atrasados). ✅ Falta o calendário único de compromissos futuros,
   juntando vencimento de fatura de cartão aos vencimentos de assinatura.
10. UI de escrita para assinaturas: cadastrar, editar, ativar/desativar, excluir e
    marcar pago/pendente. ✅
11. Corrigir o RAG antes de investir na Fase 7: upsert de chunk, `pgvector` de
    verdade, chunking por domínio. ✅
12. Fase 5 com premissas do usuário: taxa de aporte, retorno esperado e alvo
    próprio, ligando `FinancialGoal` à projeção.
13. Fechar a Fase 7: UI do relatório, exibição das fontes e moderação. ✅
14. Fase 6 - Refinamento e Escala. Feito: categorização por regras (com
    reaplicação), exportação CSV, paginação, N+1, memoização por requisição e
    alertas in-app. Falta: importação manual, exportação Excel, cache em Redis,
    e — adiados por decisão, ambos por mexerem em models — auditoria e relatórios
    periódicos.
