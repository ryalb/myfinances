import { computed, reactive, ref } from 'vue'

export function useCurrentUser() {
  const user = ref<{ id: number; email: string; first_name: string; last_name: string } | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchUser = async () => {
    if (user.value) return user.value
    loading.value = true
    error.value = null
    try {
      const data = await useApi().get<{ id: number; email: string; first_name: string; last_name: string }>('/auth/me/')
      if (data) {
        user.value = data
      }
      return data
    } catch {
      error.value = 'Failed to load user'
      return null
    } finally {
      loading.value = false
    }
  }

  const fullName = computed(() => {
    if (!user.value) return ''
    const { first_name, last_name } = user.value
    return [first_name, last_name].filter(Boolean).join(' ') || user.value.email
  })

  const initials = computed(() => {
    if (!user.value) return '?'
    const { first_name, last_name, email } = user.value
    if (first_name || last_name) {
      return [first_name, last_name].filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2)
    }
    return email.slice(0, 2).toUpperCase()
  })

  const gravatarUrl = computed(() => {
    if (!user.value?.email) return ''
    return `https://www.gravatar.com/avatar/${md5(user.value.email.toLowerCase().trim())}?d=identicon`
  })

  return reactive({
    user,
    loading,
    error,
    fetchUser,
    fullName,
    initials,
    gravatarUrl,
  })
}

