# SQLite 안내 API 검토와 실제 확인

기준 커밋: 4b7b09f. 기존 512MB 구현에서 저장소만 교체한다.
설계: ../specs/2026-11-24-guide-sqlite-design.md
계획: ../plans/2026-11-24-guide-sqlite.md

## 설계 검토

`sqlite_design_review`가 부모 대화 없이 새 문맥에서 설계, 계획과 관련 소스를 읽었다.
구조를 막는 지적은 없었고 다음 네 사항을 구현 전에 반영했다.

1. 승인된 위키 manifest와 clean checkout의 chunk id/순서/원문 해시/키를 모두 대조한다.
2. 기존 EmbeddingCache의 쓰기 lifecycle 대신 mode=ro로 장소 캐시를 읽는다.
3. GraphPolicy와 같이 상위 limit*3 청크 내에서 페이지만 중복 제거한다.
4. gzip을 content-addressed 이름으로 먼저 쓰고 manifest만 원자적으로 마지막에 공개한다.

이는 한 번의 독립 설계 검토이며 EGM 전체 수렴 완료를 주장하지 않는다.

## 구현 중 확인

- 기존 baseline: 495 passed, 43 deselected.
- 새 기능이 없는 상태에서 저장소 테스트 12개 실패를 확인한 뒤 구현했다.
- API 선택 테스트 두 개가 SQLite 모드에서 Neo4j를 여는 문제로 실패한 뒤 분기했다.
- 운영자 준비 테스트 세 개가 미구현 실패한 뒤 추가했다.
- 로컬 pyenv Python은 SQLite 확장 로드를 지원하지 않았다. 지원하는 Homebrew
  Python3.13과 같은 검증된 site-packages로 실행했다. 실제 배포는 Linux 이미지에서 별도 검증한다.
- 테스트 기대값의 heading은 기존 splitter가 별도 보관하므로 page text에서 제외했다.
  실제 GraphPolicy가 조합하는 본문 계약을 기준으로 fixture 오류를 바로잡았다.
- focused 18 passed, 전체 기본 suite 513 passed/43 deselected. 최종 검사 후 갱신한다.
- 실제 파일: DB66,617,344bytes, gzip48,943,587bytes. 장소12106/관계43087/행사209/
  지역229, 위키18/83. 과거 승인 위키의 artifact/producer와 export 해시를 manifest에 보존했다.
- SQLite Blueprint validate valid=true. 원격 생성과 공개 응답은 아직 이 기록의 완료 범위가 아니다.

## 독립 코드 검토와 수정

`sqlite_code_review`가 부모 대화 없이 실제 변경과 산출물을 읽고 압축/원본 해시,
integrity_check와 focused18개를 확인했다. Critical은 없었고 아래 사항을 수정했다.

- 잘못된 JSON 객체 모양 때문에 기동이 죽는 문제: []/null API 사례 RED→GREEN,
  안전하게 ready503을 반환한다.
- Neo4j와 다른 지구 반지름 때문에 현재 자료의 경계 행사3건을 더 노출하는 문제:
  6378140.0m를 사용한다. 1000.762m 경계 사례 RED→GREEN.
- 순위가 같은 관계의 nullable score 정렬 차이: 현재 자료에 null 점수는 없지만,
  export 계약에 포함되므로 Cypher와 같은 null-first 정렬을 적용했다. RED→GREEN.
- 단순 answered+인용만으로 메모리 smoke를 통과시킬 수 있는 문제: 질문별 실제
  성공 lookup produced와 해당 인용 ID의 교집합을 요구한다. 위키-only 예보 오답 거절
  RED→GREEN. 기본 모델 metadata도 검사한다.

최종 기본 suite519 passed/43 deselected, Ruff clean. 새 검토를 통과했다고 임의로
주장하지 않고 각 지적의 재현 테스트와 전체 suite로 수정 확인했다.

검토에서 판단을 유보한 실제 원격 공개/모델 메모리는 Task3에서 별도로 관측한다.
SQLite 전체60문항 평가는 이 전환의 공개 응답 smoke와 다르며 미실행으로 남긴다.

초기 컨테이너 smoke는3 answered/1 model_failed였다. 대안 실패를 인용 검증 차단으로
처음 설명했지만 최종 terminal에서 모델 호출 실패로 확인해 정정했다. 실패 원본을
sqlite-512mb-amd64.json에 보존한다. 512MiB/no-swap, OOM0, 표본 최대316506112bytes였다.
초기 이미지에는 수정 전 행사 거리 계산이 포함되어 있어 최종 배포 증거로 재사용하지 않는다.

