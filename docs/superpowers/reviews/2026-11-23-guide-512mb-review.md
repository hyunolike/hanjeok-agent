# 512MiB 안내 API 검토와 검증

## 설계 검토

검토자 `/root/spec_review`는 대화 이력이 없는 문맥에서 EGM design critic persona와
implementation readiness standard, 설계/계획, 관련 코드와 constitution을 읽었다.
기준 커밋 9308e57. 실제 반환된 주요 지적 5개와 반영 내용:

1. 임베딩 wire contract 미정: 모델/URL/변수/인증/전처리/타임아웃/배치를 설계에 확정.
2. 코퍼스/캐시 식별자 저장 규칙 부재: `Corpus.embedding_model`과 model_id 기반 캐시,
   API/평가의 정확 일치 검사로 통일. local legacy와 외부 모드를 구분.
3. 연결 해제 시 동기 실행이 남는 문제: 취소 시 thread 작업을 기다리고 iterator를
   닫은 뒤에만 admission을 반환. 실제 ASGI disconnect와 blocked thread 테스트 추가.
4. 수용량/실패 응답 미정: 동시 실행 1, 방문 128의 이미지 기본값과 허용 범위,
   429 응답/질문 한도 차감/활성 방문 만료 제외를 명시.
5. 메모리 검증 재현성 부족: 전용 fixture/검증 스크립트, 13,403개 이름과 50회 반복,
   512MiB/스왑 제한 및 JSON 산출물 경로를 명시.

추가 사용자 결정이 필요하지 않은 구현 세부사항이라는 검토자의 판단에 따라 반영했다.
본 문서는 EGM 전체 다중 라운드 수렴 완료를 주장하지 않는다.

## 검증 진행

- 경량 의존성 환경에서 평가 judge 테스트를 제외한 오프라인 검사를 실행한다.
  judge 패키지는 운영 경량 잠금 파일에 의도적으로 없다. 기존 bench/uv.lock은 보존했다.
- Docker 기본 이미지 조회가 macOS 자격증명 도우미에서 멈춰 공개 이미지 전용 임시
  익명 설정을 사용했다. API 이미지는 추가 uv 빌드 도구 없이 pip 해시 설치를 사용한다.
- 기본 Docker 네트워크 대역이 소진돼 기존 네트워크를 보존하고 중복되지 않는
  사설 /24 대역을 선택해 내부 검증 네트워크를 생성하도록 스크립트를 수정했다.
- 실행 결과와 최종 독립 코드 검토는 완료 후 아래에 기록한다.

## 독립 코드 검토와 수정

검토자 `/root/code_review`는 새 문맥에서 기준 커밋 대비 tracked/untracked 변경,
명세와 테스트를 확인했다. 중요 지적은 아래 재현 테스트로 수정했다. 저자 자체 검토를
Goldfish 검토로 대체하지 않았고, 수정 후 별도 LGTM을 받았다고 주장하지 않는다.

| 지적 | 조치와 검증 |
| --- | --- |
| ASGI 2.4 직접 태스크 취소 시 작업보다 먼저 슬롯 반환 | 동기 작업을 독립 태스크로 shield하고 실제 완료를 기다림. raw cancellation과 readiness 취소 테스트 RED→GREEN |
| 거절된 새 방문이 저장소 점유 | 임시 방문과 전달된 방문을 구분해 조기 거절 시 제거. 503 반복 검사 RED→GREEN |
| 기존 bench 검색에서 다른 모델 벡터 혼용 | bench ask와 평가 preflight에서도 식별자 검사. 다른 모델로 ask/context 거절 RED→GREEN |
| Render의 XFF 첫 값 조작 가능 | 플랫폼이 덮어쓰는 CF-Connecting-IP만 선택하고 IP 검증. uvicorn 프록시 재해석 비활성화. spoofed XFF 테스트 RED→GREEN |
| 최초 임베딩 모델 deprecated | 공식 현재 계약의 nemotron-3.5-embed-1b로 변경. 모델/캐시 식별자 구분. 모델 계약 테스트 RED→GREEN |
| SQLite 고아 체크포인트 누적 | 경량 이미지의 전용 파일은 시작 시 정리. 일반 saver 기본 보존 유지. 보존/정리 테스트 RED→GREEN |
| 지속 스트리밍 응답의 임베딩 예산 초과 | 분할 응답과 성공 직전에 경과 시간 검사. 가짜 시계/느린 응답 테스트 RED→GREEN |
| 판정 임베딩 메타데이터 E5 고정 | 실제 adapter 설정을 기록하고 검색/판정 임베딩을 별도로 저장. 메타데이터 검사 RED→GREEN |
| MCP VisitCapacity가 도구 예외로 노출 | 기존 usage_limit 구조로 반환. MCP 호출 테스트 RED→GREEN |
| 메모리 fixture가 단계 이름만 검사 | status=ok와 예상 장소/연관 레코드 ID까지 검증 |

