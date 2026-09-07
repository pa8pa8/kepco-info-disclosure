# 배포 가이드 (외부 접근·DB 보호)

이 문서는 `docs/PROJECT_REVIEW.md`에서 지적한 "외부에서 접근" 항목의 후속
조치입니다. 로컬 1인 실행(`실행.bat`/`launcher.py`)이 아니라 **여러 사용자가 접속하는
서버로 올릴 때** 반드시 확인해야 할 것들을 정리했습니다.

## 1. 기본 바인딩은 로컬 전용이다

`launcher.py`는 `host='127.0.0.1'`로만 바인딩합니다. 즉 **아무 설정도 하지 않으면 같은
PC 밖에서는 접근이 아예 불가능**합니다. 이는 의도된 안전한 기본값입니다.

## 2. 여러 사용자가 접속해야 한다면 — 반드시 리버스 프록시 뒤에 둘 것

이 애플리케이션 자체는 TLS(HTTPS)를 처리하지 않습니다. 사내 서버에서 여러 직원이
접속하게 하려면 nginx/IIS 같은 리버스 프록시를 앞에 두고 프록시에서 TLS를 종료해야
합니다.

nginx 예시:
```nginx
server {
    listen 443 ssl;
    server_name foia.internal.kepco.example;

    ssl_certificate     /etc/ssl/certs/foia.crt;
    ssl_certificate_key /etc/ssl/private/foia.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

프록시를 앞에 두면 반드시 다음 환경변수도 함께 설정하세요:
```
FOIA_AUTH_COOKIE_SECURE=1
```
이걸 켜지 않으면 세션 쿠키에 `Secure` 플래그가 빠져, HTTPS 환경에서도 쿠키가 평문
HTTP로도 전송될 수 있습니다.

## 3. 세션 서명키(auth_secret)를 DB 바깥에서 관리하고 싶다면

기본값은 최초 실행 시 자동 생성돼 DB(`app_settings` 테이블)에 저장됩니다. DB 파일
하나에 개인정보·비밀번호 해시·서명키가 모두 몰리는 게 싫다면, 배포 시 아래처럼
비밀 관리 도구(예: Vault, 환경변수 주입)로 직접 값을 넣어줄 수 있습니다.
```
FOIA_AUTH_SECRET=<32바이트 이상의 무작위 문자열>
```
설정하면 DB에 저장된 값 대신 이 값을 우선 사용합니다(`app/main.py`의 `_auth_secret()`).

## 4. DB 파일 보호

- `data/info_disclosure.db`에는 비밀번호 해시, 세션 서명키, 청구인 개인정보(이름·연락처)가
  모두 들어 있습니다. 서버 프로세스 시작 시 자동으로 파일 권한을 `0600`(소유자만
  읽기/쓰기)으로 좁히도록 처리했습니다(`app/db.py: _restrict_file_permissions`).
  단, **Windows는 POSIX 권한 비트를 그대로 쓰지 않아 완전히 제한되지 않습니다** — Windows
  서버에 배포한다면 `icacls`로 별도 ACL을 설정하세요.
- 정기 백업 절차는 아직 없습니다. 최소한 `data/info_disclosure.db`를 주기적으로(예: 매일)
  별도 위치에 복사하고, 백업 파일에도 동일한 권한 제한을 적용하세요.

## 5. 입력 크기 제한

청구인 성명(100자)·연락처(200자)·청구 내용(20,000자)에 서버 단 상한을 뒀습니다
(`RequestProcessorService.ingest()`에서 감시 폴더 자동 접수 시 이 상한으로 잘라 저장 —
수동 접수 폼은 더 이상 없으므로 이 경로가 유일한 접수 지점입니다). 더 긴 청구가 실제로
필요하면 `app/services/request_processor.py`의 `MAX_RAW_TEXT_LEN` 등을 조정하세요.

이미 구현됨(참고용): 로그인 시도 제한/계정 잠금(계정당 5회 실패 시 5분) —
`docs/PROJECT_REVIEW.md` 참고.

## 6. 아직 안 한 것 (별도 작업 필요)

- DB 파일 자체의 저장 시 암호화(at-rest encryption) — 현재는 파일 권한 제한만 적용
- 자동 백업 스케줄링
