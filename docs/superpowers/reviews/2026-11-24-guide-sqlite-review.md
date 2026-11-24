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
