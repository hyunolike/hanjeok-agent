/**
 * 화면 문구 사전.
 *
 * **번역되는 것은 화면의 껍데기뿐이다.** 코스 제목, 각 항목의 `reason`, LLM 설명,
 * 번들의 근거 문서 아홉 개는 전부 한국어로 생성되고 여기서 손대지 않는다. 영어
 * 화면이 그 사실을 말하지 않으면 "번역이 덜 됐다"로 읽히므로 `generatedLanguageNote`
 * 로 화면이 직접 밝힌다.
 *
 * 혼잡도 등급 라벨(`grades.ts`)도 번역하지 않는다. 네 단계의 이름은 위키의
 * `records/congestion/grade-policy.json` 이 정하고 그 문서는 번들에 실려 모델도 같은
 * 것을 본다 — 화면이 영어 이름을 새로 지어내면 서버의 GRADE_MISLABEL 검사가 막고
 * 있는 바로 그 오류를 화면이 저지른다.
 */
export const LANGS = ['ko', 'en'] as const

export type Lang = (typeof LANGS)[number]

export const DEFAULT_LANG: Lang = 'ko'

export function isLang(value: string): value is Lang {
  return (LANGS as readonly string[]).includes(value)
}

/** 반대편 언어. 토글은 상태가 아니라 두 URL 사이의 이동이다. */
export const OTHER_LANG: Record<Lang, Lang> = { ko: 'en', en: 'ko' }

const REPO = 'https://github.com/hyunolike/hanjeok-agent'

/**
 * 한국어가 원본이다. `Dict` 를 이 객체에서 파생시키므로 영어에서 키 하나만 빠져도
 * 컴파일이 깨진다 — 사전이 갈라지는 것을 배포가 아니라 타입 검사에서 잡는다.
 *
 * 한국어 값은 이 화면이 원래 쓰던 문구와 글자까지 같다. 기존 테스트가 그 문구를
 * 그대로 조회하고 있어서, 사전으로 옮기는 것만으로 화면이 바뀌면 안 된다.
 */
