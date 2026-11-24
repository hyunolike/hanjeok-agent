# 512MiB 안내 API

Python HTTP API만 실행하는 배포 구성이다. 현재 무료 프로필은 공개 관광 데이터와
동일 공간 벡터를 읽기 전용 SQLite 파일로 이미지에 넣어 Aura 인증 없이 실행한다.
임베딩 생성과 답변은 NVIDIA HTTP API를 사용한다. 기존 Neo4j 경로도 유지한다.
기존 Kotlin API의 배포는 포함하지 않는다. 실제 공개 여부는 아래 검증 기록과 구분한다.

## 현재 무료 프로필: SQLite

`render.yaml`과 `env.example`은 `GUIDE_STORE=sqlite`를 선택한다. 필요한 시크릿은
기존 `NVIDIA_API_KEY`이며 Aura 접속값은 필요 없다. API의 일반 기본값은 기존
`neo4j`이므로 SQLite 선택을 생략하면 안 된다. 오타나 파일 오류 때 다른 저장소로 폴백하지 않는다.

`bench/data/manifest.json`과 그것이 가리키는 content-addressed gzip을 배포한다.
이미지 빌드에서 gzip과 원본 DB 해시를 검사해 해제하고, 실행 시 DB 해시, 스키마,
건수, 두 코퍼스 임베딩 식별자를 다시 검사한다. 읽기 전용 연결 하나와 8MiB 페이지
캐시를 쓰고 mmap을 끈다. 모델은 SQL을 만들지 않는다. sqlite-vec의 고정 버전 C 함수로
정확 코사인 검색을 하므로 기존 Neo4j 근사 검색과 경계 순위가 달라질 수 있다.

공개 export 12,106장소, 43,087관계, 209행사와 위키18문서/83청크를 보존했다.
시점은 2026-11-23 export와 manifest의 고정 위키 revision이다. 오래된 날짜의 혼잡
예보를 파일에서 제공하지 않고 질문할 때 한적 API를 호출한다. 데이터 갱신은 새
산출물을 준비해 재배포한다. 실행 중 파일 교체는 지원하지 않는다.

운영자 준비는 기존 검증 캐시를 mode=ro로 읽으며 새 모델 호출을 하지 않는다.
아래 명령은 `bench/`에서, SQLite 확장 로드를 지원하는 Python3.13 환경에서 실행한다.

```bash
PYTHONPATH=src:. python deploy/prepare_sqlite.py prepare \
  --export .cache/exports/hanjeok-export-20261123 \
  --place-cache .cache/guide-nvidia-embeddings.sqlite \
  --wiki /path/to/clean-pinned-wiki \
  --wiki-cache .cache/wiki-nvidia-prepared.sqlite \
  --wiki-manifest reports/runtime/offline-wiki-artifact-manifest.json \
  --wiki-promotion reports/runtime/offline-wiki-promotion.json \
  --output data
```

빌더는 승인된 위키 원문 청크의 id/순서/해시까지 대조한다. gzip을 먼저 쓰고
manifest를 마지막에 원자적으로 공개하므로 실패 시 이전 파일 묶음은 유효하다.
과거 Super/Ultra의 Neo4j 품질 수치는 SQLite 품질 수치로 재사용하지 않는다.
[설계와 수용 기준](../../docs/superpowers/specs/2026-11-24-guide-sqlite-design.md),
[검토/실제 확인](../../docs/superpowers/reviews/2026-11-24-guide-sqlite-review.md).

## 구성과 유지되는 동작

- `bench/Dockerfile.api`: Python 3.13, 비루트 사용자, uvicorn 워커 1개.
- `bench/runtime/requirements.txt`: 해시 잠금. torch, sentence-transformers, ragas 제외.
- `GUIDE_STORE=neo4j` 경로는 `BENCH_NEO4J_URI`로 연결한다. AuraDB는 `neo4j+s://…`를 사용한다.
- `GUIDE_EMBEDDING_PROVIDER=nvidia`: NVIDIA의
  `nvidia/nemotron-3.5-embed-1b`를 1024차원으로 호출한다.
  최초 후보인 llama-3.2 엔드포인트는 공식 카탈로그의 deprecated 공지를 확인해 제외했다.
  [현재 모델 API](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-embed-1b-infer)
