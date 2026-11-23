# 512MiB 안내 API

Python HTTP API만 실행하는 배포 구성이다. Neo4j와 임베딩 모델을 이미지 밖으로
분리했다. 기존 Kotlin API의 배포는 포함하지 않는다. 운영 배포를 실행한 기록은 아니다.

## 구성과 유지되는 동작

- `bench/Dockerfile.api`: Python 3.13, 비루트 사용자, uvicorn 워커 1개.
- `bench/runtime/requirements.txt`: 해시 잠금. torch, sentence-transformers, ragas 제외.
- Neo4j는 `BENCH_NEO4J_URI`로 연결한다. AuraDB는 `neo4j+s://…`를 사용한다.
- `GUIDE_EMBEDDING_PROVIDER=nvidia`: NVIDIA의
  `nvidia/nemotron-3.5-embed-1b`를 1024차원으로 호출한다.
  최초 후보인 llama-3.2 엔드포인트는 공식 카탈로그의 deprecated 공지를 확인해 제외했다.
  [현재 모델 API](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-embed-1b-infer)
- 기존 LangGraph 루프, 고정 조회 7개, 서비스 순위, 인용 검사, 수정 1회와 SSE 계약을 유지한다.
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
| `BENCH_NEO4J_URI`, `BENCH_NEO4J_USER`, `BENCH_NEO4J_PASSWORD` | 외부 DB 접속값 |
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

2026-11-23 로컬 검증은 amd64 이미지(ARM64 호스트 에뮬레이션)에서 50회 반복을
통과했고, 512MiB 제한에서 20ms 간격으로 관측한 최대 메모리는 332.9MiB였다.
[결과 JSON](../../bench/reports/runtime/512mb-fixture-amd64.json)과
[검토/검증 기록](../../docs/superpowers/reviews/2026-11-23-guide-512mb-review.md)을 참고한다.
실제 제공자 지연이나 Render/Koyeb 네이티브 호스트의 성능 수치가 아니다.
