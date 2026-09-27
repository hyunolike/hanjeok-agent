# 배포

서버는 Cloud Run, 화면은 Vercel. 상태도 DB도 없어서 0으로 스케일다운된다.

**이 문서는 사람이 실행한다.** GCP 프로젝트, Vercel 팀, Secret Manager에 키를 넣는 일은
승인이 필요한 행위다. 저장소에 있는 것은 그 승인이 떨어지면 그대로 도는 산출물이다 —
`Dockerfile`, `.github/workflows/build.yml`, 그리고 이 문서.

## 환경 변수

서버가 실제로 읽는 전부다. 이 목록이 `application.yml`과 어긋나면 배포가 조용히
기본값으로 돈다.

| 변수 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `HANJEOK_BASE_URL` | **예** | 없음 | 한적 백엔드 주소. 기본값을 두지 않는다 — 빠뜨리면 기동이 이름을 지목하며 실패한다 |
| `HERMES_LLM_PROVIDER` | 아니오 | `anthropic` | `anthropic` · `openai` · `openrouter`. 하네스 `./gradlew eval <이름>`과 같은 이름이다 |
| `HERMES_LLM_MODEL` | 아니오 | `claude-opus-5` | 프로바이더에 맞는 모델 이름. **세 프로바이더 모두 이 값을 따른다** — 이전에는 anthropic 만 이 값을 무시하고 코드에 박힌 모델로 돌았다 |
| `ANTHROPIC_API_KEY` | 조건부 | 없음 | `provider=anthropic`일 때. 없으면 서버는 뜨지만 `/actuator/health`가 DOWN |
| `OPENAI_API_KEY` | 조건부 | 없음 | `provider=openai`일 때. 없으면 **기동이 멈춘다** |
| `OPENROUTER_API_KEY` | 조건부 | 없음 | `provider=openrouter`일 때. 없으면 기동이 멈춘다 |
| `HERMES_CORS_ALLOWED_ORIGINS` | **예(운영)** | `http://localhost:3000` | Vercel 도메인. 빠뜨리면 화면은 열리는데 모든 요청이 막힌다 |
| `HERMES_DEMO_COURSES` | 아니오 | 비어 있음 | `uuid\|라벨, uuid\|라벨`. `demoReachability` 태스크가 쓴다 |
| `PORT` | 아니오 | `8080` | Cloud Run이 준다 |

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
./gradlew eval --args="openai 5"   # 띄우려는 조합을 먼저 잰다
```

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
루프가 60초에 먼저 포기하면 `unavailable`이든 `aborted`든 제 이벤트로 스트림을
닫을 시간이 emitter에게 30초 남고, emitter가 90초에 먼저 끊어도 Cloud Run이
그 연결을 끊기 전에 210초가 남는다. 순서가 뒤집히면 안쪽이 보고할 새도 없이
바깥쪽이 먼저 끊어 버린다 — 그러면 실패 이벤트 하나 없이 스트림이 그냥 죽는다.

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
curl -s "$BASE/agent/context" | head   # 문서 9개. 번들이 이미지에 구워졌다는 증거
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
