# 변경 기록

- 일시: 2026-09-07 18:24
- 작성자: cshs1729
- 작업번호: FOIA-0016
- 변경 유형: fix
- 상태: reviewed

## 변경 요약
사용자 지시 "모든 기능을 점검해줘... 모든 코드를 점검해줘, 표준에 맞는지 엉키는건 없는지,
기능이 없는데 괜히 있는 코드는 없는지, 기타 개선해야될건 없는지"에 따라 프로젝트 전체를
정적 코드 검토 + 34개 시나리오 기능 회귀 테스트로 점검. 실제 버그 3건, 죽은 코드 7건 발견·수정.

## 변경 내용

### 1. 버그: JSON 파싱 실패 시 500 (진짜 오류)
- `app/main.py`: `_read_json_body()` 헬퍼 신규 — `assign`/`reject`/`decide`/`extend-deadline`
  4개 API가 전부 `await request.json()`을 가드 없이 호출하고 있어서, 잘못된 JSON 바디를
  보내면 500(서버 내부 오류)이 났음. 이제 400 JSON 오류로 깔끔하게 응답.

### 2. 버그: `FOIA_SCAN_INTERVAL` 환경변수가 문서화만 되고 실제로는 동작하지 않음
- `app/db.py`: `_seed_settings()`가 `scan_interval`을 항상 하드코딩 `'60'`으로 시드하고
  있어서, README에 문서화된 `FOIA_SCAN_INTERVAL` 환경변수를 설정해도 아무 효과가 없었음.
  `config.SCAN_INTERVAL`(환경변수를 실제로 읽는 상수)을 import해 시드값으로 사용하도록 수정.

### 3. 버그(레이아웃): 관리자 계정 목록의 "소속" 컬럼이 글자 단위로 깨져 렌더링됨
- `app/static/css/style.css`, `admin_users.html`: FOIA-0013에서 액션 컬럼을
  `.col-action`(78px) → `.col-action-wide`(150px)로 넓히면서, `table-layout: fixed`인
  표에서 폭 지정이 없던 "소속" 컬럼(`.col-target`)에 남는 공간이 14px 수준으로 줄어들어
  텍스트가 세로로 한 글자씩 쪼개지는 버그 발생. `.col-target`에 `min-width`를 줘봤지만
  `table-layout: fixed`에서는 무시됨을 확인 → 명시적 `width: 220px`로 바꿔서 해결.
  `requests.html`, `requester_history.html`도 같은 `.col-target` 클래스를 쓰고 있어
  같이 검증(회귀 없음 확인).

### 4. 죽은 코드 제거
- `app/db.py`: 아무 데서도 호출되지 않는 `count_unassigned_pending()`, `get_source_file()`
  메서드 삭제(전자는 `summary()`가 이미 자체 SQL로 같은 값을 계산하고 있어 중복).
- `app/config.py`, `app/db.py`: `AI_API_URL`/`FOIA_AI_API_URL` 삭제 — README에 문서화된
  적도 없고, 시드 직후 `main.py`의 lifespan/설정 저장 로직이 매 요청마다
  `INTERNAL_AI_API_URL`로 강제 덮어써서 사실상 한 번도 효과를 낸 적이 없는 죽은 경로였음.
  `_seed_settings()`가 이제 `INTERNAL_AI_API_URL`을 직접 시드값으로 사용.
- `app/static/css/style.css`: 아무 템플릿·JS에서도 참조하지 않는 `.ai-pick-btn`(FOIA-0005/0009
  이전 배정 버튼 스타일, `.rank-primary`/`.rank-secondary`로 대체됨), `.ai-recommend-box`,
  `.hero-grid`, `.card-grid`, `.badge-row` 규칙 삭제. `@media` 쿼리에 남아있던 `.card-grid`
  참조도 함께 정리.

## 원인
사용자 지시로 전체 프로젝트 재점검 요청. 이번 세션에서 15개 이상의 기능을 순차적으로
추가하며 누적된 죽은 코드·환경변수 불일치·레이아웃 회귀를 한 번에 점검하기 위함.

## 검증
- 정적 검토: `grep`으로 `app/db.py`의 모든 메서드, `app/static/js/app.js`의 모든 함수,
  `app/static/css/style.css`의 모든 최상위 클래스 선택자를 추출해 각각 호출/참조 여부를
  전수 확인(스크립트로 자동화). `await request.json()` 전체 호출부 점검.
- 기능 회귀: 격리 환경(포트 8088, 별도 DB, `FOIA_SCAN_INTERVAL=5`로 버그 재현 확인)에서
  Python 스크립트로 34개 시나리오 자동 검증 — 로그인/역할 경계, 감시 폴더 접수, 배정
  담당자 AI 추천, 위저드 3가지 통지 경로(진정질의/정보부존재/공개), 통지서 인쇄 접근 제어,
  거절→재배정 지명→확정, 총괄관리자 직접 재배정 및 중복 재배정 거부, 처리기한 조회·연장·
  중복연장 거부, 청구인 이력 조회(정확 일치 + 권한 차단), 계정 생성·수정·삭제·마지막
  관리자 보호, 로그인 5회 실패 잠금 — **34/34 통과**. Playwright로 대시보드/청구목록/설정/
  배정대기/내업무/계정관리 6개 화면 스크린샷 육안 확인 중 관리자 화면에서 3번 버그 발견 →
  수정 후 재스크린샷으로 확인.
- `python -m compileall app` 통과.

## 리스크
- 영향 범위: 버그 수정 3건은 전부 기존에 잘못 동작하던 것을 바로잡는 것이라 회귀 위험
  낮음. 죽은 코드 제거는 아무도 참조하지 않던 코드만 지운 것이라 기능 변화 없음.
- 주의사항: `.col-target` 폭을 `220px`로 고정하면서 표가 패널 폭보다 넓어질 수 있는데,
  `.list-scroll`의 `overflow: auto`가 필요 시 가로 스크롤을 만들어주므로 잘림은 없음
  (이번 검증에서는 실제로 스크롤이 필요할 만큼 좁아지는 경우는 없었음).

## 다음 조치
- 후속 작업: 이전 역할별 분석에서 남겨둔 "배정담당자가 무관한 청구의 판단 결과·통지문·
  AI 힌트까지 열람 가능한 문제"는 이번 점검 범위 밖 — 별도 논의 필요.
