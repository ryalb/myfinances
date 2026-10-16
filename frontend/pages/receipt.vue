<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import DatePicker from 'primevue/datepicker'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { formatBRL } from '@/composables/useCurrency'
import { toIsoDateString } from '@/composables/useDateFormat'
import { usePageLoading } from '@/composables/usePageLoading'

definePageMeta({
  middleware: 'auth',
  skipPageLoading: true,
})

const { pageLoading } = usePageLoading()
pageLoading.value = false

// Escala da folha A4 para caber na largura disponível sem alterar sua proporção
const sheetFrame = ref<HTMLElement | null>(null)
const sheetEl = ref<HTMLElement | null>(null)
const sheetScale = ref(1)
const sheetHeightPx = ref(0)
let sheetObserver: ResizeObserver | null = null

const updateSheetScale = () => {
  const frame = sheetFrame.value
  const sheet = sheetEl.value
  if (!frame || !sheet) return
  // offsetWidth/offsetHeight ignoram transform: medem sempre o tamanho natural da folha
  const naturalWidth = sheet.offsetWidth
  const naturalHeight = sheet.offsetHeight
  if (!naturalWidth) return
  sheetScale.value = frame.clientWidth / naturalWidth
  sheetHeightPx.value = naturalHeight * sheetScale.value
}

onMounted(() => {
  updateSheetScale()
  if (typeof ResizeObserver !== 'undefined' && sheetFrame.value) {
    sheetObserver = new ResizeObserver(updateSheetScale)
    sheetObserver.observe(sheetFrame.value)
  }
})

onBeforeUnmount(() => {
  sheetObserver?.disconnect()
  sheetObserver = null
})

type PaymentKind = 'salario' | 'transporte' | 'diaria' | 'adiantamento' | 'decimo_terceiro' | 'ferias' | 'declaracao'
type ExtraLineType = 'earning' | 'deduction'
type Gender = 'M' | 'F'

const GENDER_OPTIONS: Array<{ label: string, value: Gender }> = [
  { label: 'Feminino', value: 'F' },
  { label: 'Masculino', value: 'M' },
]

interface ExtraLineItem {
  id: string
  description: string
  reference: string
  type: ExtraLineType
  amount: number
}

interface KindWordingConfig {
  label: string
  receiptTitle: string
  mainLineLabel: string
  defaultRef: string
  declarationTemplate: string
}

const STORAGE_KEY = 'myfinances:domestic-receipt:v3'
const PREV_STORAGE_KEYS = ['myfinances:domestic-receipt:v2', 'myfinances:domestic-receipt:v1']

const DEFAULT_KIND_CONFIGS: Record<PaymentKind, KindWordingConfig> = {
  salario: {
    label: 'Salário mensal',
    receiptTitle: 'RECIBO DE PAGAMENTO DE SALÁRIO',
    mainLineLabel: 'Remuneração mensal (jornada parcial)',
    defaultRef: 'jornada parcial, três vezes por semana',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente à remuneração do mês de {competencia}. O trabalho é realizado na função de {cargo}, em {referencia}.',
  },
  transporte: {
    label: 'Transporte',
    receiptTitle: 'RECIBO DE AUXÍLIO-TRANSPORTE',
    mainLineLabel: 'Auxílio-transporte / Deslocamento',
    defaultRef: '10 dias de deslocamento, considerando 2 passagens diárias no valor de R$ 5,50 cada, totalizando R$ 11,00 por dia',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente ao auxílio-transporte do mês de {competencia}. O valor corresponde a {referencia}.',
  },
  diaria: {
    label: 'Diária / Eventual',
    receiptTitle: 'RECIBO DE PAGAMENTO DE DIÁRIA',
    mainLineLabel: 'Diárias trabalhadas',
    defaultRef: '1 diária avulsa, sem vínculo de continuidade',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente ao pagamento de diária(s) do mês de {competencia}. O serviço foi prestado na função de {cargo}, correspondente a {referencia}.',
  },
  adiantamento: {
    label: 'Adiantamento (Vale)',
    receiptTitle: 'RECIBO DE ADIANTAMENTO SALARIAL',
    mainLineLabel: 'Adiantamento salarial (vale)',
    defaultRef: 'adiantamento quinzenal para compensação no fechamento da folha mensal',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente a {referencia} do mês de {competencia}. O trabalho é realizado na função de {cargo}, em jornada parcial, três vezes por semana.',
  },
  decimo_terceiro: {
    label: '13º Salário',
    receiptTitle: 'RECIBO DE 13º SALÁRIO',
    mainLineLabel: 'Gratificação natalina (13º salário)',
    defaultRef: 'parcela / integral do 13º salário proporcional à jornada parcial',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente ao pagamento de {referencia} na competência de {competencia}. O trabalho é realizado na função de {cargo}, em jornada parcial, três vezes por semana.',
  },
  ferias: {
    label: 'Férias',
    receiptTitle: 'RECIBO DE PAGAMENTO DE FÉRIAS',
    mainLineLabel: 'Férias + 1/3 constitucional',
    defaultRef: 'remuneração de férias em regime de jornada parcial acrescida do terço constitucional',
    declarationTemplate:
      'Declaro que recebi {artigo_empregador} {empregador_tipo} acima {identificado_empregador} a quantia de {valor} ({extenso}), referente à {referencia} na competência de {competencia}. O trabalho é realizado na função de {cargo}, em jornada parcial, três vezes por semana.',
  },
  declaracao: {
    label: 'Declaração pessoal',
    receiptTitle: 'DECLARAÇÃO DE MANIFESTAÇÃO PESSOAL',
    mainLineLabel: 'Declaração de manifestação pessoal',
    defaultRef: 'Caráter informativo e moral',
    declarationTemplate:
      'Eu, {funcionario}, {inscrito_funcionario} no CPF sob o nº {cpf_funcionario}, declaro, de livre e espontânea vontade, que, neste momento, não desejo que seja realizada a anotação do meu contrato de trabalho na Carteira de Trabalho e Previdência Social (CTPS), por preocupação com possíveis repercussões no recebimento do benefício do Bolsa Família por meus netos.\n\nDeclaro que esta manifestação representa exclusivamente minha vontade pessoal e o motivo por mim informado, sem intenção de atribuir {ao_empregador} {empregador_tipo} qualquer responsabilidade pela minha decisão.\n\nEsta declaração é feita para registrar minha manifestação pessoal, em caráter informativo e moral, sem pretensão de afastar direitos trabalhistas ou obrigações legais eventualmente aplicáveis.',
  },
}

const PAYMENT_KIND_ORDER: PaymentKind[] = [
  'salario',
  'transporte',
  'diaria',
  'adiantamento',
  'decimo_terceiro',
  'ferias',
  'declaracao',
]

const TEMPLATE_VARIABLES = [
  { token: '{empregador}', label: 'Empregador' },
  { token: '{cpf_empregador}', label: 'CPF Empregador' },
  { token: '{funcionario}', label: 'Funcionário' },
  { token: '{cpf_funcionario}', label: 'CPF Funcionário' },
  { token: '{cargo}', label: 'Cargo' },
  { token: '{valor}', label: 'Valor R$' },
  { token: '{extenso}', label: 'Valor por extenso' },
  { token: '{competencia}', label: 'Competência' },
  { token: '{referencia}', label: 'Referência / Detalhamento' },
  { token: '{artigo_empregador}', label: 'Artigo do(a) empregador(a) (do/da)' },
  { token: '{empregador_tipo}', label: 'Empregador / Empregadora' },
  { token: '{ao_empregador}', label: 'Ao / À (empregador)' },
  { token: '{identificado_empregador}', label: 'Identificado / Identificada' },
  { token: '{inscrito_funcionario}', label: 'Inscrito / Inscrita (funcionário)' },
]

