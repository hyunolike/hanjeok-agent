import { describe, expect, it } from 'vitest'
import { DEMO_PROVES } from './demo-courses'
import { dict, isLang, LANGS, OTHER_LANG } from './i18n'

describe('화면 언어', () => {
  it('모르는 언어를 언어로 보지 않는다', () => {
    // `/de` 가 기본 언어 화면으로 200 을 주면, 없는 번역이 있는 것처럼 보인다.
    expect(isLang('ko')).toBe(true)
    expect(isLang('en')).toBe(true)
    expect(isLang('de')).toBe(false)
    expect(isLang('')).toBe(false)
    expect(isLang('KO')).toBe(false)
  })

  it('반대편 언어를 두 번 타면 제자리로 온다', () => {
    // 토글이 한쪽으로만 가면 영어 화면에 갇힌다.
    for (const lang of LANGS) expect(OTHER_LANG[OTHER_LANG[lang]]).toBe(lang)
  })

  it('영어에 빈 문구가 없다', () => {
    // 키가 빠지는 것은 타입이 잡지만, 빈 문자열은 잡지 못한다. 자리만 채운 번역은
    // 화면에서 공백으로 나타나고 그건 누락보다 알아채기 어렵다.
    const strings = (value: unknown): string[] =>
      typeof value === 'string'
        ? [value]
        : Array.isArray(value)
          ? value.flatMap(strings)
          : value && typeof value === 'object'
            ? Object.values(value).flatMap(strings)
            : []

    for (const lang of LANGS) {
      for (const text of strings(dict(lang))) expect(text.trim()).not.toBe('')
    }
  })

  it('영어 화면은 본문이 한국어로 생성된다는 것을 밝힌다', () => {
    // 코스와 설명은 번역되지 않는다. 화면이 그 말을 안 하면 "번역이 덜 됐다"로 읽힌다.
    expect(dict('en').home.generatedLanguageNote).toBeTruthy()
    // 한국어 화면에서는 할 필요가 없는 말이다.
    expect(dict('ko').home.generatedLanguageNote).toBeNull()
  })

  it('데모 종류마다 무엇을 볼지 두 언어로 적혀 있다', () => {
    // 종류를 늘리면 타입이 두 언어 모두에서 컴파일을 깨뜨린다. 여기서는 그 칸에
    // 실제로 문장이 들어갔는지를 본다 — 홈에서 이 줄이 코스를 고를 유일한 근거다.
    for (const lang of LANGS) {
      for (const text of Object.values(DEMO_PROVES[lang])) expect(text.length).toBeGreaterThan(10)
    }
  })
})
