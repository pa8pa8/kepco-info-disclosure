# 한국전력공사 정보공개 청구 지원 시스템 — 변경 이력

## v1 (2026-09-03) — 최초 구현

SCADA Dashboard(`scada_system_agent`)와 동일한 스택·구조·인증 방식을 재사용해
정보공개 청구 처리 지원 대시보드를 신규 구현.

### 백엔드
- FastAPI + Jinja2 + SQLite, pbkdf2(260,000회) + HMAC 세션 인증을 SCADA와 동일하게 재사용
- `app/services/foia_core.py`: `docs/blueprint.jpeg`의 7단계 판단 흐름을 데이터로 인코딩
- `app/services/request_processor.py`: 감시 폴더 자동 접수 + AI 식별 파이프라인(scanner.py 대응)
- `app/ai_runtime/api.py`: 로컬 전용 `/identify` API — 요청대상 추출, 반복 청구 유사도 판정
- DB 3테이블: `disclosure_requests`, `request_decisions`, `decision_log` (+ `app_settings`)

### 프론트엔드
- SCADA와 동일한 CSS 디자인 토큰·컴포넌트 클래스 재사용, 6종 통지 유형 색상 매핑 추가
- 대시보드/청구 목록/청구 접수/청구 상세(판단 위저드)/설정 5개 화면

### 문서화 도구 (`tools/`)
- `build_introduction_manual_docs.py`: 소개서 + 운영자 매뉴얼(docx)
- `build_program_materials.py`: 보안성 검토서(docx)
- `build_program_overview_deck.py`: 개요 PPT — SCADA 원본은 raw OOXML을 직접 조립하지만,
  이 프로젝트는 `python-pptx`로 더 단순하게 동일 목적을 구현 (의도적 단순화)

### 검증
- 로컬 실행 후 6가지 통지 결과(공개/부분공개/비공개/정보부존재/진정질의/종결) 전 경로,
  반복 청구 자동 감지, 감시 폴더 자동 접수, 설정 저장을 실제 HTTP 요청으로 확인
- tools/ 3개 스크립트 모두 실행해 docx 2건 + pptx 1건 정상 생성 확인

## v1.1 (2026-09-03)

- `실행.bat` 추가: 더블클릭으로 패키지 설치(최초 1회) + 서버 실행 + 브라우저 자동 오픈.
  배치 파일에 한글 콘솔 메시지를 넣으면 코드페이지 문제로 스크립트 내용 자체가 깨지는
  현상을 확인해 콘솔 출력은 영문으로 작성.
- 프로젝트 전역에서 "AIOps" 표기 제거. 제목/브랜드를 "정보공개 청구 지원 시스템"으로,
  exe/spec 이름을 `INFO_DISCLOSURE_System`으로, 세션 쿠키명을 `foia_session`으로 변경.
  다른 프로젝트(SCADA)를 지칭하는 문구는 "SCADA 프로젝트/SCADA Dashboard"로 순화.

## v1.2 (2026-09-03) — 4역할 계정/권한 분리

기존 단일 관리자 로그인을 4개 역할로 전면 개편. 로그인 계정에 따라 서로 다른 화면과
권한이 강제되도록 백엔드에서 라우트 단위로 가드를 걸었다.

- `app/db.py`: `users.role` CHECK 제약을 (시스템관리자/총괄관리자/배정담당자/업무담당자)로
  변경. `disclosure_requests`에 `assigned_to`/`assigned_by`/`assigned_at` 컬럼 추가.
  이전 3역할(관리자/운영자/담당자) 스키마가 남아있으면 자동으로 `users` 테이블을 재생성하는
  마이그레이션 포함 (더미 계정만 있던 단계라 데이터 보존 없이 처리).
- `app/main.py`: `_require_role()`/`_require_role_api()` 가드를 모든 페이지·API 라우트에 적용.
  로그인 성공 시 역할별 홈(`ROLE_HOME`)으로 자동 이동 — 시스템관리자→`/admin/users`,
  총괄관리자→`/`, 배정담당자→`/dispatch`, 업무담당자→`/requests`(본인 배정건만 자동 필터).