- 기존 LangGraph 루프, 고정 조회 7개, 서비스 순위, 인용 검사, 수정 1회와 SSE 계약을 유지한다.
- 답변 기본 모델은 `nvidia/nemotron-3-ultra-550b-a55b`다. 사용자 요청으로
  무료 Super에서 Ultra로 전환했다. 이전 3-Super는
  실제 요청에서 HTTP 410을 반환해 교체했다. 같은 NVIDIA 키와 strict JSON 계약을 사용한다.
- 로컬 모드는 기존처럼 `GUIDE_EMBEDDING_PROVIDER=local`이며 E5 모델을 사용한다.
  기존 `bench/Dockerfile`과 `uv.lock`은 로컬 모델 실행을 계속 지원한다.

## 먼저 별도 데이터베이스를 준비한다

모델을 바꾸면 장소와 위키의 벡터를 모두 다시 만들어야 한다. 1024차원이라는 이유로
기존 E5 벡터를 재사용하면 안 된다. 외부 API 모드는 두 코퍼스의 `embedding_model`
식별자가 현재 모델과 일치해야 준비 상태가 된다. 식별자가 없는 옛 데이터도 거절한다.
식별자는 모델, 차원, query/passage 처리, truncate와 정규화 버전을 포함한다.

모델 변경은 새 DB에 적재하고 검증한 뒤 접속 주소를 바꾼다. 운영 DB의 모델을
인플레이스로 바꾸지 않는다. 위키 rebuild는 기존 동작대로 먼저 지우므로 적재 도중에는
그 DB의 API가 준비되지 않음으로 응답할 수 있다. 적재 작업은 하나씩 실행한다.

아래 명령은 실제 임베딩 API를 호출해 계정 한도를 사용한다. 512MiB API 컨테이너에서
실행하지 않는다. 원본 export와 위키는 운영자가 로컬 작업 환경에 준비한다.
`BENCH_WIKI_ROOT`에는 기존 배포와 같은 위키 커밋
`7fc19c0c4a034868866bcf5a920e3f82050830c7`의 체크아웃을 지정한다.

```bash
cd bench
uv sync --frozen
# 자격증명은 셸/시크릿 관리에서 설정한다. 파일을 Git에 넣지 않는다.
export GUIDE_EMBEDDING_PROVIDER=nvidia
# BENCH_NEO4J_URI, BENCH_NEO4J_USER, BENCH_NEO4J_PASSWORD,
# BENCH_WIKI_ROOT, NVIDIA_API_KEY를 설정한 뒤 새 DB에 실행한다.
uv run bench corpus load wiki
uv run guide refresh --export .cache/exports/hanjeok-export-20261123 \
  --cache .cache/guide-nvidia-embeddings.sqlite
```

2026-11-23 운영 API 점검에서 기존 2026-10-14 export의 장소 ID가 더 이상 유효하지
않음을 확인했다. 같은 경복궁이 옛 ID `653`에서는 404, 현재 ID `10000028`에서는
200이었다. 현재 운영 DB에서 기존 공개 컬럼 허용 목록을 읽기 전용 트랜잭션으로
다시 내보냈으며 장소 12,106개, 연관 링크 43,087개, 행사 209개를 검증했다.
실제 내보내기 파일과 임베딩 캐시는 Git에 넣지 않는다. 이후 배포에서도 최신 export의
장소 ID를 실제 혼잡도 API와 확인해야 한다.

`bench/questions/hanjeok-prod-20261123.yaml`은 현재 ID와 연관 링크에 맞춘 별도 60문항
세트다. 장소와 위키 참조 검증은 통과했지만 모델 평가는 아직 실행하지 않았다.
기존 `hanjeok-v1.yaml`과 그 결과는 이전 데이터의 기록으로 보존한다.
[제공자 점검](../../bench/reports/runtime/production-provider-preflight.json)과
[새 평가 세트 점검](../../bench/reports/runtime/production-question-preflight.json)에
외부 적재/배포/평가의 실행 여부를 구분해 기록했다.

