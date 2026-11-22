# Cloudflare 배포 독립 검토 기록

범위: 2278001 기준 프론트 배포 설정과 generated bundle, 기존 빌드 및 폰트 경로.
검토자는 `/root/cloudflare_review`이며 대화 이력이 없는 별도 문맥에서 읽기 전용으로 검토했다.

## 지적과 조치

1. P1: Vite8과 Vitest3가 사용하는 Vite7의 플러그인 타입 충돌. typecheck와 Next.js
   빌드가 실패했다. Vitest5.1.1로 맞췄고296개 테스트, 타입 검사와 Next 빌드가 통과했다.
2. P2: CSS의184개 폰트 상대 경로가 모두 누락됐다. font CSS를 layout에서 직접
   import하도록 바꿨다. 검토자가 재검사해184개 모두 존재함을 확인했다.

## 추가 검토 근거

- ASSETS 바인딩만 있으며 KV/R2/Images/DO 및 추가 Worker를 생성하는 설정이 없다.
- 두 운영 Cloud Run API URL은 client/server 번들에 유지돼 있다.
- 검토자는130개 서버 JS 모듈을 AST로 확인했다. 동적 import59개는 모두 리터럴이며
  정적 import/export467개가 있다. 단일 ESM 번들링을 막는 계산된 import는 없었다.
- 원본 Pages 디렉터리 모듈의 로컬 미들웨어 충돌 이후 단일 ESM으로 재구성했다.
  로컬 Pages 런타임과 무료 공개 배포에서 주요 경로, CSS와 폰트, 서버 코드404를 검증했다.
- Free 요금제는 Cloudflare 대시보드의 US$0/현재 요금제 표시로 직접 확인했다.
- 최종 Pages 스크립트와 설정을 독립 재검토해 중대한 지적 없음으로 확인했다.
  사용자 도메인도 certificate/verification/validation 모두 active이며 HTTPS 검사가 통과했다.
- API의500과 새 오리진 CORS는 프론트 배포 성공과 별개의 제약으로 남긴다.
  GCP 결제 비활성 상태는 읽기 전용 명령으로 확인했다.

아직 검증하지 않은 것: 임의 질문의 실시간 완료, 복구 이후의 새 pages.dev CORS,
장기간 트래픽에서의 무료 한도. 전체 서비스 복구나 무제한 무료 운영을 주장하지 않는다.