최종 컨테이너의 연속 HTTP 요청 검사에서 EOF와 슬롯 반환 사이의 짧은 경합을
발견했다. generator가 끝나면 EOF 전송 전에 슬롯을 반환하도록 정리 순서를 바꿨다.
EOF 전송을 막는 재현 테스트 RED→GREEN과 기존 취소/예외 테스트를 함께 실행했다.

## 실행 환경과 범위

- 기존 bench/uv.lock의 평가 의존성도 별도 테스트 환경에 설치해 전체 오프라인
  suite를 실행한다. 경량 이미지 잠금 의존성에는 평가 패키지를 넣지 않는다.
- amd64 이미지는 ARM64 Docker 호스트에서 에뮬레이션으로 실행한다. 실제 Render나
  Koyeb 네이티브 호스트의 성능 수치로 표현하지 않는다.
- 최초 ARM64 메모리 결과는 독립 코드 검토 이전 이미지다. 최종 코드 검증은
  amd64 산출물을 기준으로 한다.
- 공개 배포, 실제 NVIDIA 호출, 운영 AuraDB 적재와 실데이터 60문항 평가는 미실행이다.

## 최종 결과

- 전체 기본 오프라인 테스트: 478 passed, 43 integration/costly deselected.
- Ruff 전체 검사와 git diff --check 통과.
- 최종 amd64 이미지의 512MiB/스왑 없음 검사: 50회 반복, 성공 상태와 예상 레코드 ID,
  인용 거절, 동시 요청과 방문 상한 모두 통과. 관측 최대 349,020,160bytes(332.9MiB),
  20ms 간격 표본이다. 이 커널은 memory.peak를 제공하지 않아 커널 peak로 표현하지 않는다.
- [최종 산출물](../../../bench/reports/runtime/512mb-fixture-amd64.json).
  ARM64 최초 산출물은 512mb-fixture-arm64-pre-review.json으로 구분해 보존했다.
- 검증 네트워크와 컨테이너는 검사 스크립트가 제거했다. 기존 사용자 자원은 제거하지 않았다.

## 실제 위키 적재 산출물 독립 검토

검토자 `/root/offline_embedding_review`가 새 문맥에서 공식 체크포인트, hosted API 명세,
실험 생성기와 캐시를 읽었다. hosted Preview가 BF16을 사용한다는 공식 설명과 25개
참조의 수치 비교는 일회성 동일 공간 대응의 근거가 되지만, 초기 산출물은 아직 적재
승인 근거로 부족하다고 판단했다. 기존 코드 검토나 EGM 전체 수렴 완료를 뜻하지 않는다.

