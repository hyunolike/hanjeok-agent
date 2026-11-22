# 질문 API 무료 이전 조사

**상태: 2026-11-22 사용자 요청으로 보류.** 프론트 복구와 도메인 연결은 완료했고,
질문 API는 중단 상태다. 추가 가입 절차나 서버 생성은 진행하지 않는다.
기존 작업 브랜치 fix/cloudflare-free-deploy와 로컬 데이터 백업을 보존한다.

## 현재 상태와 범위

사용자는 Cloudflare 무료 프론트 복구 후 실시간 질문 API의 무료 이전도 요청했다.
프론트는 https://agent.hanjeok.com 에서 정상 응답하며 질문 API는 아직 복구되지 않았다.
유료 플랜 가입, GCP 결제 활성화와 기존 동작을 녹화본으로 바꾸는 것은 승인 범위가 아니다.

## 확인한 운영 조건

- GCP 프로젝트 hanjeok-prod의 billingEnabled=false.
- hanjeok-guide의 운영 이미지:
  asia-northeast3-docker.pkg.dev/hanjeok-prod/hermes/hanjeok-guide:real-20261014-ctx5
- 2 CPU / 8Gi, 로컬 Neo4j와 intfloat/multilingual-e5-large 임베딩 모델을 함께 사용한다.
- GUIDE_LIVE_MODE=live, HANJEOK_BASE_URL=https://api.hanjeok.com.
- NVIDIA_API_KEY는 Secret Manager의 HANJEOK_GUIDE_NVIDIA_API_KEY:latest 참조.
  시크릿 값은 조회하거나 출력하지 않았다.
- 기존 CORS는 hanjeok.com, agent.hanjeok.com, 이전 Vercel 별칭과 localhost를 허용한다.
- 처음에는 실제 export와 캐시가 없었지만 다른 로컬 작업 폴더에서 기존 데이터를
  찾아 현재 bench/.cache로 복사했다. 원본은 보존했다. 로컬 Docker 이미지는 없다.
  Dockerfile 기본 fixture를 운영 데이터 대신 올리면 안 된다.

## Hugging Face 확인 결과

웹 로그인 계정은 hyunolike. 공개 계정 API의 isPro=false, numSpaces=0을 확인했다.
CLI에는 별도 인증이 없지만 무료 생성 가능 여부 확인을 위해 토큰을 만들 필요는 없다.
최신 공식 Spaces Overview는 새 Docker/Gradio compute Space 생성에 개인 PRO 또는
조직 유료 플랜이 필요하다고 명시한다. 가격표의 CPU Basic FREE는 compute 가격이며
새 Docker Space를 무료 계정에서 생성할 수 있다는 뜻으로 단정하지 않는다.
유료 업그레이드나 새 Space 생성은 하지 않았다. 기존 Docker Space도 없다.

## 다음 후보와 미정 사항

현 구조를 유지하는 후보는 Oracle Always Free의 Ampere A1 최대2 OCPU/12GB다.
기존 계정, 홈 리전의 무료 자원 가용량, ARM 빌드 호환성, 실제 운영 이미지/데이터
복구 가능 여부를 확인해야 한다. 계정이 있다고 해서 할당량이나 공급 가능성을
보장하지 않는다. 로컬 OCI 인증 설정은 없으며 사용자에게 계정 보유 여부를 확인했다.

사용자가 계정 가입을 진행할 수 있도록 공식 가입 페이지를 열었다. 실제 선택 목록에
서울이 없어 사용자의 직접 선택 요청에 따라 Japan Central (Osaka)를 선택했다.
가입 제출이나 계정 생성 완료는 확인하지 않았다. Oracle 서버나 유료 자원은 만들지 않았다.

Render 등의 작은 무료 인스턴스로 옮기려면 Neo4j와 임베딩 모델을 분리하는 설계
변경이 필요하다. 이 조사를 근거로 기존 API의 검색 방식이나 모델을 바꾸지 않았다.

## 재개할 때 확인할 순서

1. 사용자의 Oracle 가입 완료 여부, 홈 리전과 Always Free A1의 실제 할당량/가용량 확인.
2. 복구한 임베딩 캐시의 행 수와 차원 및 ARM 빌드 호환성 확인. export 자체는 검증 완료.
3. 구체적 배포 설계/작업 목록을 준비하고 무료 범위를 확인한 뒤 서버 배포.
4. 새 API의 status, 장소 수/데이터 시점, 기존 검색과 CORS 및 SSE 계약을 검증.
5. 검증한 API로 프론트 공개 주소를 바꾼 뒤 실제 질문 완료까지 확인.

## 운영 데이터 복구

원본은 /Volumes/T9/Projects/orca/hermes-agent/.claude/worktrees/service-agent/bench/.cache다.
hanjeok-export-20261014의 실제 데이터17MB와 guide-embeddings.sqlite60MB를 현재
체크아웃으로 복사했다. export loader가 파일별 SHA256, 행 수와 허용 컬럼을 검증했다.
장소13,403건, 관련 장소45,244건, 축제219건, 전시134건이다.
둘 다 기존 gitignore 대상이어서 Git 추적이나 공개 저장소 업로드는 하지 않았다.

Artifact Registry 이미지 조회는 BILLING_DISABLED로 거절됐다. GCP 결제를 켜지
않았으며 위 로컬 복구 경로를 사용한다.

## 근거

- bench/Dockerfile, bench/deploy/neo4j.sh, bench/src/bench/embeddings.py
- bench/src/guide/api.py, bench/src/guide/model.py
- https://huggingface.co/docs/hub/spaces-overview
- https://huggingface.co/pricing
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
