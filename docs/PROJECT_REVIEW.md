# 프로젝트 점검 보고서 (2026-09-07)

이 문서는 `docs/DEVELOPMENT_STANDARD.md` 6.1절("자세한 동작 기준은 docs/ 하위에 정리")에 따라
작성한 코드 레벨 점검 결과입니다. README/CHANGELOG의 기능 요약과 달리, 이 문서는 **아직
README의 "알려진 제약사항"에 없는 리스크와 개선 항목**을 다룹니다.

## 1. 현재 상태 요약

- 스택: FastAPI + Jinja2 + SQLite + 바닐라 JS, `scada_system_agent`와 동일한 구조·인증 방식 재사용
- 화면: 대시보드/청구 목록·상세/청구 접수/배정 대기/설정/계정 관리 (역할 4종에 따라 분기)
- 2026-09-07 KRDS 라이트 테마 전환 완료(FOIA-0004, 0005), Git 저장소 초기화 및
  `github.com/pa8pa8/kepco-info-disclosure`에 push 완료
- 상세 변경 이력은 `CHANGELOG.md`, 근거·검증은 `logs/changes/` 참고

## 2. 점검 결과

### 잘 되어 있는 부분
- 페이지 라우트(`require_role`)와 API 라우트(`require_role_api`, 둘 다 `app/security.py`)
  이중 권한 가드가 모든 엔드포인트에 일관되게 적용되어 있음
- 비밀번호는 pbkdf2_sha256 260,000회 해싱, 세션은 HMAC 서명 + `httponly` + `SameSite=Strict`
  쿠키로 구현되어 있어 기본기가 탄탄함
- 모든 SQL이 파라미터 바인딩(`?`)을 사용 — SQL 인젝션 경로 없음
- Jinja2 템플릿 어디에도 `|safe` 필터가 없어 자동 이스케이프가 항상 적용됨(XSS 안전)
- 배정/판단 단계 전이에 서버사이드 상태 검증이 되어 있음 (이미 배정된 건 재배정 불가,
  현재 단계와 다른 step 요청 거부, 이미 완료된 건 재판단 불가 등)
- 변경 로그(`logs/changes/`)와 `CHANGELOG.md`가 실제로 매 작업마다 갱신되고 있어 추적 가능성이 높음

### 발견된 이슈 (심각도순)

