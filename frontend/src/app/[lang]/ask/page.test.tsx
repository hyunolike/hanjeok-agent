import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import * as guide from '@/lib/guide'
import AskPage from './page'
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn() }), notFound: () => { throw new Error('notFound') } }))
afterEach(() => vi.restoreAllMocks())
const place = { place_id: 653, name: '경복궁', region: '서울 종로구', category: '고궁', overview: '', has_congestion_data: true }
const renderPage = async (searchParams: Record<string, string | string[]>) => render(await AskPage({ params: Promise.resolve({lang:'ko'}), searchParams: Promise.resolve(searchParams) }))
it('선택한 ID를 확인한 뒤 지역이 있는 장소 맥락과 편집 가능한 초안을 보여 준다', async () => {
  vi.spyOn(guide, 'fetchPlace').mockResolvedValue({ok:true, data:{place,related:[],events:[],as_of:'2026-10-18'}})
  await renderPage({place:'653'})
  expect(screen.getByRole('region',{name:'선택한 장소'})).toHaveTextContent('경복궁 · 서울 종로구')
  expect(screen.getByLabelText('질문')).toHaveValue('이 장소의 특징과 주변에 갈 만한 곳을 알려줘.')
  expect(screen.getByRole('link',{name:'장소 선택 해제'})).toHaveAttribute('href','/ko/ask')
})
it('잘못된 장소 주소를 일반 질문으로 조용히 바꾸지 않는다', async () => {
  const request = vi.spyOn(guide, 'fetchPlace')
  await renderPage({place:'653oops'})
  expect(screen.getByRole('alert')).toHaveTextContent('장소 주소를 확인해 주세요')
  expect(screen.queryByLabelText('질문')).not.toBeInTheDocument()
  expect(request).not.toHaveBeenCalled()
})
it('장소 조회 실패는 재시도를 제공하고 맥락 없는 전송을 막는다', async () => {
  vi.spyOn(guide, 'fetchPlace').mockResolvedValue({ok:false,cause:'unavailable'})
  await renderPage({place:'653'})
  expect(screen.getByRole('alert')).toHaveTextContent('선택한 장소를 불러오지 못했어요')
  expect(screen.getByRole('button',{name:'다시 시도'})).toBeInTheDocument()
  expect(screen.queryByLabelText('질문')).not.toBeInTheDocument()
})
it('영어 화면에서도 같은 장소를 확인하고 영어 초안을 제공한다', async () => {
  vi.spyOn(guide, 'fetchPlace').mockResolvedValue({ok:true, data:{place,related:[],events:[],as_of:'2026-10-18'}})
  render(await AskPage({params:Promise.resolve({lang:'en'}),searchParams:Promise.resolve({place:'653'})}))
  expect(screen.getByRole('region',{name:'Selected place'})).toHaveTextContent('경복궁 · 서울 종로구')
  expect(screen.getByLabelText('Question')).toHaveValue('Tell me about this place and related places nearby.')
})
it('없는 장소 ID는 잘못된 선택으로 표시한다', async () => {
  vi.spyOn(guide, 'fetchPlace').mockResolvedValue({ok:false,cause:'not_found'})
  await renderPage({place:'999999999'})
  expect(screen.getByRole('alert')).toHaveTextContent('장소 주소를 확인해 주세요')
  expect(screen.queryByLabelText('질문')).not.toBeInTheDocument()
})
it('선택 없이 연 질문 화면에는 장소 조회와 미리 채운 질문이 없다', async () => {
  const request = vi.spyOn(guide, 'fetchPlace')
  await renderPage({})
  expect(screen.getByLabelText('질문')).toHaveValue('')
  expect(request).not.toHaveBeenCalled()
})