const ko = {
  nav: {
    brand: 'Hermes Agent',
    evidence: '근거 문서',
    /** 반대편 언어 화면으로 가는 링크. 그 언어로 쓴다. */
    switchTo: 'English',
  },

  home: {
    ruleTitle: '순위는 백엔드가 정합니다. LLM은 설명만 씁니다.',
    ruleBody:
      '어디를 언제 갈지 고르는 것은 한적 백엔드입니다. 모델이 하는 일은 그 결과를 문장으로 옮기는 것뿐이고, 근거로 쓸 수 있는 문서는 미리 정해 둔 번들 안에만 있습니다.',
    ruleConsequence:
      '번들에 없는 문서를 인용하면 그 설명은 통째로 버려집니다. 틀린 문장만 골라 지우지 않습니다.',
    // 설명이 실패하면 블록이 조용히 사라진다(스펙 §6.1). 제품으로는 옳지만 처음 보는
    // 사람에게는 아무 일도 없었던 것처럼 보인다. 그 빈자리를 만나기 전에 여기서 말한다.
    silentFailure:
      '그래서 설명을 만들지 못한 코스에는 사과문 대신 빈자리가 남습니다. 장소와 혼잡도 등급은 그대로 있고 설명 문단만 없습니다.',

    metricsTitle: '화면에 적힌 숫자는 전부 실측입니다',
    bundle: {
      value: (docs: number, bytes: string) => `문서 ${docs}개 · ${bytes}바이트`,
      /** 번들 목록을 못 받았을 때. 숫자를 지어내는 대신 못 받았다고 적는다. */
      unavailable: '번들 목록을 불러오지 못했습니다',
      label: '모델이 매 요청 보는 근거의 전부입니다. 검색도 색인도 없습니다.',
      cta: '문서 열어 보기',
    },
    forbidden: {
      value: '위반율 0%',
      label: '금지 행동 8종을 매 실행마다 셉니다. 후보 모델 둘 다 여덟 항목에서 0%였습니다.',
      cta: '금지 행동 8종 보기',
      href: `${REPO}/blob/main/README.ko.md#-금지-행동-8종`,
    },
    citationGuard: {
      value: '5회 중 5회 차단',
      label: '첫 실제 실행에서, 지어낸 인용이 답 전체를 막았습니다.',
      cta: '검증 방식 보기',
      href: `${REPO}/blob/main/README.ko.md#2-인용-검증--테스트가-아니라-런타임-방어선`,
    },

    demoTitle: '데모 코스',
    demoIntro:
      '다섯 코스는 각각 다른 상황을 겁니다. 설명이 없는 말을 지어내기 쉬운 자리를 하나씩 골라 둔 것입니다.',
    provesLabel: '확인할 것',

    emptyTitle: '데모 코스가 아직 설정되지 않았습니다.',
    emptyBody: (missing: string) =>
      `한적에 코스를 만들고 uuid를 src/lib/demo-courses.ts에 넣으면 여기에 뜹니다. 아직 채워지지 않은 종류: ${missing}`,

    openAnySummary: '코스 uuid로 직접 열기',
    openAnyNote:
      '위 목록은 종류별로 고른 예시입니다. 서버는 데모 uuid를 특별 취급하지 않으므로 한적에 있는 코스라면 어느 것이든 열립니다.',

    // 한국어 화면에서는 할 필요가 없는 말이다. 영어 화면에서만 뜬다.
    generatedLanguageNote: null as string | null,
  },

  openAny: {
    label: '코스 uuid로 열기',
    placeholder: '한적에서 만든 코스의 uuid',
    submit: '열기',
  },

  course: {
    loadFailTitle: '코스를 불러오지 못했습니다',
    loadFailBody: (status: number) =>
      `한적에서 사실을 받지 못했습니다(${status}). 코스가 삭제되었거나 백엔드가 내려가 있습니다.`,
    noForecast: '예보 없음',
    travelMinutes: (minutes: number) => `이동 ${minutes}분`,
    reductionRate: (rate: number) => `혼잡도 ${rate}% 낮음`,
    noAlternatives:
      '이 근처에는 대안으로 삼을 만한 조용한 실내 장소가 없었습니다. 점수가 낮아 밀린 것이 아니라 후보 자체가 없었습니다.',
    // 코스와 설명은 지금 똑같이 생긴 회색 상자다. 이 프로젝트의 주장이 곧 그 둘 사이의
    // 경계인데, 화면이 그 경계를 그리지 않고 있었다.
    backendBoundary:
      '여기까지가 백엔드의 결과입니다. 장소와 순서, 혼잡도 등급은 아래 설명과 상관없이 정해졌습니다.',
    llmBadge: '아래 문단은 LLM이 썼습니다',
    citationsLabel: (count: number) =>
      `근거 ${count}개. 모두 번들에 있는 문서이고, 누르면 모델이 읽은 그대로 열립니다.`,
  },

  ask: {
    heading: '이 코스에 대해 더 묻기',
    placeholder: '이 코스에 대해 물어보세요',
    submit: '묻기',
    submitting: '묻는 중…',
    failed: '답을 만들지 못했어요. 잠시 후 다시 물어봐 주세요.',
    suggestions: ['왜 이 순서예요?', '왜 이 장소들이에요?', '다른 날이 더 나은가요?'],
    looking: {
      congestion: '혼잡도를 다시 확인하는 중',
      alternatives: '주변 대안을 찾아보는 중',
      fallback: '자료를 더 찾아보는 중',
    },
  },

  citation: {
    close: '닫기',
    loading: '불러오는 중…',
    notInBundle: (status: number) => `이 문서는 번들에 없습니다 (${status}).`,
  },

  evidence: {
    title: '근거 문서',
    count: (docs: number, bytes: string) =>
      `문서 ${docs}개 · ${bytes}바이트. 모델은 매 요청 이 전부를 봅니다.`,
    // 아래 목록의 바이트를 더하면 이 숫자보다 작다. 문서 사이의 구분 줄이 프롬프트에는
    // 실리기 때문인데, 말해 주지 않으면 화면이 자기 숫자와 어긋나 보인다.
    sumNote: (sum: string) =>
      `아래 문서 본문만 더하면 ${sum}바이트입니다. 차이는 문서 사이의 구분 줄이고, 그것도 프롬프트에 함께 들어갑니다.`,
    why: '검색해서 골라 오는 구조가 아닙니다. 번들이 통째로 프롬프트에 들어가고, 여기 없는 경로를 인용한 답은 사용자에게 닿기 전에 막힙니다.',
    loading: '불러오는 중…',
    loadFailBody: (status: number) => `문서를 불러오지 못했습니다 (${status}).`,
    listFailTitle: '근거 문서를 불러오지 못했습니다',
    listFailBody: (status: number) => `에이전트 서버가 번들 목록을 주지 않았습니다(${status}).`,
  },
}

/** `ko` 를 그대로 모양으로 삼는다. 영어가 여기서 벗어나면 타입 검사가 잡는다. */
export type Dict = typeof ko

