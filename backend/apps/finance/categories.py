"""Traducao das categorias da Pluggy para pt-BR.

O categorizador da Pluggy devolve a categoria em ingles (`Bookstore`,
`Vehicle maintenance`), e esse texto ia direto para a tela.

O mapa abaixo cobre a arvore documentada em https://docs.pluggy.ai/docs/transaction-categories
(niveis 1 a 3). A Pluggy tambem expoe `descriptionTranslated` no `GET /categories`,
que seria a fonte canonica -- usar aquilo exigiria gravar o `categoryId` da transacao
e sincronizar a arvore, o que nao esta feito. Ate lá, o mapa e estatico e o que nao
estiver nele passa intacto, entao categoria nova aparece em ingles em vez de virar
"Outros" silenciosamente.

A comparacao ignora caixa e espacos nas bordas: os nomes chegam do provedor e nao ha
garantia de capitalizacao estavel.
"""

# Fallbacks internos, usados quando nem a Pluggy nem uma regra classificam.
CATEGORY_INCOME = "Receitas"
CATEGORY_EXPENSES = "Despesas"
CATEGORY_UNCATEGORIZED = "Sem categoria"

PLUGGY_CATEGORY_PT: dict[str, str] = {
    # Nivel 1
    "income": "Receitas",
    "loans and financing": "Empréstimos e financiamentos",
    "investments": "Investimentos",
    "same person transfer": "Transferência entre contas próprias",
    "transfers": "Transferências",
    "legal obligations": "Obrigações legais",
    "services": "Serviços",
    "shopping": "Compras",
    "digital services": "Serviços digitais",
    "groceries": "Supermercado",
    "food and drinks": "Alimentação",
    "travel": "Viagens",
    "donations": "Doações",
    "gambling": "Apostas",
    "taxes": "Impostos",
    "bank fees": "Tarifas bancárias",
    "housing": "Moradia",
    "healthcare": "Saúde",
    "transportation": "Transporte",
    "insurance": "Seguros",
    "leisure": "Lazer",
    "other": "Outros",
    # Receitas
    "salary": "Salário",
    "retirement": "Aposentadoria",
    "entrepreneurial activities": "Atividades empreendedoras",
    "government aid": "Auxílio governamental",
    "non-recurring income": "Receita não recorrente",
    # Empréstimos e financiamentos
    "late payment and overdraft costs": "Juros de atraso e cheque especial",
    "interests charged": "Juros cobrados",
    "loans": "Empréstimos",
    "financing": "Financiamentos",
    "real estate financing": "Financiamento imobiliário",
    "vehicle financing": "Financiamento de veículo",
    "student loan": "Financiamento estudantil",
    # Investimentos
    "automatic investment": "Investimento automático",
    "fixed income": "Renda fixa",
    "mutual funds": "Fundos de investimento",
    "variable income": "Renda variável",
    "margin": "Margem",
    "proceeds interests and dividends": "Proventos, juros e dividendos",
    "pension": "Previdência",
    # Transferências
    "same person transfer - cash": "Transferência própria - Dinheiro",
    "same person transfer - pix": "Transferência própria - PIX",
    "same person transfer - ted": "Transferência própria - TED",
    "transfer - bank slip (boleto)": "Transferência - Boleto",
    "transfer - cash": "Transferência - Dinheiro",
    "transfer - check": "Transferência - Cheque",
    "transfer - doc": "Transferência - DOC",
    "transfer - foreign exchange": "Transferência - Câmbio",
    "transfer - internal": "Transferência - Interna",
    "transfer - pix": "Transferência - PIX",
    "transfer - ted": "Transferência - TED",
    "credit card payment": "Pagamento de cartão de crédito",
    "third-party transfers": "Transferências para terceiros",
    "bank slip": "Boleto",
    "debt card": "Cartão de débito",
    "doc": "DOC",
    "pix": "PIX",
    "ted": "TED",
    # Obrigações legais
    "blocked balances": "Saldos bloqueados",
    "alimony": "Pensão alimentícia",
    # Serviços
    "telecommunications": "Telecomunicações",
    "internet": "Internet",
    "mobile": "Telefonia móvel",
    "tv": "TV",
    "education": "Educação",
    "online courses": "Cursos online",
    "university": "Faculdade",
    "school": "Escola",
    "kindergarten": "Educação infantil",
    "wellness and fitness": "Bem-estar e fitness",
    "gyms and fitness centers": "Academias",
    "sports practice": "Prática esportiva",
    "wellness": "Bem-estar",
    "tickets": "Ingressos",
    "stadiums and arenas": "Estádios e arenas",
    "landmarks and museums": "Pontos turísticos e museus",
    "cinema, theater and concerts": "Cinema, teatro e shows",
    # Compras
    "online shopping": "Compras online",
    "electronics": "Eletrônicos",
    "pet supplies and vet": "Pet shop e veterinário",
    "clothing": "Vestuário",
    "kids and toys": "Infantil e brinquedos",
    "bookstore": "Livraria",
    "sports goods": "Artigos esportivos",
    "office supplies": "Material de escritório",
    "cashback": "Cashback",
    # Serviços digitais
    "gaming": "Jogos",
    "video streaming": "Streaming de vídeo",
    "music streaming": "Streaming de música",
    # Alimentação
    "eating out": "Restaurantes",
    "food delivery": "Delivery de comida",
    # Viagens
    "airport and airlines": "Aeroportos e companhias aéreas",
    "accommodation": "Hospedagem",
    "mileage programs": "Programas de milhas",
    "bus tickets": "Passagens de ônibus",
    # Apostas
    "lottery": "Loteria",
    "online bet": "Apostas online",
    # Impostos
    "income taxes": "Imposto de renda",
    "taxes on investments": "Impostos sobre investimentos",
    "tax on financial operations": "IOF",
    # Tarifas bancárias
    "account fees": "Tarifas de conta",
    "wire transfer fees and atm fees": "Tarifas de transferência e saque",
    "credit card fees": "Tarifas de cartão de crédito",
    # Moradia
    "rent": "Aluguel",
    "houseware": "Utensílios domésticos",
    "urban land and building tax": "IPTU",
    "utilities": "Utilidades",
    "water": "Água",
    "electricity": "Energia elétrica",
    "gas": "Gás",
    # Saúde
    "dentist": "Dentista",
    "pharmacy": "Farmácia",
    "optometry": "Ótica",
    "hospital clinics and labs": "Hospitais, clínicas e laboratórios",
    # Transporte
    "taxi and ride-hailing": "Táxi e aplicativos",
    "public transportation": "Transporte público",
    "car rental": "Aluguel de carro",
    "bicycle": "Bicicleta",
    "automotive": "Automotivo",
    "gas stations": "Postos de combustível",
    "parking": "Estacionamento",
    "tolls and in-vehicle payment": "Pedágios",
    "vehicle ownership taxes and fees": "IPVA e taxas",
    "vehicle maintenance": "Manutenção de veículo",
    "traffic tickets": "Multas de trânsito",
    # Seguros
    "life insurance": "Seguro de vida",
    "home insurance": "Seguro residencial",
    "health insurance": "Plano de saúde",
    "vehicle insurance": "Seguro de veículo",
}


def translate_category(value: str | None) -> str:
    """Traduz uma categoria da Pluggy, ou devolve o valor original.

    Devolver o original em vez de um generico e deliberado: categoria nova da Pluggy
    aparece em ingles, o que e visivel e corrigivel, ao contrario de virar "Outros"
    e se misturar ao resto.
    """
    if not value:
        return ""
    return PLUGGY_CATEGORY_PT.get(value.strip().lower(), value.strip())