| 심각도 | 항목 | 내용 |
|---|---|---|
| 높음 (수정 완료) | 로그인 무차별 대입 방어 없음 | `/login`에 시도 횟수 제한·계정 잠금이 전혀 없었음. 기본 데모 계정이 `admin/admin`처럼 아이디=비밀번호라 위험 → 계정당 5회 실패 시 5분 잠금(메모리 기반, `main.py`의 `_login_attempts`) 추가 |
| 중간 | 계정 생성 비밀번호 정책 불일치 | `/setup`(최초 관리자)은 8자 이상 요구, `/admin/users`(이후 계정 추가)는 3자 이상만 요구 — 관리자가 매우 약한 비밀번호로 계정을 만들 수 있음 |
| 낮음 (수정 완료) | 계정 추가 폼 비밀번호 평문 노출 | `admin_users.html`의 비밀번호 입력이 `type="text"`라 화면에 그대로 보였음 → 이번 점검에서 `type="password"`로 즉시 수정 |
| 중간 (수정 완료) | 테스트 코드 전무 | 단위/통합 테스트가 하나도 없었음, 검증은 전부 수동(curl, Playwright 스크린샷) → `pytest` + FastAPI `TestClient` 기반 자동화 테스트 추가(`tests/`, FOIA-0020에서 34개로 시작, FOIA-0024에서 CSRF 테스트 7개 추가해 현재 41개). 인증/잠금, 역할별 접근 통제(FOIA-0019 회귀 포함), 배정·거절·재배정·판단 흐름, 계정 관리, CSRF 검증 커버 |
| 낮음 (수정 완료) | CSRF 토큰 없음 | 배정·판단·계정 삭제 등 상태 변경 POST에 CSRF 토큰이 없었음. `SameSite=Strict` 쿠키가 대부분의 크로스사이트 요청을 막아주지만 명시적 토큰은 없어 방어 심층화 관점에서 아쉬웠음 → synchronizer token 패턴으로 전 상태 변경 POST(폼 8개 + JSON API 7개)에 CSRF 검증 추가(FOIA-0024). 서버 저장 없이 auth_secret에서 매번 재계산 |
| 낮음 (수정 완료) | 의존성 버전 하한선(`>=`)만 고정 | `requirements.txt`가 전부 `>=`만 사용 — 설치 시점에 따라 다른 버전이 깔릴 수 있어 "오래된 서버에서도 재현 가능"이라는 프로젝트 목표와 상충 → 현재 검증된 버전으로 전부 `==` 고정(FOIA-0020), 테스트 전용 `requirements-dev.txt` 신규 분리 |
| 낮음 | 동기 DB 호출이 이벤트 루프를 블로킹 | `app/main.py`의 모든 라우트가 `async def`이지만 SQLite 호출은 동기 함수를 그대로 호출 — 쿼리 실행 중 다른 요청·SSE 하트비트·백그라운드 스캔이 함께 멈춤. 현재 트래픽 규모(내부 소수 사용자)에서는 체감 안 되지만 확장 시 병목 가능 |
| 높음 (완화 완료) | DB 파일 하나에 리스크 집중 | `data/info_disclosure.db`가 평문 SQLite 파일이고 파일 권한도 `644`(소유자 외 읽기 가능)였음. 그 안에 비밀번호 해시·세션 서명키(`auth_secret`)·청구인 개인정보(이름·연락처)가 전부 들어있어, 파일 하나 유출로 셋 다 노출되는 구조 → 서버 시작 시 자동으로 `0600`(소유자 전용)으로 권한을 좁히도록 수정, `FOIA_AUTH_SECRET` 환경변수로 서명키를 DB 밖에서 주입할 수 있는 경로도 추가 |
| 중간 (수정 완료) | 입력 길이 제한 없음 | 청구인 성명·연락처·청구 원문(`raw_text`)에 최대 길이 검증이 전혀 없어, 실수로 매우 큰 텍스트를 붙여넣어도 그대로 DB에 저장됨 → `/requests/new`는 FastAPI `Form(max_length=...)`로 즉시 거부(성명 100자/연락처 200자/원문 20,000자), 감시 폴더 자동 접수 경로(`RequestProcessorService.ingest`)에도 동일 상한으로 자르는 로직 추가 |
| 낮음 | 외부 노출 자체는 기본값이 안전하나 배포 가이드 부재 | `launcher.py`가 `host='127.0.0.1'`로만 바인딩하고 CORS 미들웨어도 없어 기본 자세는 안전함. 다만 실제로 여러 사용자가 접속하는 서버로 올릴 때 필요한 리버스 프록시·TLS 종료·`FOIA_AUTH_COOKIE_SECURE` 설정 방법이 문서화되어 있지 않았음 → `docs/DEPLOYMENT.md` 신규 작성 |
| 낮음 | 연락처 형식 검증 없음 | `requester_contact`가 자유 문자열이라 전화번호/이메일 형식 여부를 서버가 확인하지 않음(치명적 보안 이슈는 아니고 데이터 품질 문제) — 아직 미해결 |

## 3. 이번 점검에서 즉시 수정한 것
- `app/templates/admin_users.html`: 계정 추가 폼의 비밀번호 입력 필드를 `type="text"` →
  `type="password"`로 수정 (`autocomplete="new-password"` 추가).
- `app/db.py`: DB 파일 권한을 서버 시작 시 자동으로 `0600`(소유자 전용)으로 제한
  (`_restrict_file_permissions`). Windows는 POSIX 권한 모델이 달라 완전히 제한되지는 않음 —
  Windows 배포 시 `icacls` 별도 필요(`docs/DEPLOYMENT.md` 4절 참고).
- `app/main.py`: 세션 서명키(`auth_secret`)를 `FOIA_AUTH_SECRET` 환경변수로 직접 주입할 수
  있는 경로 추가(미설정 시 기존처럼 DB에 자동 생성·저장, 하위 호환 유지).
- `app/services/request_processor.py`, `app/main.py`, `app/templates/request_new.html`:
  청구인 성명(100자)·연락처(200자)·청구 원문(20,000자) 길이 상한 추가. HTTP 접수는
  FastAPI `Form(max_length=...)`로 즉시 거부, 감시 폴더 자동 접수는 `ingest()`에서 동일
  상한으로 잘라 저장. 폼에는 브라우저 단 `maxlength`도 함께 추가해 사용자가 미리 알 수 있게 함.
- `docs/DEPLOYMENT.md` 신규 작성: 리버스 프록시/TLS 구성 예시, `FOIA_AUTH_COOKIE_SECURE`·
  `FOIA_AUTH_SECRET` 사용법, DB 백업·권한 안내.
- `app/main.py`: 로그인 시도 제한 추가 — 계정당 5회 연속 실패 시 5분간 잠금(`_login_lockout_remaining`/
  `_register_login_failure`/`_register_login_success`). 메모리 기반이라 서버 재시작 시
  초기화되며(단일 프로세스 내부 도구라 이 정도로 충분하다고 판단), 다른 계정에는 영향 없음
  (계정별로 독립 카운트). 잠긴 동안은 올바른 비밀번호를 넣어도 429로 거부.
