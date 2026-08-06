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
**Status:** Em andamento (sync de contas, transações, cartões e investimentos implementado)

- Implementar conexão com Pluggy
- Criar fluxo de consentimento e vínculo de instituição
- Sincronizar contas e transações
- Sincronizar cartões, saldos e investimentos quando disponíveis
- Persistir status de sincronização e erros
- Criar reprocessamento e atualização incremental

### Fase 3 - Consolidação Financeira
**Status:** Em andamento (consolidação inicial implementada)

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

### Fase 4 - Dashboard e Análises
**Status:** Não iniciada (há apenas dashboard base)

- Criar dashboard principal
- Evolução patrimonial no tempo
- Fluxo de caixa mensal
- Percentual de poupança
- Distribuição por classe de ativo
- Visão de passivos e compromissos futuros
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

### Relações importantes
- Um usuário possui várias conexões com instituições
- Uma conexão possui várias contas e cartões
- Uma conta possui várias transações e saldos históricos
- Um investimento pode ter várias posições e histórico de valuation
- Um usuário pode ter várias metas financeiras

## API e Contratos

### REST
Usar REST para:
- autenticação
- gerenciamento de integrações
- execução de sync jobs
- ações operacionais
- upload/importação manual
- administração

### GraphQL
Usar GraphQL para:
- dashboard
- análises agregadas
- consultas profundas e compostas
- detalhamento de patrimônio
- projeções financeiras
- visualizações por período e categoria

## Segurança e Privacidade

- Autenticação segura
- Tokens com expiração e rotação
- Criptografia de dados sensíveis em repouso
- Segregação de credenciais do Pluggy
- Auditoria de acesso e sincronização
- Minimização de dados armazenados
- Validação forte de entrada e proteção contra abuso

## Observabilidade

- Logs estruturados
- Métricas de sincronização
- Rastreamento de falhas de integração
- Monitoramento de jobs assíncronos
- Alertas para integrações quebradas ou dados desatualizados

## Critérios de Sucesso do MVP

- Usuário consegue conectar instituições via Pluggy
- Dados financeiros aparecem consolidados no dashboard
- Patrimônio líquido é calculado corretamente
- Fluxo de caixa mensal é visível
- O sistema mostra progresso rumo à liberdade financeira
- Sincronização é estável e reexecutável

## Riscos e Pontos de Atenção

- Qualidade e disponibilidade dos dados retornados pelo Pluggy
- Normalização de categorias entre instituições diferentes
- Diferenças entre saldo contábil e saldo disponível
- Tratamento de investimentos com estrutura complexa
- Privacidade e compliance com dados financeiros

## Próximos Passos

1. Definir o escopo exato do MVP.
2. Desenhar o modelo de dados inicial.
3. Criar a base do backend Django com REST e GraphQL.
4. Estruturar o frontend Nuxt com layout e design system.
5. Implementar a primeira integração com Pluggy.
6. Construir o dashboard inicial com métricas principais.