- 신규 화면: `/admin/users`(계정 추가·삭제), `/dispatch`(배정 대기 큐 + 담당자 배정).
- `/requests/{id}` 상세 페이지가 역할에 따라 3갈래로 다르게 렌더링됨 — 총괄관리자/배정받은
  업무담당자는 판단 위저드, 배정담당자는 배정 UI, 그 외에는 읽기 전용.
- 기본 계정 4개 자동 생성: `admin/admin`, `manager/manager`, `dispatcher/dispatcher`,
  `staff/staff` (DB에 계정이 하나도 없을 때만, 이후 비밀번호 변경분은 유지됨).
- 검증: 4개 계정 전부 로그인→랜딩 페이지, 다른 역할 화면 직접 접근 시 자기 화면으로
  리다이렉트, API 403 경계, 배정→위저드 처리→완료까지 전 과정을 실제 HTTP 요청으로 확인.
  테스트 중 "이미 완료(반복청구)된 청구도 배정 가능"한 허점을 발견해 배정 API에 가드 추가.

## v1.3 (2026-09-03) — 배정 대기 화면 원문 노출 + AI 판단(데모) 기능

- `/dispatch`, `/requests/{id}`에서 미배정 청구의 **원문 전체를 카드에 바로 표시**하도록 변경
  (기존엔 요청대상 요약 + "원문 보기" 링크만 있었음).
- "🤖 AI 판단하기" 버튼 추가. **실시간 계산이나 무작위 추천을 쓰지 않는다** — 최초에는
  `random.sample()`로 목업 추천을 구현했다가, "random 절대 쓰지 말고 예시 txt 파일만
  쓰라"는 지시에 따라 전면 재작성함:
  - `app/config.py`: `AI_RESULTS_DIR`(`data/ai_recommendations/`) 추가
  - `POST /api/requests/{id}/recommend`: 청구의 `source_file`과 같은 이름의 예시 결과
    파일이 있으면 읽어서 추천 순위(1~3위)와 사유를 파싱해 반환, 없으면
    `has_result: false` + 안내 메시지만 반환
  - `POST /api/requests/{id}/generate-recommendation`: "AI로 생성하기" 버튼 핸들러.
    실제 생성 로직 없이 "사전 준비된 5건만 지원합니다"라고 정직하게 안내
  - 추천된 담당자를 클릭하면 바로 배정(`assignRequestTo`)됨
- `app/main.py`의 `DEFAULT_ACCOUNTS`를 `staff1`~`staff10` 10개 업무담당자 계정으로 교체
  (기존 단일 `staff` 계정 제거). 계정별 존재 여부를 확인해 없는 것만 생성하는 방식이라
  기존 DB를 지우지 않아도 다음 실행 시 자동으로 채워짐.
- `data/watch/`를 예시 청구 10건(`20260201`~`20260210`)으로 교체, 그 중 5건에 대해서만
  `data/ai_recommendations/`에 짝이 되는 예시 결과 파일을 준비(나머지 5건은 의도적으로
  비워 "AI로 생성하기" 안내 문구 확인용).
- 검증: 10건 전부 원문 노출, 예시 있는 5건은 정확한 추천 순위·사유 파싱, 예시 없는 5건은
  안내 메시지, 추천 클릭 시 배정까지 실제 HTTP 요청으로 확인. `random` 사용처가 코드에
  전혀 남아있지 않은 것도 grep으로 재확인.

## v1.4 (2026-09-07) — KRDS 라이트 테마 적용 + 화면 정리 + Git 저장소 초기화