최종 이미지80507396의 표본 최대는302747648bytes(288.72MiB), OOM0/swap0이었다.
실제 source-sensitive 검사에서 예보/정책/일반 검색은 답변과 필요한 원본 인용을 확인했다.
대안 질문은 모델이 대안 API 대신 장소 검색을 선택한 뒤 model_failed로 끝났다.
실패와 전체 passed=false를 sqlite-512mb-final-amd64.json에 보존했다.
Render Free 서비스를 생성했지만 원격 준비/답변과 프론트 공개는 후속 확인 대상이다.

## 실제 공개 응답에서 추가 발견한 대안 출처 누락

26c1a95의 Render 공개 ready/status는200, live 상태였다. 예보와 정책은 실제 조회/인용을
확인했지만 대안 질문은 장소 검색 결과를 날짜별 서비스 대안 순서라고 잘못 말했다.
sqlite-public-sse.json은 source_verified=false/passed=false 그대로 보존한다. 프론트는
아직 이 API로 공개하지 않은 상태에서 아래 수정에 착수했다.

- 하나로 확정된 장소/날짜의 명시적 대안 요청에서 search_places/related_places를
  실제 alternatives API로 실행하도록 두 전략에 같은 처리를 했다.
- 최종 답변은 해당 날짜 대안 레코드의 조회와 인용을 요구한다. 문구를 바꿔도
  빠져나가지 못하며 기존 단일 수정/차단 예산을 공유한다.
- 새 문맥의 alternative_source_review가 '2026-10-17 기준 … 대안 목록'이 정책 키워드
  예외에 걸려 검사를 우회함을 재현했다. 광범위 단어 제외 대신 실제 정책 질문 형태만
  제외하도록 수정하고 같은 사례의 RED→GREEN을 확인했다. 추가 Critical/Minor는 없었다.
- 기존 테스트의 내용/혼잡 검증 fixture는 해당 질문을 명시하게 고쳤고, 시간 제한
  fixture는 이미 조회한 대안도 인용한다. assertion을 줄이지 않았다.
- 가짜 평가 모델이 라이브 대안을 조회하지 않는 합성 사례는 새 계약상 실패이므로
  합성 golden 보고서와 화면 기대 분모9/경고1건을 갱신했다. 과거 실제 평가는 그대로다.
- 백엔드525 passed/43 deselected, 프론트27파일296 tests passed, Ruff clean.
  수정된 image06db4b81은 별도 실제 512MiB 검사를 진행했다. 이전 이미지 결과를 최종으로 쓰지 않는다.

## 공개 배포와 최종 관측

Render Free의 수정본5c576f9가 live이고 ready/status200과 정확한 코퍼스 건수를 확인했다.
수정 후 공개 예보/정책은 원본 lookup/인용 검사 통과, 대안은 정확한 날짜별 API 조회
뒤 모델 호출 실패였다. 이 결과를 passed=false로 그대로 보존했다.
최종 소스 이미지06db4b81의 512MiB/no-swap 표본 최대는312135680bytes(297.68MiB),
OOM0이었다. 예보/대안/일반 검색은 원본 인용 포함 answered, 정책은 model_failed였다.
무료 모델의 가용성/응답 변동까지 해결했다고 주장하지 않는다.

Cloudflare Pages Production/main에 새 API URL을 포함한 빌드를 배포했다.
배포6cd94b67-1e37-4ed0-853f-70c33fabde83, Render deploy dep-dc2evouk1f9s73fpjemg.
실제 Chrome에서 agent.hanjeok.com/ko/ask를 열어 경복궁 예보 질문을 제출했고,
7.6초 표시와 실제 답변/경복궁 혼잡 예보 원본 인용이 화면에 나왔다.
sqlite-public-forecast.jpg와 sqlite-deployment.json이 실제 관측 증거다.
검증 화면을 얻기 위해 기존에 차단된 다운로드/잠금 보호를 우회한 것은 아니다.
SQLite가 Aura 인증 자체를 필요 없게 했고 공개 HTTP 화면만 정상 브라우저 API로 검사했다.

백엔드525/43deselected, 프론트296/27files, Ruff clean과 최종 Pages 빌드 성공을 기록했다.
배포 기록을 저장하면서 모델/검사/코드를 추가로 바꾸지 않는다. main 병합/결제 추가는 없었다.
