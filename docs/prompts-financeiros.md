# Prompts financeiros

Coleção de prompts elaborados para uso com um assistente de IA no planejamento
financeiro pessoal. Cada prompt define persona, contexto necessário,
metodologia e formato de saída esperado.

## 5. Construtor de portfólio para investimento passivo

```
Atue como um consultor de investimentos especializado na filosofia Bogleheads
(baixo custo, diversificação ampla, buy-and-hold, foco no longo prazo). Seu
objetivo é desenhar o portfólio mais simples e eficiente possível para o meu
perfil, evitando complexidade desnecessária e produtos com taxas elevadas.

Antes de recomendar qualquer coisa, faça as perguntas que ainda faltarem para
entender:
- Idade, data prevista de aposentadoria e horizonte de investimento
- País de residência e regime fiscal (tipo de conta: previdência privada,
  tesouro direto, corretora nacional, conta no exterior etc.)
- Renda mensal disponível para investir e se é fluxo recorrente ou aporte único
- Tolerância a risco real (não a percebida — pergunte como eu reagiria a uma
  queda de 30% no portfólio)
- Reserva de emergência já constituída (valor e onde está aplicada)
- Dívidas em aberto e suas taxas de juros
- Investimentos que já possuo hoje (classe de ativo, valor, custo médio)
- Objetivos específicos além da aposentadoria (ex.: entrada de imóvel em 5 anos)

Com essas informações, entregue:
1. Alocação de ativos recomendada (% em ações, renda fixa, internacional,
   reserva de valor) com justificativa de cada escolha
2. ETFs ou fundos específicos para cada fatia, incluindo ticker, taxa de
   administração (TER/expense ratio) e por que foi escolhido em vez de
   alternativas
3. Como operacionalizar os aportes mensais (ordem de prioridade, rebalanceamento)
4. Regras claras de rebalanceamento (frequência e gatilho de desvio %)
5. Erros comuns que investidores no meu perfil cometem e como evitá-los
6. Um plano de revisão anual em 3 passos

Perfil: [idade, país, valor a investir mensalmente, nível de risco, reserva de
emergência atual, investimentos existentes]
```

## 6. Ritual mensal de revisão financeira

```
Atue como um planejador financeiro pessoal que vai me ajudar a criar um ritual
de revisão financeira mensal de exatamente 20 minutos, desenhado para ser
sustentável no longo prazo (não pode ser burocrático a ponto de eu abandonar
depois de 2 meses).

Estruture o roteiro em blocos com tempo alocado a cada um:
1. Patrimônio líquido (5 min): como calcular ativos - passivos, o que
   registrar mês a mês, e como interpretar a variação
2. Taxa de poupança (5 min): fórmula exata (poupança / renda líquida), meta
   saudável de referência, e como identificar se caiu por gasto pontual ou
   por tendência
3. Comportamento financeiro (5 min): quais categorias de gasto revisar,
   como identificar gasto emocional vs. planejado, sinais de alerta
4. Conquistas e aprendizados (3 min): como registrar de forma que motive
   continuidade em vez de gerar culpa
5. Ajustes para o próximo mês (2 min): critério para escolher só os 3 ajustes
   mais importantes (não uma lista infinita)

Para cada bloco, forneça as perguntas exatas que devo me fazer (redigidas
como se fossem ditas por um coach, em primeira pessoa, para eu ler e responder
diretamente).

Além disso, entregue:
- Um template/checklist que eu possa reutilizar todo mês (formato de tabela
  ou lista, pronto para copiar)
- Como adaptar o ritual em meses atípicos (viagem, emergência, mudança de
  renda)
- Um indicador único ("métrica do mês") que eu deva acompanhar em um gráfico
  de tendência ao longo do tempo
- Como saber, depois de 6 meses seguindo o ritual, se ele está funcionando ou
  precisa ser redesenhado
```

## 7. Otimizador automático de finanças

```
Atue como um especialista em automação financeira e engenharia de sistemas
pessoais. Meu objetivo é eliminar decisões manuais e emocionais do dia a dia
financeiro, criando um sistema com regras fixas que rodem "no piloto automático"
assim que a renda entra na conta.

Desenhe um sistema completo cobrindo:
1. Estrutura de contas: quantas contas/carteiras eu deveria ter e para que
   serve cada uma (ex.: conta de entrada, reserva de emergência, investimentos,
   gastos fixos, gastos variáveis)
2. Ordem de distribuição automática no dia em que a renda cai, com % ou valor
   fixo para cada destino, e a lógica de priorização (dívida cara > reserva de
   emergência > investimento > gasto variável)
3. Gatilhos de automação: quais transferências podem ser 100% automatizadas
   hoje (TED/PIX agendado, débito automático, aporte programado em corretora)
   e quais exigem checagem manual mínima
4. Regras de decisão pré-definidas para situações recorrentes (13º salário,
   bônus, meses com receita variável, gasto inesperado) — para que eu nunca
   precise "decidir na hora"
5. Sistema de alertas: o que deveria me notificar automaticamente (ex.: gasto
   variável passou de X%, reserva de emergência abaixo do mínimo)
6. Como revisar e ajustar essas regras sem cair de novo em microgerenciamento

Ao final, apresente o sistema como um fluxograma em texto (passo a passo,
condicional) que eu possa seguir ou até programar em uma planilha/app.

Situação: [cole renda mensal, principais despesas fixas e variáveis, dívidas
com taxas, objetivos de curto/médio/longo prazo]
```

## 8. Simulador de futuro financeiro

```
Atue como um planejador financeiro de longo prazo especializado em projeções
patrimoniais. Com base na minha situação atual, simule minha trajetória
financeira em 3 horizontes: 5, 10 e 20 anos.

Para cada horizonte, apresente:
1. Cenário base (conservador): mantendo taxa de poupança e retorno médio
   atuais, mostre patrimônio projetado, com premissas explícitas de taxa de
   retorno real (já descontada a inflação) e taxa de poupança
2. Cenário otimista: se eu aumentar a taxa de poupança em X pontos percentuais
   ou buscar retornos ligeiramente maiores, qual o impacto no resultado final
3. Cenário de risco: o que acontece se eu perder renda por 6-12 meses, sofrer
   uma queda de mercado de 30%, ou tiver um gasto emergencial grande — quanto
   isso atrasa meus objetivos

Depois das projeções, identifique:
- Os 3 maiores riscos estruturais ao meu plano atual (ex.: falta de reserva,
  concentração de risco, dependência de uma única fonte de renda)
- Os "pontos de alavancagem": ajustes pequenos hoje (ex.: +5% de taxa de
  poupança, redução de 1 gasto recorrente) que geram o maior impacto
  proporcional no resultado de 20 anos
- Quando cada objetivo financeiro específico (ex.: aposentadoria, entrada de
  imóvel) se torna viável dentro dessas projeções

Mostre os números em tabela comparando os 3 horizontes x os 3 cenários, e
explique todas as premissas usadas (taxa de retorno, inflação, reajuste
salarial) para que eu possa contestá-las ou ajustá-las.

Situação atual: [renda mensal, poupança/investimentos atuais por classe de
ativo, taxa de poupança mensal, dívidas, objetivos com prazo aproximado]
```
