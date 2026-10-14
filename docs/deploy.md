# 배포

서버는 Cloud Run, 화면은 Vercel. 상태도 DB도 없어서 0으로 스케일다운된다.

**이 문서는 사람이 실행한다.** GCP 프로젝트, Vercel 팀, Secret Manager에 키를 넣는 일은
승인이 필요한 행위다. 저장소에 있는 것은 그 승인이 떨어지면 그대로 도는 산출물이다 —
`Dockerfile`, `.github/workflows/build.yml`, 그리고 이 문서.

## 먼저 로컬에서 실행하기

JDK 21·Node.js 22.12+ (22.x)·pnpm 10 준비, 무료 빌드/테스트, `bootRun`, frontend
`.env.local`/`pnpm dev`와 두 서버의 연결은 [README 시작하기](explainer/README.ko.md#-시작하기)에
한곳에 정리했습니다([English](explainer/README.md#-getting-started)). 아래 클라우드 명령은
로컬 quickstart에 필요하지 않습니다.

에이전트 자체 DB는 없지만 실제 코스에는 별도 한적 백엔드와 기존 UUID가 필요합니다.
기본 FULL 실행에는 retrieval/Python/Neo4j가 필요 없습니다. 키 없는 근거 화면 확인은
실제 facts·모델 연결 검증과 다릅니다. health UP도 키의 유효성이나 백엔드 도달성을
확인하지 않습니다. 코스를 열면 EXPLAIN이 자동 호출될 수 있으므로 모델 비용 경계를
먼저 확인하세요.

## 환경 변수

기본 FULL 서버의 환경 변수다. opt-in retrieval 변수는 아래 별도 절에 있다.
`bootRun`은 루트 `.env`를 읽지 않으므로 셸 환경에 export한다. 루트 `.env`를 읽는
Gradle 태스크는 `eval`과 `demoReachability`뿐이며, frontend는 별도의
`frontend/.env.local`을 사용한다. 서버 모델은 `HERMES_LLM_MODEL`이고 평가 모델의
`OPENAI_MODEL`/`ANTHROPIC_MODEL`/`OPENROUTER_MODEL`과 구분한다.

| 변수 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `HANJEOK_BASE_URL` | **예** | 없음 | 한적 백엔드 주소. 기본값을 두지 않는다 — 빠뜨리면 기동이 이름을 지목하며 실패한다 |
| `HERMES_LLM_PROVIDER` | 아니오 | `anthropic` | `anthropic` · `openai` · `openrouter`. 하네스 `./gradlew eval <이름>`과 같은 이름이다 |
| `HERMES_LLM_MODEL` | 아니오 | `claude-opus-5` | 프로바이더에 맞는 모델 이름. **세 프로바이더 모두 이 값을 따른다** — 이전에는 anthropic 만 이 값을 무시하고 코드에 박힌 모델로 돌았다 |
| `ANTHROPIC_API_KEY` | 조건부 | 없음 | `provider=anthropic`일 때. 없으면 서버는 뜨지만 `/actuator/health`가 DOWN |
| `ANTHROPIC_AUTH_TOKEN` | 조건부 | 없음 | Anthropic SDK가 지원하는 대체 인증값. 키와 토큰이 모두 없으면 health DOWN |
| `OPENAI_API_KEY` | 조건부 | 없음 | `provider=openai`일 때. 없으면 **기동이 멈춘다** |
| `OPENROUTER_API_KEY` | 조건부 | 없음 | `provider=openrouter`일 때. 없으면 기동이 멈춘다 |
| `HERMES_CORS_ALLOWED_ORIGINS` | **예(운영)** | `http://localhost:3000` | Vercel 도메인. 빠뜨리면 화면은 열리는데 모든 요청이 막힌다 |
| `HERMES_DEMO_COURSES` | 아니오 | 비어 있음 | `uuid\|라벨, uuid\|라벨`. `demoReachability` 태스크가 쓴다 |
| `PORT` | 아니오 | `8080` | Cloud Run/Docker entrypoint가 `-Dserver.port`로 전달. `bootRun`에서는 읽지 않음 |
| `SERVER_PORT` | 아니오 | `8080` | 로컬 `bootRun` 포트 변경용 Spring Boot 설정. Docker는 entrypoint의 `PORT`가 우선 |

> **키를 이미지에 굽지 않는다.** `.dockerignore`가 `.env`를 막지만, 그건 마지막 방어선이지
> 첫 번째가 아니다. 키는 Secret Manager에서 환경 변수로 주입한다.

## 어느 프로바이더로 띄울 것인가

측정된 것은 OpenAI뿐이다(`gpt-4o-mini`, `gpt-4o`). 기본값 `anthropic`으로 띄우면 **한 번도
재본 적 없는 프로바이더**가 도는 것이고, 하네스가 낸 위반율 0%는 그 서버에 대해 아무것도
말해 주지 않는다. 잰 것을 띄우거나, 띄울 것을 재고 나서 띄운다.

**둘 중에는 `gpt-4o`다.** 두 모델 모두 규칙 위반 8종이 0%였고, 가른 것은 가독성이었다
(실행당 지적 1.2건 대 0.5건). 설명이 이 서비스의 유일한 산출물이라 그 축이 결정한다 —
근거와 한계는 위키 `decisions/choose-explanation-model.md`.

```bash
OPENAI_MODEL=gpt-4o ./gradlew eval --args="openai 5"   # 실제 API 호출/비용, 로컬 무료 검사에 포함되지 않음
```

루트 `.env`가 있으면 그 파일의 값이 평가 환경을 덮어쓰므로 `OPENAI_MODEL`도 확인한다.
위 명령은 서버의 `HERMES_LLM_MODEL`을 사용하지 않는다. `JUDGE_MODEL`을 설정하면
추가 LLM 판정 호출도 발생한다. OpenRouter 무료 티어도 모델 가용성·요금·할당량에
따르며 무료 실행을 보증하지 않는다.

## Cloud Run

```bash
PROJECT=<프로젝트 ID>
REGION=asia-northeast3

# 1. 이미지
gcloud builds submit --tag "gcr.io/$PROJECT/hermes-agent"

# 2. 키 (한 번만)
echo -n "$OPENAI_API_KEY" | gcloud secrets create hermes-openai-key --data-file=-

# 3. 배포
gcloud run deploy hermes-agent \
  --image "gcr.io/$PROJECT/hermes-agent" \
  --region "$REGION" \
  --allow-unauthenticated \
  --min-instances 0 \
  --set-env-vars "HANJEOK_BASE_URL=<한적 주소>,HERMES_LLM_PROVIDER=openai,HERMES_LLM_MODEL=gpt-4o,HERMES_CORS_ALLOWED_ORIGINS=<Vercel 도메인>" \
  --set-secrets "OPENAI_API_KEY=hermes-openai-key:latest"
```

`--timeout`을 90초 밑으로 주지 않는다. `AskStreamController`가 이어 묻기 SSE 연결에
90초짜리 emitter 타임아웃을 이미 걸어 두었다 — Cloud Run 타임아웃이 그보다 짧으면
emitter가 아니라 Cloud Run이 먼저 연결을 끊어, 본문을 보내는 도중이던 스트림이
`aborted`도 못 내고 그냥 끊긴다. 위 명령처럼 `--timeout`을 생략하면 Cloud Run
기본값인 300초가 적용돼 지금은 emitter가 먼저 끊는다.

**이 90초 앞에 숫자가 하나 더 있다.** `AgentLoop`의 마감은 60초다 — 도구 라운드(최대
2회, 모델 호출 최대 3회)와 인용 무효 수리가 이 60초를 함께 쓴다. 세 숫자는
`루프 60초 < emitter 90초 < Cloud Run 300초` 순서로 겹쳐 있고, 그 순서가 이유다.
순서가 뒤집히면 안쪽이 보고할 새도 없이 바깥쪽이 먼저 끊어 버린다 — 그러면 실패
이벤트 하나 없이 스트림이 그냥 죽는다.

**다만 60초는 보장이 아니다.** 마감은 **다음 모델 호출을 시작할지**를 가를 때만 본다.
호출별 HTTP 타임아웃이 LLM 클라이언트에 걸려 있지 않아서, 이미 나간 호출 하나가
60초를 넘겨도 루프는 그 호출이 끝날 때까지 기다린다. 즉 "루프가 60초에 포기하면
emitter에게 30초가 남는다"는 계산은 **호출들이 제때 돌아오는 평소**의 이야기이고,
모델이 오래 물고 있으면 그 30초는 줄어들거나 없어진다. 그때 먼저 포기하는 쪽은
emitter(90초)이고, 그 뒤를 Cloud Run(300초)이 받는다 — 그래서 `--timeout`을 90초
밑으로 주지 않는 이유가 그대로 남는다. 마감이 실제로 사 주는 것은 벽시계 상한이
아니라 **호출 횟수의 상한**이다.

**도구를 부르는 질문은 그만큼 느리다.** `congestion`이나 `alternatives`를 한 번
부르면 모델 호출이 하나 늘어난다 — 왕복이 대략 한 번 더 붙는다고 보면 된다. 90초
밑으로 `--timeout`을 주지 않는 이유가 하나 더 생긴 셈이다. 라운드가 없는 질문은
예전과 같은 한 번의 모델 호출로 끝난다.

한적이 같은 VPC 안의 VM이면 내부 IP를 쓰고 커넥터를 붙인다. 공개 주소로 부르면
서버-서버 호출이라 **CORS 변경은 여전히 0건**이다 — 브라우저가 한적을 직접 부르지 않는다.

### 배포 확인

```bash
BASE=$(gcloud run services describe hermes-agent --region "$REGION" --format='value(status.url)')

curl -s "$BASE/actuator/health"        # UP 이어야 한다. DOWN 이면 번들이나 키다
                                       # documents 와 bytes 가 함께 나온다 — 번들이 이미지에 구워졌다는 증거
curl -s "$BASE/agent/context" | head   # {documents: [...], systemTextBytes} 모양이어야 한다
curl -s "$BASE/agent/facts/<uuid>"     # 한적 연결 확인. 503이면 한적에 못 닿은 것
```

`/actuator/health`가 DOWN인 채로 트래픽을 받으면 안 된다 — 번들이 없으면 근거 없이
답하게 되고, 그게 이 프로젝트가 막으려는 일이다.

## Vercel

| 항목 | 값 |
| --- | --- |
| 프로젝트 | `hermes-agent` (팀 `hyunho-jangs-projects`) |
| Root Directory | `frontend` — CLI 를 그 디렉터리에서 돌리면 자동으로 그렇게 된다 |
| Framework | Next.js (자동 감지) |
| 환경 변수 | `NEXT_PUBLIC_AGENT_BASE_URL` = Cloud Run 주소 (production·preview·development 셋 다) |
| 도메인 | `agent.hanjeok.com` — 가비아에 CNAME → `cname.vercel-dns.com.` |

```bash
cd frontend
vercel deploy --prod
```

**CORS 를 잊지 말 것.** 도메인을 붙인 뒤 Cloud Run 에 그 오리진을 넣어야 한다. gcloud 는
값 안의 쉼표를 구분자로 읽으므로 구분자를 바꿔 준다.

```bash
gcloud run services update hermes-agent --region asia-northeast3 \
  --update-env-vars "^@^HERMES_CORS_ALLOWED_ORIGINS=https://agent.hanjeok.com,http://localhost:3000"
```

프론트에 내려가는 것은 이 주소 하나뿐이다. 한적 주소도, 어떤 키도 브라우저로 가지 않는다.

빌드는 백엔드가 떠 있지 않아도 성공한다 — 두 페이지가 요청 시점에 그려지고, 연결 거부는
예외가 아니라 "불러오지 못했습니다" 화면이 된다. 첫 빌드가 이것 때문에 죽은 적이 있어
CI가 매번 확인한다.

## 배포된 것

| 항목 | 값 |
| --- | --- |
| 서버 | `https://hermes-agent-508380543987.asia-northeast3.run.app` |
| 이미지 | `asia-northeast3-docker.pkg.dev/hanjeok-prod/hermes/hermes-agent` |
| 한적 | `https://api.hanjeok.com` (VM `hanjeok-app`, 34.50.38.158) |
| 프로바이더 | `openai` / `gpt-4o` |
| 시크릿 | `hermes-openai-key` — 런타임 서비스 계정에 **그 시크릿에만** accessor 부여 |
| 인스턴스 | 최소 0, 최대 3, 1Gi |
| 화면 | `https://agent.hanjeok.com` (Vercel, 프로젝트 `hermes-agent`) |
| CORS | `agent.hanjeok.com`, `hermes-agent-olive-beta.vercel.app`, `localhost:3000` |

배포하며 막힌 것 셋: Cloud Run·Cloud Build API 미활성화, Artifact Registry `hermes`
저장소 없음(이미지는 빌드됐고 push만 실패했다), 런타임 서비스 계정의 시크릿 권한 없음.

## 데모 코스

한적에 만들어 둔 셋이다(전부 2026-09-12).

| 종류 | uuid | 코스 |
| --- | --- | --- |
| `crowded-with-alternatives` | `129efdef-…` | 덕수궁(매우혼잡) + 대안 2개, 감소율 39% |
| `no-alternatives` | `e66302c6-…` | 경복궁 — 대안 0개, 세 장소 전부 매우혼잡이라 **감소율 0%** |
| `better-date` | `5a2eb601-…` | 국립중앙박물관 — 9월 24일을 권함(감소율 32%) |

두 번째가 이 데모에서 가장 값을 한다. 줄지 않은 혼잡도를 줄었다고 말하지 않는지,
없는 대안을 지어내지 않는지가 거기서 드러난다.

```bash
HANJEOK_BASE_URL=https://api.hanjeok.com \
HERMES_DEMO_COURSES="129efdef-41ec-4044-ac87-303abe4ccdde|덕수궁, e66302c6-b413-4a07-88a5-3bd55e61fc2a|경복궁, 5a2eb601-1f2b-499b-83eb-8a0093f4817e|국립중앙박물관" \
  ./gradlew demoReachability
```

코스가 삭제되면 데모가 깨진다. 이건 결함이 아니라 "사실은 백엔드에서만 온다"를 지킨
대가이고, 조용히 깨지지 않도록 이 검사가 있다.

## 별도 검색 API 후속 코드 — 아직 운영 미배포

현재 운영 기본값 FULL과 운영 배포는 유지합니다. 이 로컬 브랜치의 [검색 서비스 준비 문서](../deployment/retrieval/README.md)는 별도 private Python API, 고정 인덱스 수동 검증/공개/롤백, 요청별 인용 검증을 설명합니다. 새 코드의 cloud IAM/Enterprise reader 권한/이미지 빌드/실제 배포는 미검증·미실행이며 별도 승인이 필요합니다.

| 변수 | 기본값 / 의미 |
| --- | --- |
| `HERMES_RETRIEVAL_MODE` | `FULL`; 명시적으로만 `VECTOR` / `HYBRID_GRAPH` 사용 |
| `HERMES_RETRIEVAL_URL` | 비어 있음; 선택 모드에서 승인된 private HTTPS origin |
| `HERMES_RETRIEVAL_INDEX_VERSION` | 비어 있음; 검증된 immutable manifest SHA-256 |
| `HERMES_RETRIEVAL_MODEL_REVISION` | 비어 있음; `tfidf-v1` 또는 고정 semantic revision |
| `HERMES_RETRIEVAL_AUTH_MODE` | `cloud-run-iam`; 기존 attached identity의 ID token 사용 |

로컬 모드만 `loopback-test`와 `HERMES_RETRIEVAL_LOCAL_TOKEN`을 사용하며 K_SERVICE가 있으면 거부합니다. 실제 비밀 값은 저장하거나 출력하지 않습니다. FULL에서는 검색 HTTP/metadata token 호출이 없습니다. API 장애·핀 불일치에는 검증된 FULL로 복구하고, 원본 FULL이 손상됐으면 기동에서 실패합니다.

## 한적 에이전트 (guide) — Cloud Run 서비스 하나 더

위의 `hermes-agent`(Kotlin)와 별개로, 질문에 답하는 파이썬 서비스가 같은 프로젝트와 리전에
`hanjeok-guide`라는 이름으로 올라가 있다. **2026-10-14에 실제로 실행한 명령**이고, 그날의
측정값을 함께 적는다.

이 서비스는 상태가 없지 않다. 이미지 안에 Neo4j와 그 그래프가 들어 있다 — 그래프는 내보내기
파일과 위키에서 다시 만들 수 있는 파생물이라, 이미지를 새로 지으면 통째로 바뀐다.

### 1. 데이터

```bash
# 한적 운영 서버에서 (한적 저장소의 scripts/guide-agent-export.sh)
./guide-agent-export.sh                       # 읽기 전용, 1.7초, hanjeok-export-YYYYMMDD/
# 내려받아 bench/.cache/exports/ 에 두고
cd bench
uv run guide refresh --export .cache/exports/hanjeok-export-20261014 --check
uv run guide refresh --export .cache/exports/hanjeok-export-20261014   # 임베딩까지. CPU 로 40분
```

관광지 13,403곳의 임베딩은 로컬에서 한 번 계산해 `.cache/guide-embeddings.sqlite`에 남긴다.
이미지 빌드는 그 파일을 받아 쓰므로 다시 계산하지 않는다. `.cache/`는 git 에 올라가지 않는다.

### 2. 이미지

```bash
cd bench
gcloud builds submit --config cloudbuild.yaml --substitutions \
  _IMAGE=asia-northeast3-docker.pkg.dev/$PROJECT/hermes/hanjeok-guide:real-20261014,\
_EXPORT_DIR=.cache/exports/hanjeok-export-20261014,\
_EMBEDDING_CACHE=.cache/guide-embeddings.sqlite
```

12분 걸렸다. 빌드가 이미지 안에서 Neo4j 를 띄워 위키와 장소를 올리고 깨끗이 내린다(그래프
738MB). 올라가는 파일은 `.gcloudignore`의 허용 목록뿐이다 — `.env`와 가상환경은 나가지 않는다.

### 3. 키와 배포

```bash
# 한 번만. 값은 화면에 찍지 않는다
grep -E '^NVIDIA_API_KEY=' .env | cut -d= -f2- | tr -d '\n' | \
  gcloud secrets create HANJEOK_GUIDE_NVIDIA_API_KEY --replication-policy=automatic --data-file=-
gcloud secrets add-iam-policy-binding HANJEOK_GUIDE_NVIDIA_API_KEY \
  --member="serviceAccount:<Cloud Run 서비스 계정>" --role=roles/secretmanager.secretAccessor

gcloud run deploy hanjeok-guide \
  --image asia-northeast3-docker.pkg.dev/$PROJECT/hermes/hanjeok-guide:real-20261014 \
  --region asia-northeast3 --allow-unauthenticated \
  --memory 8Gi --cpu 2 --min-instances 0 --max-instances 1 --concurrency 20 \
  --timeout 300 --port 7860 --execution-environment gen2 --cpu-boost \
  --startup-probe "tcpSocket.port=7860,periodSeconds=10,failureThreshold=30,timeoutSeconds=5" \
  --set-env-vars "^@^GUIDE_CORS_ALLOWED_ORIGINS=https://agent.hanjeok.com,<미리보기 도메인>@GUIDE_LIVE_MODE=live@HANJEOK_BASE_URL=https://api.hanjeok.com" \
  --set-secrets "NVIDIA_API_KEY=HANJEOK_GUIDE_NVIDIA_API_KEY:latest"
```

- **`--max-instances 1`은 선택이 아니다.** 방문 기록과 사용 한도가 프로세스 메모리에 있다.
  인스턴스가 둘이면 「어느 곳인가요?」에 대한 답이 질문을 받은 적 없는 인스턴스로 갈 수 있다.
- **메모리 8Gi**는 임베딩 모델과 Neo4j 를 함께 올리기 위한 넉넉한 값이다. 실제 사용량은 재지
  않았다. 줄일 수 있는지는 재 보고 정한다.
- **깨어나는 데 약 30초**(Neo4j 19초 + 서버 10초, 실측). `--min-instances 0`이라 한동안 요청이
  없던 뒤의 첫 질문은 그만큼 기다린다.
- `GUIDE_LIVE_MODE=live`는 한적의 `/attractions/{id}/congestion`과 `/alternatives`를 실제로
  부른다. 둘 다 읽기 전용이고 조회수를 남기지 않는다.

### 4. 화면

Vercel 프로젝트의 **Production** 환경 변수 `NEXT_PUBLIC_GUIDE_BASE_URL`에 서비스 주소를 넣는다.
비어 있으면 화면은 녹화본을 재생한다. 값은 빌드할 때 박히므로 넣은 뒤 다시 배포해야 반영된다.

### 확인

```bash
BASE=$(gcloud run services describe hanjeok-guide --region asia-northeast3 --format='value(status.url)')
curl -s "$BASE/guide/status"            # ready: true, 장소 수, 내보낸 시각
curl -sN "$BASE/guide/ask" -H 'content-type: application/json' \
  -d '{"question":"이번 토요일 경복궁 대신 조용한 곳 있어?"}'
```

