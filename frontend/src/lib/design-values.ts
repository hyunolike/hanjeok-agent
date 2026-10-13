/**
 * 디자인 값의 원본은 `app/globals.css` 하나다. 이 파일은 값을 갖지 않는다 —
 * 그 CSS 를 읽어 푸는 방법과, 어떤 글자가 어떤 바탕 위에 놓이는지만 안다.
 *
 * 값을 여기에도 적으면 두 곳이 어긋나는 날이 온다. 그래서 명암비 테스트와
 * `/design` 화면이 둘 다 같은 CSS 를 읽는다.
 */

export type Appearance = 'light' | 'dark'
export type DesignValues = Record<Appearance, Record<string, string>>

/** 글자색과 그 글자가 실제로 놓이는 바탕. `/design` 화면과 명암비 테스트가 함께 쓴다. */
export const CONTRAST_PAIRS: ReadonlyArray<{ ink: string; surface: string }> = [
  { ink: 'ink-title', surface: 'surface-canvas' },
  { ink: 'ink-title', surface: 'surface-panel' },
  { ink: 'ink-title', surface: 'surface-subtle' },
  { ink: 'ink-body', surface: 'surface-canvas' },
  { ink: 'ink-body', surface: 'surface-panel' },
  { ink: 'ink-body', surface: 'surface-subtle' },
  { ink: 'ink-muted', surface: 'surface-canvas' },
  { ink: 'ink-muted', surface: 'surface-panel' },
  { ink: 'ink-muted', surface: 'surface-subtle' },
  { ink: 'ink-inverse', surface: 'surface-inverse' },
  { ink: 'brand-on-primary', surface: 'brand-primary' },
  { ink: 'brand-primary', surface: 'surface-panel' },
  { ink: 'brand-primary', surface: 'brand-soft' },
  { ink: 'grade-relaxed-text', surface: 'grade-relaxed-soft' },
  { ink: 'grade-normal-text', surface: 'grade-normal-soft' },
  { ink: 'grade-crowded-text', surface: 'grade-crowded-soft' },
  { ink: 'grade-very-crowded-text', surface: 'grade-very-crowded-soft' },
  { ink: 'grade-unknown-text', surface: 'grade-unknown-soft' },
  { ink: 'status-info-text', surface: 'status-info-soft' },
  { ink: 'status-success-text', surface: 'status-success-soft' },
  { ink: 'status-warning-text', surface: 'status-warning-soft' },
  { ink: 'status-danger-text', surface: 'status-danger-soft' },
  { ink: 'cite-record-text', surface: 'cite-record-soft' },
  { ink: 'cite-policy-text', surface: 'cite-policy-soft' },
]

function declarations(block: string): Record<string, string> {
  const found: Record<string, string> = {}
  for (const match of block.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) found[match[1]] = match[2].trim()
  return found
}

function resolve(name: string, scope: Record<string, string>, depth = 0): string {
  const value = scope[name]
  if (value === undefined || depth > 8) return value ?? ''
  const reference = /^var\(--([a-z0-9-]+)\)$/.exec(value)
  return reference ? resolve(reference[1], scope, depth + 1) : value.toLowerCase()
}

/** `:root` 블록과 다크 블록을 읽어, 용도 이름마다 최종 색을 푼다. */
export function readDesignValues(css: string): DesignValues {
  const darkStart = css.indexOf('@media (prefers-color-scheme: dark)')
  const themeStart = css.indexOf('@theme inline')
  if (darkStart < 0 || themeStart < 0) throw new Error('globals.css 의 구조가 바뀌었다')

  const light = declarations(css.slice(css.indexOf(':root'), darkStart))
  const dark = { ...light, ...declarations(css.slice(darkStart, themeStart)) }

  const names = Object.keys(light).filter((name) => !name.startsWith('raw-'))
  return {
    light: Object.fromEntries(names.map((name) => [name, resolve(name, light)])),
    dark: Object.fromEntries(names.map((name) => [name, resolve(name, dark)])),
  }
}

function channel(value: number): number {
  const scaled = value / 255
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16))
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/** WCAG 2.1 명암비. 1(같은 색)부터 21(검정과 흰색)까지. */
export function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}
