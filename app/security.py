"""인증(누구인지)과 인가(뭘 할 수 있는지) 관련 로직을 한 곳에 모은다.

세션 쿠키 서명·검증, 비밀번호 해싱, 로그인 무차별 대입 방어, 역할 기반 라우트 가드가
전부 여기 있다. `app/routers/auth.py`(로그인 화면 라우트)와 이름이 겹치지 않도록
모듈명은 `security`로 뒀다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse

from .deps import ROLE_HOME, db

AUTH_COOKIE_NAME = 'foia_session'
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
AUTH_COOKIE_SECURE = os.getenv('FOIA_AUTH_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
PUBLIC_PATH_PREFIXES = ('/static/',)
PUBLIC_PATHS = {'/health', '/favicon.ico', '/login', '/setup'}

# 로그인 무차별 대입 방어. 단일 프로세스(uvicorn 워커 1개) 전제의 메모리 기반 구현이라
# 서버 재시작 시 초기화된다 — 내부 소수 사용자용 도구라 이 정도로 충분하다고 판단.
# 여러 워커/여러 서버 인스턴스로 확장한다면 DB나 공유 캐시로 옮겨야 한다.
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECONDS = 300
_login_attempts: dict[str, dict[str, float]] = {}


def auth_secret() -> str:
    # DB 파일 하나에 비밀번호 해시 + 개인정보 + 세션 서명키가 모두 몰리는 것을 피하고
    # 싶다면 배포 시 FOIA_AUTH_SECRET 환경변수로 직접 주입할 수 있다(비밀 관리 도구 연동용).
    # 미설정 시엔 기존처럼 최초 실행 때 자동 생성해 DB에 저장한다(하위 호환).
    env_secret = os.getenv('FOIA_AUTH_SECRET', '').strip()
    if env_secret:
        return env_secret
    secret = db.get_setting('auth_secret', '')
    if not secret:
        secret = secrets.token_urlsafe(48)
        db.set_setting('auth_secret', secret)
    return secret


def admin_configured() -> bool:
    return db.any_user_exists()


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode("ascii")}'


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, digest_text = stored_hash.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        iterations = int(iterations_text)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), iterations)
        return hmac.compare_digest(base64.b64encode(digest).decode('ascii'), digest_text)
    except Exception:
        return False


def login_lockout_remaining(username: str) -> int:
    """이 계정이 잠겨 있으면 남은 초, 아니면 0."""
    entry = _login_attempts.get(username)
    if not entry:
        return 0
    remaining = entry.get('locked_until', 0) - time.time()
    return max(0, int(remaining))


def register_login_failure(username: str) -> None:
    entry = _login_attempts.setdefault(username, {'count': 0, 'locked_until': 0})
    entry['count'] += 1
    if entry['count'] >= _LOGIN_MAX_ATTEMPTS:
        entry['locked_until'] = time.time() + _LOGIN_LOCKOUT_SECONDS
        entry['count'] = 0


def register_login_success(username: str) -> None:
    _login_attempts.pop(username, None)


def sign_session(username: str, expires_at: int) -> str:
    payload = f'{username}|{expires_at}'
    sig = hmac.new(auth_secret().encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    token = f'{payload}|{sig}'.encode('utf-8')
    return base64.urlsafe_b64encode(token).decode('ascii')


def read_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode('ascii')).decode('utf-8')
        username, expires_text, sig = decoded.rsplit('|', 2)
        expires_at = int(expires_text)
        if expires_at < int(time.time()):
            return None
        expected = hmac.new(
            auth_secret().encode('utf-8'),
            f'{username}|{expires_at}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        if db.get_user(username) is None:
            return None
        return username
    except Exception:
        return None


def is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def safe_next_path(next_path: str | None) -> str:
    if not next_path:
        return '/'
    next_path = next_path.strip()
    if (
        not next_path.startswith('/')
        or next_path.startswith('//')
        or '\\' in next_path
        or any(ord(ch) < 32 for ch in next_path)
    ):
        return '/'
    return next_path


def set_auth_cookie(response: RedirectResponse, username: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        sign_session(username, int(time.time()) + SESSION_MAX_AGE_SECONDS),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite='strict',
    )


def role_home(role: str | None) -> str:
    return ROLE_HOME.get(role, '/login')


def require_role(request: Request, *roles: str):
    """페이지 라우트 권한 가드. 통과하면 None, 막히면 자기 홈으로 리다이렉트."""
    if request.state.auth_role not in roles:
        return RedirectResponse(role_home(request.state.auth_role), status_code=303)
    return None


def require_role_api(request: Request, *roles: str):
    """API 라우트 권한 가드. 통과하면 None, 막히면 403 JSON."""
    if request.state.auth_role not in roles:
        return JSONResponse({'success': False, 'message': '권한이 없습니다.'}, status_code=403)
    return None


async def read_json_body(request: Request) -> dict | None:
    """POST 바디를 JSON으로 파싱한다. 잘못된 형식(비어있음, 깨진 인코딩 등)이면 예외를
    올리지 않고 None을 반환 — 호출부에서 500 대신 깔끔한 400으로 응답하게 한다."""
    try:
        data = await request.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None
