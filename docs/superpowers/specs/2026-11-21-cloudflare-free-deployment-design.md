# Cloudflare 무료 배포

## 문제와 승인 범위

2026-11-21 Vercel Hobby 팀이 Edge Config 읽기 한도 초과로 정지됐다.
`agent.hanjeok.com`은 402 DEPLOYMENT_DISABLED를 반환하고 API와 CLI 재배포도
resource_creation_blocked로 거부됐다. 팀 API의 해제 예정은 2026-12-21 01:42 KST다.
사용자는 무료 요금을 유지하는 Cloudflare 이전을 선택하고 진행을 승인했다.

## 요구사항

- CF-1: 기존 Next.js 화면, 한국어/영어 경로와 리다이렉트를 보존한다.
- CF-2: Workers Free에서 배포한다. 유료 플랜, 유료 이미지/캐시 서비스를 만들지 않는다.
- CF-3: 운영의 공개 API 주소를 유지한다. 기존 녹화본 전환을 실시간 복구로 표현하지 않는다.
- CF-4: Workers 주소를 먼저 검증한 뒤 기존 도메인을 연결한다. 인증이나 DNS 변경 권한이
  없으면 준비한 배포물과 필요한 외부 작업을 명시한다.
- CF-5: pnpm 테스트와 타입 검사, Cloudflare 빌드 및 로컬 Worker 검증을 수행한다.
  배포 후 리다이렉트, 한국어/영어, 질문 화면과 정적 자산을 검사한다.

## 접근과 대안

선택: Cloudflare Pages 고급 모드에서 Workers Free 런타임과 vinext를 사용한다.
Pages는 외부 DNS의 서브도메인 CNAME 연결을 지원하므로 hanjeok.com 전체의
네임서버를 옮길 필요가 없다. 공식 이전 가이드가 권장하는 vinext로 기존 소스와
Next.js 명령을 유지할 수 있다. 호환성 검사에는 치명적 문제 0건, App Router의
reactStrictMode 부분 지원 1건이 나왔다. 캐시와 이미지 최적화는 none으로 둔다.

Vercel 재배포는 팀 차단 때문에 실패했다. 정적 Pages export는 임의 UUID 경로와
요청 시 렌더링을 보존하려면 화면을 바꿔야 하므로 채택하지 않는다. OpenNext는
Next.js 구현을 그대로 유지하지만 우선 공식 권장 vinext 경로를 검증한다.

## 구조와 비용 경계

frontend에 Vite/Cloudflare 설정과 별도 빌드/실행/배포 명령을 추가한다.
기존 next.config 리다이렉트를 재사용한다. NEXT_PUBLIC 값은 빌드 시 주입한다.
이 프로젝트는 Edge Config, KV, R2와 Cloudflare Images를 사용하지 않는다.
Workers Free의 요청별 CPU 10ms를 실제 응답으로 검증한다. 현재 공식 코드 크기
한도는 압축 전 64 MiB이며 생성 서버 모듈이 이 범위인지 검사한다.
무료 한도를 넘으면 유료 전환 없이 중단하고 확인된 제한을 보고한다.

## 외부 의존성과 미확인 사항

Cloud Run의 기존 Kotlin health는 500이었다. 별도 Python guide 상태도 확인해야 한다.
프론트 배포 성공과 API 복구는 구분한다. 백엔드 재배포, LLM 호출과 유료 자원 생성은
이 프론트 이전 작업에 묶지 않는다. 도메인이 Cloudflare 계정에 없으면 DNS 접근이나
별도 호스팅 연결 작업이 필요하다. 현재 계정에는 zone이 없어 Pages 경로를 선택했다.
계정의 Workers 요금제 화면에서 현재 Free US$0임을 직접 확인했다.

## 확인한 이전 구현

`vinext init`으로 만든 빌드는 ASSETS 바인딩 하나만 사용한다. scripts/prepare-pages.mjs는
빌드의 assets를 Pages 루트로 옮긴다. 서버 bundle은 esbuild로 단일 비공개 ESM
_worker.js 파일로 묶는다. Pages의 로컬 미들웨어가 원본 SSR의 ../index.js 순환
경로를 바꾸는 문제가 있어 네이티브 모듈 디렉터리 대신 이 방식을 검증했다.
`wrangler pages deploy --no-bundle`로 검증한 ESM을 배포한다. 정적 폰트와 이미지
경로는 _routes.json에서 함수 실행을 제외해 무료 정적 자산으로 제공한다.

## 확인한 근거

- https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/
- https://developers.cloudflare.com/workers/static-assets/migration-guides/vercel-to-workers/nextjs/
- https://developers.cloudflare.com/workers/platform/pricing/
- docs/deploy.md, frontend/next.config.mjs, frontend/src/lib/agent.ts, frontend/src/lib/guide.ts
