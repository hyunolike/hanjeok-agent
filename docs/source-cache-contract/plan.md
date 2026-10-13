# 설명 캐시와 출처 버전 계약

작성: 2026-10-09. 범위: 두 저장소의 로컬 설계, 구현, 검증.

기준: wiki `59f2240609cc6c690106093006e6c2a653d2b724`, agent
`f7a917f0527cd18242fe7aa65b066f85a6b1d88f`, 참고 데모
`e0165f5ced30bfbdc12e586c517fd2e260a3c753`. 원격 main 재확인 결과 동일.

## 계약

1. 설명 캐시와 single-flight 키는 `(courseUuid, SHA-256(facts의 실제 UTF-8 바이트))`다.
   facts는 매 요청 다시 읽는다. 설명, 생성 시각, facts hash를 함께 저장하고 기본 TTL은
   생성 완료 시점부터 5분이다. LRU 상한 1000을 유지한다. 실패는 저장하지 않는다.
   모델과 번들은 프로세스 고정이므로 인프라나 모델별 캐시를 추가하지 않는다.
   응답의 기존 `generatedAt`은 실제 생성 완료 시각으로 바로잡는다. `retrievedAt`,
   `cached`, `factsSha256`, `bundleSha256`은 추가 필드다. TTL은 자료의 신선함을
   보증하지 않는다. 과거 targetDate도 그대로 기록하며 오늘의 예보로 바꾸지 않는다.
2. `indexes/provenance.json`은 canonical/record/prompt의 내용 hash와 claim을
   원문 source 경로, SHA-256, 해당 source의 마지막 Git revision에 연결한다.
   기존 페이지 전체를 포괄하는 `page` claim과 선택된 개별 문장 claim을 구분한다.
   초기 이관은 모두 `unverified`이며 인간 검토나 실험 승인을 추정하지 않는다.
   원문 hash 또는 주장 변경은 검증 실패(`needs-review`)를 내고 번들 생성을 막는다.
   명시적인 refresh는 바뀐 항목을 `needs-review`로 남기며 승인으로 승격하지 않는다.
   `reviewed`는 raw 근거와 명시적 reviewer/검토 revision을 요구한다.
3. raw 근거가 없는 모델 선택 문서는 숫자와 과거 기록을 보존하되 미검증으로 표시한다.
   prompt/canonical은 관련 문서이며 원문 실험 증거가 아니다. 기존 이관 예외는 이
   페이지 하나에 명시한다. 새 페이지에 원문 없는 claims를 암묵적으로 허용하지 않는다.
   기존 raw는 바꾸지 않는다. 정책 변경은 decision page, index/log에 기록한다.
4. full static bundle과 FILE marker 형식은 유지한다. 별도 결정적 JSON 메타데이터는
   bundle hash, provenance hash, source revision/hash, claim 상태를 담는다. Git HEAD와
   작업 diff는 검증 실행 기록에 남긴다. CI는 본문과 sidecar를 모두 다시 생성해 비교한다.
   현재 branch 이름이나 생성 시각을 bundle/sidecar에 넣지 않는다.
5. contested 또는 low confidence 자료는 full bundle에서 삭제하지 않고 상태를 보존한다.
   verified 사실로 쓰지 않으며 backend facts가 우선한다. `unverified`/`needs-review`는
   출처 연결 상태이지 의미적 정답 승인 상태가 아니다. Hanjeok 날씨는 활성화하지 않는다.
6. citations API는 `List<String>` 경로를 유지한다. source/claim 연결은 sidecar로 노출한다.
   제한된 혼잡도/대안 정책 주제에 대해 관련 canonical 경로를 요구하는 회귀 방어를
   추가한다. 의미적 entailment 전체를 보장하지 않는다. 스트리밍은 첫 본문 전에 질문의
   정책 주제를 검사한다. 대화는 참조 맥락이며 이전 답변은 새 사실로 승격하지 않는다.

## 파일 범위와 순서

- wiki: 먼저 harness scenario/fixtures/tests, 이어 provenance 검증/refresh 및 metadata
  생성 스크립트, SCHEMA/retrieval policy, 모델 선택 표시와 신규 decision, index/log.
- agent: ExplanationCache/CourseExplainer/ExplainController, citation 주제 검증과 연결,
  Bundle metadata loader/context endpoint, 생성된 bundle/sidecar, CI 동기화 검사, 테스트.
- 외부 DB, 그래프/벡터 검색, 새 서비스, 날씨 도구, 모델 변경은 없다.

## 검증

시계와 fake provider/client로 변경 facts, TTL 경계, 동시 변경, 생성/조회 시각,
데이터 없음, 과거 날짜, 실패 복구, 여러 턴 참조, 유효하지만 무관한 인용을 검증한다.
wiki smoke, index check, provenance 단위 테스트, shell lint와 agent test/build를 실행한다.
frontend 기존 typecheck/test/build도 가능하면 실행한다. 실제 LLM 평가/SMTP/운영 API는
실행하지 않는다. 번들과 sidecar의 바이트 비교, SHA-256, 정확한 기준 revision과
작업 diff를 최종 검증 기록에 남긴다. 원격 push/PR/merge/배포는 범위 밖이다.