초기 외부 사전 검증에서 장소 12,106곳의 벡터는 모두 준비됐으나 위키는 7/83개
청크까지만 hosted API에 저장됐다. NVIDIA가 `concepts/congestion-diagnosis.md#2`를 콘텐츠 검사로
거절했다(422). 단일 청크와 명시적 `modality=text` 요청도 동일했다. 원문을 누락하거나
검사를 끄는 처리는 하지 않았다. [임베딩 사전 검증](../../bench/reports/runtime/production-embedding-preflight.json)에
입력 범위와 미실행 항목을 기록했으며, 이 상태를 운영 배포 완료로 간주하면 안 된다.

### 위키의 동일 체크포인트 산출물 준비

원문을 유지한 83개 후보는 동일 공식 BF16 체크포인트를 CPU float32로 실행해 만들었다.
API의 온라인 질의는 hosted 모델을 계속 사용한다. 아래 도구는 별도 운영자 환경에서만
실행하며 API 이미지에 torch나 체크포인트를 추가하지 않는다. 임의 모델의 같은 차원
벡터를 허용하는 절차가 아니다.

고정 revision은 `e24ca1e346bcc53572bd7bdc02b3e8ebf66c197c`다. 공식 모델 metadata는
`https://huggingface.co/api/models/nvidia/Nemotron-3.5-Embed-1B-BF16/revision/`
뒤에 해당 revision과 `?blobs=true`를 붙인 HTTPS URL에서 받는다. `hf download`도
동일 revision으로 고정한다. model 디렉터리에는 공식 JSON, Jinja, safetensors와
README만 두며 다운로드 캐시 외의 추가 파일은 거절된다.

```bash
cd bench
# API용 환경과 분리한 Python 3.13 환경에 설치한다.
uv pip install --python /path/to/operator/bin/python -r runtime/requirements.txt \
  -r deploy/offline-wiki-requirements.txt
PYTHONPATH=src:. /path/to/operator/bin/python deploy/prepare_wiki_offline.py build \
  --model /path/to/pinned-model --metadata /path/to/official-model-metadata.json \
  --wiki /path/to/pinned-wiki --export .cache/exports/hanjeok-export-20261123 \
  --hosted-wiki .cache/wiki-nvidia-embeddings.sqlite \
  --hosted-places .cache/guide-nvidia-embeddings.sqlite \
  --candidate .cache/wiki-nvidia-reviewed-candidate.sqlite \
  --anchors .cache/wiki-nvidia-reviewed-anchors.sqlite \
  --manifest reports/runtime/offline-wiki-artifact-manifest.json
```

출력 파일은 새 경로여야 한다. 모델 파일 해시, 깨끗한 위키 full commit, 83개 원문과
토큰 수를 확인하고 25개 hosted 참조와 비교한다. cosine 0.999 이상, 최대 성분 오차
0.005 이하를 모두 통과해야 한다. 모든 벡터와 생성기 해시를 manifest에 기록하며
이 단계의 `accepted_for_load`는 false다. 실제 producer identity를 별도로 보존한다.

독립 검토 기록을 읽고 필요한 수정이 끝난 다음 같은 인자에 `prepare` 동작과 아래
인자를 추가한다. `--export`는 prepare에서 생략할 수 있다.

```text
--target .cache/wiki-nvidia-prepared.sqlite
--review ../docs/superpowers/reviews/2026-11-23-guide-512mb-review.md
--report reports/runtime/offline-wiki-promotion.json
```

기존 hosted 위키 캐시는 보존하고 별도 파일에 7개 hosted 벡터와 76개 로컬 벡터를
준비한다. 적재 직전 `deploy.wiki_artifact.verified_cache`로 manifest, 허용 기록과
최종 캐시 해시를 다시 확인해야 한다. 검증된 캐시만 기존 wiki rebuild의 embedder에
주입한다. 원문/벡터 누락, 식별자 완화와 자동 제공자 폴백은 허용하지 않는다.
이 일회성 대응은 검색 품질을 보장하지 않는다. 정책 질의 사전 검사에서는 hosted
임베딩 10/10 성공, 기대 페이지 상위 3개 포함은 8/10이었다. 실제 DB를 적재한 후
60문항 평가와 공개 SSE 확인이 여전히 필요하다.

