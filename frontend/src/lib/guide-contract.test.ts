import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { isTerminal, parseGuideFrame } from './guide-schema'

/**
 * 서버가 실제로 만든 스트림을 이 화면의 스키마로 읽는다.
 *
 * 파일은 서버 쪽 계약 테스트(`bench/tests/contract/test_guide_recorded_streams.py`)가
 * 만들고, 서버가 여전히 그 모양을 내는지 그 테스트가 지킨다. 여기서는 화면이 그 모양을
 * 여전히 읽는지 지킨다. 한쪽만 바꾸면 둘 중 하나가 깨진다.
 */
const directory = join(process.cwd(), '..', 'bench', 'tests', 'fixtures', 'guide-streams')
const names = readdirSync(directory).filter((name) => name.endsWith('.json'))

describe('서버가 녹화한 스트림', () => {
  it('여섯 가지 경우가 모두 있다', () => {
    expect(names.sort()).toEqual([
      'ambiguous.json',
      'answered.json',
      'declined.json',
      'failed.json',
      'no-data.json',
      'refused-step.json',
    ])
  })

  it.each(names)('%s 의 모든 프레임을 읽고, 종결 사건 하나로 끝난다', (name) => {
    const frames: { event: string; data: unknown }[] = JSON.parse(readFileSync(join(directory, name), 'utf8'))
    const events = frames.map((frame) => parseGuideFrame(frame.event, frame.data))

    expect(events[0].type).toBe('visit')
    expect(events.filter(isTerminal)).toHaveLength(1)
    expect(isTerminal(events[events.length - 1])).toBe(true)
  })

  it('답의 인용은 전부 그 스트림의 단계가 가져온 것이다', () => {
    const frames: { event: string; data: unknown }[] = JSON.parse(readFileSync(join(directory, 'answered.json'), 'utf8'))
    const events = frames.map((frame) => parseGuideFrame(frame.event, frame.data))
    const fetched = new Set(events.flatMap((event) => (event.type === 'step' ? event.step.produced : [])))
    const answer = events.find((event) => event.type === 'answer')
    if (answer?.type !== 'answer') throw new Error('답이 없다')

    expect(answer.citations.length).toBeGreaterThan(0)
    for (const citation of answer.citations) expect(fetched.has(citation.id), citation.id).toBe(true)
  })
})
