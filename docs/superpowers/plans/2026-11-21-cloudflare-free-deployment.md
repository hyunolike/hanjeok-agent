# Cloudflare Free Deployment Implementation Plan

**상태:** 프론트 무료 이전 완료. 후속 질문 API 이전은 2026-11-22 사용자 요청으로 보류.
재개 정보는 [API 이전 조사](../specs/2026-11-22-free-guide-deployment-investigation.md)에 기록했다.

> **For agentic workers:** Use superpowers:executing-plans to implement in this session.

**Goal:** 기존 프론트를 Cloudflare 무료 플랜에 배포하고 접속 경로를 검증한다.

**Architecture:** vinext로 기존 App Router를 Workers에서 실행한다. API 주소와
UI는 유지하고 배포 설정만 추가한다. 무료 계정과 Worker 검증을 먼저 수행한다.

**Tech Stack:** Next.js 16, React 19, vinext, Vite, Cloudflare Workers Free, pnpm.

**Spec:** ../specs/2026-11-21-cloudflare-free-deployment-design.md

## Global Constraints

- 유료 플랜과 유료 캐시/이미지 서비스를 만들지 않는다.
- 기존 Next.js 실행과 테스트를 유지한다.
- 사용자 승인 범위는 무료 Cloudflare 이전과 검증이다.

## Task 1: 배포 설정과 검증

- [x] 기준 커밋 2278001, 시작 작업 트리 clean 확인. Vercel 차단과 vinext 호환성 확인.
- [x] Cloudflare 계정은 Workers Free US$0. hanjeok.com zone은 없음.
- [x] frontend/package.json, pnpm-lock.yaml에 별도 vinext 명령과 의존성 추가.
- [x] frontend/vite.config.ts, cloudflare.config.ts와 생성물 ignore 설정 추가.
- [x] 공개 API 주소를 빌드에 전달하고 비밀 파일은 추적하지 않는다.
- [x] pnpm test 296개, typecheck, 기존 Next.js 빌드와 Cloudflare 빌드 통과.
- [x] 로컬 Worker 주요 경로와 정적 자산, 무료 코드 크기 검사.
- [x] 독립 검토에서 실제 변경과 무료 플랜 조건 확인.
- [x] Pages 고급 모드로 패키징하고 로컬 HTTP와 서버 코드 비공개 확인.
- [x] Pages 운영 배포 후 공개 HTTP 검사 통과. 도메인 등록 및 가비아 CNAME 변경 완료.
- [x] 사용자 도메인 인증서 활성화 후 실제 HTTPS 재검사. verification/validation/status 모두 active.
- [x] docs/deploy.md에 실제 결과와 API 상태, 제한을 기록한다.

## Review Focus

- 빌드 시 NEXT_PUBLIC 주소 누락으로 실서버 대신 녹화본이 실행되는 상황.
- 요청별 10ms CPU 또는 압축 코드 한도를 넘는 상황.
- 기존 redirects, 임의 UUID와 잘못된 언어 경로의 처리 차이.
- Cloud Run 장애가 있는 상태에서 프론트 복구만 성공하는 상황.
- 도메인 권한이 없어 원래 주소를 바꿀 수 없는 상황.

## 결정 및 검증 기록

- Vite 8은 기존 Vitest 3의 타입과 충돌했다. Vitest 5.1.1로 맞춰 해결했다.
- CSS 내 font @import는 Vite 빌드에서 상대 경로를 잃었다. layout.tsx에서
  직접 import하도록 옮겨 생성 CSS의 184개 폰트 경로가 모두 존재함을 확인했다.
- 독립 검토의 위 두 지적을 수정하고 재검토로 해결을 확인했다.
- 기본 cf CLI는 Wrangler OAuth를 자동으로 재사용하지 않았다. 기존 Wrangler
  인증을 지원하고 외부 DNS CNAME으로 연결 가능한 Pages 경로를 선택했다.
- Pages는 사용자 지정 config 파일명과 account_id 설정을 지원하지 않는다.
  deployment/cloudflare-pages의 표준 wrangler.jsonc와 배포 시 계정 환경 변수를 사용한다.
- 원본 네이티브 모듈 디렉터리는 Wrangler 개발 미들웨어와 순환 경로 충돌이 있었다.
  esbuild로 단일 ESM을 만든 뒤 로컬과 공개 Pages 주소에서 동작을 확인했다.
- 배포: 90c8195c.hanjeok-agent.pages.dev, 운영 별칭 hanjeok-agent.pages.dev.
  GET /, /evidence는307, /ko와/en 및 질문/그래프/평가/근거는200,
  /de와/_worker.js/index.js는404. 폰트와 배너 이미지도200.
- 가비아 `agent` CNAME만 hanjeok-agent.pages.dev.로 변경, TTL3600 유지.
- GCP `gcloud billing projects describe`는 billingEnabled=false.
- 2026-11-22 기존 사용자 도메인 HTTPS도 전체 smoke 검사 통과.
  한국어/영어 저장 예시 코스도200. Pages 패키징 최종 독립 검토에서 중대한 지적 없음.