2026-11-23 최종 산출물의 독립 검토와 `prepare` 실행이 끝났다.
[원문/벡터 manifest](../../bench/reports/runtime/offline-wiki-artifact-manifest.json)와
[적재 허용 기록](../../bench/reports/runtime/offline-wiki-promotion.json)에 정확한 해시,
hosted 7개 보존과 offline 76개 추가를 기록했다. 원래 hosted 참조 캐시는 그대로
보존했다. 이 기록만으로 Aura 적재나 공개 배포가 완료됐다는 뜻은 아니다.

적재 캐시의 키에도 같은 식별자가 들어가므로 옛 E5 캐시와 섞이지 않는다.
`guide eval`은 선택한 임베딩으로 두 검색 전략을 비교하고 보고서/실행 기록에
식별자를 남긴다. 기존 E5 모델의 60문항 평가를 새 모델의 품질 근거로 재사용하지 않는다.

## 배포 환경

`env.example`에 필요한 변수 이름을 모았다. 빈 비밀번호와 API 키는 운영 시크릿으로
넣는다. Render에서는 `render.yaml`을 Blueprint 경로로 지정한다. Koyeb에서는 같은
Dockerfile/context와 환경 변수를 사용하고 인스턴스 수를 1로 유지한다.

| 변수 | 기본/필수값과 의미 |
| --- | --- |
| `GUIDE_CORS_ALLOWED_ORIGINS` | 필수. `https://agent.hanjeok.com` 등 정확한 오리진 |
| `NVIDIA_API_KEY` | 필수. 기존 답변 생성과 새 임베딩에 사용 |
| `BENCH_ANSWER_MODEL` | `nvidia/nemotron-3-ultra-550b-a55b`; 실행 중 모델 폴백 없음 |
| `GUIDE_STORE` | 무료 프로필은 `sqlite`; 일반 코드 기본값은 `neo4j` |
| `GUIDE_SNAPSHOT_DB`, `GUIDE_SNAPSHOT_MANIFEST` | SQLite 이미지의 `/app/data/snapshot.sqlite`, `/app/data/manifest.json` |
| `BENCH_NEO4J_URI`, `BENCH_NEO4J_USER`, `BENCH_NEO4J_PASSWORD` | Neo4j 모드에서만 필요한 외부 DB 접속값 |
| `GUIDE_EMBEDDING_PROVIDER` | API 이미지 기본값 `nvidia`; 오타 시 시작 실패 |
| `GUIDE_LIVE_MODE`, `HANJEOK_BASE_URL` | 운영값 `live`, `https://api.hanjeok.com` |
| `GUIDE_MAX_CONCURRENT` | 이미지 기본값 `1`, 허용 1~8. 512MiB에서는 1 유지 |
| `GUIDE_MAX_VISITS` | 기본값 `128`, 허용 1~10000. 진행 중인 방문은 만료시키지 않음 |
| `GUIDE_CHECKPOINT_DB` | 이미지 기본값 `/tmp/guide/checkpoints.sqlite` |
| `GUIDE_RESET_CHECKPOINTS` | 이미지 기본값 `1`; 새 프로세스의 방문 레지스트리가 모르는 옛 체크포인트 정리 |
| `PORT` | 이미지 기본값 8000; 플랫폼이 제공한 값 우선 |
| `GUIDE_TRUST_PROXY` | 통제된 프록시가 헤더를 덮어쓰는 배포에서만 `1` |
| `GUIDE_CLIENT_IP_HEADER` | Render 공개 서비스에서 `cf-connecting-ip`; 클라이언트가 제어하는 XFF 첫 값을 사용하지 않음 |

질문 슬롯은 대기열 없이 획득한다. 사용 중인 방문/실행 슬롯은 기존 429 응답의
`scope=visitor`, `retry_after_s=5`로 거절한다. 방문 저장소가 가득 차면
`scope=day`, `retry_after_s=30`이다. 이 두 경우 질문 한도는 차감하지 않는다.
새 방문 ID를 전달하기 전에 거절한 요청은 임시 방문을 제거한다.
SSE 연결을 끊어도 진행 중인 동기 조회가 끝나기 전에는 슬롯을 반환하지 않는다.
모든 질문은 같은 방문 체크포인트에 동시에 쓰지 못한다.