const en: Dict = {
  nav: {
    brand: 'Hermes Agent',
    evidence: 'Evidence',
    switchTo: '한국어',
  },

  home: {
    ruleTitle: 'The backend decides the ranking. The LLM only writes the explanation.',
    ruleBody:
      'Where to go and when is decided by the hanjeok backend. All the model does is put that result into sentences, and the only documents it may cite live in a bundle fixed ahead of time.',
    ruleConsequence:
      'Cite a document that is not in the bundle and the whole explanation is thrown away. It is not edited down to the parts that were fine.',
    silentFailure:
      'So a course whose explanation could not be produced is left with a gap rather than an apology. The stops and congestion grades stay; only the explanation is missing.',

    metricsTitle: 'Every number on this site is measured',
    bundle: {
      value: (docs: number, bytes: string) => `${docs} documents · ${bytes} bytes`,
      unavailable: 'Could not load the bundle listing',
      label: 'This is everything the model sees on every request. No retrieval, no index.',
      cta: 'Open the documents',
    },
    forbidden: {
      value: '0% violations',
      label:
        'Eight forbidden behaviours, counted on every run. Both candidate models scored 0% on all eight.',
      cta: 'See the eight',
      href: `${REPO}/blob/main/README.md#-the-eight-forbidden-behaviours`,
    },
    citationGuard: {
      value: 'Blocked 5 of 5',
      label: 'On the first real run, a fabricated citation stopped the entire answer.',
      cta: 'See how it is checked',
      href: `${REPO}/blob/main/README.md#2-citation-validation--a-runtime-guard-not-a-test`,
    },

    demoTitle: 'Demo courses',
    demoIntro:
      'Each of the five sets up a different situation — one spot per course where an explanation would find it easy to make something up.',
    provesLabel: 'What to watch',

    emptyTitle: 'No demo courses are configured yet.',
    emptyBody: (missing: string) =>
      `Create a course in hanjeok and put its uuid in src/lib/demo-courses.ts. Kinds still missing: ${missing}`,

    openAnySummary: 'Open a course by uuid',
    openAnyNote:
      'The list above is one example per kind. The server gives demo uuids no special treatment, so any course that exists in hanjeok will open.',

    generatedLanguageNote:
      'Course data, citations and the explanation itself are generated in Korean — only this interface is translated.',
  },

  openAny: {
    label: 'Open by course uuid',
    placeholder: 'uuid of a course created in hanjeok',
    submit: 'Open',
  },

  course: {
    loadFailTitle: 'Could not load this course',
    loadFailBody: (status: number) =>
      `No facts came back from hanjeok (${status}). The course was deleted, or the backend is down.`,
    noForecast: 'no forecast',
    travelMinutes: (minutes: number) => `${minutes} min away`,
    reductionRate: (rate: number) => `${rate}% less crowded`,
    noAlternatives:
      'There was no quiet indoor place nearby to offer instead. Not a candidate that scored too low — there were no candidates at all.',
    backendBoundary:
      'Everything above is the backend’s output. The stops, their order and the congestion grades were decided without reference to the explanation below.',
    llmBadge: 'The paragraph below was written by the LLM',
    citationsLabel: (count: number) =>
      `${count} citations, every one a document in the bundle. Click to read exactly what the model read.`,
  },

  ask: {
    heading: 'Ask more about this course',
    placeholder: 'Ask about this course',
    submit: 'Ask',
    submitting: 'Asking…',
    failed: 'No answer could be produced. Please try again in a moment.',
    suggestions: ['Why this order?', 'Why these places?', 'Would another day be better?'],
    looking: {
      congestion: 'Checking congestion again',
      alternatives: 'Looking for nearby alternatives',
      fallback: 'Looking up more facts',
    },
  },

  citation: {
    close: 'Close',
    loading: 'Loading…',
    notInBundle: (status: number) => `This document is not in the bundle (${status}).`,
  },

  evidence: {
    title: 'Evidence documents',
    count: (docs: number, bytes: string) =>
      `${docs} documents · ${bytes} bytes. The model sees all of it on every request.`,
    sumNote: (sum: string) =>
      `The document bodies below add up to ${sum} bytes on their own. The difference is the separator lines between them, which go into the prompt too.`,
    why: 'Nothing is retrieved and selected here. The whole bundle goes into the prompt, and an answer citing a path that is not in it is blocked before it reaches the user.',
    loading: 'Loading…',
    loadFailBody: (status: number) => `Could not load this document (${status}).`,
    listFailTitle: 'Could not load the evidence documents',
    listFailBody: (status: number) =>
      `The agent server did not return the bundle listing (${status}).`,
  },
}

const DICTS: Record<Lang, Dict> = { ko, en }

export function dict(lang: Lang): Dict {
  return DICTS[lang]
}
