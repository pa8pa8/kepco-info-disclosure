# 변경 기록

- 일시: 2026-09-07 23:54
- 작성자: cshs1729
- 작업번호: FOIA-0021
- 변경 유형: docs
- 상태: reviewed

## 변경 요약
6개 관점 점검 보고서의 마지막 항목 "6. 문서화적" 처리. 원 지적("`DEVELOPMENT_STANDARD.md`/
`DEPLOYMENT.md`/`PROJECT_REVIEW.md` 간 내용이 겹친다")을 실제로 파고들어 보니, 세 문서의
본문 내용 자체가 겹치는 곳은 거의 없었고 진짜 문제는 (1) 최근 리팩터(FOIA-0018~0020)로
바뀐 코드 위치·심볼 이름을 문서가 못 따라간 stale 참조, (2) 어느 문서를 봐야 할지
안내하는 진입점이 없어 겹쳐 보이는 것 두 가지였다. 둘 다 해결.

## 변경 내용

### Stale 참조 수정 (리팩터 이후 못 따라간 것)
- `docs/PROJECT_REVIEW.md`: "페이지/API 라우트 이중 가드" 설명이 여전히 옛 비공개 함수
  이름(`_require_role`/`_require_role_api`, `main.py` 시절)을 쓰고 있던 것을 현재 이름
  (`require_role`/`require_role_api`, `app/security.py`)으로 수정.
- `docs/DEPLOYMENT.md`: `FOIA_AUTH_SECRET` 설명이 `app/main.py`의 `_auth_secret()`을
  가리키고 있었는데, 라우터 분리(FOIA-0018)로 `app/security.py`의 `auth_secret()`으로
  이동한 걸 반영 안 하고 있었음 → 수정.
- `docs/DEVELOPMENT_STANDARD.md`: "Git 저장소가 초기화되어 있지 않다"는 최초 작성 시점
  서술이 그대로 남아 있어 지금 읽으면 오해 소지 → 최초 지시 원문은 보존하고, 이후
  실제로 초기화·push했다는 것과 기본 브랜치가 `main`이 아니라 `master`라는 걸 인용구로
  추가.
- `README.md`: "테스트 코드가 아직 없다"·"배정담당자가 판단 세부 내용까지 열람 가능
  (수정 전)" 두 항목이 이번 세션에서 이미 해결됐는데 "알려진 제약사항"에 그대로 남아
  있던 것 제거/수정. `DEFAULT_ACCOUNTS` 위치가 `app/main.py`에서 `app/deps.py`로
  이동한 참조도 수정(FOIA-0020에서 발견, 여기서 반영).

### docs 안내 문서 신규
- `docs/README.md` 신규: 6개 문서(`DEVELOPMENT_STANDARD.md`/`DEPLOYMENT.md`/
  `PROJECT_REVIEW.md`/`blueprint.*`/`design/`/`reference/`)가 각각 "다루는 것/다루지
  않는 것"을 표로 정리 — 겹치는 내용이 생기면 이 경계를 기준으로 정리하라는 원칙 명시.
  루트 `README.md`에서 이 문서로 가는 링크 추가.
- `docs/reference/README.md` 신규: `docs/design/README.md`와 동일한 패턴으로, 이 폴더가
  "이 프로젝트 문서가 아니라 SCADA 프로젝트 참고 자료"임을 폴더 진입 시점에 바로 알 수
  있게 함(기존엔 루트 README까지 가야만 알 수 있었음).

## 원인
사용자 지시 "5,1,2,3,4,6 순서로 진행해줘"의 마지막 항목. 원 점검 보고서에서 "문서 간
내용 중복"으로 지적됐던 것을 실제로 검토한 결과였음.

## 검증
- 확인 방법: `python -m pytest -q` 재실행(문서만 바꾼 변경이라 영향 없을 것으로 예상,
  34개 전부 통과로 확인). 리팩터 이후(FOIA-0018) 이동한 심볼/경로를 전부
  grep(`_require_role`, `_auth_secret`, `app/main.py`, `/requests/new`, `/api/stream`)으로
  재검색해 "현재 상태를 설명하는 문장"과 "그 당시를 기록한 히스토리 문장"을 구분 —
  히스토리 문장(예: PROJECT_REVIEW.md "3. 이번 점검에서 즉시 수정한 것" 절의 과거 함수
  이름들)은 FOIA-0018에서 세운 선례(과거 로그의 역사적 언급은 보존)대로 그대로 둠.
- 결과: 현재 상태를 설명하는 stale 참조는 전부 수정, 히스토리 기록은 보존.

## 리스크
- 영향 범위: 문서만 변경, 코드 동작 없음.
- 주의사항: 앞으로 심볼/경로를 옮기는 리팩터를 할 때는 `docs/README.md`가 가리키는 문서들도
  같이 grep해서 stale 참조가 안 남게 할 것.

## 다음 조치
- 후속 작업: 6개 관점(디자인·디렉토리/파일명·명칭통일성·기능적·IT기술적·문서화적) 전부
  1회씩 처리 완료. 남은 낮은 우선순위 항목(동기 DB 호출, 연락처 형식 검증, CSRF 토큰,
  `admin.py`의 도달 불가능한 "마지막 관리자 삭제 방지" 분기 정리 여부)은 각각의 로그에
  기록된 대로 별도 판단 필요 시 진행.
