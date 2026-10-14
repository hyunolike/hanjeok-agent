import type { Citation } from '@/lib/guide-schema'

const KIND: Record<Citation['kind'], string> = {
  record: 'bg-cite-record-soft text-cite-record-text',
  policy: 'bg-cite-policy-soft text-cite-policy-text',
}

/**
 * 인용 하나. 누르면 그 근거가 열린다.
 *
 * 두 종류를 색으로만 가르지 않는다 — 앞에 종류 이름을 글로 붙인다. 레코드는 사실,
 * 정책 문서는 이유라서, 둘이 섞여 보이면 "한적이 그렇게 정했다"와 "그날 그랬다"가
 * 구분되지 않는다.
 */
export function CitationChip({
  citation,
  kindLabel,
  onOpen,
}: {
  citation: Citation
  kindLabel: string
  onOpen: (citation: Citation) => void
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      data-citation-kind={citation.kind}
      className={`inline-flex min-h-control-sm items-center gap-2 rounded-chip px-3 text-left text-caption focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary ${KIND[citation.kind]}`}
    >
      <span className="font-semibold">{kindLabel}</span>
      <span>{citation.label}</span>
    </button>
  )
}
