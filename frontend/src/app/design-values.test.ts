import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { CONTRAST_PAIRS, contrastRatio, readDesignValues } from '@/lib/design-values'

// jsdom 환경에서는 import.meta.url 이 file: 이 아니다.
const css = readFileSync(join(process.cwd(), 'src/app/globals.css'), 'utf8')
const values = readDesignValues(css)

describe('디자인 값', () => {
  it('밝은 화면과 어두운 화면이 같은 용도 이름을 모두 갖는다', () => {
    // 다크에서 빠진 이름은 밝은 값을 그대로 물려받는다 — 어두운 바탕에 어두운 글자가 된다.
    const paired = CONTRAST_PAIRS.flatMap((pair) => [pair.ink, pair.surface])
    for (const name of new Set(paired)) {
      expect(values.light[name], `light ${name}`).toMatch(/^#[0-9a-f]{6}$/)
      expect(values.dark[name], `dark ${name}`).toMatch(/^#[0-9a-f]{6}$/)
    }
  })

  it.each(CONTRAST_PAIRS)('$ink 는 $surface 위에서 4.5:1 이상으로 읽힌다', ({ ink, surface }) => {
    for (const mode of ['light', 'dark'] as const) {
      const ratio = contrastRatio(values[mode][ink], values[mode][surface])
      expect(ratio, `${mode} ${ink} on ${surface} = ${ratio.toFixed(2)}`).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('"데이터 없음"은 어떤 등급과도 같은 색이 아니다', () => {
    for (const mode of ['light', 'dark'] as const) {
      const unknown = values[mode]['grade-unknown-soft']
      for (const grade of ['relaxed', 'normal', 'crowded', 'very-crowded']) {
        expect(values[mode][`grade-${grade}-soft`]).not.toBe(unknown)
      }
    }
  })

  it('컴포넌트가 쓰는 색 유틸리티는 전부 용도 이름을 가리킨다', () => {
    // @theme 에 원색이 직접 들어가면 bg-[그 값] 이 다크에서 따라 바뀌지 않는다.
    const theme = css.slice(css.indexOf('@theme inline'))
    const colours = [...theme.matchAll(/--color-[a-z0-9-]+:\s*([^;]+);/g)].map((m) => m[1].trim())
    expect(colours.length).toBeGreaterThan(40)
    for (const value of colours) expect(value).toMatch(/^var\(--(?!raw-)[a-z0-9-]+\)$/)
  })
})

/** `src` 아래의 화면 파일 전부. 테스트 파일은 뺀다 — 화면이 아니다. */
function screens(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return screens(path)
    return /\.tsx$/.test(entry.name) && !/\.test\.tsx$/.test(entry.name) ? [path] : []
  })
}

describe('화면', () => {
  // 용도 이름 밖의 색이나 글자 크기를 화면이 직접 적으면, 그 화면만 다크에서 어긋나고
  // 값 하나를 바꿔도 따라오지 않는다. 한 번 옮겨 놓은 것이 다시 흩어지지 않게 지킨다.
  const RAW = [
    /\b(?:black|white)\/\d+/,
    /\b(?:red|rose|amber|emerald|green|sky|blue|gray|slate|zinc|neutral|stone)-\d{2,3}\b/,
    /(?<![:\w-])opacity-\d+/,
    /\btext-(?:xs|sm|base|lg|xl|[2-9]xl)\b/,
    /#[0-9a-fA-F]{6}\b/,
  ]

  it.each(screens(join(process.cwd(), 'src')))('%s 는 용도 이름만 쓴다', (path) => {
    const source = readFileSync(path, 'utf8')
    for (const pattern of RAW) expect(source.match(pattern)?.[0], String(pattern)).toBeUndefined()
  })
})

describe('contrastRatio', () => {
  it('검정과 흰색은 21:1 이다', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 5)
  })
})
