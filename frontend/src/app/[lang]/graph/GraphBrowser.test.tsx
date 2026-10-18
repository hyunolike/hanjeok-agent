import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { fetchPlace, fetchPlaces, fetchStatus } from '@/lib/guide'
import { GraphBrowser, neighbourhoodPath } from './GraphBrowser'

/** 녹화본을 읽는다. 화면은 실제 클라이언트와 같은 결과를 받는다. */
const recorded = {
  fetchPlaces: (query: string) => fetchPlaces(query, { baseUrl: '' }),
  fetchPlace: (id: number) => fetchPlace(id, { baseUrl: '' }),
  fetchStatus: () => fetchStatus({ baseUrl: '' }),
}

async function search(query: string) {
  await userEvent.type(screen.getByLabelText('장소 이름'), query)
  await userEvent.click(screen.getByRole('button', { name: '찾기' }))
}

describe('GraphBrowser', () => {
  it('데이터 기준 시각과 실린 양을 보여 준다', async () => {
    render(<GraphBrowser lang="ko" api={recorded} />)
    expect(await screen.findByText(/한적 데이터 기준 시각 .* 장소 7곳, 연관 10건/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '찾기' })).toBeDisabled()
  })

  it('이름으로 찾고, 고른 장소의 이웃을 한적의 순위대로 보여 준다', async () => {
    render(<GraphBrowser lang="ko" api={recorded} />)
    await search('가람')
    await userEvent.click(await screen.findByRole('button', { name: /가람궁/ }))

    const panel = await screen.findByTestId('place-panel')
    expect(within(panel).getByRole('heading', { name: '가람궁' })).toBeInTheDocument()
    expect(within(panel).getByText('한빛시 가람구 · 고궁')).toBeInTheDocument()
    const related = within(within(panel).getByTestId('related-places')).getAllByRole('button')
    expect(related.map((b) => b.textContent)).toEqual([
      '1순위솔내 한옥마을 · 한빛시 가람구',
      '2순위물빛 서원 · 한빛시 솔내구',
      '3순위달맞이 숲길 · 한빛시 솔내구',
    ])
    // 행사는 목록에 한 번, 그림에 한 번 나온다.
    expect(within(panel).getAllByText('가람궁 달빛 야행').length).toBeGreaterThan(0)
    expect(within(panel).getByText('2026-10-16 – 2026-10-25')).toBeInTheDocument()
  })

  it('예보 대상인 곳에는 값을 적지 않고 물어보라고 안내한다', async () => {
    render(<GraphBrowser lang="ko" initialPlaceId={101} api={recorded} />)
    const panel = await screen.findByTestId('place-panel')
    expect(within(panel).getByText('혼잡 예보 대상')).toBeInTheDocument()
    expect(within(panel).getByRole('link', { name: '이 장소에 대해 물어보기' })).toHaveAttribute('href', '/ko/ask?place=101')
    expect(panel).not.toHaveTextContent(/매우혼잡|여유|상위 \d+%/)
  })

  it('예보 대상이 아닌 곳은 "데이터 없음"이고, 한적하다고 말하지 않는다', async () => {
    render(<GraphBrowser lang="ko" initialPlaceId={150} api={recorded} />)
    const panel = await screen.findByTestId('place-panel')
    expect(within(panel).getByText('혼잡 데이터 없음')).toBeInTheDocument()
    expect(within(panel).getByText(/한적하다는 뜻이 아닙니다/)).toBeInTheDocument()
    expect(within(panel).queryByRole('link', { name: '이 장소에 대해 물어보기' })).not.toBeInTheDocument()
    expect(within(panel).getByText('이어 둔 장소가 없습니다.')).toBeInTheDocument()
  })

  it('이웃을 누르면 그 장소로 옮겨 간다', async () => {
    render(<GraphBrowser lang="ko" initialPlaceId={101} api={recorded} />)
    await userEvent.click(await screen.findByRole('button', { name: /물빛 서원/ }))
    expect(await screen.findByRole('heading', { name: '물빛 서원' })).toBeInTheDocument()
  })

  it('찾는 이름이 없으면 그렇게 말한다', async () => {
    render(<GraphBrowser lang="ko" api={recorded} />)
    await search('없는곳')
    expect(await screen.findByText(/"없는곳"\(이\)라는 이름의 장소를 찾지 못했습니다/)).toBeInTheDocument()
  })

  it('없는 장소는 글로 말하고 빈 그림을 그리지 않는다', async () => {
    const { container } = render(<GraphBrowser lang="ko" initialPlaceId={999} api={recorded} />)
    expect(await screen.findByText('그런 장소가 없습니다')).toBeInTheDocument()
    expect(screen.queryByTestId('place-panel')).not.toBeInTheDocument()
    expect(container.querySelector('svg')).toBeNull()
  })

  it('서버에 닿지 못하면 다시 시도할 수 있다', async () => {
    const fetchPlaceOnce = vi
      .fn<typeof recorded.fetchPlace>()
      .mockResolvedValueOnce({ ok: false, cause: 'unavailable' })
      .mockImplementation(recorded.fetchPlace)
    const { container } = render(
      <GraphBrowser lang="ko" initialPlaceId={101} api={{ ...recorded, fetchPlace: fetchPlaceOnce }} />,
    )
    expect(await screen.findByText('장소를 불러오지 못했습니다')).toBeInTheDocument()
    expect(container.querySelector('svg')).toBeNull()

    await userEvent.click(screen.getByRole('button', { name: '다시 물어보기' }))
    expect(await screen.findByTestId('place-panel')).toBeInTheDocument()
  })
})

