# 변경 기록

- 일시: 2026-09-07 13:42
- 작성자: cshs1729
- 작업번호: FOIA-0007
- 변경 유형: fix
- 상태: reviewed

## 변경 요약
FOIA-0006 점검 결과 중 사용자가 추가로 지목한 "DB/입출력/외부 접근" 3개 영역을 더 파고들어
발견한 이슈(DB 파일에 리스크 집중, 입력 길이 제한 없음, 배포 가이드 부재)를 실제로 수정.

## 변경 내용
- `app/db.py`: `Database.__init__()` 마지막 단계에 `_restrict_file_permissions()` 추가 —
  서버 시작 시 DB 파일 권한을 `0600`(소유자 전용)으로 제한(`os.chmod`, 실패해도 무시).
  Windows는 POSIX 권한 비트를 그대로 쓰지 않아 완전히 제한되지는 않음을 확인(격리
  환경에서 재현: chmod 후에도 `ls -la` 상 644로 보임, 예외는 발생하지 않음 — 코드의
  try/except OSError로 이미 대비된 동작이며 Linux 배포 시에는 실제로 동작).
- `app/main.py`: `_auth_secret()`이 `FOIA_AUTH_SECRET` 환경변수를 최우선으로 사용하도록
  변경(미설정 시 기존처럼 DB에 자동 생성·저장, 하위 호환 유지) — DB 파일 하나가 유출돼도
  세션 위조 키까지 같이 새지 않도록 별도 관리할 수 있는 경로 제공.
- `app/services/request_processor.py`: `MAX_NAME_LEN`(100)/`MAX_CONTACT_LEN`(200)/
  `MAX_RAW_TEXT_LEN`(20000) 상수 추가, `ingest()`에서 세 값을 해당 길이로 잘라 저장 —
  HTTP 접수와 감시 폴더 자동 접수 양쪽 경로 모두에 적용됨.
- `app/main.py`: `/requests/new` 라우트의 `requester_name`/`requester_contact`/`raw_text`
  Form 파라미터에 `max_length` 추가 — 상한 초과 시 422로 즉시 거부(폼까지 안 감).
- `app/templates/request_new.html`: 위와 동일한 상한을 `maxlength` 속성으로 추가해
  브라우저 단에서도 사용자가 미리 인지하도록 함.
- `docs/DEPLOYMENT.md` 신규 작성: 리버스 프록시(nginx 예시)+TLS 종료 구성,
  `FOIA_AUTH_COOKIE_SECURE`/`FOIA_AUTH_SECRET` 사용법, DB 파일 보호·백업 안내, 아직
  안 한 것(로그인 잠금, at-rest 암호화, 자동 백업) 목록.
- `README.md`: 환경변수 절에 `FOIA_AUTH_SECRET` 추가 및 `docs/DEPLOYMENT.md` 링크.
- `docs/PROJECT_REVIEW_2026-09-07.md`: DB/입출력/외부 접근 3개 항목을 이슈 표에 추가하고
  이번에 수정한 항목은 "완료"로 표시, 우선순위 목록에 잔여 항목(at-rest 암호화, 자동
  백업, 연락처 형식 검증) 추가.

## 원인
사용자가 "DB와 입출력, 외부에서 접근 이런걸 따지면 어때?"로 점검 범위를 구체화 요청 →
확인 결과 DB 파일 권한(644)에 비밀번호 해시·세션 서명키·개인정보가 함께 저장되는 구조적
리스크와 입력 길이 무제한 문제를 발견, "다 해줘"로 문서화+수정 둘 다 승인받아 진행.

## 검증
- 확인 방법: `python -m compileall app` 통과. 격리 환경(별도 포트 8098, 별도 DB 파일)에서
  서버 기동 후 (1) DB 파일 생성 및 권한 적용 코드가 예외 없이 실행되는지, (2) dispatcher
  로그인 후 25,000자짜리 `raw_text`로 `/requests/new` 제출 시 422 거부되는지, (3) 정상
  범위 제출은 303으로 성공하는지 curl로 확인.
- 결과: 셋 다 기대대로 동작. 서버 로그에 예외 없음.

## 리스크
- 영향 범위: 기존에 떠 있는 개발 서버(launcher.py, 포트 8000)는 이번 변경 전 코드로
  이미 기동돼 있어 재시작 전까지는 이번 수정(DB 권한/길이 제한/시크릿 우선순위)이
  적용되지 않음.
- 주의사항: 길이 상한(성명 100/연락처 200/원문 20,000자)이 실제 업무에 너무 빡빡하면
  `request_processor.py`의 상수와 `main.py`의 `max_length`, 템플릿의 `maxlength`
  세 곳을 함께 조정해야 함(현재 하드코딩, 설정값화되어 있지 않음).

## 다음 조치
- 후속 작업: 사용자에게 기존 개발 서버(8000) 재시작 필요 여부 확인. `docs/PROJECT_REVIEW_2026-09-07.md`
  4절에 남은 항목(로그인 잠금, at-rest 암호화, 자동 백업, 연락처 형식 검증) 우선순위 논의.