function md5(string: string): string {
  function rotateLeft(lValue: number, iShiftBits: number) {
    return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits))
  }
  function addUnsigned(lX: number, lY: number) {
    const lX8 = lX & 0x80000000
    const lY8 = lY & 0x80000000
    const lX4 = lX & 0x40000000
    const lY4 = lY & 0x40000000
    const lResult = (lX & 0x3FFFFFFF) + (lY & 0x3FFFFFFF)
    if (lX4 & lY4) return lResult ^ 0x80000000 ^ lX8 ^ lY8
    if (lX4 | lY4) {
      if (lResult & 0x40000000) return lResult ^ 0xC0000000 ^ lX8 ^ lY8
      return lResult ^ 0x40000000 ^ lX8 ^ lY8
    }
    return lResult ^ lX8 ^ lY8
  }
  function f(x: number, y: number, z: number) { return (x & y) | ((~x) & z) }
  function g(x: number, y: number, z: number) { return (x & z) | (y & (~z)) }
  function h(x: number, y: number, z: number) { return x ^ y ^ z }
  function inverse(x: number, y: number, z: number) { return y ^ (x | (~z)) }
  function ff(a: number, b: number, c: number, d: number, x: number, s: number, ac: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(f(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }
  function gg(a: number, b: number, c: number, d: number, x: number, s: number, ac: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(g(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }
  function hh(a: number, b: number, c: number, d: number, x: number, s: number, ac: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(h(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }
  function ii(a: number, b: number, c: number, d: number, x: number, s: number, ac: number) {
    a = addUnsigned(a, addUnsigned(addUnsigned(inverse(b, c, d), x), ac))
    return addUnsigned(rotateLeft(a, s), b)
  }
  function convertToWordArray(string: string) {
    let lWordCount
    const lMessageLength = string.length
    const lNumberOfWordsTemp1 = lMessageLength + 8
    const lNumberOfWordsTemp2 = (lNumberOfWordsTemp1 - (lNumberOfWordsTemp1 % 64)) / 64
    const lNumberOfWords = (lNumberOfWordsTemp2 + 1) * 16
    const lWordArray = new Array(lNumberOfWords - 1)
  let lBytePosition
  let lByteCount = 0
    while (lByteCount < lMessageLength) {
      lWordCount = (lByteCount - (lByteCount % 4)) / 4
      lBytePosition = (lByteCount % 4) * 8
      lWordArray[lWordCount] = lWordArray[lWordCount] | (string.charCodeAt(lByteCount) << lBytePosition)
      lByteCount++
    }
    lWordCount = (lByteCount - (lByteCount % 4)) / 4
    lBytePosition = (lByteCount % 4) * 8
    lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition)
    lWordArray[lNumberOfWords - 2] = lMessageLength << 3
    lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29
    return lWordArray
  }
  function wordToHex(lValue: number) {
    let wordToHexValue = ''
    for (let nCount = 0; nCount <= 3; nCount++) {
      const wordToHexValueTemp = (lValue >>> (nCount * 8)) & 255
      wordToHexValue += ('0' + wordToHexValueTemp.toString(16)).slice(-2)
    }
    return wordToHexValue
  }
  const x = convertToWordArray(string)
  let a = 0x67452301
  let b = 0xEFCDAB89
  let c = 0x98BADCFE
  let d = 0x10325476
  const S11 = 7, S12 = 12, S13 = 17, S14 = 22
  const S21 = 5, S22 = 9, S23 = 14, S24 = 20
  const S31 = 4, S32 = 11, S33 = 16, S34 = 23
  const S41 = 6, S42 = 10, S43 = 15, S44 = 21
  let i
  for (i = 0; i < x.length; i += 16) {
    const lA = a, lB = b, lC = c, lD = d
    a = ff(a, b, c, d, x[i], S11, 0xD76AA478)
    d = ff(d, a, b, c, x[i + 1], S12, 0xE8C7B756)
    c = ff(c, d, a, b, x[i + 2], S13, 0x242070DB)
    b = ff(b, c, d, a, x[i + 3], S14, 0xC1BDCEEE)
    a = ff(a, b, c, d, x[i + 4], S11, 0xF57C0FAF)
    d = ff(d, a, b, c, x[i + 5], S12, 0x4787C62A)
    c = ff(c, d, a, b, x[i + 6], S13, 0xA8304613)
    b = ff(b, c, d, a, x[i + 7], S14, 0xFD469501)
    a = ff(a, b, c, d, x[i + 8], S11, 0x698098D8)
    d = ff(d, a, b, c, x[i + 9], S12, 0x8B44F7AF)
    c = ff(c, d, a, b, x[i + 10], S13, 0xFFFF5BB1)
    b = ff(b, c, d, a, x[i + 11], S14, 0x895CD7BE)
    a = ff(a, b, c, d, x[i + 12], S11, 0x6B901122)
    d = ff(d, a, b, c, x[i + 13], S12, 0xFD987193)
    c = ff(c, d, a, b, x[i + 14], S13, 0xA679438E)
    b = ff(b, c, d, a, x[i + 15], S14, 0x49B40821)
    a = gg(a, b, c, d, x[i + 1], S21, 0xF61E2562)
    d = gg(d, a, b, c, x[i + 6], S22, 0xC040B340)
    c = gg(c, d, a, b, x[i + 11], S23, 0x265E5A51)
    b = gg(b, c, d, a, x[i], S24, 0xE9B6C7AA)
    a = gg(a, b, c, d, x[i + 5], S21, 0xD62F105D)
    d = gg(d, a, b, c, x[i + 10], S22, 0x2441453)
    c = gg(c, d, a, b, x[i + 15], S23, 0xD8A1E681)
    b = gg(b, c, d, a, x[i + 4], S24, 0xE7D3FBC8)
    a = gg(a, b, c, d, x[i + 9], S21, 0x21E1CDE6)
    d = gg(d, a, b, c, x[i + 14], S22, 0xC33707D6)
    c = gg(c, d, a, b, x[i + 3], S23, 0xF4D50D87)
    b = gg(b, c, d, a, x[i + 8], S24, 0x455A14ED)
    a = gg(a, b, c, d, x[i + 13], S21, 0xA9E3E905)
    d = gg(d, a, b, c, x[i + 2], S22, 0xFCEFA3F8)
    c = gg(c, d, a, b, x[i + 7], S23, 0x676F02D9)
    b = gg(b, c, d, a, x[i + 12], S24, 0x8D2A4C8A)
    a = hh(a, b, c, d, x[i + 5], S31, 0xFFFA3942)
    d = hh(d, a, b, c, x[i + 8], S32, 0x8771F681)
    c = hh(c, d, a, b, x[i + 11], S33, 0x6D9D6122)
    b = hh(b, c, d, a, x[i], S34, 0xFDE5380C)
    a = hh(a, b, c, d, x[i + 9], S31, 0xA4BEEA44)
    d = hh(d, a, b, c, x[i + 12], S32, 0x4BDECFA9)
    c = hh(c, d, a, b, x[i + 15], S33, 0xF6BB4B60)
    b = hh(b, c, d, a, x[i + 2], S34, 0xBEBFBC70)
    a = hh(a, b, c, d, x[i + 13], S31, 0x289B7EC6)
    d = hh(d, a, b, c, x[i + 6], S32, 0xEAA127FA)
    c = hh(c, d, a, b, x[i + 7], S33, 0xD4EF3085)
    b = hh(b, c, d, a, x[i + 14], S34, 0x4881D05)
    a = hh(a, b, c, d, x[i + 3], S31, 0xD9D4D039)
    d = hh(d, a, b, c, x[i + 10], S32, 0xE6DB99E5)
    c = hh(c, d, a, b, x[i + 1], S33, 0x1FA27CF8)
    b = hh(b, c, d, a, x[i + 4], S34, 0xC4AC5665)
    a = ii(a, b, c, d, x[i], S41, 0xD8AA8F)
    d = ii(d, a, b, c, x[i + 7], S42, 0x3283FAF)
    c = ii(c, d, a, b, x[i + 14], S43, 0x432AFF97)
    b = ii(b, c, d, a, x[i + 5], S44, 0xDB04351)
    a = ii(a, b, c, d, x[i + 12], S41, 0xAB9423A7)
    d = ii(d, a, b, c, x[i + 3], S42, 0xFC93A039)
    c = ii(c, d, a, b, x[i + 10], S43, 0x655B59C3)
    b = ii(b, c, d, a, x[i + 15], S44, 0x8F0CCC92)
    a = ii(a, b, c, d, x[i + 8], S41, 0xFFEFF47D)
    d = ii(d, a, b, c, x[i + 1], S42, 0x85845DD1)
    c = ii(c, d, a, b, x[i + 6], S43, 0x6FA87E4F)
    b = ii(b, c, d, a, x[i + 14], S44, 0xFE2CE6E0)
    a = ii(a, b, c, d, x[i + 11], S41, 0xA3014314)
    d = ii(d, a, b, c, x[i + 4], S42, 0x4E0811A1)
    c = ii(c, d, a, b, x[i + 9], S43, 0xF7537E82)
    b = ii(b, c, d, a, x[i + 2], S44, 0xBD3AF235)
    a = addUnsigned(a, lA)
    b = addUnsigned(b, lB)
    c = addUnsigned(c, lC)
    d = addUnsigned(d, lD)
  }
  const tempValue = wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)
  return tempValue.toLowerCase()
}
