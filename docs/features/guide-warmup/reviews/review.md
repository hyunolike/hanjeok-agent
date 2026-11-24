# 연결 대기 기능 검토

기준 커밋 `87e445a`, 당시 작업 트리는 깨끗했다. 변경 대상은 이 기능 명세/작업 목록,
화면 계약, AskGuide/테스트, WarmupPanel, readiness HTTP 클라이언트/테스트,
연결 hook와 한/영 문구다. 기존 선택 장소의 SSR 검증은 변경하지 않았다.

## 설계 검토

EGM design_critic persona와 feature-spec-standard를 읽는 새 문맥의 검토자를 각각
`fork_turns:none`으로 실행했다. 검토 대상 spec 1–61행을 매번 다시 확인했으며
AskGuide, guide.ts, backend readiness를 읽는 목록으로 전달했다.

1. warmup_spec_review: 읽기 완료, material finding 없음.
2. warmup_spec_review_2: 읽기 완료, material finding 없음.

주요 확인 범위는 유한한 순차 GET, 단일 활성 확인, POST 한 번, 취소 뒤 완료 무시,
선택/방문 정보 보존, 연결과 SSE 예산 분리, 원격 모델 가용성의 한계다.

## 최종 코드 검토

새 문맥의 warmup_code_review가 기준 diff와 새 파일 전체, 관련 UI/SSE 코드와
명세/테스트를 읽었다. 구현자 자신의 검토를 독립 검토로 기록하지 않았다.

Important: 연결 완료 시 WarmupPanel이 언마운트되어 카드 버튼을 사용하던 키보드
포커스가 BODY로 옮겨간다. W6 위반이며 카드 조작을 유지해야 한다.

조치: 선택형 카드 컴포넌트는 준비 완료와 답변 시작에도 유지하고, 연결 문구만
준비 완료로 바꿨다. 실제 답변 진행은 기존 SSE 영역에서 표시한다.
`연결이 완료되어도 조작 중인 카드의 키보드 포커스를 유지한다` 테스트에서 기존 구현의
BODY 포커스 실패를 확인한 후 수정해 통과했다. 제출 큐에서 SSE로 넘어가는 동안의
카드 포커스 회귀 테스트도 통과했다. 최종 전체 314개 테스트가 통과했다.

검토자가 별도로 판단하지 않은 범위: 기존 선택 장소 SSR, 실제 Render/NVIDIA 외부
가용성과 기동 시간, 브라우저 viewport 배치. SSR 계약은 기존 테스트로 유지했고
viewport는 별도 Chrome 검사로 확인했다. 외부 기동 시간/추론은 이번 검증에서 측정하지 않았다.
남은 코드 검토 지적이나 보류한 minor는 없다. 수정 뒤 새 검토 회차는 실행하지 않았다.

## 참고 자료

- [Render Free](https://render.com/docs/free)
- [Progress Indicators — NN/g](https://www.nngroup.com/articles/progress-indicators/)
- [Time swipes when you’re having fun — Utrecht University](https://research-portal.uu.nl/en/publications/time-swipes-when-youre-having-fun-reducing-perceived-waiting-time/)
- [Reduced motion — W3C](https://www.w3.org/WAI/WCAG22/Techniques/css/C39)
