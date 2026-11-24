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

구현과 로컬 검증을 완료했다. 공개 배포와 main 병합은 수행하지 않았다.