const EXTRA_LINE_TYPE_OPTIONS: Array<{ label: string, value: ExtraLineType }> = [
  { label: '+ Provento', value: 'earning' },
  { label: '− Desconto', value: 'deduction' },
]

const cloneDefaultKindConfigs = (): Record<PaymentKind, KindWordingConfig> => ({
  salario: { ...DEFAULT_KIND_CONFIGS.salario },
  transporte: { ...DEFAULT_KIND_CONFIGS.transporte },
  diaria: { ...DEFAULT_KIND_CONFIGS.diaria },
  adiantamento: { ...DEFAULT_KIND_CONFIGS.adiantamento },
  decimo_terceiro: { ...DEFAULT_KIND_CONFIGS.decimo_terceiro },
  ferias: { ...DEFAULT_KIND_CONFIGS.ferias },
  declaracao: { ...DEFAULT_KIND_CONFIGS.declaracao },
})

const PAYMENT_METHODS = [
  'PIX',
  'Transferência bancária (TED/DOC)',
  'Dinheiro em espécie',
  'Cheque',
]

const ROLE_SUGGESTIONS = [
  'Empregada doméstica',
  'Diarista',
  'Babá',
  'Cuidador(a)',
  'Cozinheiro(a)',
  'Jardineiro(a)',
]

const now = new Date()
const currentYearMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
const currentIsoDate = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

const createDefaultState = () => ({
  paymentKind: 'salario' as PaymentKind,
  referenceMonth: currentYearMonth,
  paymentDate: currentIsoDate,
  paymentMethod: 'PIX',
  locationCity: 'Fortaleza/CE',
  employeeName: '',
  employeeCpf: '',
  employeeRole: 'Empregada doméstica',
  employeeGender: 'F' as Gender,
  employeeAddress: '',
  baseAmount: 1200 as number | null,
  baseReference: DEFAULT_KIND_CONFIGS.salario.defaultRef,
  pixThirdPartyEnabled: true,
  pixHolderName: 'Sheila Medeiros',
  pixHolderRelation: 'filha da empregada doméstica',
  pixHolderCpf: '038.994.733-45',
  employerName: '',
  employerCpf: '',
  employerGender: 'M' as Gender,
  workplaceAddress: '',
  notes: '',
  extraItems: [] as ExtraLineItem[],
  kindConfigs: cloneDefaultKindConfigs(),
})

const state = reactive(createDefaultState())
const showAdvanced = ref(false)
const showWordingEditor = ref(true)
const copyFeedback = ref(false)
const hydrated = ref(false)

