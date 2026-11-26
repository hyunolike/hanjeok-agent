# 작업과 검증

- [x] W1/W3/W4: 유한 readiness HTTP 확인과 화면별 단일 확인 구현, RED→GREEN 검증.
- [x] W2/W4: 제출 큐, 재연결, 취소와 늦은 완료 방어 구현, RED→GREEN 검증.
- [x] W5/W6: 잎새 대기 카드, 초안 예시, 한/영 상태와 접근성 구현.
- [x] 기존 화면 계약에 대기 상태 추가.
- [x] 새 문맥의 설계 검토와 코드 검토 기록.
- [x] 전체 frontend 테스트/typecheck/Pages 빌드와 브라우저 검증.

검증 결과는 실행 후 기록한다. 미실행 검토/검사는 통과로 표시하지 않는다.

## 검증 결과

- `pnpm --dir frontend test`: 29개 파일, 314개 테스트 통과.
- `pnpm --dir frontend exec next typegen` 후 `pnpm --dir frontend typecheck`: 통과.
  기존 Next validator와 vinext의 generated routes 충돌은 타입 재생성으로 정리했다.
- 공개 API URL을 지정한 `pnpm --dir frontend build:pages`: 종료 코드 0.
  vinext/RSC의 sourcemap 및 중복 dynamic import 경고는 남지만 빌드는 완료됐다.
- `git diff --check`: 통과.
- 로컬 Chrome 1280px 밝은 화면 / 360px 어두운 화면, reduced-motion 설정에서 확인했다.
  준비 확인은 제어된 지연 응답, 답변은 기존 fixture의 HTTP SSE를 사용했다.
  이번 UI 검증을 실제 NVIDIA 추론 성공이나 Render 기동 시간 측정으로 보지 않는다.
- 준비 완료 시 카드 포커스 유지, 미제출 초안 무전송, 준비 전 제출 질문 보존과
  준비 뒤 POST 한 번, SSE 파싱/답변 표시, 모바일 가로 넘침 없음 확인.
  [브라우저 결과](reviews/browser-check.json), [모바일 대기](reviews/warmup-360.png),
  [데스크톱 대기](reviews/warmup-1280.png), [모바일 응답](reviews/answered-360.png).
- 독립 설계 검토 2회와 최종 코드 검토 1회 실행. 카드 포커스 지적은 재현 테스트의
  RED→GREEN과 전체 suite로 수정 확인했다. [검토 기록](reviews/review.md).

초기 구현과 로컬 검증 뒤 사용자가 공개 배포를 승인했다. 아래 배포까지 완료했으며,
Git main 병합은 수행하지 않았다.

## 공개 배포 결과

- 소스: `22ab1b7d4aeb3b43708ac3d925ff3b0d29716df0`.
- Cloudflare Pages 운영 배포 `b88b9bdf-96f8-445e-9585-e9f145053a22`.
  `main`은 Pages 운영 라벨이다. 작업 Git 브랜치는 `feat/guide-512mb-runtime`이다.
- [공개 질문 화면](https://agent.hanjeok.com/ko/ask)에서 새 카드와 질문 예시의 초안 채우기 확인.
- 실제 질문 “경복궁은 2026-11-26에 얼마나 붐벼?”에 HTTP200, `answer`, 인용,
  terminal `done`과 화면 답변을 확인했다. 질문 POST는 한 번이며 녹화 응답을 사용하지 않았다.
- 360px 어두운 화면의 대기 검사는 별도 브라우저 문맥에서만 readiness를 503으로 제어했다.
  제출한 질문 보존, 카드 키보드 조작, 대기 취소 후 입력 복구, 가로 넘침 없음과
  reduced-motion의 짧은 animation duration을 확인했다. 이 문맥에서는 POST0이었다.
- 첫 자동화 시도는 JS 초기화 전 화면을 조작해 전송 버튼을 활성화하지 못했다.
  초기화를 기다리는 조건을 추가한 뒤 같은 운영 코드로 통과했다. 제품 수정은 없었다.
- 실제 서버 기동 시간이나 전체 질문 성공률, p95 지연을 측정한 결과는 아니다.
  백엔드 재배포나 새로운 과금은 하지 않았다.

[배포 기록](reviews/deployment.json), [공개 브라우저 결과](reviews/public-browser-check.json),
[실제 예보 SSE](reviews/public-response.sse), [공개 응답 화면](reviews/public-answer.png),
[모바일 대기 화면](reviews/public-mobile-waiting.png).