- 검증: `python -m compileall app` 통과. 위 항목들은 로직 변경 범위가 작아(권한 설정,
  환경변수 우선순위, Form 검증 파라미터 추가) 기존 동작을 깨지 않음.

## 4. 앞으로 해야 할 일 (제안 우선순위)

### 우선순위 1 — 실배포 전 필수
1. ~~로그인 시도 제한/계정 잠금 추가~~ — 완료(계정당 5회 실패 시 5분 잠금, 3절 참고)
2. 기본 데모 계정 비밀번호 변경 유도 — 최초 로그인 시 강제 변경 화면 또는 최소한 대시보드
   경고 배너
3. ~~`/admin/users` 계정 생성 비밀번호 최소 길이를 `/setup`과 동일하게 8자 이상으로 통일~~ —
   완료(FOIA-0013, 계정 수정 기능 추가하며 같이 정리)

### 우선순위 2 — 안정성/유지보수성
4. ~~핵심 로직에 최소한의 단위 테스트 추가~~ — 완료(FOIA-0020, 현재 `tests/` 41개: 인증/잠금,
   역할별 접근 통제, 배정·거절·재배정·판단 흐름, 계정 관리, CSRF 검증). `foia_core` 내부 함수 단위
   테스트는 아직 없음 — API 레벨 테스트로 간접 커버되는 상태, 필요 시 보강
5. ~~`requirements.txt` 버전 고정~~ — 완료(FOIA-0020, 전부 `==` 고정 + `requirements-dev.txt` 분리)
6. 동기 DB 호출을 `asyncio.to_thread`로 감싸거나, 트래픽 증가 시 SQLite WAL 모드 검토 —
   현재 내부 소수 사용자 규모에서는 체감 영향 없다고 판단해 보류(2026-09-07 재확인)
7. DB 파일 저장 시 암호화(at-rest)와 자동 백업 스케줄링 — 현재는 파일 권한 제한(`0600`)만
   적용됨(`docs/DEPLOYMENT.md` 6절), 연락처(`requester_contact`) 형식 검증 추가

### 우선순위 3 — 기능 확장 (README "알려진 제약사항" 연장선)
8. 실제 PDF/HWPX 원문 파싱 지원 (현재는 텍스트 붙여넣기/자동 수집 `.txt`만 지원)
9. 반복 청구 판정 고도화 검토 (현재 `difflib` 문자열 유사도 → 필요 시 임베딩 기반으로 교체)
10. 공식 KRDS Figma 컴포넌트 라이브러리 인스턴스 적용 여부 확정 (현재는 색상·레이아웃
    토큰 수준의 근사치 — Figma MCP 연결 방법 결정 필요)

### 확정된 향후 계획 (사용자 지시, 2026-09-08)
11. **로그인/계정을 회사 DB와 연동 예정 — 지금은 착수하지 않음.** 지금의 로컬 계정
    (pbkdf2 해싱 + `users` 테이블, `admin`/`manager`/`dispatcher`/`staff1~10` 데모 계정)은
    그 전까지의 임시 구조다. → 그래서 "기본 데모 계정 비밀번호 변경 유도"(우선순위 1의
    2번) 같은 로컬 계정 강화 작업은 지금 진행하지 않는다 — 회사 DB 연동 시 계정 모델
    자체가 바뀌므로 그 위에 쌓을 이유가 없다.
12. **업무담당자 배정 추천을 LLM과 GradientBoost 두 엔진으로 시도(FOIA-0028, 착수함).**
    `/api/requests/{id}/recommend`(예시 5건 조회)는 그대로 두고, "AI로 생성하기"
    (`/generate-recommendation`)가 이제 실제로 두 엔진을 각각 돌려 나란히 보여준다
    (`app/services/recommend/`). GradientBoost(TF-IDF + `GradientBoostingClassifier`)는
    실제로 동작 — 다만 실제 배정 이력이 아직 거의 없어(10건) 부서별 전형적인 청구 문구로
    만든 합성 데이터로 학습했다(`app/services/recommend/synthetic_data.py`,
    `tools/train_gbm_recommender.py`). 회사 DB 연동으로 실제 배정 이력이 쌓이면 그
    데이터로 재학습해야 한다. LLM은 인터페이스만 구축(어떤 공급자를 쓸지, API 키 관리,
    청구인 개인정보의 외부 전송 여부가 아직 미정이라 항상 "준비 중"을 반환,
    `app/services/recommend/llm_recommender.py`의 TODO가 실제 연동 지점).
    요청대상 추출·반복청구 판정 같은 나머지 AI 기능은 이번 범위 밖 — 여전히 데모.
    `data/training/staff_assignments.csv`(개인정보라 `.gitignore` 처리됨)를 채우면
    실제 이력으로 재학습 가능(FOIA-0030, `data/training/README.md` 참고).