| 지적 | 반영한 검증 |
| --- | --- |
| report와 실제 모델/생성기/원문/후보를 묶는 해시 부재 | 공식 고정 revision의 metadata를 HTTPS로 다시 받고 모델 파일 전체를 대조. full wiki commit, 원문, 토큰 수, 생성기와 모든 벡터 해시 manifest 추가 |
| 기존 후보 재사용과 zip 비교가 잘못된 벡터를 놓칠 가능성 | 별도 후보 83개를 모두 다시 생성. 정확한 차원, 유한성, 단위 노름과 동일 길이 비교. 25개 참조의 로컬 벡터도 별도 캐시에 저장해 적재 전 재검증 |
| 동일 폭을 이유로 canonical identity를 붙일 위험 | 동일 공식 체크포인트와 고정 전처리만 한 번 대응. 실제 CPU float32 producer identity와 revision 보존. hosted query와 엄격한 준비 상태 검사 유지 |
| 부분 실패가 원본 캐시를 덮어쓸 위험 | hosted 참조 캐시는 읽기 전용 보존. 새 임시 DB의 단일 트랜잭션에 7개 보존/76개 추가 후 전체 집합과 해시 검사. 별도 적재용 파일로 교체 |
| 임시 생성기의 재현성 부족 | `bench/deploy/prepare_wiki_offline.py`, `wiki_artifact.py`와 별도 operator 의존성 파일 추가. API 이미지에는 포함되지 않음 |

초기 CPU BF16 실험은 고정 성분 오차 기준을 넘어서 거절했다. 기준을 완화하지 않고
CPU float32로 바꾼 비교가 통과했다. 실패 기록도 보존한다. 이번 컴포넌트 검증에서
hosted 정책 질의 10/10은 1024차원으로 성공했고, exact cosine 상위 3페이지에 기대
문서가 있는 경우는 8/10이었다. q32와 q36은 빠졌다. 이 검사는 Neo4j 검색이나 전체
에이전트의 60문항 평가가 아니다. `policy-query-preflight.json`에 구분했다.

후보의 최종 해시 manifest와 후속 독립 검토를 확인한 뒤 적재 허용 기록을 만든다.
실제 DB 적재와 공개 SSE 검증 전에는 운영 준비 완료로 표현하지 않는다.

### 최종 산출물 재검토

동일 검토자의 두 번째이자 마지막 후속 검토에서 실제 최종 manifest와 모든 캐시를
읽고 다음 항목을 독립 재계산했다. 추가 차단 사항은 발견하지 않았다.

- Manifest SHA256: `b09fecfd5a3d80953d01aed052319ad61544f6086ecdeb0386674e45e3a66b56`.
- 공식 metadata와 모델 파일 12개, 생성기 두 파일의 해시 일치.
- 깨끗한 위키 full commit, 정확한 83청크의 원문/키 집합과 현행 export 해시 일치.
- 후보 83개, 저장된 비교 벡터 25개와 hosted 참조의 모든 해시/지표 일치.
- 모델 추론 없이 tokenizer 수를 재계산해 manifest와 일치 확인. 위키 입력 18~428토큰,
  참조 입력 최대 436토큰으로 END 자르기가 필요하지 않음.
- 최소 cosine `0.9999990901477778`, 최대 성분 오차 `0.000529702752828598`.
  기존 고정 기준을 모두 만족. 별도 적재용 캐시의 one-time canonical 대응을 허용하는 근거다.
- 생성 중 생성기 변경 검사를 시작/종료 해시 비교로 보완. 실제 최종 실행은 코드 확정 뒤
  새 출력 파일로 전량 재생성했다. 초기 임시 실행은 적재용으로 채택하지 않았다.
- 실제 운영자 로더가 `verified_cache()`를 호출하고 반환된 검증 바이트만 소비함을 확인.
- 검토자가 guard 테스트 10개를 직접 실행해 통과를 확인. 작성자의 최종 기본 suite는
  488 passed, 43 integration/costly deselected이며 Ruff와 diff 검사도 통과했다.

이 검토는 적재 전 증거 요건을 충족한다는 판단이다. 이후 `prepare` 트랜잭션과 허용
보고서를 실행해야 하며, 실제 Neo4j 적재/평가/배포 완료를 뜻하지 않는다. 이 검토 파일은
허용 보고서에 기록할 해시를 보존하기 위해 준비 후 변경하지 않는다.