describe('neighbourhoodPath', () => {
  it('받은 이웃만 옮기고 순위를 그대로 싣는다', async () => {
    const result = await recorded.fetchPlace(101)
    if (!result.ok) throw new Error('녹화본이 없다')
    const path = neighbourhoodPath(result.data)
    expect(path.edges.filter((e) => e.kind === 'related').map((e) => [e.to, e.rank])).toEqual([
      ['hanjeok:place/118', 1],
      ['hanjeok:place/124', 2],
      ['hanjeok:place/131', 3],
    ])
    expect(path.nodes.filter((n) => n.kind === 'region').map((n) => n.label)).toEqual(['한빛시 가람구', '한빛시 솔내구'])
    const ids = new Set(path.nodes.map((n) => n.id))
    for (const edge of path.edges) expect(ids.has(edge.from) && ids.has(edge.to)).toBe(true)
  })
})

it('검색 중 진행 상태와 스켈레톤을 보여 주고 중복 제출을 막는다', async () => {
  let finish: (value: Awaited<ReturnType<typeof fetchPlaces>>) => void = () => {}
  const waiting = vi.fn<typeof fetchPlaces>(() => new Promise(resolve => { finish = resolve }))
  render(<GraphBrowser lang="ko" api={{ ...recorded, fetchPlaces: waiting }} />)
  await search('가람')
  expect(screen.getByRole('region', { name: '장소를 찾고 있어요' })).toHaveTextContent('장소를 찾고 있어요')
  expect(screen.getByLabelText('장소 이름')).toBeDisabled()
  expect(screen.getByRole('button', { name: '찾는 중' })).toBeDisabled()
  await userEvent.click(screen.getByRole('button', { name: '찾는 중' }))
  expect(waiting).toHaveBeenCalledTimes(1)
  finish(await recorded.fetchPlaces('가람'))
  expect(await screen.findByRole('heading', { name: /찾은 장소/ })).toBeInTheDocument()
  expect(screen.queryByText('장소를 찾고 있어요')).not.toBeInTheDocument()
})
it('검색 실패나 예외 후 로딩을 종료하고 같은 검색을 재시도한다', async () => {
  const request = vi.fn<typeof fetchPlaces>().mockRejectedValueOnce(new Error('network')).mockImplementation(recorded.fetchPlaces)
  render(<GraphBrowser lang="ko" api={{ ...recorded, fetchPlaces: request }} />)
  await search('가람')
  await userEvent.click(await screen.findByRole('button', { name: '검색 다시 시도' }))
  expect(await screen.findByRole('heading', { name: /찾은 장소/ })).toBeInTheDocument()
  expect(screen.queryByText('장소를 찾고 있어요')).not.toBeInTheDocument()
})
