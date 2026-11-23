# 512MB 안내 API

상태: 2026-11-23 사용자가 외부 Neo4j와 임베딩 API를 사용하는 방향으로 구현 진행을 승인했다.
기준 커밋: 9308e57. 기존 작업 트리는 깨끗했다.

## 목적과 범위

Render/Koyeb의 512MB 컨테이너에서 안내 HTTP API만 실행한다. Neo4j 서버,
PyTorch 모델, 데이터 적재와 평가는 컨테이너 밖에서 실행한다. 프론트 SSE 계약,
고정 조회, 서비스 순위 보존, 인용 검증과 재작성 1회는 유지한다.
외부 계정 생성, 운영 데이터 적재, 실제 모델 호출과 공개 배포는 이번 로컬 구현의
검증과 구분한다. 무료 API의 상시 운영 가능성은 보장하지 않는다.

## 선택한 구조와 대안

- 선택: API는 Python 단일 워커, Neo4j AuraDB, NVIDIA 다국어 임베딩 HTTP API.
  기존 Places/Policy와 embed_query 경계를 재사용한다. 기존 로컬 모델 경로도 유지한다.
- 기존 모델을 별도 서버로 옮기면 벡터를 보존할 수 있지만 큰 무료 서버가 다시 필요하다.
- 작은 모델이나 키워드 검색으로 교체하면 검색 동작이 달라져 이번 목표에서 제외한다.

## 요구사항과 수용 기준

- R1: NVIDIA 임베딩 어댑터는 문서/질의를 구분하며 1024차원 유한 벡터를 검증한다.
  선택한 모델은 nvidia/nemotron-3.5-embed-1b다. 오류 응답, 잘못된 응답,
  타임아웃은 외부 메시지나 키를 노출하지 않고 실패한다. 로컬 모델로 폴백하지 않는다.
- R2: 장소와 위키에 임베딩 식별자(모델, 차원, 전처리 버전)를 기록한다.
  외부 모드에서 두 코퍼스의 식별자가 현재 모델과 다르거나 없으면 준비되지 않음으로
  처리한다. 기존 e5 벡터와 새 모델을 혼용하지 않는다. 운영용 적재는 CLI에서 수행한다.
- R3: HTTP 전용 잠금 의존성에는 torch, sentence-transformers, ragas가 없다.
  Python만 포함한 비루트 컨테이너를 제공한다. 기존 bench 의존성은 유지한다.
- R4: API에는 질문 동시 실행 제한과 방문 수 상한을 둔다. 수용 불가 요청은
  기존 429 usage_limit 계약으로 응답한다. 질문 슬롯은 예외/연결 해제에도 반환한다.
  체크포인트는 SQLite에 보관하고 종료 시 자원을 닫는다. 무료 컨테이너의 로컬 디스크는
  영속성을 보장하지 않으며 재시작 시 방문 상태와 일일 한도가 초기화된다.
- R5: 오프라인 단위/계약 테스트에서 기존 SSE 순서와 인용 거절을 유지한다.
  Linux 컨테이너에 512MiB 메모리 제한을 적용하고 가짜 외부 서비스로 시작,
  벡터/그래프 조회, 답변, 반복 대화, 사용량 제한을 검증한다. 측정값은 fixture 결과이며
  실데이터/실제 NVIDIA 서비스 결과로 표현하지 않는다.

## 데이터 적재와 실패 처리

새 모델을 사용한 데이터는 별도 DB에 준비하고 API URL을 전환한다. 장소 갱신은 기존
generation 전환을 유지한다. 위키 rebuild는 기존 CLI와 같이 중단될 수 있으므로 운영
DB에서 모델을 바꾸는 인플레이스 이전을 안내하지 않는다. 단일 DB 쓰기 작업은 운영자가
직렬 실행한다. 외부 모드의 평가도 같은 임베딩과 식별자를 사용하며 기존 평가 수치는
새 모델의 품질 근거로 재사용하지 않는다.

## 확정한 구현 계약

- `GUIDE_EMBEDDING_PROVIDER` 기본값은 local, 경량 이미지에서는 nvidia다.
  NVIDIA 모델은 `nvidia/nemotron-3.5-embed-1b`로 고정한다. 이전 llama-3.2 후보는
  공식 deprecated 공지를 확인해 제외했다. URL은
  `https://integrate.api.nvidia.com/v1/embeddings`, 인증은 `NVIDIA_API_KEY` Bearer다.
  `input_type=query|passage`, `dimensions=1024`, `truncate=END`, float 출력 후
  L2 정규화한다. 배치 16개, HTTP 타임아웃 10초, 자동 재시도 없음, 본문 최대 4MiB다.
  오류는 configuration/unavailable/invalid_response만 노출한다.
- 식별자는 `nvidia/nemotron-3.5-embed-1b@1024:input-type-v1:truncate-END:l2`이며
  `Corpus.embedding_model`과 장소 EmbeddingCache 키에 동일 문자열을 저장한다.
  두 코퍼스에 대해 정확히 비교한다. local에서만 미기록 legacy 데이터를 허용한다.
- `GUIDE_MAX_CONCURRENT`: 코드 기본 2, 이미지 기본 1, 허용 1~8.
  `GUIDE_MAX_VISITS`: 기본 128, 허용 1~10000. SQLite 경로는
  `GUIDE_CHECKPOINT_DB=/tmp/guide/checkpoints.sqlite`다. 사용 중인 방문은 pin하며
  실행 종료 후 unpin 시점부터 만료 시간을 센다. API 거절은 실행/동일 방문의 경우
  기존 429 visitor/5초, 방문 저장소 상한은 day/30초이며 질문 한도는 차감하지 않는다.
- ID를 전달하지 못한 새 방문은 거절 시 되돌린다. 경량 이미지에서는
  `GUIDE_RESET_CHECKPOINTS=1`로 이전 프로세스의 접근 불가능한 SQLite 상태를 정리한다.
- Render 공개 서비스는 `GUIDE_CLIENT_IP_HEADER=cf-connecting-ip`로 플랫폼이
  덮어쓰는 헤더만 신뢰한다. 일반 배포에서는 헤더 계약을 확인하기 전까지 trust proxy를 끈다.
- 동기 generator의 next는 취소 시에도 실행 종료를 기다린다. ASGI 응답 종료 정리에서
  iterator를 닫은 뒤에만 슬롯을 반환한다. blocked next와 실제 ASGI disconnect를
  조합한 테스트로 이 순서를 검증한다.
- `GET /guide/ready`를 health check로 추가한다. 호환 데이터가 없으면 503이며 기존
  `/guide/status` 계약은 유지한다. 제공자 가용성을 확인하는 endpoint는 아니다.
- `bench/deploy/verify-api-memory.py`는 Docker 내부 네트워크의 실제 Neo4j와
  `bench/deploy/memory_fixture.py`의 가짜 HTTP 제공자를 사용한다. 임베딩된 가상
  장소 41곳과 총 13,403개 이름, 연속 질문 50회, 인용 거절과 동시 요청/방문 상한을
  검증한다. 512MiB RAM/스왑 상한, OOM 없음과 모든 시나리오 성공을 통과 기준으로 한다.
  산출물은 `bench/reports/runtime/512mb-fixture-<architecture>.json`이다.

## 참고

- https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-embed-1b-infer
- https://build.nvidia.com/nvidia/llama-3_2-nv-embedqa-1b-v2 (최초 후보의 deprecated 공지)
- https://neo4j.com/docs/aura/quotas-and-limits/
- https://render.com/docs/free
- 기존 명세: specs/002-hanjeok-guide-agent/spec.md와 contracts/guide-api.md

## 남은 외부 검증

실제 AuraDB의 1GB 저장공간/인덱스 호환성, NVIDIA 계정 한도, 실데이터 60문항 재평가는
외부 리소스가 준비된 뒤 검증한다. 이 항목의 미실행을 테스트 통과로 기록하지 않는다.
