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

## 실제 평가에서 발견한 순위/등급 검사 누락

첫 완료 실행 `guide-20261123-072954`에서 평가기가 대안 순서 변경 5건과 영문 등급
표기 1건을 발견했다. 실제 조회 목록과 답을 대조해 모두 확인했다. 응답 전에는 같은
검사 중 혼잡 근거와 순서 이유만 사용하던 누락을 수정했다. 기존 평가기의 두 신호를
기존 단일 수정/차단 경로에 연결했고, 답변을 재정렬하거나 검사를 완화하지 않았다.

독립 검토자는 서로 다른 위반이 연속되는 세 조합에서도 수정 1회를 공유하고 답변을
내보내지 않음을 확인했다. 기존 순서 위반 fixture 두 개의 수정 후 focused suite
76개가 통과했다. 전체 기본 suite는 495 passed, 43 deselected다.

완료한 postguard 실행 `guide-20261123-075018`의 raw 결과는 보존한다. 벡터는
45 answered/12 declined/3 failed, 그래프는 47 answered/12 declined/1 failed였다.
반복 위반 3건은 답변을 내보내지 않았고, 벡터 q33은 제공자 가용성 오류였다.
정책 q39/q40의 기존 범위 판정 거절도 남아 있다. 판정 모델 지표는 미실행이다.
INVENTED_PLACE 1건은 `홈페이지나 인스타그램`의 공백을 없애 `페이지나인`이라는
장소명과 잘못 일치시킨 오탐으로 확인했다. 자동 집계값을 고쳐 쓰지 않고 별도 감사
기록에 설명했다. 평가기에는 이런 문자열 경계 오탐이 있을 수 있다.

최종 guard 이미지의 실제 전체 데이터/제공자 3질문 검사도 512MiB/no-swap에서
모두 answered였고, 관측 최대는 285,437,952bytes(272.2MiB), OOM은 0이었다.
별도 50질문 fixture 최대는 331.6MiB였다. 실제 DB는 로컬 외부 Community이고
AMD64 에뮬레이션 환경이다. Aura/Render의 공개 배포 검증은 아직 실행하지 않았다.

## 사용자 요청에 따른 무료 Ultra 전환

후속 요청으로 기본 답변 모델을 `nvidia/nemotron-3-ultra-550b-a55b`로 변경했다.
현행 API 목록과 strict JSON 200/stop/정상 JSON을 확인했다. Qwen은 종료 응답,
Gemma와 Mistral은 30초 read timeout, Lightning은 실제 세 질문 중 두 건이 기존
검사를 통과하지 못해 제외했다. 이 관측을 후보 전체의 영구적인 품질 판단으로 일반화하지 않는다.

새 문맥의 `/root/lightning_switch_review`가 최종 Ultra 선택을 재검토했다. 기본값,
Render/env, 명시적 answer/judge override가 일관되고 임베딩 식별자, 캐시, 검증
gate가 그대로임을 확인했다. focused adapter/judge 테스트 11개를 직접 실행해 통과했다.
작성자의 최종 기본 suite는 495 passed, 43 deselected였고 Ruff와 diff 검사도 통과했다.

실제 환경 변수 Ultra 설정은 예보/정책/대안 세 질문을 모두 인용과 함께 완료했다.
최종 기본값 이미지에서는 BENCH_ANSWER_MODEL을 지정하지 않고 정책 질문을 추가
검증해 Ultra 선택과 answered를 확인했다. 두 실행 모두 512MiB/no-swap/OOM0이었다.
명시 설정 세 질문은 약272.1MiB, 기본값 한 질문은268.1MiB 표본 최대다.
각 JSON에 정확한 이미지 해시와 환경 한계를 기록했다. 무료 접근은 기존 NVIDIA
프로토타이핑 API 범위이며 계정/결제 추가나 자동 모델 폴백은 없다.

이 smoke 자체는 Ultra의 전체60문항 품질 평가나 공개 배포를 뜻하지 않는다.
Super의 기존 점수와 데이터는 해당 모델의 역사적 결과로 보존한다.

## 2026-11-24 Ultra 전체 평가 후속 기록

소스 `103b4b4`를 변경하지 않고 `guide-ultra-20261124-215604`에서 현행 60문항을
두 전략으로 실행했다. 벡터 42 answered/12 declined/6 failed, 그래프
45 answered/12 declined/3 failed였다. 검색 ID recall은 각각 0.4880/0.6500이고,
판정 모델 지표는 실행하지 않았다. live 응답 시점이 다른 Super 평가와의 차이를
모델 변경만의 인과 효과로 해석하지 않는다.

실패 8회는 기존 단일 수정 후 검증을 통과하지 못해 답변을 내보내지 않았으며,
UNCITED_CLAIM 8건은 이 보류 결과의 평가 표기다. 나머지 실패 1회는 q31/벡터의
output_limit이다. 기존 예산이나 검사를 이번 평가 중 바꾸지 않았다.
지원 범위 밖 질문 20회는 예상대로 거절했고, q39/q40의 기존 정책 범위 누락 4회도 남았다.
기록된 제공자 rate-limit 대기는 11회, 수정이 있었던 실행은 15회다.

답변이 표시된 자동 경고는 q37/벡터의 INVENTED_PLACE 1건이다. 연관 관광지의 데이터
출처를 묻는 질문에서 필요한 `wiki:entities/related-attraction-api.md`를 조회하지 않고
장소 소개 5건을 검색해 답했다. 직접 조회하지 않은 묵호항, 까막바위, 백제문화단지,
낙화암, 국립낙동강생물자원관은 실제 조회한 소개문에 명시되어 있다. 따라서 새 장소를
지어냈다는 증거로 단정하지 않지만, 직접 장소 레코드가 없다는 원시 경고는 보존한다.
정책 의도와 다른 검색/답변, 답변 문장의 내부 인용 ID 노출은 확인된 한계다.
과거 Super q16의 공백 경계 오탐을 이 사례의 판정으로 재사용하지 않는다.

원시 120행, 별도 live 기록, 보고서와 수동 감사 기록을 보존했다. 데이터는 11월 23일
export와 고정 위키이며, DB는 로컬 외부 Community 5.26이다. 공개 보고서 포인터는
바꾸지 않았고 Aura 적재/Render 배포/프론트 공개도 미실행이다. 이 기록은 새 코드의
독립 검토나 품질 문제 해결을 주장하지 않는다.
