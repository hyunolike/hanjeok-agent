# 실제 답변 모델 호환성 수정 검토

## 재현과 수정

- 현행 데이터 60문항을 두 전략으로 실행하자 종료된 기본 모델에서 96회
  `provider_error`, 범위/입력 분기에서 24회 declined였다. 단일 기본 채팅 요청으로
  HTTP 410과 제공자 종료일 2026-10-03을 확인했다. 이 결과를 품질 점수로 채택하지 않았다.
- NVIDIA의 실제 `/v1/models`와 공식 API 명세에서 확인한
  `nvidia/nemotron-3.5-super-vl-120b-a12b`로 기본값을 변경했다. 같은 키/제공자,
  비활성 thinking과 strict JSON schema 요청이 실제 HTTP 200/stop/정상 JSON이었다.
  기존 `BENCH_ANSWER_MODEL` 선택과 응답 예산은 유지하고 자동 폴백은 추가하지 않았다.
- 새 모델의 수정 전 진단 실행에서 대괄호를 포함한 `[hanjeok:…]` 인용을 반복했다.
  같은 실패 프롬프트로 이 동작을 재현했다. 기존 인용 검사는 이를 올바르게 거절했다.
- 각 모델 호출에 이번 질문에서 조회한 원본 ID만 schema enum으로 전달한다.
  조회 전에는 citations의 maxItems=0이다. 원문 표시와 응답 뒤의 검증/수정 1회는 유지한다.
  같은 실패 프롬프트의 실제 재실행에서 정확한 bare ID가 반환됐다.

## 독립 검토

새 문맥의 `/root/citation_compat_review`가 HEAD `b69006e` 이후 변경만 읽고 검토했다.
중요/치명 지적은 없었다. 저자의 자체 검토를 독립 검토로 기록하지 않았으며 EGM 전체
수렴 완료를 뜻하지 않는다.

- schema 선택지가 현재 질문의 Fetched.passages와 동일함을 확인했다.
- 같은 Agent/thread의 다음 정책 질문에서 증거가 초기화되고 maxItems=0이 되는지 확인했다.
- LangChain의 strict 변환이 빈 배열 제약과 enum을 보존함을 확인했다.
- 기존 인용 gate와 수정 1회가 그대로이고, schema 크기가 이미 조회한 문서 수에만
  비례하며 로컬 모델을 불러오지 않음을 확인했다.
- 검토자가 focused suite 59개를 직접 실행해 통과했다. 작성자의 전체 기본 suite는
  491 passed, 43 integration/costly deselected였다.

## 실제 검증과 한계

로컬 실제 Neo4j/현행 export와 hosted NVIDIA, live 한적 API를 사용한 ASGI HTTP/SSE
질문 두 건이 모두 200/answered였다. 경복궁 예보는 원본 record ID, 혼잡 기준 질문은
원본 wiki ID를 인용했고 answer/path/done 이벤트가 나왔다. `/guide/ready`도 200이었다.
근거는 `bench/reports/runtime/local-real-sse-preflight.json`이다.

최종 코드의 amd64 이미지(ARM 호스트 에뮬레이션)도 512MiB/no-swap 제한에서
50회 fixture 검증을 통과했다. 표본 최대 메모리는 348,659,712bytes(332.5MiB)였다.
`bench/reports/runtime/512mb-fixture-amd64-final-model.json`에 이미지 해시와 한계를
기록했다. 이는 실제 제공자/운영 코퍼스의 컨테이너 메모리 측정과 구분한다.

실제 모델 품질 전체와 Aura/Render 공개 배포는 이 검토의 통과 범위가 아니다.
수정 전 진단 실행과 수정 후 전체 평가는 별도 실행 ID로 보존한다. 모델 판정 지표는
실행하지 않으며, 관측하지 않은 품질이나 인프라 준비 상태를 통과로 기록하지 않는다.

공식 API: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer
