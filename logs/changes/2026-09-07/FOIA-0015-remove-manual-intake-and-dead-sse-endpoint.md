# 변경 기록

- 일시: 2026-09-07 18:03
- 작성자: cshs1729
- 작업번호: FOIA-0015
- 변경 유형: refactor
- 상태: reviewed

## 변경 요약
사용자 결정으로 수동 청구 접수 기능(`/requests/new`) 전체 제거, 역할별 기능 분석에서
"불필요한 기능"으로 지목했던 죽은 `/api/stream` SSE 엔드포인트와 그 지원 코드 제거.

## 변경 내용

### 수동 접수 제거
- `app/main.py`: `GET/POST /requests/new` 라우트 삭제.
- `app/templates/request_new.html` 파일 삭제.
- `app/templates/base.html`: 총괄관리자·배정담당자 네비게이션에서 "청구 접수" 링크 삭제.
- `app/templates/dispatch.html`, `dashboard.html`, `requests.html`: "＋ 새 청구 접수" 버튼
  삭제(레이아웃은 `.panel-header`의 flex가 자식 하나만 남아도 그대로 유지됨).
- `app/services/request_processor.py`: 주석에서 더는 존재하지 않는 `/requests/new` 언급 제거.
  `ingest()` 함수 자체는 감시 폴더 자동 접수가 계속 쓰므로 유지.
- `README.md`: 배정담당자 권한 설명("청구 접수 + 배정" → "배정만"), 처리 흐름 다이어그램
  ("배정담당자 접수" 단계 제거, 감시 폴더 자동 수집으로 명시), 주요 화면 표에서
  `/requests/new` 행 삭제, "청구 자동 접수" 절에 이게 유일한 접수 경로임을 명시.

### 죽은 SSE 코드 제거
- `app/main.py`: `GET /api/stream` 라우트 삭제. 이제 아무 클라이언트도 쓰지 않던
  `StreamingResponse` import도 함께 정리.
- `app/services/request_processor.py`: `/api/stream`에만 쓰이던 `_scan_event`
  (`asyncio.Event`)와 `_last_result` 필드, `_loop()`에서 이걸 세팅하던 코드 삭제 — SSE
  엔드포인트를 지웠는데 이 상태만 남겨두면 그 자체로 또 죽은 코드가 되므로 함께 정리.

## 원인
- 수동 접수: 사용자 지시 "수동접수 안할거야 지워줘" — 감시 폴더 자동 접수만 쓰기로 결정.
- SSE: 직전 역할별 기능 분석("있으면 안되는 기능과 불필요한 기능 분석")에서 `app.js`
  어디에도 `EventSource`가 없어 서버 SSE 엔드포인트가 완전히 죽은 코드임을 발견 →
  사용자가 "불필요한 코드 3" 삭제 지시.

## 검증
- 확인 방법: 격리 환경(포트 8089, 별도 DB)에서 Python `requests`로 (1) `GET /requests/new`가
  더는 접수 폼을 반환하지 않고(422 — `/requests/{id}` 패턴에 흡수되어 정수 파싱 실패),
  (2) `POST /requests/new`도 더는 청구를 생성하지 않으며(405), (3) `GET /api/stream`이
  404인지, (4) 대시보드·배정 대기·청구 목록 화면 어디에도 `/requests/new` 링크가 남지
  않았는지, (5) 감시 폴더 자동 접수(watch scan)는 영향 없이 10건 정상 접수되는지 확인.
- 결과: 전부 기대대로. `python -m compileall app` 통과.

## 리스크
- 영향 범위: HTTP로 청구를 새로 만드는 유일한 경로가 감시 폴더(`data/watch/`)뿐이 됨 —
  이후 "정말 필요하면 텍스트를 붙여넣어 접수" 같은 임시방편이 완전히 사라짐. 의도된 변경.
- 주의사항: 실제 서버에 반영할 콘솔(`launcher.py`)에서도 재시작 필요(늘 그렇듯).

## 다음 조치
- 후속 작업: 지난 분석에서 지목한 우선순위 1번(배정담당자가 자신과 무관한 청구의 판단
  결과·통지문·AI 힌트까지 열람 가능한 문제)은 아직 미해결 — 다음 작업으로 논의 필요.
