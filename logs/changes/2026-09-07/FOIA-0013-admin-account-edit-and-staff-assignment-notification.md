# 변경 기록

- 일시: 2026-09-07 17:38
- 작성자: cshs1729
- 작업번호: FOIA-0013
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
사용자가 지목한 남은 두 항목을 함께 구현: (1) 시스템관리자 계정 수정(역할/소속/비밀번호)
기능, (2) 업무담당자 새 배정 알림(폴링 기반).

## 변경 내용

### 계정 수정
- `app/db.py`: `update_user(user_id, role, region, branch, department, password_hash=None)`
  신규 — 아이디는 변경하지 않음(배정·판단이력 전반이 아이디 문자열로 참조 중이라 바꾸면
  깨짐). `password_hash`가 주어졌을 때만 비밀번호를 갱신.
- `app/main.py`: `GET/POST /admin/users/{id}/edit` 신규. 검증: 유효한 역할인지, 비밀번호
  입력 시 8자 이상인지, 마지막 남은 시스템관리자의 역할을 바꾸려는 시도인지(삭제의
  "마지막 관리자 보호"와 동일한 원칙 재사용). 기존 계정 생성(`admin_users_create`)의
  비밀번호 최소 길이도 3자 → 8자로 통일(`docs/PROJECT_REVIEW_2026-09-07.md` 우선순위 1의
  남은 항목이었음, 같은 파일을 만지는 김에 함께 정리).
- `app/templates/admin_user_edit.html` 신규, `admin_users.html`에 "수정" 링크 추가.
- `app/static/css/style.css`: 액션 컬럼에 링크+버튼 두 개를 나란히 담기 위한
  `.col-action-wide`(150px) 클래스 추가.

### 업무담당자 새 배정 알림
- `app/main.py`: `GET /api/requests`를 업무담당자도 호출할 수 있게 확장 —
  `_require_role_api`에 '업무담당자' 추가, `assigned_to`를 본인 아이디로 자동 필터링
  (페이지 라우트 `/requests`와 동일한 원칙).
- `app/templates/requests.html`: `is_my_queue`일 때 `window.MY_QUEUE_POLL = true` 마커.
- `app/static/js/app.js`: `pollMyQueue()`/`initMyQueuePolling()` 신규 — 20초 간격으로
  `/api/requests`를 다시 불러 이전에 없던 id가 나타나면 토스트 알림 후 1.2초 뒤 페이지
  새로고침. 최초 호출은 기준선만 세우고 알리지 않음. 이 앱은 애초에 실시간 SSE/웹소켓이
  아니라 대시보드도 `setInterval` 폴링만 쓰고 있어(`connectSSE()`라는 이름이지만 실제로는
  폴링) 같은 방식으로 통일.

## 원인
사용자 지시: "이거 두개 다 해줘" — 역할별 재점검(FOIA-0009~0012)에서 남은 항목 중
배정 알림과 계정 수정 기능을 지목.

## 검증
- 확인 방법: **주의** — curl로 한글이 포함된 폼 값을 보낼 때(`-d`, `--data-urlencode`
  둘 다) 이 환경에서 인코딩이 깨져 엉뚱한 400 에러가 반복적으로 발생함을 발견 → Python
  `requests` 라이브러리로 전환해 정확히 재현·검증함(비슷한 이슈가 FOIA-0011에서도 있었으나
  이번엔 JSON이 아니라 form-urlencoded 자체가 깨지는 것까지 확인). `requests`로:
  (1) 계정 수정이 실제 DB에 반영되는지, (2) 8자 미만 비밀번호 거부, (3) 비밀번호 변경 후
  새 비밀번호로 로그인 성공·기존 비밀번호로는 실패하는지, (4) 마지막 시스템관리자의 역할
  변경 시도 차단, (5) 잘못된 역할 값 거부 — 전부 확인. 알림 기능은 Playwright로 staff4
  로그인 후 `pollMyQueue()`를 최초 호출(기준선)한 뒤 별도 세션에서 배정 실행, 다시
  `pollMyQueue()` 호출 시 토스트("새로 배정된 청구가 1건 있습니다...")가 뜨는 것을
  스크린샷으로 확인.
- 결과: 전부 기대대로 동작. `python -m compileall app` 통과.

## 리스크
- 영향 범위: `GET /api/requests`가 이제 업무담당자도 호출 가능 — 응답은 본인 배정건으로
  자동 필터링되므로 다른 사람 정보 노출 없음.
- 주의사항: 알림은 20초 폴링 기반이라 최대 20초 지연이 있을 수 있고(실시간 아님), 브라우저
  탭이 백그라운드에 있으면 브라우저 정책상 타이머가 느려질 수 있음(이 앱의 다른 폴링과
  동일한 한계). 이 프로젝트에서 curl+한글 조합이 반복적으로 문제를 일으키는 것을 재확인 —
  앞으로 한글이 섞인 값을 테스트할 때는 curl 대신 Python `requests`를 우선 사용할 것.

## 다음 조치
- 후속 작업: `docs/PROJECT_REVIEW_2026-09-07.md` 6절의 마지막 남은 항목("배정담당자의
  `/requests` 접근 제한이 의도된 것인지")은 정책 확인이 필요해 보류 — 사용자와 논의 필요.
