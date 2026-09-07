# 변경 기록

- 일시: 2026-09-07 17:17
- 작성자: cshs1729
- 작업번호: FOIA-0011
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
정보공개법 제11조 기준 법정 처리기한(접수일+10일, 1회 연장 시 +10일) D-day 계산·표시와
연장 기능 신규 구현. 역할별 재점검에서 나온 "법정 처리기한 추적 없음" 공백 해결.

## 변경 내용
- `app/services/foia_core.py`: `STATUTORY_DAYS=10`, `EXTENSION_DAYS=10`,
  `compute_deadline_info(received_at, extended, is_finalized)` 신규 — 접수일(역일 기준)로부터
  마감일 계산, 남은 일수에 따라 tone(normal/warning/fault/unknown)과 `short_label`(목록용,
  "D-3"/"기한초과 D+2"/"완료")·`label`(상세용, 날짜 포함) 둘 다 생성. 역일(달력일) 기준이라
  실제로는 근무일 기준일 수도 있어 참고용이라는 점을 코드 주석과 문서에 명시(법률 자문 아님).
- `app/db.py`: `disclosure_requests`에 `deadline_extended` 컬럼 추가(마이그레이션).
  `extend_deadline(request_id, actor, reason)` 신규 — 플래그 세팅 + `decision_log`에
  `extend` 단계로 사유 기록(제11조 제2항 근거 표기).
- `app/main.py`: `_with_deadline()` 헬퍼로 청구 dict에 `deadline` 필드를 계산해 붙임 —
  `/requests`, `/dispatch`, `/api/requests` 세 곳에서 재사용. `request_detail`에
  `deadline_info`/`can_extend`(배정된 업무담당자 본인 또는 총괄관리자, 미확정, 미연장일
  때만) 추가. `POST /api/requests/{id}/extend-deadline` 신규 — 권한·완료여부·중복연장
  여부 검증 후 연장.
- `app/templates/requests.html`, `dispatch.html`: 목록/카드에 기한 상태알약(`short_label`,
  hover 시 `title`로 전체 날짜) 추가.
- `app/templates/request_detail.html`: 접수 정보 카드에 처리기한 알약 + 연장 여부 표시,
  `can_extend`일 때 "기한 연장 (+10일)" 버튼.
- `app/templates/dashboard.html`, `app/static/js/app.js`: 상단 툴바에 "처리기한: 초과 N건 ·
  임박 N건" 배지 추가(`/api/requests` 응답의 `deadline.tone` 집계), 판단 대기 목록 각 행에도
  기한 알약 표시. `extendDeadline()` JS 함수 신규(사유 입력은 `prompt()`, 확인 후 API 호출).

## 원인
사용자 지시 "이어서 진행해줘" — 직전 역할별 재점검(FOIA-0009/0010)에서 "이 시스템의 존재
이유와 직결되는 항목"으로 우선순위를 매겼던 처리기한 추적을 다음 순서로 진행.

## 검증
- 확인 방법: 격리 환경(포트 8093, 별도 DB)에서 sqlite3로 특정 청구의 `received_at`을
  과거로 조작해 (1) 기한초과(D+2)/임박(D-2)/정상(D-10) 세 톤이 API·목록·배정 대기 화면에서
  정확히 계산·표시되는지, (2) 연장 API가 최초 1회는 성공하고 이후 재호출은 409로 거부되는지,
  (3) 연장 후 마감일이 정확히 +10일로 갱신되는지, (4) 대시보드 배지가 `/api/requests`
  응답을 집계해 정확한 건수를 보여주는지 확인. Playwright로 대시보드/목록/상세 화면
  스크린샷 확인. 테스트 중 한글이 포함된 curl 요청이 이 환경의 인코딩 문제로 500을
  유발하는 것을 발견했으나(요청 본문이 깨진 UTF-8로 전송됨), ASCII 사유로 재검증해
  기능 자체는 정상임을 확인 — 이 이슈는 `await request.json()`을 감싸는 에러 핸들링이
  없는 기존 전체 API 패턴의 문제라 이번 기능 범위 밖으로 분류.
- 결과: 전부 기대대로 동작. `python -m compileall app` 통과.

## 리스크
- 영향 범위: `_with_deadline()`가 `db.list_requests()`/`db.get_request()` 반환값을
  `dict(r)`로 변환하는 지점이 늘어남(기존엔 `sqlite3.Row` 그대로 템플릿에 넘기던 곳들) —
  두 타입 모두 `r['key']` 접근은 동일하게 동작하므로 템플릿 쪽 회귀는 없음을 확인.
- 주의사항: 역일(달력일) 기준 계산이라 공휴일 등을 제외한 근무일 기준과는 다를 수 있음
  (README·코드 주석에 명시). 잘못된 JSON 바디를 보내면 500이 나는 기존 패턴은 그대로임
  (이번 건에서 새로 발견했지만 고치지 않음 — 아래 다음 조치 참고).

## 다음 조치
- 후속 작업: (1) API 전반에 걸친 `await request.json()` 예외 처리 일원화(잘못된 JSON에
  500 대신 400 반환) — 별도 티켓으로 분리 검토. (2) `docs/PROJECT_REVIEW_2026-09-07.md`
  6절의 남은 항목(배정 알림, 통지서 산출물, 계정 수정, 배정담당자 이력 조회 제한) 중
  다음 진행 항목을 사용자와 확인.
