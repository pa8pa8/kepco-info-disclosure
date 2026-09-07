# 변경 기록

- 일시: 2026-09-08 00:37
- 작성자: cshs1729
- 작업번호: FOIA-0024
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
`docs/PROJECT_REVIEW.md`에 "낮음" 심각도로 남아있던 CSRF 토큰 부재를 해결하고,
FOIA-0020에서 발견해 판단을 미뤄뒀던 `admin.py`의 도달 불가능한 "마지막 관리자 삭제
방지" 분기를 정리했다. 두 건 다 작아서 한 번에 처리(사용자가 이 순서로 함께 요청).

## 변경 내용

### CSRF 토큰 검증 (synchronizer token 패턴)
- `app/security.py`: `csrf_token_for(username)` — 서버에 아무것도 저장하지 않고
  `auth_secret()`으로 `HMAC-SHA256('csrf:' + username)`를 매번 재계산하는 방식.
  로그인 전 화면은 `username=None`이 `'anonymous'` 고정값으로 매핑되어 동일한 메커니즘을
  그대로 쓸 수 있다. `require_csrf_form`(폼 필드, 헤더도 대체 경로로 허용)과
  `require_csrf_api`(JSON API, 헤더 전용) 두 가드를 `require_role`/`require_role_api`와
  같은 패턴("통과하면 None, 막히면 에러 응답")으로 추가.
  `templates.env.globals['csrf_token']`에 등록해 모든 템플릿에서
  `{{ csrf_token(request) }}`로 바로 쓸 수 있게 함.
- 상태 변경 POST 전부에 적용: 폼 8개(로그아웃·로그인·최초 계정 생성·설정 2개·AI
  테스트·계정 추가/수정/삭제)에 hidden `csrf_token` input 추가, JSON API 7개(배정·거절·
  판단·기한연장·AI추천 2종·감시폴더 스캔)에는 `<meta name="csrf-token">`을 `app.js`의
  `getCsrfToken()`이 읽어 `X-CSRF-Token` 헤더로 붙임.
- 검증 실패 시: 폼은 403 안내 HTML, API는 403 JSON(`{success: false, message: ...}`) —
  기존 `require_role`/`require_role_api` 실패 응답과 같은 성격으로 맞춤.

### admin.py 도달 불가능한 분기 제거
- `admin_users_delete()`의 "마지막 시스템관리자는 삭제 불가" 별도 체크를 제거. 이유:
  이 라우트는 관리자만 오고(`require_role`), 바로 위에서 target이 본인이 아님을 이미
  확인한다 — target이 관리자 역할이면 그 시점에 관리자가 최소 2명(본인+target)이라는
  뜻이라 "마지막 관리자를 지운다"는 상황 자체가 논리적으로 성립하지 않는다.
  자기 자신 삭제 금지(`error=self`) 체크 하나로 이미 완전히 막혀 있었다.
  왜 제거해도 안전한지 주석으로 남김. `admin_users.html`의 대응하는 `error=lastadmin`
  토스트 분기도 함께 제거(다른 곳에서 참조 없음, grep으로 확인).
- 참고: 계정 **수정**(`admin_users_edit_submit`)의 "마지막 관리자 역할 변경 금지" 체크는
  건드리지 않음 — 그건 본인 계정을 수정하는 경로에 self-체크가 없어서 실제로 도달
  가능하고 필요한 로직이다(다른 문제, 착각하기 쉬워서 명시).

## 원인
사용자가 "5,1,2,3,4,6" 순서로 6개 관점 점검을 마친 뒤 "지금 뭘 해야할까"라고 물어,
남은 항목 중 우선순위 높은 것(기본 계정 비밀번호 변경 유도)과 작고 빠른 것(CSRF +
admin.py 죽은 코드) 두 갈래를 제시했고 "두번째거 해줘"로 후자를 선택.

## 검증
- 확인 방법: `python -m compileall app` 통과. `tests/test_csrf.py` 신규 7개(토큰 없이/
  틀린 토큰으로/올바른 토큰으로 로그인 시도, JSON API 헤더 누락·위조 거부, 사용자별
  토큰이 서로 다름, 폼 기반 라우트도 헤더 누락 시 거부) — 기존 34개 + 신규 7개 =
  **41개 전부 통과**. 기존 테스트가 CSRF 도입 후에도 그대로 통과하도록
  `tests/conftest.py`의 `_new_client()`가 로그인 전엔 anonymous 토큰, 로그인 후엔
  실제 사용자명 토큰을 기본 헤더로 자동으로 얹도록 수정.
- 개발 서버(포트 8000) 재기동 후 실제 HTTP로 재확인: 로그인 폼에서 토큰 없이/틀린
  토큰으로 POST → 403, 화면에서 긁은 올바른 토큰으로 POST → 303 정상 로그인.
  로그인 후 JSON API에 `X-CSRF-Token` 헤더 없이 POST → 403 JSON. manager/dispatcher/
  staff1으로 각각 대시보드·청구 목록·설정·배정 대기·청구인 이력 화면이 전부 정상
  렌더링되는지 확인(메타 태그·hidden input 추가가 기존 화면을 깨지 않았는지).
  admin 계정으로 자기 자신 삭제 시도 → 여전히 `error=self`로 차단됨(분기 제거 후에도
  동일 동작 유지 확인).
- 결과: 전부 기대대로.

## 리스크
- 영향 범위: 상태 변경이 있는 라우트 전부(백엔드) + 그 라우트로 이어지는 폼/JS 전부
  (프런트엔드). 조회(GET) 라우트는 변경 없음.
- 주의사항: 앞으로 새 상태 변경 POST 라우트를 추가할 때는 (1) 폼이면 hidden
  `csrf_token` input, (2) JS fetch면 `headers: { 'X-CSRF-Token': getCsrfToken() }`를
  빠뜨리지 않아야 한다 — 빠뜨리면 항상 403이 나서 바로 눈에 띄긴 하지만, 그 전에
  `require_csrf_form`/`require_csrf_api` 가드 자체를 추가하는 걸 잊으면(즉 검증을 안
  걸면) 조용히 취약한 채로 남는다는 게 더 위험한 실패 모드다.

## 다음 조치
- 후속 작업: `docs/PROJECT_REVIEW.md` "실배포 전 필수" 우선순위 1에 유일하게 남은
  항목 — 기본 데모 계정(admin/manager/dispatcher/staff1~10) 비밀번호 변경 유도.
