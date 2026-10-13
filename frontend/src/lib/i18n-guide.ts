/**
 * 안내 에이전트 화면의 문구. `i18n.ts` 의 사전에 펼쳐 들어간다 — 그 파일이 이미
 * 길어서 여기로 나눴을 뿐, 규칙은 같다: 한국어가 원본이고 영어는 그 모양을 따른다.
 *
 * 번역되는 것은 껍데기뿐이다. 답, 단계 요약, 장소 이름은 서버가 한국어로 만든다.
 */

const STEP_KIND_KO: Record<string, string> = {
  scope: '질문 읽기',
  resolve: '장소 찾기',
  search_places: '장소 검색',
  place_detail: '장소 정보',
  related_places: '연관 장소',
  congestion: '혼잡 예보 조회',
  alternatives: '대안 장소 조회',
  events: '행사 확인',
  policy: '정책 문서',
}

const STEP_KIND_EN: Record<string, string> = {
  scope: 'Read the question',
  resolve: 'Find the place',
  search_places: 'Search places',
  place_detail: 'Place details',
  related_places: 'Related places',
  congestion: 'Congestion forecast',
  alternatives: 'Alternatives',
  events: 'Events',
  policy: 'Policy document',
}

export const guideKo = {
  guide: {
    navLabel: '물어보기',
    title: '한적에게 물어보기',
    lead: '어디가 언제 붐비는지, 대신 갈 만한 곳이 있는지 물어보세요. 답이 어디에서 왔는지 단계마다 보여 드립니다.',
    replayTitle: '녹화본을 재생하고 있습니다',
    replayBody: '안내 서버에 연결되어 있지 않아 미리 녹화한 응답을 보여 드립니다. 여기 나오는 장소와 숫자는 전부 지어낸 것입니다.',
    asOf: (exportTime: string) => `한적 데이터 기준 시각 ${exportTime}`,

    waitingTitle: '무엇이 궁금하세요?',
    waitingBody: '장소와 날짜를 함께 말해 주시면 가장 정확합니다.',
    examplesLabel: '이렇게 물어볼 수 있어요',
    examples: [
      '이번 토요일 가람궁 대신 조용한 곳 있어?',
      '가람궁은 다음 주 화요일에 덜 붐벼?',
      '대안 장소는 어떤 기준으로 고르는 거야?',
      '솔내 한옥마을이랑 비슷한 분위기인 곳 알려줘',
    ],

    fieldLabel: '질문',
    fieldPlaceholder: '예: 이번 토요일 가람궁 대신 조용한 곳 있어?',
    followUpPlaceholder: '이어서 물어보기',
    submit: '물어보기',
    retry: '다시 물어보기',

    lookingTitle: '찾아보는 중입니다',
    stepsTitle: '답을 찾은 단계',
    stepsSummary: (count: number) => `${count}단계를 거쳤습니다`,
    stepKind: (kind: string) => STEP_KIND_KO[kind] ?? kind,
    stepStatus: {
      running: '진행 중',
      ok: '완료',
      refused: '거절됨',
      no_data: '데이터 없음',
      failed: '실패',
    },
    stepAsOf: (time: string) => `기준 ${time}`,

    foundTitle: '찾았습니다',
    partialTitle: '일부만 확인했습니다',
    partialBody: '시간 안에 조회를 다 마치지 못해, 확인한 것만으로 답했습니다.',
    citationsLabel: '이 답의 근거',
    citationKind: { record: '한적 레코드', policy: '정책 문서' },
    citationRecordNote: '한적 서비스에서 가져온 사실입니다.',
    citationPolicyNote: '한적이 그 사실을 어떻게 읽는지 정한 위키 문서입니다.',
    citationId: '식별자',
    citationFetchedBy: '가져온 단계',
    citationFetchedAt: '가져온 시각',
    close: '닫기',
    showPath: '경로 보기',
    hidePath: '경로 접기',

    pathTitle: '이 답이 지나온 경로',
    pathStart: '출발',
    pathRank: (rank: number) => `${rank}순위`,
    pathRankNote: '장소의 순서는 한적이 정한 순위 그대로입니다.',
    pathColumns: { document: '읽은 정책 문서', place: '장소', region: '지역' },
    pathEdge: {
      related: '연관 장소',
      alternative: '대안',
      in_region: '속한 지역',
      explains: '근거가 된 문서',
      held_at: '열리는 곳',
    },
    pathListTitle: '목록으로 보기',

    chooseTitle: '어느 곳인지 골라 주세요',
    noDataTitle: '알 수 없습니다',
    declinedTitle: '답할 수 없는 질문입니다',
    failedTitle: '답을 가져오지 못했습니다',
    limitTitle: '오늘은 여기까지입니다',
    limitBody: (minutes: number) => `질문 수 한도에 닿았습니다. 약 ${minutes}분 뒤에 다시 물어봐 주세요.`,
    limitDayBody: '오늘 데모 전체의 질문 한도에 닿았습니다. 내일 다시 찾아 주세요.',
    cutTitle: '연결이 끊겼습니다',
    cutBody: '답을 받기 전에 연결이 끊겼습니다. 받은 단계까지만 보여 드립니다.',
    model: (name: string, seconds: string) => `${name} · ${seconds}초`,
  },
  design: {
    title: '디자인 값',
    lead: '모든 화면은 여기 있는 이름만 씁니다. 값 하나를 바꾸면 그 이름을 쓰는 화면이 전부 따라 바뀝니다.',
    appearanceNote: '기기의 밝은 화면과 어두운 화면 설정을 바꿔 가며 확인하세요. 글자와 바탕의 명암비는 테스트가 4.5:1 이상인지 잽니다.',
    colours: '색',
    pairs: '글자와 바탕',
    type: '글자',
    components: '컴포넌트',
    character: '안내 캐릭터 잎새',
    characterNote: '그림은 장식이고 상태는 옆의 글이 전합니다. 캐릭터는 누를 수 없습니다.',
    sample: '한적한 곳으로 안내합니다',
    states: {
      waiting: '기다리는 중',
      looking: '찾아보는 중',
      found: '찾음',
      choose: '고르기 요청',
      'no-data': '데이터 없음',
      failed: '실패',
    },
  },
}

