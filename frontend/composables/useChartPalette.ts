// Paleta categorica validada (contraste e daltonismo) para fundo branco --
// tons fora da escala sepia de proposito: fatias vizinhas de um grafico de
// rosca precisam se distinguir de relance, o que tons de uma mesma cor nao
// garantem. Vermelho fica de fora porque no app ele significa saldo negativo.
export const CHART_PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#4a3aa7']

// "Outros"/agrupado: neutro, para nao competir com as categorias reais.
export const CHART_OTHER_COLOR = '#ad8a54'

// Cor fixa por categoria de investimento (mesma chave de `display_category`):
// a cor segue a categoria em todas as telas, nao a posicao no ranking.
export const INVESTMENT_CATEGORY_COLORS: Record<string, string> = {
  fixed_income: CHART_PALETTE[0],
  equity_br: CHART_PALETTE[1],
  fii: CHART_PALETTE[2],
  equity_intl: CHART_PALETTE[3],
  etf: CHART_PALETTE[4],
  mutual_fund: CHART_PALETTE[5],
  coe: CHART_OTHER_COLOR,
  other: CHART_OTHER_COLOR,
}