SQLite는 RAM 누적을 줄이는 용도다. 무료 플랫폼의 `/tmp`는 영구 저장소가 아니므로
재시작/절전 시 대화가 초기화될 수 있다. 방문 상태와 일일 한도도 프로세스 메모리이므로
재시작 시 초기화된다. 여러 워커/인스턴스로 확장하지 않는다.
경량 이미지는 시작 시 옛 SQLite 체크포인트도 정리한다. 일반 로컬 saver의 보존
동작은 기본값으로 유지하며 `GUIDE_RESET_CHECKPOINTS=1`일 때만 정리한다.
Render 공개 서비스의 프록시 설정은 플랫폼이 덮어쓰는 `CF-Connecting-IP`만 사용한다.
다른 배포에서는 신뢰할 헤더를 확인하기 전까지 `GUIDE_TRUST_PROXY=0`을 유지한다.
[Render의 헤더 계약](https://render.com/articles/host-pocketbase-on-render).
Neo4j 연결 풀은 4개이며 연결/풀 대기는 각각 최대 5초다.
임베딩 요청은 최대 16문서씩, NVIDIA 공통 pacer 대기를 포함한 요청 타임아웃 예산은
10초다. 네트워크 오류를 자동 재시도하거나 다른 모델로 폴백하지 않는다.
응답 본문은 최대 4MiB, 반환 벡터는 인덱스/차원/유한수/방향을 검사하고 L2 정규화한다.

```bash
docker build -f bench/Dockerfile.api -t hanjeok-guide:api bench
docker run --rm --memory 512m --memory-swap 512m --cpus 1 \
  --env-file /path/outside-repository/guide.env \
  -p 127.0.0.1:8000:8000 hanjeok-guide:api
```

`GET /guide/ready`는 호환되는 두 코퍼스를 읽을 수 있을 때만 200, 그 밖에는 503이다.
플랫폼 health check에 사용한다. `/guide/status`의 데이터 시점과 건수도 확인한다.
이 검사는 NVIDIA와 한적 API까지 호출하지 않으므로 실제 질문 완료를 별도로 확인한다.
새 API URL은 `NEXT_PUBLIC_GUIDE_BASE_URL`에 넣고 프론트를 다시 빌드해야 한다.

## 재현 가능한 로컬 검사

```bash
docker build -f bench/Dockerfile.api -t hanjeok-guide:512mb-check bench
python3 bench/deploy/verify-api-memory.py \
  --output bench/reports/runtime/512mb-fixture-arm64.json
```

검사는 고유 이름의 내부 Docker 네트워크, 별도 Neo4j와 512MiB API 컨테이너를 만들고
끝나면 자기 자원만 제거한다. 실제 제공자 대신 HTTP MockTransport를 사용한다.
가상 장소 41곳의 벡터와 연관 링크, 총 13,403개 이름으로 부하를 구성한다.
50회 연속 질문, 실제 벡터 검색/그래프 조회, 검증된 SSE, 잘못된 인용 거절,
같은 방문의 동시 요청 거절과 방문 수 상한을 검사한다.
조회 단계 이름뿐 아니라 성공 상태와 예상 레코드 ID도 확인한다.
커널 peak가 없으면 20ms 간격 cgroup 메모리 표본의 최댓값을 기록한다.
메모리 상한/스왑을 512MiB로 제한하고 OOM 없이 모든 시나리오를 통과해야 성공한다.
테스트 모듈과 가상 데이터는 운영 이미지에 복사하지 않는다.

실제 AuraDB의 1GB 디스크/벡터 인덱스 호환성, NVIDIA 계정의 현재 한도와 실제 데이터
검색 품질은 이 검사로 검증되지 않는다. NVIDIA는 무료 API를 프로토타이핑용으로
안내하며 장기 무료 운영을 보장하지 않는다. [NVIDIA 안내](https://docs.api.nvidia.com/nim/docs/run-anywhere)
Render/Koyeb의 무료 절전과 요청 자원 제한도 적용된다.
[Render](https://render.com/docs/free), [Koyeb](https://www.koyeb.com/docs/reference/instances),
[AuraDB](https://neo4j.com/docs/aura/quotas-and-limits/).

2026-11-23 Super를 사용한 순위/등급 검사 코드의 amd64 이미지(ARM64 호스트 에뮬레이션)는
50회 fixture 반복을 통과했고, 512MiB 제한에서 관측한 최대 메모리는 331.6MiB였다.
[최종 fixture JSON](../../bench/reports/runtime/512mb-fixture-amd64-final-guard.json)과
[검토/검증 기록](../../docs/superpowers/reviews/2026-11-23-guide-512mb-review.md)을 참고한다.
종료된 답변 모델 교체와 실제 SSE 확인은 [호환성 검토](../../docs/superpowers/reviews/2026-11-23-guide-answer-compat-review.md)에 있다.
실제 제공자 지연이나 Render/Koyeb 네이티브 호스트의 성능 수치가 아니다.

실제 장소 12,106개/위키 83청크와 NVIDIA·한적 API를 사용한 최종 컨테이너도
512MiB/no-swap에서 예보, 정책, 대안 질문 세 건을 완료했다. 20ms 표본 최대는
272.2MiB, OOM은 0이었다. [실데이터 메모리 JSON](../../bench/reports/runtime/512mb-realdata-final-guard-amd64.json).
DB는 별도의 로컬 Neo4j이며, 세 질문은 장시간 부하 검사를 대신하지 않는다.

Super로 현행 60문항을 두 전략에서 실행한 [평가 감사](../../bench/reports/runtime/currentdata-evaluation-audit.json)에는
거절/실패와 오탐을 함께 기록했다. 판정 모델 지표는 미실행이고, 정책 두 문항의 범위
거절 및 제공자 오류가 남아 있다. 이전 E5 점수나 수정 전 실행을 새 모델 점수로 재사용하지 않는다.
Aura 접속 파일 미확보로 실제 Aura 적재, Render 생성과 프론트 URL 공개는 아직 미실행이다.

후속 요청으로 기본 모델을 Ultra로 바꿨다. 기존 무료 체험 NVIDIA 키를 사용하며
임베딩 모델과 캐시 식별자는 유지한다. [Ultra 실제 설정 검증](../../bench/reports/runtime/512mb-ultra-amd64.json)은
예보/정책/대안 세 질문이 모두 인용을 포함해 완료되고, 512MiB/no-swap에서 약
272.1MiB를 관측했다. 명시적 모델 환경 변수로 검증한 설정이다.
위 Super 점수를 Ultra의 품질 점수로 사용하면 안 된다.
최종 Ultra 기본값 이미지도 모델 환경 변수를 지정하지 않은 실제 정책 SSE를 완료했다.
[기본값 경로 검증](../../bench/reports/runtime/512mb-ultra-default-amd64.json)의 512MiB/no-swap
관측 최대는 268.1MiB이며 OOM은 없었다. 이전 단계와 같이 AMD64 에뮬레이션/로컬 외부 DB 검증이다.

2026-11-24 Ultra의 [현행 60문항 평가 감사](../../bench/reports/runtime/ultra-currentdata-evaluation-audit.json)를 완료했다.
벡터는 답변 42/거절 12/실패 6회, 그래프는 답변 45/거절 12/실패 3회였다.
거절 중 20회는 지원 범위 밖 질문의 예상 결과이고, 4회는 기존 정책 질문 범위 판정 누락이다.
실패 중 8회는 검증 후 답변을 내보내지 않았고, 1회는 출력 예산 초과였다.
q37/벡터는 데이터 출처 질문에 장소 소개를 검색해 잘못 답했다. 장소명은 조회한 소개문에
있지만 해당 장소 레코드를 직접 조회하지 않아 자동 INVENTED_PLACE 경고가 남는다.
이전 Super의 공백 오탐과는 다른 사례이며 원시 경고를 보존했다. 답변 본문의 내부 인용 ID 노출도 남아 있다.
판정 모델은 실행하지 않았고, 로컬 외부 Neo4j와 11월 23일 export/실제 NVIDIA·한적 API를
사용했다. 이 결과는 모든 답변의 정확성이나 Aura/Render 공개 배포 완료를 뜻하지 않는다.
