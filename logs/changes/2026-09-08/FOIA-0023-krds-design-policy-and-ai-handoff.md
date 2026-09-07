# 변경 기록

- 일시: 2026-09-08 00:17 (Codex가 생성) / 09:20 (Claude가 내용 작성)
- 작성자: Codex(빈 티켓 생성) → cshs1729 (Claude가 이어받아 검증·작성)
- 작업번호: FOIA-0023
- 변경 유형: docs
- 상태: reviewed

## 변경 요약
Codex가 FOIA-0022(KRDS 웹 디자인 적용) 작업 직후 이 티켓을 생성만 해두고 내용을
채우지 못한 채 세션이 끝났다(제목만 있는 빈 draft, 새 세션에서 확인). 사용자가
"GPT를 통해 이어서 개발했다, 확인해서 이어서 개발할 수 있게 해달라"고 요청해 Claude가
Codex의 미커밋 작업(FOIA-0022)을 검증하고 커밋하면서, 비어 있던 이 티켓에 그 인수인계
기록을 채워 넣었다.

## 변경 내용
- Codex가 FOIA-0022에서 만든 작업 트리 변경분(커밋 안 된 상태)을 검증:
  `app/static/css/krds.css`(신규), `app/static/fonts/pretendard-gov/`(신규 폰트 2종 +
  라이선스), `docs/design/krds-web-*.png`(검증 캡처 5장) + `krds-web-verification.json`,
  `app/templates/base.html` 등 템플릿 9개, `app/static/js/app.js`, `README.md`,
  `docs/README.md`, `docs/design/README.md`.
- 직전 세션(Claude, FOIA-0019)에서 넣은 `dispatcher_limited_view` 조건부 렌더링
  (배정담당자 판단정보 가림)이 `request_detail.html`에서 로직 변경 없이 그대로 보존됐는지
  diff로 확인 — 스타일만(인라인 `style=` → `text-warning`/`section-gap`/`content-gap` 등
  유틸리티 클래스) 바뀌었고 `{% if dispatcher_limited_view %}` 분기 자체는 손대지 않음.
- `app.js`의 담당자 배정/재배정 후보 선택이 `onclick="...('${username}')"` 문자열
  삽입 방식에서 `data-staff-username` 속성 + `escapeHtml`로 바뀐 것 확인 — 사용자명에
  작은따옴표가 들어가는 경우의 JS 문자열 이스케이프 취약점이 부수적으로 없어짐.
- 새 유틸리티 클래스(`text-warning`/`text-danger`/`text-success`/`section-gap`/
  `content-gap`/`btn-full`/`action-row`/`pre-wrap`)가 템플릿에서만 쓰이고 CSS에는
  정의가 없는 경우가 없는지 전수 grep으로 확인 — 전부 `krds.css`에 정의돼 있음.
- `python -m compileall app`, `python -m pytest -q`(34개 전부 통과) 재실행, 실행 중인
  개발 서버(포트 8000)에서 `/login` 응답에 `krds.css` 링크가 실제로 포함되는지 확인.
- 검증 완료 후 FOIA-0022 관련 전체 변경분을 그대로 커밋(별도 수정 없음 — Codex 작업
  자체가 이미 완성도 높음).

## 원인
AI 두 개(Claude Code, Codex/GPT)가 번갈아 같은 저장소에서 작업하는 협업 구조라, 한쪽이
커밋하지 않고 세션을 마치면 다음 세션(다른 AI 또는 사람)이 "이게 신뢰할 수 있는 변경인지"
검증할 방법이 필요하다. 이번 건은 그 인수인계 과정 자체를 기록한 사례.

## 검증
- 확인 방법: 위 "변경 내용" 참고. 추가로 `git diff --stat`으로 변경 범위가 프런트엔드
  (CSS/템플릿/JS/폰트/문서)로 한정되고 백엔드 라우트·DB 스키마·권한 로직이 전혀 바뀌지
  않았음을 확인.
- 결과: 전부 기대대로. 커밋 진행.

## 리스크
- 영향 범위: 프런트엔드 전반(FOIA-0022와 동일). 코드 검증은 Claude가 했지만 실제
  디자인 QA(다양한 브라우저·보조기기)는 FOIA-0022에 기록된 대로 Chromium 기준으로만
  이뤄졌다는 한계는 그대로 남음.
- 주의사항: 두 AI가 번갈아 작업할 때는 세션 종료 전 반드시 커밋까지 마치는 게 이상적이나,
  안 됐을 경우 다음 세션이 이렇게 diff 전수 검증 후 커밋하는 방식으로 이어받을 것.

## 다음 조치
- 후속 작업: Figma MCP 사용량 한도가 풀리면 공식 컴포넌트 인스턴스 이식 여부 재검토
  (FOIA-0022에 기록된 대로 현재는 색상·서체·공통 클래스 수준 근사치).
- `docs/PROJECT_REVIEW.md` 우선순위 3번(공식 KRDS Figma 컴포넌트 적용 여부 확정) 항목과
  연계해 다음에 진행.