export type GuideDict = typeof guideKo

export const guideEn: GuideDict = {
  guide: {
    navLabel: 'Ask',
    title: 'Ask Hanjeok',
    lead: 'Ask when a place is crowded and where to go instead. Every step that led to the answer is shown.',
    replayTitle: 'Playing a recording',
    replayBody:
      'No guide server is connected, so this is a recorded response. Every place and number here is made up.',
    asOf: (exportTime: string) => `Hanjeok data as of ${exportTime}`,

    waitingTitle: 'What would you like to know?',
    waitingBody: 'Naming a place and a date gives the most precise answer.',
    examplesLabel: 'Things you can ask',
    examples: [
      '이번 토요일 가람궁 대신 조용한 곳 있어?',
      '가람궁은 다음 주 화요일에 덜 붐벼?',
      '대안 장소는 어떤 기준으로 고르는 거야?',
      '솔내 한옥마을이랑 비슷한 분위기인 곳 알려줘',
    ],

    fieldLabel: 'Question',
    fieldPlaceholder: 'e.g. 이번 토요일 가람궁 대신 조용한 곳 있어?',
    followUpPlaceholder: 'Ask a follow-up',
    submit: 'Ask',
    retry: 'Ask again',

    lookingTitle: 'Looking it up',
    stepsTitle: 'Steps to the answer',
    stepsSummary: (count: number) => `${count} steps`,
    stepKind: (kind: string) => STEP_KIND_EN[kind] ?? kind,
    stepStatus: {
      running: 'Running',
      ok: 'Done',
      refused: 'Refused',
      no_data: 'No data',
      failed: 'Failed',
    },
    stepAsOf: (time: string) => `as of ${time}`,

    foundTitle: 'Found it',
    partialTitle: 'Only partly checked',
    partialBody: 'The lookups did not finish in time, so this answer uses only what was checked.',
    citationsLabel: 'What this answer rests on',
    citationKind: { record: 'Hanjeok record', policy: 'Policy document' },
    citationRecordNote: 'A fact fetched from the Hanjeok service.',
    citationPolicyNote: 'A wiki page that says how Hanjeok reads that fact.',
    citationId: 'Identifier',
    citationFetchedBy: 'Fetched by',
    citationFetchedAt: 'Fetched at',
    close: 'Close',
    showPath: 'Show path',
    hidePath: 'Hide path',

    pathTitle: 'The path this answer took',
    pathStart: 'Start',
    pathRank: (rank: number) => `Rank ${rank}`,
    pathRankNote: 'Places are in the order Hanjeok ranked them.',
    pathColumns: { document: 'Policy documents read', place: 'Places', region: 'Regions' },
    pathEdge: {
      related: 'Related place',
      alternative: 'Alternative',
      in_region: 'In region',
      explains: 'Document that explains it',
      held_at: 'Held at',
    },
    pathListTitle: 'As a list',

    chooseTitle: 'Which one do you mean?',
    noDataTitle: 'Not known',
    declinedTitle: 'This cannot be answered',
    failedTitle: 'Could not get an answer',
    limitTitle: 'That is all for now',
    limitBody: (minutes: number) => `You reached the question limit. Try again in about ${minutes} minutes.`,
    limitDayBody: 'The demo reached its question limit for today. Please come back tomorrow.',
    cutTitle: 'Connection lost',
    cutBody: 'The connection dropped before an answer arrived. Only the steps received are shown.',
    model: (name: string, seconds: string) => `${name} · ${seconds}s`,
  },
  design: {
    title: 'Design values',
    lead: 'Every screen uses only the names on this page. Changing one value changes every screen that uses its name.',
    appearanceNote:
      'Switch your device between light and dark appearance to check both. A test measures that text on its background meets 4.5:1.',
    colours: 'Colours',
    pairs: 'Text on background',
    type: 'Type',
    components: 'Components',
    character: 'The guide character, Ipsae',
    characterNote: 'The image is decorative; the text beside it carries the state. The character is never a control.',
    sample: 'Guiding you somewhere quiet',
    states: {
      waiting: 'Waiting',
      looking: 'Looking',
      found: 'Found',
      choose: 'Asking you to choose',
      'no-data': 'No data',
      failed: 'Failed',
    },
  },
}