### AI 코드 점검에서 발견, 보류 (사용자 지시, 2026-09-08)
13. `app/ai_runtime/api.py`가 `/identify` 호출마다 청구인 원문 전체를
    `data/ai_log.jsonl`에 무기한 누적한다. `.gitignore`로 GitHub 유출은 막혀 있지만,
    로컬 디스크에 개인정보가 로테이션 없이 계속 쌓이는 구조 — 보존 기간 정책이나
    주기적 삭제/로테이션 검토 필요.
14. `find_repeat_candidate`(`app/ai_runtime/utils_text.py`)가 신규 접수마다 최근
    500건(`db.recent_raw_texts`)과 `difflib.SequenceMatcher`로 전수 비교한다. 지금
    규모에서는 문제없지만 물량이 늘면 접수 지연 요인이 될 수 있다 — 9번(임베딩 기반
    전환) 검토 시 같이 해결될 가능성 높음.
15. `app/static/js/app.js`의 `renderEngineComparison`/`renderRecommendations`가 담당자
    이름을 `onclick` 문자열에 직접 끼워 넣는다(예: `onclick="assignRequestTo(${id},
    '${name}')"`). 지금은 이름이 항상 `staffN` 패턴이라 위험은 없지만, FOIA-0022에서
    담당자 검색 결과만 더 안전한 `data-*` 속성 + `escapeHtml` 방식으로 바꿔놓은 것과
    일관성이 안 맞음 — 통일 검토.

## 5. 참고
- 개발 서버가 이전 세션부터 `http://127.0.0.1:8000`에서 계속 실행 중입니다. 이 점검·문서화
  작업 자체에는 영향이 없으나, 더 이상 필요 없으면 종료 요청해주세요.

## 6. 역할별 화면 점검 (2026-09-07 추가)

보안 점검과 별개로, 4개 역할(시스템관리자/총괄관리자/배정담당자/업무담당자)이 실제 업무에
필요한 기능을 화면이 제공하는지 재점검했다. 상세 근거는 `logs/changes/2026-09-07/FOIA-0009-*.md`,
현재 진행 중인 이후 티켓 참고.

| 역할 | 발견한 공백 | 상태 |
|---|---|---|
| 업무담당자 | 잘못 배정된 청구를 되돌릴 방법이 없음 | ✅ 완료 — "거절(재배정 후보 1~3명 지명)" 기능 추가(FOIA-0009) |
| 총괄관리자/배정담당자 | 이미 배정된 건을 담당자 동의 없이 재배정할 방법이 없음 | ✅ 완료 — `/requests/{id}`에 "담당자 재배정" 패널 추가, `POST /api/requests/{id}/assign`이 이미 배정된 건도 처리하도록 확장 |
| 업무담당자 | 새로 배정돼도 알림이 없음(SSE가 총괄관리자 전용) | ✅ 완료 — "내 업무" 화면에서 20초 간격 폴링으로 새 배정을 감지해 토스트 알림(FOIA-0013). 실시간 SSE/웹소켓이 아니라 기존 대시보드와 동일한 폴링 방식 |
| 업무담당자 | 법정 처리기한(원칙 10일) 표시가 전혀 없음 | ✅ 완료 — 접수일+10일(연장 시 +10일 추가) 기준 D-day를 목록/배정 대기/상세/대시보드에 표시, 연장(+10일, 1회 한정) 기능 추가(FOIA-0011) |
| 업무담당자 | 판단 완료 후 통지서를 실제로 내보낼 방법이 없음(화면 텍스트뿐) | ✅ 완료 — `/requests/{id}/notice` 인쇄용 문서 화면 추가, 브라우저 인쇄→PDF 저장으로 산출물 생성(FOIA-0012) |
| 시스템관리자 | 계정 수정(역할/소속/비밀번호 변경) 기능이 없음, 생성·삭제만 가능 | ✅ 완료 — `/admin/users/{id}/edit` 신규(아이디는 참조 무결성 때문에 변경 불가), 마지막 시스템관리자 역할 변경 방지, 비밀번호는 비워두면 유지(FOIA-0013) |
| 배정담당자 | `/requests` 목록/검색 접근이 막혀있어 과거 이력을 찾을 방법이 제한적 | ✅ 완료 — 전체 목록 대신 `/requester-history`로 청구인 이름 정확 일치 검색만 허용(원문·요청대상 전체검색은 계속 차단). `/dispatch` 카드·상세 화면에 바로가기 링크 추가(FOIA-0014) |
