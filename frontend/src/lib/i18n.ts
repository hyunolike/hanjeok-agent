import { guideEn, guideKo } from './i18n-guide'

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
    brand: '한적 에이전트',
    evidence: '근거 문서',
    /** 반대편 언어 화면으로 가는 링크. 그 언어로 쓴다. */
    switchTo: 'English',
  },

  home: {
    // 홈은 이 사이트가 한적의 어디에 들어가는 무엇인지부터 말한다. 예전 홈은 앞서 만든
    // 코스 설명기를 소개하고 있어서, 지금 에이전트와 맞지 않는 숫자와 규칙이 남아 있었다.
    bannerEyebrow: '한적 에이전트',
    bannerTitle: ['붐비는지 묻고,', '대신 갈 곳을 들어 보세요.'],
    bannerBody:
      '한적의 장소 화면과 코스 화면에서 부르는 안내 기능입니다. 이 사이트에서 따로 떼어 써 볼 수 있습니다.',
    bannerCta: '한적에게 물어보기',
    bannerSecondary: '예시 코스 보기',

    roleTitle: '한적 안에서 하는 일',
    roleLead:
      '한적이 이미 가진 혼잡 예보와 추천을 질문 하나로 꺼내 주는 것이 이 에이전트의 일입니다. 장소를 새로 고르거나 점수를 매기지 않습니다.',
    roles: [
      {
        title: '보고 있는 화면에서 이어 묻습니다',
        body: '장소나 코스 화면에서 "여기 토요일에 붐벼?"라고 물으면 그 화면의 장소와 날짜로 알아듣습니다. 질문에 다른 장소나 날짜를 적으면 그쪽을 따릅니다.',
      },
      {
        title: '한적의 데이터를 읽기만 합니다',
        body: '장소와 연관 관계는 한적이 내보낸 공개 관광 데이터에서 읽습니다. 혼잡 예보와 대안은 질문할 때 한적의 읽기 전용 API로 가져옵니다. 한적 데이터베이스에는 접속하지 않습니다.',
      },
      {
        title: '순위는 한적이 정합니다',
        body: '대신 갈 곳은 한적이 정한 순서 그대로 전합니다. 모델은 정해 둔 조회 일곱 가지 중 무엇을 부를지 고르고 답을 쓸 뿐입니다. 장소를 고르거나 순서를 바꾸지 않습니다.',
      },
    ],
    scopeYesLabel: '물어볼 수 있는 것',
    scopeYes: '날짜별 혼잡 예보, 대신 갈 곳, 이어진 장소와 행사, 한적이 혼잡과 추천을 다루는 방식',
    scopeNoLabel: '답하지 않는 것',
    scopeNo: '입장료, 영업시간, 예약, 길 찾기, 순위를 바꿔 달라는 요청',
    stageNote:
      '아직 한적 앱 화면에 붙이기 전이라 이 사이트에서 따로 띄워 둔 데모입니다. 한적 백엔드가 같은 기능을 부를 수 있도록 MCP 입구도 열어 두었습니다.',

    ruleLimit:
      '인용 검사는 인용한 레코드가 진짜인지만 봅니다. 레코드보다 더 나간 주장은 아래 금지 행동 규칙으로 따로 셉니다.',

    metricsTitle: '실데이터 질문으로 잰 숫자',
    metricsLead: (count: number, exportDate: string) =>
      `${exportDate}에 내보낸 한적 데이터로 질문 ${count}개를 풀게 한 결과입니다. 지금 서비스가 쓰는 "연관 링크까지" 방식의 값이고, 모델 없이 센 숫자만 적었습니다.`,
    metricsUnavailable: '평가 보고서를 불러오지 못했습니다. 평가 화면에서 다시 확인해 주세요.',
    recall: {
      value: (pct: string) => `필요한 레코드 ${pct} 확보`,
      label: (n: number, other: string) =>
        `답할 수 있는 ${n}문항 기준입니다. 연관 링크 없이 글 유사도만 쓰면 ${other}입니다.`,
    },
    abstention: {
      value: (correct: number, total: number) => `${total}문항 중 ${correct}문항 거절`,
      label: '입장료나 영업시간처럼 한적에 없는 정보, 순위를 바꿔 달라는 요청에는 답하지 않아야 합니다.',
    },
    forbidden: {
      value: (count: number) => `금지 행동 ${count}건`,
      label: (runs: number, kinds: number) =>
        `답 ${runs}개에서 규칙 ${kinds}가지로 센 건수입니다. 목표는 0건이고 아직 닿지 못했습니다.`,
    },
    metricsCta: '평가 보고서 보기',

    demoHeading: '코스 화면에서 이어 묻기',
    demoLead:
      '한적에서 만든 코스 화면입니다. 코스 아래에서 "왜 이 순서예요?"처럼 이 코스에 대해 물어볼 수 있습니다.',
    demoSavedNote: '2026년 9월 12일에 저장된 예시예요. 혼잡도는 저장 당시 값이며 현재 예보가 아니에요.',
    // 설명 실패는 블록이 조용히 사라지는 것으로 나타난다(스펙 §6.1). 그 빈자리를
    // 만나기 전에 여기서 말한다.
    silentFailure:
      '코스 아래 설명 문단은 앞서 만든 코스 설명기가 씁니다. 정해 둔 문서 묶음 안에서만 인용하고, 설명을 만들지 못하면 사과문 대신 빈자리로 둡니다.',

    emptyTitle: '데모 코스가 아직 설정되지 않았습니다.',
    emptyBody: (missing: string) =>
      `한적에 코스를 만들고 uuid를 src/lib/demo-courses.ts에 넣으면 여기에 뜹니다. 아직 채워지지 않은 종류: ${missing}`,

    openAnySummary: '개발용: 코스 uuid로 직접 열기',
    openAnyNote:
      '위 목록은 종류별로 고른 예시입니다. 서버는 데모 uuid를 특별 취급하지 않으므로 한적에 있는 코스라면 어느 것이든 열립니다.',

    // 한국어 화면에서는 할 필요가 없는 말이다. 영어 화면에서만 뜬다.
    generatedLanguageNote: null as string | null,
  },

  explainer: {
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
      href: `${REPO}/blob/main/docs/explainer/README.ko.md#-금지-행동-8종`,
    },
    citationGuard: {
      value: '5회 중 5회 차단',
      label: '첫 실제 실행에서, 지어낸 인용이 답 전체를 막았습니다.',
      cta: '검증 방식 보기',
      href: `${REPO}/blob/main/docs/explainer/README.ko.md#2-인용-검증--테스트가-아니라-런타임-방어선`,
    },
  },

  openAny: {
    label: '코스 uuid로 열기',
    placeholder: '한적에서 만든 코스의 uuid',
    submit: '열기',
  },

  course: {
    loadFailTitle: '코스를 불러오지 못했습니다',
    loadFailBody: (status: number) =>
      `한적에서 사실을 받지 못했습니다(${status}). 코스가 삭제되었거나, 예보 날짜 범위를 벗어났거나, 서버에 연결할 수 없어요.`,
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
  ...guideKo,
}

