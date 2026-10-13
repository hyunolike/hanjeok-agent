import type { ReactNode } from 'react'

/** 방문자가 놓일 수 있는 상태 여섯. 포즈는 상태마다 하나다. */
export const CHARACTER_STATES = ['waiting', 'looking', 'found', 'choose', 'no-data', 'failed'] as const

export type CharacterState = (typeof CHARACTER_STATES)[number]

const SIZE = { sm: 64, md: 112, lg: 160 } as const

/**
 * 안내 캐릭터 잎새.
 *
 * **그림은 장식이고 상태는 글이 전한다.** 그래서 이 컴포넌트는 제목 없이 쓸 수
 * 없게 되어 있다 — 그림만 놓을 방법이 없다. 이미지에는 빈 alt 를 준다. 같은 내용을
 * 바로 옆 글이 말하고 있어서, alt 를 채우면 스크린 리더가 같은 말을 두 번 읽는다.
 *
 * 캐릭터는 버튼이 아니다. 누를 것은 `children` 으로 넣는다.
 *
 * 그림은 완성된 정지 포즈다. `looking` 에만 떠 있는 움직임이 붙고, 움직임을 줄여
 * 달라고 한 사람에게는 `globals.css` 가 그것을 멈춘다.
 */
export function Character({
  state,
  title,
  size = 'md',
  children,
}: {
  state: CharacterState
  title: string
  size?: keyof typeof SIZE
  children?: ReactNode
}) {
  const px = SIZE[size]
  return (
    <div className="flex flex-col items-center gap-3 text-center sm:flex-row sm:items-start sm:text-left" data-character-state={state}>
      {/* 다음 이미지 최적화를 쓰지 않는다 — 384px 짜리 투명 그림 여섯 장이고, 그대로 내보내는 편이 단순하다. */}
      <img
        src={`/brand/guide/${state}.webp`}
        alt=""
        width={px}
        height={px}
        className={`shrink-0 ${state === 'looking' ? 'animate-[guide-hover_2.4s_ease-in-out_infinite]' : ''}`}
      />
      <div className="flex min-w-0 flex-col gap-2">
        <p className="text-title-2 text-ink-title">{title}</p>
        {children}
      </div>
    </div>
  )
}
