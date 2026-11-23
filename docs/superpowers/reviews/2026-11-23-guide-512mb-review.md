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