팀장 지시("Figma에서 KRDS/범정부 UX디자인 컴포넌트를 가져와 플러그인으로 뼈대를 구성하고
AI에게 코드로 바이브코딩시키는 방식")를 이 프로젝트 스택(FastAPI + Jinja2 + 바닐라 JS)에
맞게 적용. 이미 준비돼 있던 디자인 시안(`docs/design/krds-dispatch-draft.svg`, FOIA-0002)의
톤을 실제 화면 코드로 옮기는 작업으로 진행했으며, 상세 변경 근거·검증 로그는
`logs/changes/2026-09-07/FOIA-0004-*.md`, `FOIA-0005-*.md`에 있음.

### 1단계 — 전역 라이트 테마 전환 + 배정 대기 화면 재구성 (FOIA-0004)
- `app/static/css/style.css`: 색상 토큰(`:root`)을 기존 다크 네이비 테마에서 KRDS 스타일의
  밝은 배경 + 흰 카드 테마로 전면 교체. 사이드바만 기존 다크 남색을 유지하되
  `--sidebar-*` 전용 변수로 분리. 색상·레이아웃 토큰이 전역이라 배정 대기 화면 하나만
  부분 적용하면 다른 화면과 스타일이 어긋나므로, "전역 토큰을 먼저 교체" 방식을 사용자
  승인 하에 선택. 배지·상태알약·요약카드·토스트·카드류 등 다크 배경을 전제로
  하드코딩돼 있던 rgba 값을 전부 밝은 배경 기준으로 재조정.
- `app/templates/dispatch.html`: 청구 카드를 시안대로 좌(청구 원문)/우(업무담당자 배정,
  1·2·3순위 추천 버튼) 2단 레이아웃으로 재구성. "미배정" 배지, "청구 상세 보기" 링크 추가.
- `app/static/js/app.js`: "AI 판단하기" 클릭 후 동적 렌더링(`renderRecommendations`)도
  새 마크업(`.rank-primary`/`.rank-secondary-row`)에 맞게 재작성.
- 검증: 로컬 서버 기동 후 Playwright로 관리자/배정담당자 로그인 → 로그인/대시보드/청구
  목록/청구 상세/설정/배정 대기 전 화면 스크린샷 캡처해 육안 확인. 색상 대비 문제나
  깨진 레이아웃 없음.

### 2단계 — 나머지 화면 순차 정리 (FOIA-0005)
- `app/static/css/style.css`: `.table-fixed` + 컬럼 유틸리티 클래스(`col-time`/`col-name`/
  `col-pill`/`col-target`/`col-action`) 추가 — 좁은 컬럼은 고정폭, 긴 텍스트 컬럼만 남은
  폭을 흡수해 자연스럽게 줄바꿈되도록 함.
- `app/templates/requests.html`: 표에 위 컬럼 클래스 적용(1차 폭 조정 후 스크린샷
  재검증에서 부족함을 발견해 폭 재조정). 청구 상태(접수/판단중/완료) 알약 톤을
  통지 유형과 별개로 매핑(이전엔 전부 회색 한 가지 톤).
- `app/templates/admin_users.html`: 계정 목록 표에도 동일 컬럼 클래스 적용 — 역할 라벨과
  "나" 배지, "삭제" 버튼이 겹치거나 줄바꿈되던 문제 해결.
- `app/templates/request_detail.html`: 담당자 배정 섹션의 AI 추천 버튼을 `/dispatch`와
  동일한 `.rank-primary`/`.rank-secondary-row` 컴포넌트로 교체해 두 화면의 시각 언어 통일.
- 검증: manager/admin/staff2 세 계정으로 로그인해 나머지 전 화면 스크린샷 재확인.
  `python -m compileall app` 통과.

### Git 저장소 초기화
- `.gitignore` 추가(런타임 DB `data/info_disclosure.db`, AI 호출 로그
  `data/ai_log.jsonl`, `__pycache__`, 오래된 백업 `app/app.zip`, 로컬 설치 마커
  `.installed` 제외) 후 `git init` + 최초 커밋(64 files) 생성. 원격 저장소는 아직
  등록/push하지 않음 — 개발 표준에 따라 GitHub 업로드는 별도 단계로 분리.

### 남은 미확정 사항
- 공식 KRDS Figma 컴포넌트 라이브러리 인스턴스를 그대로 가져와 적용하는 것은 미확정
  (현재는 색상·레이아웃 토큰 수준의 근사치 반영). 이 세션에는 Figma MCP가 연결되어 있지
  않아, 공식 라이브러리를 실제로 반영하려면 Figma 접근 방법을 먼저 정해야 함.
- `/requests/{id}` "처리 이력" 표 등 `.table-fixed`를 적용하지 않은 나머지 표들은
  이번 작업 범위 밖.