// Formata CPF progressivamente no padrão 000.000.000-00
const formatCpf = (raw: string): string => {
  const digits = raw.replace(/\D/g, '').slice(0, 11)
  if (digits.length <= 3) return digits
  if (digits.length <= 6) return `${digits.slice(0, 3)}.${digits.slice(3)}`
  if (digits.length <= 9) return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6)}`
  return `${digits.slice(0, 3)}.${digits.slice(3, 6)}.${digits.slice(6, 9)}-${digits.slice(9, 11)}`
}

// Validação algorítmica oficial dos dígitos verificadores do CPF
const isValidCpf = (raw: string): boolean => {
  const digits = raw.replace(/\D/g, '')
  if (digits.length !== 11) return false
  if (/^(\d)\1{10}$/.test(digits)) return false

  const calcDigit = (sliceLen: number) => {
    let sum = 0
    for (let i = 0; i < sliceLen; i++) {
      sum += Number(digits[i]) * (sliceLen + 1 - i)
    }
    const remainder = (sum * 10) % 11
    return remainder === 10 ? 0 : remainder
  }

  return calcDigit(9) === Number(digits[9]) && calcDigit(10) === Number(digits[10])
}

const updateEmployeeCpf = (val: string | undefined) => {
  state.employeeCpf = formatCpf(val ?? '')
}

const updateEmployerCpf = (val: string | undefined) => {
  state.employerCpf = formatCpf(val ?? '')
}

const updatePixHolderCpf = (val: string | undefined) => {
  state.pixHolderCpf = formatCpf(val ?? '')
}

const employeeCpfDigits = computed(() => state.employeeCpf.replace(/\D/g, ''))
const employerCpfDigits = computed(() => state.employerCpf.replace(/\D/g, ''))

const employeeCpfStatus = computed<'empty' | 'incomplete' | 'valid' | 'invalid'>(() => {
  if (!employeeCpfDigits.value.length) return 'empty'
  if (employeeCpfDigits.value.length < 11) return 'incomplete'
  return isValidCpf(employeeCpfDigits.value) ? 'valid' : 'invalid'
})

const employerCpfStatus = computed<'empty' | 'incomplete' | 'valid' | 'invalid'>(() => {
  if (!employerCpfDigits.value.length) return 'empty'
  if (employerCpfDigits.value.length < 11) return 'incomplete'
  return isValidCpf(employerCpfDigits.value) ? 'valid' : 'invalid'
})

const activeKindMeta = computed(
  () => state.kindConfigs[state.paymentKind] ?? DEFAULT_KIND_CONFIGS.salario,
)

const selectPaymentKind = (kind: PaymentKind) => {
  const prevDefault = activeKindMeta.value.defaultRef
  const allDefaults = Object.values(DEFAULT_KIND_CONFIGS).map(k => k.defaultRef)
  state.paymentKind = kind
  const nextMeta = state.kindConfigs[kind]
  if (
    nextMeta
    && (!state.baseReference || state.baseReference === prevDefault || allDefaults.includes(state.baseReference))
  ) {
    state.baseReference = nextMeta.defaultRef
  }
}

const resetActiveKindWording = () => {
  const kind = state.paymentKind
  state.kindConfigs[kind] = { ...DEFAULT_KIND_CONFIGS[kind] }
  state.baseReference = DEFAULT_KIND_CONFIGS[kind].defaultRef
}

const insertTemplateVariable = (token: string) => {
  const current = state.kindConfigs[state.paymentKind].declarationTemplate
  const separator = current.endsWith(' ') || !current.length ? '' : ' '
  state.kindConfigs[state.paymentKind].declarationTemplate = `${current}${separator}${token}`
}

const allLines = computed(() => {
  const primary = {
    id: 'primary-base',
    description: activeKindMeta.value.mainLineLabel,
    reference: state.baseReference || activeKindMeta.value.defaultRef,
    type: 'earning' as ExtraLineType,
    amount: Math.max(0, Number(state.baseAmount) || 0),
    isPrimary: true,
  }
  const extras = state.extraItems.map(item => ({
    ...item,
    amount: Math.max(0, Number(item.amount) || 0),
    isPrimary: false,
  }))
  return [primary, ...extras]
})

const totalEarnings = computed(() =>
  allLines.value
    .filter(item => item.type === 'earning')
    .reduce((acc, item) => acc + item.amount, 0),
)

const totalDeductions = computed(() =>
  allLines.value
    .filter(item => item.type === 'deduction')
    .reduce((acc, item) => acc + item.amount, 0),
)

const netAmount = computed(() => Math.max(0, totalEarnings.value - totalDeductions.value))

// Conversor determinístico de valores em BRL para extenso em português (até centenas de milhões)
const UNITS = ['', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove']
const TEENS = [
  'dez',
  'onze',
  'doze',
  'treze',
  'quatorze',
  'quinze',
  'dezesseis',
  'dezessete',
  'dezoito',
  'dezenove',
]
const TENS = ['', '', 'vinte', 'trinta', 'quarenta', 'cinquenta', 'sessenta', 'setenta', 'oitenta', 'noventa']
const HUNDREDS = [
  '',
  'cento',
  'duzentos',
  'trezentos',
  'quatrocentos',
  'quinhentos',
  'seiscentos',
  'setecentos',
  'oitocentos',
  'novecentos',
]

const tripletToWords = (n: number): string => {
  if (n === 0) return ''
  if (n === 100) return 'cem'
  const h = Math.floor(n / 100)
  const rem = n % 100
  const t = Math.floor(rem / 10)
  const u = rem % 10

  const parts: string[] = []
  if (h > 0) parts.push(HUNDREDS[h])
  if (rem >= 10 && rem < 20) {
    parts.push(TEENS[rem - 10])
  } else {
    if (t >= 2) parts.push(TENS[t])
    if (u > 0) parts.push(UNITS[u])
  }
  return parts.join(' e ')
}

const numberToBRLWords = (value: number): string => {
  const safe = Math.max(0, Math.min(999_999_999.99, Number.isFinite(value) ? value : 0))
  const totalCents = Math.round(safe * 100)
  const integerPart = Math.floor(totalCents / 100)
  const centsPart = totalCents % 100

  if (integerPart === 0 && centsPart === 0) return 'zero reais'

  const millions = Math.floor(integerPart / 1_000_000)
  const thousands = Math.floor((integerPart % 1_000_000) / 1_000)
  const remainder = integerPart % 1_000

  const groups: string[] = []
  if (millions > 0) {
    groups.push(`${tripletToWords(millions)} ${millions === 1 ? 'milhão' : 'milhões'}`)
  }
  if (thousands > 0) {
    groups.push(thousands === 1 ? 'mil' : `${tripletToWords(thousands)} mil`)
  }
  if (remainder > 0) {
    groups.push(tripletToWords(remainder))
  }

  let integerWords = ''
  if (groups.length === 1) {
    integerWords = groups[0]
  } else if (groups.length > 1) {
    const last = groups[groups.length - 1]
    const head = groups.slice(0, -1).join(', ')
    const needsConjunction = remainder > 0 && (remainder < 100 || remainder % 100 === 0)
    integerWords = `${head}${needsConjunction ? ' e ' : ', '}${last}`
  }

  const parts: string[] = []
  if (integerPart > 0) {
    const isExactMillion = millions > 0 && thousands === 0 && remainder === 0
    const currencyUnit = integerPart === 1 ? 'real' : isExactMillion ? 'de reais' : 'reais'
    parts.push(`${integerWords} ${currencyUnit}`)
  }

  if (centsPart > 0) {
    const centsWords = tripletToWords(centsPart)
    parts.push(`${centsWords} ${centsPart === 1 ? 'centavo' : 'centavos'}`)
  }

  return parts.join(' e ')
}

const netAmountInWords = computed(() => numberToBRLWords(netAmount.value))

const MONTH_NAMES = [
  'janeiro',
  'fevereiro',
  'março',
  'abril',
  'maio',
  'junho',
  'julho',
  'agosto',
  'setembro',
  'outubro',
  'novembro',
  'dezembro',
]

// Ex: "setembro de 2026" para fluir naturalmente nas frases dos modelos
const formattedCompetence = computed(() => {
  if (!state.referenceMonth || !state.referenceMonth.includes('-')) return '—'
  const [year, month] = state.referenceMonth.split('-')
  const monthIdx = Number(month) - 1
  const monthName = MONTH_NAMES[monthIdx] ?? month
  return `${monthName} de ${year}`
})

const formattedCompetenceCapitalized = computed(() => {
  const val = formattedCompetence.value
  if (!val || val === '—') return '—'
  return `${val.charAt(0).toUpperCase()}${val.slice(1)}`
})

const formattedPaymentDateLong = computed(() => {
  if (!state.paymentDate || !state.paymentDate.includes('-')) return '___ de __________ de ______'
  const [year, month, day] = state.paymentDate.split('-')
  const monthIdx = Number(month) - 1
  const monthName = MONTH_NAMES[monthIdx] ?? month
  return `${ day } de ${monthName} de ${year}`
})

const formattedPaymentDateShort = computed(() => {
  if (!state.paymentDate || !state.paymentDate.includes('-')) return '__/__/____'
  const [year, month, day] = state.paymentDate.split('-')
  return `${day}/${month}/${year}`
})

// Models Date <-> string ISO para os componentes DatePicker do PrimeVue
const referenceMonthModel = computed<Date | null>({
  get: () => {
    if (!state.referenceMonth || !state.referenceMonth.includes('-')) return null
    const [year, month] = state.referenceMonth.split('-').map(Number)
    if (!year || !month) return null
    return new Date(year, month - 1, 1)
  },
  set: (date) => {
    if (!date) {
      state.referenceMonth = ''
      return
    }
    const y = date.getFullYear()
    const m = String(date.getMonth() + 1).padStart(2, '0')
    state.referenceMonth = `${y}-${m}`
  },
})

const paymentDateModel = computed<Date | null>({
  get: () => {
    if (!state.paymentDate || !state.paymentDate.includes('-')) return null
    const [year, month, day] = state.paymentDate.split('-').map(Number)
    if (!year || !month || !day) return null
    return new Date(year, month - 1, day)
  },
  set: (date) => {
    state.paymentDate = date ? toIsoDateString(date) : ''
  },
})

const employerIsFemale = computed(() => state.employerGender === 'F')
const employeeIsFemale = computed(() => state.employeeGender === 'F')
const employerLabel = computed(() => (employerIsFemale.value ? 'Empregadora' : 'Empregador'))
const employerSignatureLabel = computed(() =>
  employerIsFemale.value ? 'Assinatura da empregadora' : 'Assinatura do empregador',
)

// Interpola o template da modalidade selecionada destacando cada variável em negrito.
// Variáveis de concordância de gênero (artigos, "identificado/identificada", etc.)
// aparecem em texto normal, já flexionadas conforme o sexo informado.
const TOKEN_REGEX = /(\{[a-z_]+\})/g

const renderedDeclarationSegments = computed(() => {
  const rawTemplate = activeKindMeta.value.declarationTemplate || DEFAULT_KIND_CONFIGS[state.paymentKind].declarationTemplate
  const bold: Record<string, string> = {
    '{empregador}': state.employerName.trim() || '____________________________________',
    '{cpf_empregador}': state.employerCpf || '___.___.___-__',
    '{funcionario}': state.employeeName.trim() || '____________________________________',
    '{cpf_funcionario}': state.employeeCpf || '___.___.___-__',
    '{cargo}': (state.employeeRole || 'empregada doméstica').toLowerCase(),
    '{valor}': formatBRL(netAmount.value),
    '{extenso}': netAmountInWords.value,
    '{competencia}': formattedCompetence.value,
    '{referencia}': state.baseReference || activeKindMeta.value.defaultRef,
  }
  const plain: Record<string, string> = {
    '{artigo_empregador}': employerIsFemale.value ? 'da' : 'do',
    '{empregador_tipo}': employerIsFemale.value ? 'empregadora' : 'empregador',
    '{ao_empregador}': employerIsFemale.value ? 'à' : 'ao',
    '{identificado_empregador}': employerIsFemale.value ? 'identificada' : 'identificado',
    '{inscrito_funcionario}': employeeIsFemale.value ? 'inscrita' : 'inscrito',
  }

  const segments: Array<{ text: string, bold: boolean }> = []
  for (const part of rawTemplate.split(TOKEN_REGEX)) {
    if (!part) continue
    if (part in plain) {
      segments.push({ text: plain[part], bold: false })
    } else if (part in bold) {
      segments.push({ text: bold[part], bold: true })
    } else {
      segments.push({ text: part, bold: false })
    }
  }

  return segments
})

const addExtraItem = (preset?: { description: string, reference: string, type: ExtraLineType, amount?: number }) => {
  showAdvanced.value = true
  state.extraItems.push({
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    description: preset?.description ?? '',
    reference: preset?.reference ?? '',
    type: preset?.type ?? 'earning',
    amount: preset?.amount ?? 0,
  })
}

const removeExtraItem = (id: string) => {
  const index = state.extraItems.findIndex(item => item.id === id)
  if (index !== -1) {
    state.extraItems.splice(index, 1)
  }
}

const resetForm = () => {
  const fresh = createDefaultState()
  Object.assign(state, fresh)
  copyFeedback.value = true
  setTimeout(() => {
    copyFeedback.value = false
  }, 2000)
}

const isDeclarationKind = computed(() => state.paymentKind === 'declaracao')

const isReadyToPrint = computed(
  () => Boolean(state.employeeName.trim()) && (isDeclarationKind.value || netAmount.value > 0),
)

const triggerPrint = () => {
  if (typeof window !== 'undefined') {
    window.print()
  }
}

const copies = computed(() => [
  {
    number: '1ª VIA',
    holder: employerIsFemale.value ? 'EMPREGADORA' : 'EMPREGADOR',
    subtitle: 'Arquivo e comprovação de quitação',
    tone: 'employer' as const,
  },
  {
    number: '2ª VIA',
    holder: employeeIsFemale.value ? 'EMPREGADA DOMÉSTICA' : 'EMPREGADO DOMÉSTICO',
    subtitle: 'Comprovante da trabalhadora',
    tone: 'employee' as const,
  },
])

onMounted(async () => {
  if (typeof window !== 'undefined') {
    try {
      const savedV3 = window.localStorage.getItem(STORAGE_KEY)
      if (savedV3) {
        const parsed = JSON.parse(savedV3)
        const defaults = createDefaultState()
        const mergedKindConfigs = cloneDefaultKindConfigs()
        if (parsed.kindConfigs && typeof parsed.kindConfigs === 'object') {
          for (const key of PAYMENT_KIND_ORDER) {
            if (parsed.kindConfigs[key]) {
              const rawDecl = String(parsed.kindConfigs[key].declarationTemplate ?? DEFAULT_KIND_CONFIGS[key].declarationTemplate)
              mergedKindConfigs[key] = {
                ...DEFAULT_KIND_CONFIGS[key],
                ...parsed.kindConfigs[key],
                declarationTemplate: key === 'declaracao' ? rawDecl : rawDecl.replace(/\s*\n+\s*/g, ' '),
              }
            }
          }
        }
        Object.assign(state, defaults, parsed, { kindConfigs: mergedKindConfigs })
      } else {
        // Migra dados pessoais já digitados em versões anteriores preservando os novos modelos de texto
        for (const legacyKey of PREV_STORAGE_KEYS) {
          const legacyRaw = window.localStorage.getItem(legacyKey)
          if (!legacyRaw) continue
          const legacy = JSON.parse(legacyRaw)
          if (legacy.employeeName) state.employeeName = legacy.employeeName
          if (legacy.employeeCpf) state.employeeCpf = legacy.employeeCpf
          if (legacy.employeeRole) state.employeeRole = legacy.employeeRole
          if (legacy.employerName) state.employerName = legacy.employerName
          if (legacy.employerCpf) state.employerCpf = legacy.employerCpf
          if (legacy.workplaceAddress) state.workplaceAddress = legacy.workplaceAddress
          if (legacy.baseAmount !== undefined) state.baseAmount = legacy.baseAmount
          if (legacy.referenceMonth) state.referenceMonth = legacy.referenceMonth
          if (legacy.paymentDate) state.paymentDate = legacy.paymentDate
          break
        }
      }
      if (Array.isArray(state.extraItems) && state.extraItems.length > 0) {
        showAdvanced.value = true
      }
    } catch {
      // Ignora estado local corrompido
    } finally {
      hydrated.value = true
    }
  }
})

watch(
  state,
  (val) => {
    if (!hydrated.value || typeof window === 'undefined') return
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
    } catch {
      // Ignora falhas de quota do navegador
    }
  },
  { deep: true },
)
</script>

<template>
  <section class="space-y-6 print:space-y-0">
    <!-- Cabeçalho da ferramenta (oculto na impressão) -->
    <div class="flex flex-col gap-4 border-b border-sepia-200 pb-5 sm:flex-row sm:items-end sm:justify-between print:hidden">
      <div>
        <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-sepia-500">
          <Icon icon="mdi:file-document-check-outline" class="h-4 w-4 text-sepia-600" />
          <span>Emissão em 2 vias • Folha A4 (210 × 297 mm) • Salvo automaticamente</span>
        </div>
        <h1 class="mt-1 text-2xl font-semibold text-sepia-950">
          Recibo de pagamento doméstico
        </h1>
        <p class="mt-1 max-w-2xl text-sm text-sepia-600">
          Preencha os dados da funcionária e o valor. A folha A4 ao lado monta automaticamente
          a <strong>1ª via (Empregador)</strong> e a <strong>2ª via (Empregada doméstica)</strong> conforme seus modelos.
        </p>
      </div>

      <div class="flex flex-wrap items-center gap-2.5">
        <Button
          class="!rounded-lg !border !border-sepia-300 !bg-white !px-3.5 !py-2 !text-xs !font-medium !text-sepia-800 hover:!bg-sepia-100"
          @click="resetForm"
        >
          <Icon icon="mdi:refresh" class="mr-1.5 h-4 w-4" />
          {{ copyFeedback ? 'Padrão restaurado' : 'Limpar campos' }}
        </Button>

        <Button
          :disabled="!isReadyToPrint"
          class="!rounded-lg !bg-sepia-900 !px-4 !py-2 !text-sm !font-semibold !text-sepia-50 shadow-sm hover:!bg-sepia-950 disabled:!opacity-40"
          @click="triggerPrint"
        >
          <Icon icon="mdi:printer-outline" class="mr-2 h-4 w-4" />
          Imprimir 2 vias em A4
        </Button>
      </div>
    </div>

    <!-- Aviso rápido quando faltam dados essenciais para impressão -->
    <div
      v-if="!isReadyToPrint"
      class="flex items-center gap-3 rounded-lg border border-sepia-300 bg-sepia-100/80 px-4 py-2.5 text-xs text-sepia-800 print:hidden"
    >
      <Icon icon="mdi:information-outline" class="h-4 w-4 shrink-0 text-sepia-700" />
      <span>
        Informe o <strong>nome do(a) funcionário(a)</strong> e um <strong>valor de pagamento maior que zero</strong> para liberar a impressão das duas vias.
      </span>
    </div>

    <!-- Grid principal com coluna esquerda ampla -->
    <div class="grid gap-6 lg:grid-cols-[540px_1fr] xl:grid-cols-[580px_1fr] 2xl:grid-cols-[620px_1fr] lg:items-start print:block">
      <!-- COLUNA ESQUERDA: Editor estruturado com componentes PrimeVue (oculto na impressão) -->
      <div class="space-y-4 print:hidden">
        <!-- Bloco 1: Funcionário e Valor -->
        <div class="rounded-xl border border-sepia-200 border-t-4 border-t-sepia-900 bg-white p-6 shadow-theme-sm">
          <div class="mb-4 flex items-center justify-between gap-3">
            <div>
              <span class="text-[11px] font-semibold uppercase tracking-wider text-sepia-500">
                1. Dados essenciais
              </span>
              <h2 class="text-base font-semibold text-sepia-950">
                Empregada doméstica e valor do pagamento
              </h2>
            </div>
            <span class="shrink-0 rounded-full bg-sepia-100 px-3 py-1 font-mono text-xs font-semibold text-sepia-800">
              {{ formatBRL(netAmount) }}
            </span>
          </div>

          <div class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-[1fr_180px] sm:items-end">
              <div>
                <label for="employee-name" class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Nome completo do(a) funcionário(a) *
                </label>
                <InputText
                  id="employee-name"
                  v-model="state.employeeName"
                  type="text"
                  placeholder="Ex: Maria Aparecida dos Santos"
                  class="w-full"
                />
              </div>
              <div>
                <label for="employee-gender" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Sexo
                </label>
                <Select
                  v-model="state.employeeGender"
                  input-id="employee-gender"
                  :options="GENDER_OPTIONS"
                  option-label="label"
                  option-value="value"
                  class="w-full"
                />
              </div>
            </div>

            <!-- CPF e Valor lado a lado com mensagens auxiliares abaixo de cada input -->
            <div class="grid gap-4 sm:grid-cols-2 sm:items-start">
              <div>
                <label for="employee-cpf" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  CPF do(a) funcionário(a) *
                </label>
                <InputText
                  id="employee-cpf"
                  :model-value="state.employeeCpf"
                  type="text"
                  inputmode="numeric"
                  maxlength="14"
                  placeholder="000.000.000-00"
                  class="w-full font-mono"
                  @update:model-value="updateEmployeeCpf"
                />
                <p
                  v-if="employeeCpfStatus === 'valid'"
                  class="mt-1.5 text-xs font-medium text-azul-600"
                >
                  CPF válido
                </p>
                <p
                  v-else-if="employeeCpfStatus === 'invalid'"
                  class="mt-1.5 text-xs font-medium text-vermelho-600"
                >
                  Dígito inválido
                </p>
              </div>

              <div>
                <label for="payment-value" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Valor do pagamento (R$) *
                </label>
                <InputNumber
                  v-model="state.baseAmount"
                  input-id="payment-value"
                  mode="currency"
                  currency="BRL"
                  locale="pt-BR"
                  :min="0"
                  placeholder="R$ 0,00"
                  class="w-full font-mono"
                />
                <p class="mt-1.5 text-right text-xs italic text-sepia-600">
                  {{ netAmountInWords }}
                </p>
              </div>
            </div>

            <!-- Endereço da empregada doméstica -->
            <div>
              <label for="employee-address" class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                Endereço da empregada doméstica (opcional)
              </label>
              <InputText
                id="employee-address"
                v-model="state.employeeAddress"
                type="text"
                placeholder="Ex: Rua Exemplo, 100, Bairro, Fortaleza/CE"
                class="w-full"
              />
            </div>

            <!-- Cargo / Função com sugestões rápidas -->
            <div>
              <label for="employee-role" class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                Cargo / Função
              </label>
              <InputText
                id="employee-role"
                v-model="state.employeeRole"
                type="text"
                placeholder="Ex: Empregada doméstica"
                class="w-full"
              />
              <div class="mt-2 flex flex-wrap gap-1.5">
                <Button
                  v-for="role in ROLE_SUGGESTIONS"
                  :key="role"
                  type="button"
                  :class="[
                    '!rounded-md !border !px-2.5 !py-1 !text-xs transition-colors',
                    state.employeeRole === role
                      ? '!border-sepia-900 !bg-sepia-900 !font-medium !text-sepia-50'
                      : '!border-sepia-200 !bg-sepia-50 !text-sepia-700 hover:!border-sepia-400 hover:!bg-sepia-100',
                  ]"
                  @click="state.employeeRole = role"
                >
                  {{ role }}
                </Button>
              </div>
            </div>
          </div>
        </div>

        <!-- Bloco 2: Competência, Natureza, Redação por Modalidade e Pagamento -->
        <div class="rounded-xl border border-sepia-200 bg-white p-6 shadow-theme-sm">
          <span class="text-[11px] font-semibold uppercase tracking-wider text-sepia-500">
            2. Referência e quitação
          </span>
          <h2 class="mb-3 text-base font-semibold text-sepia-950">
            Modalidade, dizeres e forma de pagamento
          </h2>

          <div class="space-y-4">
            <!-- Natureza do pagamento -->
            <div>
              <label class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                Referente a
              </label>
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Button
                  v-for="kindKey in PAYMENT_KIND_ORDER"
                  :key="kindKey"
                  type="button"
                  :class="[
                    '!justify-start !whitespace-nowrap !rounded-lg !border !px-3 !py-2 !text-left !text-xs transition-colors',
                    state.paymentKind === kindKey
                      ? '!border-sepia-900 !bg-sepia-900 !font-semibold !text-sepia-50'
                      : '!border-sepia-200 !bg-sepia-50/70 !text-sepia-800 hover:!border-sepia-400 hover:!bg-sepia-100',
                  ]"
                  @click="selectPaymentKind(kindKey)"
                >
                  {{ state.kindConfigs[kindKey].label }}
                </Button>
              </div>
            </div>

            <!-- Detalhamento / Referência da modalidade (ex: jornada parcial ou cálculo das passagens) -->
            <div>
              <label for="base-reference" class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                Detalhamento / Referência ({{ activeKindMeta.label }})
              </label>
              <InputText
                id="base-reference"
                v-model="state.baseReference"
                type="text"
                placeholder="Ex: jornada parcial, três vezes por semana"
                class="w-full"
              />
            </div>

            <!-- Editor de redação específica para a opção "Referente a" selecionada -->
            <div class="rounded-lg border border-sepia-200 bg-sepia-50/70 p-3.5">
              <div class="flex items-center justify-between gap-2">
                <Button
                  text
                  type="button"
                  class="!p-0 !text-left !text-xs !font-semibold !text-sepia-900"
                  @click="showWordingEditor = !showWordingEditor"
                >
                  <Icon icon="mdi:text-box-edit-outline" class="mr-1.5 h-4 w-4 text-sepia-700" />
                  <span>Redação para “{{ activeKindMeta.label }}”</span>
                  <Icon :icon="showWordingEditor ? 'mdi:chevron-up' : 'mdi:chevron-down'" class="ml-1 h-4 w-4 text-sepia-500" />
                </Button>
                <Button
                  text
                  type="button"
                  class="!p-0 !text-[11px] !font-medium !text-sepia-600 underline hover:!text-sepia-900"
                  title="Restaurar o texto padrão desta modalidade"
                  @click="resetActiveKindWording"
                >
                  Restaurar padrão
                </Button>
              </div>

              <div v-if="showWordingEditor" class="mt-3 space-y-3">
                <div class="grid gap-3 sm:grid-cols-2 sm:items-end">
                  <div>
                    <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                      Nome da modalidade
                    </label>
                    <InputText
                      v-model="state.kindConfigs[state.paymentKind].label"
                      type="text"
                      class="w-full !text-xs"
                    />
                  </div>
                  <div>
                    <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                      Título no topo do recibo
                    </label>
                    <InputText
                      v-model="state.kindConfigs[state.paymentKind].receiptTitle"
                      type="text"
                      class="w-full !text-xs"
                    />
                  </div>
                </div>

                <div>
                  <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                    Descrição da verba na tabela
                  </label>
                  <InputText
                    v-model="state.kindConfigs[state.paymentKind].mainLineLabel"
                    type="text"
                    class="w-full !text-xs"
                  />
                </div>

                <div>
                  <label class="mb-1 block text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                    Texto de declaração / quitação ({{ activeKindMeta.label }})
                  </label>
                  <Textarea
                    v-model="state.kindConfigs[state.paymentKind].declarationTemplate"
                    rows="3"
                    class="w-full !text-xs leading-relaxed"
                  />
                  <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <span class="text-[10px] text-sepia-500">Variáveis:</span>
                    <Button
                      v-for="variable in TEMPLATE_VARIABLES"
                      :key="variable.token"
                      type="button"
                      class="!rounded !border !border-sepia-200 !bg-white !px-1.5 !py-0.5 font-mono !text-[10px] !text-sepia-700 hover:!border-sepia-400 hover:!bg-sepia-100"
                      :title="`Inserir ${variable.token}`"
                      @click="insertTemplateVariable(variable.token)"
                    >
                      {{ variable.token }}
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div class="grid gap-4 sm:grid-cols-2 sm:items-end">
              <div>
                <label for="reference-month" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Mês de competência
                </label>
                <DatePicker
                  v-model="referenceMonthModel"
                  input-id="reference-month"
                  view="month"
                  date-format="mm/yy"
                  show-icon
                  icon-display="input"
                  class="w-full"
                />
              </div>

              <div>
                <label for="payment-date" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Data do pagamento
                </label>
                <DatePicker
                  v-model="paymentDateModel"
                  input-id="payment-date"
                  date-format="dd/mm/yy"
                  show-icon
                  icon-display="input"
                  show-button-bar
                  class="w-full"
                />
              </div>
            </div>

            <div class="grid gap-4 sm:grid-cols-2 sm:items-end">
              <div>
                <label for="payment-method" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Forma de pagamento
                </label>
                <Select
                  v-model="state.paymentMethod"
                  input-id="payment-method"
                  :options="PAYMENT_METHODS"
                  class="w-full"
                />
              </div>

              <div>
                <label for="location-city" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Cidade / UF de emissão
                </label>
                <InputText
                  id="location-city"
                  v-model="state.locationCity"
                  type="text"
                  placeholder="Ex: Fortaleza/CE"
                  class="w-full"
                />
              </div>
            </div>

            <!-- Configuração de Conta PIX de Terceiro (conforme os modelos enviados) -->
            <div class="rounded-lg border border-sepia-200 bg-sepia-50/70 p-3.5 space-y-3">
              <label class="flex items-center gap-2.5 text-xs font-semibold text-sepia-900 cursor-pointer">
                <Checkbox v-model="state.pixThirdPartyEnabled" binary />
                <span>Pagamento via PIX em conta de titularidade de terceiro (ex: filha)</span>
              </label>

              <div v-if="state.pixThirdPartyEnabled" class="grid gap-3 sm:grid-cols-3 sm:items-end">
                <div>
                  <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                    Titular da conta PIX
                  </label>
                  <InputText
                    v-model="state.pixHolderName"
                    type="text"
                    placeholder="Ex: Sheila Medeiros"
                    class="w-full !text-xs"
                  />
                </div>
                <div>
                  <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                    CPF da titular PIX
                  </label>
                  <InputText
                    :model-value="state.pixHolderCpf"
                    type="text"
                    inputmode="numeric"
                    maxlength="14"
                    placeholder="000.000.000-00"
                    class="w-full font-mono !text-xs"
                    @update:model-value="updatePixHolderCpf"
                  />
                </div>
                <div>
                  <label class="mb-1 block whitespace-nowrap text-[11px] font-semibold uppercase tracking-wider text-sepia-600">
                    Vínculo / Parentesco
                  </label>
                  <InputText
                    v-model="state.pixHolderRelation"
                    type="text"
                    placeholder="Ex: filha da empregada doméstica"
                    class="w-full !text-xs"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Bloco 3: Empregador e Verbas Extras -->
        <div class="rounded-xl border border-sepia-200 bg-white p-6 shadow-theme-sm">
          <div class="mb-3">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-sepia-500">
              3. Dados do(a) empregador(a)
            </span>
            <h2 class="text-base font-semibold text-sepia-950">
              Identificação do pagador
            </h2>
          </div>

          <div class="space-y-4">
            <div class="grid gap-4 sm:grid-cols-[1fr_180px] sm:items-end">
              <div>
                <label for="employer-name" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Nome completo do(a) empregador(a)
                </label>
                <InputText
                  id="employer-name"
                  v-model="state.employerName"
                  type="text"
                  placeholder="Nome do empregador doméstico"
                  class="w-full"
                />
              </div>
              <div>
                <label for="employer-gender" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Sexo
                </label>
                <Select
                  v-model="state.employerGender"
                  input-id="employer-gender"
                  :options="GENDER_OPTIONS"
                  option-label="label"
                  option-value="value"
                  class="w-full"
                />
              </div>
            </div>

            <div>
              <label for="employer-cpf" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                CPF do(a) empregador(a)
              </label>
              <InputText
                id="employer-cpf"
                :model-value="state.employerCpf"
                type="text"
                inputmode="numeric"
                maxlength="14"
                placeholder="000.000.000-00"
                class="w-full font-mono"
                @update:model-value="updateEmployerCpf"
              />
              <p
                v-if="employerCpfStatus === 'valid'"
                class="mt-1.5 text-xs font-medium text-azul-600"
              >
                CPF válido
              </p>
              <p
                v-else-if="employerCpfStatus === 'invalid'"
                class="mt-1.5 text-xs font-medium text-vermelho-600"
              >
                Dígito inválido
              </p>
            </div>

            <div>
              <label for="workplace-address" class="mb-1.5 block whitespace-nowrap text-xs font-semibold uppercase tracking-wider text-sepia-700">
                Endereço do(a) empregador(a)
              </label>
              <InputText
                id="workplace-address"
                v-model="state.workplaceAddress"
                type="text"
                placeholder="Ex: Rua Professor Francisco Gonçalves, 1271, Apto 1703, Cocó, Fortaleza/CE"
                class="w-full"
              />
            </div>
          </div>

          <!-- Acréscimos / Descontos opcionais -->
          <div class="mt-5 border-t border-sepia-200 pt-4">
            <Button
              text
              type="button"
              class="!flex !w-full !items-center !justify-between !p-0 !text-left !text-xs !font-semibold uppercase tracking-wider !text-sepia-700 hover:!text-sepia-950"
              @click="showAdvanced = !showAdvanced"
            >
              <span>Acréscimos, descontos e observações ({{ state.extraItems.length }})</span>
              <Icon :icon="showAdvanced ? 'mdi:chevron-up' : 'mdi:chevron-down'" class="h-4 w-4" />
            </Button>

            <div v-if="showAdvanced" class="mt-3 space-y-3">
              <div class="flex flex-wrap gap-1.5">
                <Button
                  type="button"
                  class="!rounded-md !border !border-azul-200 !bg-azul-50 !px-2.5 !py-1 !text-xs !font-medium !text-azul-700 hover:!bg-azul-100"
                  @click="addExtraItem({ description: 'Auxílio-transporte', reference: 'Mensal', type: 'earning', amount: 110 })"
                >
                  + Auxílio-transporte
                </Button>
                <Button
                  type="button"
                  class="!rounded-md !border !border-azul-200 !bg-azul-50 !px-2.5 !py-1 !text-xs !font-medium !text-azul-700 hover:!bg-azul-100"
                  @click="addExtraItem({ description: 'Horas extras (50%)', reference: 'Horas', type: 'earning', amount: 150 })"
                >
                  + Horas extras
                </Button>
                <Button
                  type="button"
                  class="!rounded-md !border !border-vermelho-200 !bg-vermelho-50 !px-2.5 !py-1 !text-xs !font-medium !text-vermelho-700 hover:!bg-vermelho-100"
                  @click="addExtraItem({ description: 'INSS retido (empregado)', reference: 'eSocial', type: 'deduction', amount: 90 })"
                >
                  − INSS empregado
                </Button>
                <Button
                  type="button"
                  class="!rounded-md !border !border-vermelho-200 !bg-vermelho-50 !px-2.5 !py-1 !text-xs !font-medium !text-vermelho-700 hover:!bg-vermelho-100"
                  @click="addExtraItem({ description: 'Adiantamento salarial (vale)', reference: 'Desconto', type: 'deduction', amount: 400 })"
                >
                  − Adiantamento
                </Button>
              </div>

              <div
                v-for="item in state.extraItems"
                :key="item.id"
                class="grid grid-cols-[1fr_130px_140px_auto] items-center gap-2 rounded-lg border border-sepia-200 bg-sepia-50/60 p-2"
              >
                <InputText
                  v-model="item.description"
                  type="text"
                  placeholder="Descrição da verba"
                  class="w-full !text-xs"
                />
                <Select
                  v-model="item.type"
                  :options="EXTRA_LINE_TYPE_OPTIONS"
                  option-label="label"
                  option-value="value"
                  class="w-full !text-xs"
                />
                <InputNumber
                  v-model="item.amount"
                  mode="currency"
                  currency="BRL"
                  locale="pt-BR"
                  :min="0"
                  placeholder="R$ 0,00"
                  class="w-full font-mono !text-xs"
                />
                <Button
                  text
                  rounded
                  title="Remover linha"
                  class="!text-sepia-400 hover:!text-vermelho-600"
                  @click="removeExtraItem(item.id)"
                >
                  <Icon icon="mdi:trash-can-outline" class="h-4 w-4" />
                </Button>
              </div>

              <div>
                <label for="receipt-notes" class="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-sepia-700">
                  Observação na via impressa (opcional)
                </label>
                <InputText
                  id="receipt-notes"
                  v-model="state.notes"
                  type="text"
                  maxlength="140"
                  placeholder="Ex: Guarde o comprovante do PIX junto ao recibo assinado"
                  class="w-full"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- COLUNA DIREITA: Mesa de prova A4 com 2 vias idênticas e linha de picote -->
      <div class="rounded-xl border border-sepia-300/80 bg-sepia-200/60 p-3 sm:p-6 print:border-0 print:bg-transparent print:p-0">
        <!-- Barra de status da folha (oculta na impressão) -->
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-sepia-700 print:hidden">
          <div class="flex items-center gap-2 font-mono">
            <span class="inline-block h-2 w-2 rounded-full bg-azul-600" />
            <span>PROVA DE IMPRESSÃO • A4 RETRATO (210mm × 297mm)</span>
          </div>
          <span class="text-sepia-600">
            1ª via (Empregador) + 2ª via (Empregada doméstica) na mesma página
          </span>
        </div>

        <!-- FOLHA A4 (proporção fixa, escalada para a largura disponível) -->
        <div ref="sheetFrame" class="a4-frame" :style="{ height: sheetHeightPx ? `${sheetHeightPx}px` : 'auto' }">
          <article
            ref="sheetEl"
            class="a4-sheet flex flex-col justify-between bg-white text-sepia-950 shadow-theme-xl ring-1 ring-sepia-300 print:shadow-none print:ring-0"
            :style="{ transform: `scale(${sheetScale})` }"
          >
          <template v-for="(copy, idx) in copies" :key="copy.number">
            <!-- VIA DO RECIBO (ocupa exatamente metade útil da folha A4) -->
            <section
              class="receipt-copy flex flex-1 flex-col justify-between rounded-sm border border-sepia-800/80 p-3.5 sm:p-4"
            >
              <div class="space-y-2.5">
                <!-- Topo da Via: Título, Competência, Selo da Via e Quadro de Valor Líquido -->
                <header class="flex items-start justify-between gap-3 border-b-2 border-sepia-900 pb-2">
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-2">
                      <span
                        :class="[
                          'inline-flex items-center rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wider',
                          copy.tone === 'employer'
                            ? 'bg-sepia-900 text-sepia-50'
                            : 'bg-azul-700 text-white',
                        ]"
                      >
                        {{ copy.number }} • {{ copy.holder }}
                      </span>
                      <span
                        v-if="!isDeclarationKind"
                        class="font-mono text-[10px] font-semibold text-sepia-800"
                      >
                        Competência: {{ formattedCompetenceCapitalized }}
                      </span>
                    </div>

                    <h2 class="mt-1 text-base font-bold tracking-tight text-sepia-950">
                      {{ activeKindMeta.receiptTitle }}
                    </h2>
                  </div>

                  <!-- Quadro contábil do Valor Líquido (apenas para recibos financeiros) -->
                  <div v-if="!isDeclarationKind" class="shrink-0 rounded border-2 border-sepia-900 bg-sepia-50 px-3 py-1 text-right">
                    <span class="block text-[9px] font-bold uppercase tracking-widest text-sepia-600">
                      Valor líquido (R$)
                    </span>
                    <span class="ledger-total-rule block font-mono text-base font-bold text-sepia-950">
                      {{ formatBRL(netAmount) }}
                    </span>
                  </div>
                </header>

                <!-- Quadro de Identificação das Partes (Empregador e Empregada Doméstica com Nome, CPF e Endereço) -->
                <div v-if="!isDeclarationKind" class="grid grid-cols-2 gap-2.5 text-[11px]">
                  <div class="rounded border border-sepia-300 bg-sepia-50/50 px-2.5 py-1.5">
                    <span class="block text-[9px] font-bold uppercase tracking-wider text-sepia-500">
                      {{ employerLabel }}
                    </span>
                    <p class="break-words font-bold leading-snug text-sepia-950">
                      {{ state.employerName.trim() || '________________________________________' }}
                    </p>
                    <p class="font-mono text-[10px] text-sepia-800">
                      CPF: <strong>{{ state.employerCpf || '___.___.___-__' }}</strong>
                    </p>
                    <p class="break-words text-[10px] leading-snug text-sepia-600">
                      Endereço: {{ state.workplaceAddress.trim() || '____________________________________' }}
                    </p>
                  </div>

                  <div class="rounded border border-sepia-300 bg-sepia-50/50 px-2.5 py-1.5">
                    <span class="block text-[9px] font-bold uppercase tracking-wider text-sepia-500">
                      {{ state.employeeRole || 'Empregada doméstica' }}
                    </span>
                    <p class="break-words font-bold leading-snug text-sepia-950">
                      {{ state.employeeName.trim() || '________________________________________' }}
                    </p>
                    <p class="font-mono text-[10px] text-sepia-800">
                      CPF: <strong>{{ state.employeeCpf || '___.___.___-__' }}</strong>
                    </p>
                    <p class="break-words text-[10px] leading-snug text-sepia-600">
                      Endereço: {{ state.employeeAddress.trim() || '____________________________________' }}
                    </p>
                  </div>
                </div>

                <!-- Tabela de Discriminação de Valores (exibida quando houver acréscimos/descontos extras) -->
                <div v-if="!isDeclarationKind && state.extraItems.length > 0" class="overflow-hidden rounded border border-sepia-300">
                  <table class="w-full border-collapse text-[10px]">
                    <thead>
                      <tr class="border-b border-sepia-300 bg-sepia-100/80 text-[9px] font-bold uppercase tracking-wider text-sepia-700">
                        <th class="px-2 py-0.5 text-left">Discriminação</th>
                        <th class="px-2 py-0.5 text-right">Proventos (+)</th>
                        <th class="px-2 py-0.5 text-right">Descontos (−)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="line in allLines.slice(0, 3)"
                        :key="line.id"
                        class="border-b border-sepia-200/70 last:border-0"
                      >
                        <td class="px-2 py-0.5 font-medium text-sepia-900">
                          {{ line.description || '—' }}
                        </td>
                        <td class="px-2 py-0.5 text-right font-mono font-medium text-sepia-900">
                          {{ line.type === 'earning' ? formatBRL(line.amount) : '—' }}
                        </td>
                        <td class="px-2 py-0.5 text-right font-mono font-medium text-vermelho-700">
                          {{ line.type === 'deduction' ? formatBRL(line.amount) : '—' }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Corpo do Recibo / Declaração fiel aos modelos enviados -->
                <div class="space-y-2 rounded border border-sepia-300 bg-sepia-50/60 px-3 py-2.5 text-[11px] leading-relaxed text-sepia-950">
                  <p class="whitespace-pre-line">
                    <template v-for="(seg, segIdx) in renderedDeclarationSegments" :key="segIdx">
                      <strong v-if="seg.bold" class="font-bold text-sepia-950">{{ seg.text }}</strong>
                      <span v-else>{{ seg.text }}</span>
                    </template>
                  </p>

                  <template v-if="!isDeclarationKind">
                    <p v-if="state.pixThirdPartyEnabled && state.paymentMethod === 'PIX'">
                      <strong>Forma de pagamento:</strong> PIX em <strong>{{ formattedPaymentDateShort }}</strong> para a conta de
                      <strong>{{ state.pixHolderName.trim() || '____________________' }}</strong>
                      (<template v-if="state.pixHolderRelation.trim()">{{ state.pixHolderRelation.trim() }}, </template>CPF
                      <strong class="font-mono">{{ state.pixHolderCpf || '___.___.___-__' }}</strong>), com plena ciência e concordância da
                      {{ (state.employeeRole || 'empregada doméstica').toLowerCase() }}, que firma este recibo dando quitação.
                    </p>
                    <p v-else>
                      <strong>Forma de pagamento:</strong> {{ state.paymentMethod }}, recebido em <strong>{{ formattedPaymentDateShort }}</strong>, pelo qual firmo o presente recibo dando plena quitação.
                    </p>
                  </template>

                  <p v-if="state.notes" class="break-words text-[10px] leading-snug text-sepia-600">
                    <strong>Obs.:</strong> {{ state.notes }}
                  </p>
                </div>

                <div class="flex items-center justify-between pt-0.5 text-[11px] text-sepia-800">
                  <span>
                    {{ state.locationCity || 'Fortaleza/CE' }}, <strong>{{ formattedPaymentDateLong }}</strong>.
                  </span>
                </div>
              </div>

              <!-- Rodapé de Assinaturas -->
              <footer class="pt-10">
                <!-- Na Declaração de Manifestação Pessoal, apenas a assinatura da declarante conforme o modelo -->
                <div v-if="isDeclarationKind" class="mx-auto max-w-xs text-center text-[11px]">
                  <div class="border-t border-sepia-900 pt-1">
                    <p class="font-bold text-sepia-950">
                      Assinatura da declarante
                    </p>
                    <p class="break-words font-mono text-[10px] text-sepia-700">
                      {{ state.employeeName.trim() || 'Declarante' }} • CPF {{ state.employeeCpf || '___.___.___-__' }}
                    </p>
                  </div>
                </div>

                <div v-else class="grid grid-cols-2 gap-6 text-center text-[11px]">
                  <div>
                    <div class="border-t border-sepia-900 pt-1">
                      <p class="font-bold text-sepia-950">
                        Assinatura da {{ (state.employeeRole || 'empregada doméstica').toLowerCase() }}
                      </p>
                      <p class="break-words font-mono text-[10px] text-sepia-700">
                        {{ state.employeeName.trim() || 'Nome' }} • CPF {{ state.employeeCpf || '___.___.___-__' }}
                      </p>
                    </div>
                  </div>

                  <div>
                    <div class="border-t border-sepia-900 pt-1">
                      <p class="font-bold text-sepia-950">
                        {{ employerSignatureLabel }}
                      </p>
                      <p class="break-words font-mono text-[10px] text-sepia-700">
                        {{ state.employerName.trim() || 'Nome' }} • CPF {{ state.employerCpf || '___.___.___-__' }}
                      </p>
                    </div>
                  </div>
                </div>
              </footer>
            </section>

            <!-- LINHA DE PICOTE CENTRAL ENTRE A 1ª E A 2ª VIA -->
            <div
              v-if="idx === 0"
              class="cut-divider relative my-1.5 flex items-center justify-center py-0.5 text-sepia-500 select-none"
              aria-hidden="true"
            >
              <div class="w-full border-t border-dashed border-sepia-500" />
              <span class="mx-3 flex shrink-0 items-center gap-1.5 bg-white px-2 font-mono text-[9px] uppercase tracking-widest text-sepia-600">
                <Icon icon="mdi:content-cut" class="h-3.5 w-3.5" />
                Destacar na linha pontilhada • 1ª via empregador / 2ª via empregada doméstica
              </span>
              <div class="w-full border-t border-dashed border-sepia-500" />
            </div>
          </template>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Folha A4 de proporção fixa (210mm × 297mm). Na tela ela é escalada via
   transform para caber na largura disponível; o layout interno nunca muda. */
.a4-frame {
  position: relative;
  width: 100%;
  overflow: hidden;
}

.a4-sheet {
  width: 210mm;
  height: 297mm;
  padding: 10mm;
  box-sizing: border-box;
  overflow: hidden;
  transform-origin: top left;
}

@page {
  size: A4 portrait;
  margin: 0;
}

@media print {
  .a4-frame {
    height: auto !important;
    overflow: visible !important;
  }

  .a4-sheet {
    transform: none !important;
    width: 210mm;
    height: 297mm;
    padding: 8mm 10mm;
    margin: 0;
    page-break-after: avoid;
    page-break-inside: avoid;
    break-inside: avoid;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .receipt-copy {
    page-break-inside: avoid;
    break-inside: avoid;
  }
}
</style>
