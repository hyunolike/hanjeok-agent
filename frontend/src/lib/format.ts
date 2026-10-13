import type { Lang } from './i18n'

/**
 * 시각은 언제나 한국 시간으로 적는다. 한적의 예보와 내보내기 시각이 그 기준이고,
 * 보는 사람의 시간대로 바꾸면 "10월 17일 예보"가 다른 날짜로 보이는 사람이 생긴다.
 */
export function formatSeoul(iso: string, lang: Lang): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat(lang === 'ko' ? 'ko-KR' : 'en-GB', {
    timeZone: 'Asia/Seoul',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}