/** `ko` 를 그대로 모양으로 삼는다. 영어가 여기서 벗어나면 타입 검사가 잡는다. */
export type Dict = typeof ko

const en: Dict = {
  nav: {
    brand: 'Hanjeok Agent',
    evidence: 'Evidence',
    switchTo: '한국어',
  },

  home: {
    bannerEyebrow: 'Hanjeok Agent',
    bannerTitle: ['Ask if it is crowded.', 'Hear where to go instead.'],
    bannerBody:
      'The guide that Hanjeok’s place and course screens call on. This site lets you try it on its own.',
    bannerCta: 'Ask Hanjeok',
    bannerSecondary: 'See example courses',

    roleTitle: 'What it does inside Hanjeok',
    roleLead:
      'Its job is to bring out, in answer to one question, the congestion forecasts and recommendations Hanjeok already has. It does not pick places or score them.',
    roles: [
      {
        title: 'It picks up from the screen you are on',
        body: 'Ask “is it crowded here on Saturday?” from a place or course screen and it takes that screen’s place and day. Name another place or day in the question and it follows the question.',
      },
      {
        title: 'It only reads Hanjeok’s data',
        body: 'Places and their links come from public tourism data Hanjeok exports. Forecasts and alternatives are fetched at question time from Hanjeok’s read-only APIs. It never connects to Hanjeok’s database.',
      },
      {
        title: 'Hanjeok decides the ranking',
        body: 'Places to go instead arrive in the order Hanjeok gave them. The model only chooses which of seven fixed lookups to call and writes the answer. It does not choose places or reorder them.',
      },
    ],
    scopeYesLabel: 'You can ask about',
    scopeYes: 'congestion forecasts by date, places to go instead, linked places and events, how Hanjeok treats crowding and recommendations',
    scopeNoLabel: 'It will not answer',
    scopeNo: 'admission fees, opening hours, bookings, directions, or requests to change the ranking',
    stageNote:
      'It is not yet wired into the Hanjeok app’s screens, so this site runs it as a separate demo. An MCP entry point is open so Hanjeok’s backend can call the same guide.',

    ruleLimit:
      'The citation check only confirms that a cited record is real. Claims that go further than the record are counted separately by the forbidden-behaviour rules below.',

    metricsTitle: 'Measured on questions over real data',
    metricsLead: (count: number, exportDate: string) =>
      `${count} questions answered over Hanjeok data exported on ${exportDate}. Values are for “plus relatedness links”, the method the service uses, and only counts made without a model are shown.`,
    metricsUnavailable: 'Could not load the evaluation report. Check the evaluation page instead.',
    recall: {
      value: (pct: string) => `${pct} of needed records fetched`,
      label: (n: number, other: string) =>
        `Over the ${n} answerable questions. With text similarity alone and no links, it is ${other}.`,
    },
    abstention: {
      value: (correct: number, total: number) => `Declined ${correct} of ${total}`,
      label: 'Questions it must not answer: information Hanjeok does not have, like fees and opening hours, or requests to change the ranking.',
    },
    forbidden: {
      value: (count: number) => `${count} forbidden behaviours`,
      label: (runs: number, kinds: number) =>
        `Counted by ${kinds} rules over ${runs} answers. The goal is zero, and it is not there yet.`,
    },
    metricsCta: 'Read the evaluation',

    demoHeading: 'Ask from a course screen',
    demoLead:
      'Course screens made in Hanjeok. Below each course you can ask about it, such as “why this order?”.',
    demoSavedNote: 'Saved examples for September 12, 2026. Grades are historical values, not current forecasts.',
    silentFailure:
      'The explanation under each course is written by the course explainer built earlier. It cites only a fixed set of documents, and when it cannot produce an explanation it leaves a gap rather than an apology.',

    emptyTitle: 'No demo courses are configured yet.',
    emptyBody: (missing: string) =>
      `Create a course in hanjeok and put its uuid in src/lib/demo-courses.ts. Kinds still missing: ${missing}`,

    openAnySummary: 'For developers: open a course by uuid',
    openAnyNote:
      'The list above is one example per kind. The server gives demo uuids no special treatment, so any course that exists in hanjeok will open.',

    generatedLanguageNote:
      'Course data, citations and the explanation itself are generated in Korean — only this interface is translated.',
  },

  explainer: {
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
      href: `${REPO}/blob/main/docs/explainer/README.md#-the-eight-forbidden-behaviours`,
    },
    citationGuard: {
      value: 'Blocked 5 of 5',
      label: 'On the first real run, a fabricated citation stopped the entire answer.',
      cta: 'See how it is checked',
      href: `${REPO}/blob/main/docs/explainer/README.md#2-citation-validation--a-runtime-guard-not-a-test`,
    },
  },

  openAny: {
    label: 'Open by course uuid',
    placeholder: 'uuid of a course created in hanjeok',
    submit: 'Open',
  },

  course: {
    loadFailTitle: 'Could not load this course',
    loadFailBody: (status: number) =>
      `No facts came back from hanjeok (${status}). The course may be missing, its forecast date may be out of range, or the service may be unavailable.`,
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
  ...guideEn,
}

const DICTS: Record<Lang, Dict> = { ko, en }

export function dict(lang: Lang): Dict {
  return DICTS[lang]
}
