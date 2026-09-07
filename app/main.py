from __future__ import annotations

from contextlib import asynccontextmanager

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import quote

from fastapi import FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import AI_RESULTS_DIR, APP_TITLE, INTERNAL_AI_API_URL, RESOURCE_DIR
from .db import Database, ROLES
from .services import foia_core
from .services.ai_client import AIClient
from .services.local_ai_server import LocalAIServer
from .services.request_processor import RequestProcessorService


db = Database()
ai_client = AIClient()
processor = RequestProcessorService(db=db, ai_client=ai_client)
local_ai_server = LocalAIServer()


# 업무담당자 예시 계정의 소속(1차사업소=지역본부 / 2차사업소=지사 / 부서).
# 담당자 배정 검색 UI에서 이 정보로 필터링할 수 있다.
STAFF_ORG = [
    ('서울지역본부', '강남지사', '정보공개팀'),
    ('서울지역본부', '종로지사', '정보공개팀'),
    ('경기지역본부', '수원지사', '고객지원팀'),
    ('경기지역본부', '성남지사', '고객지원팀'),
    ('인천지역본부', '인천지사', '정보공개팀'),
    ('강원지역본부', '춘천지사', '총무팀'),
    ('충북지역본부', '청주지사', '감사팀'),
    ('대전세종충남지역본부', '대전지사', '정보공개팀'),
    ('전북지역본부', '전주지사', '총무팀'),
    ('부산울산지역본부', '부산지사', '고객지원팀'),
]

DEFAULT_ACCOUNTS = [
    ('admin', 'admin', '시스템관리자', '', '', ''),
    ('manager', 'manager', '총괄관리자', '', '', ''),
    ('dispatcher', 'dispatcher', '배정담당자', '', '', ''),
] + [
    (f'staff{i}', f'staff{i}', '업무담당자', *STAFF_ORG[i - 1])
    for i in range(1, 11)
]

ROLE_HOME = {
    '시스템관리자': '/admin/users',
    '총괄관리자': '/',
    '배정담당자': '/dispatch',
    '업무담당자': '/requests',
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 계정별로 없을 때만 생성 — 기존 계정 비밀번호는 건드리지 않고, 새로 추가된
    # 기본 계정(예: staff1~staff10)만 다음 실행 시 자동으로 채워지도록 한다.
    for username, password, role, region, branch, department in DEFAULT_ACCOUNTS:
        if db.get_user(username) is None:
            db.create_user(username, _hash_password(password), role, region, branch, department)
    db.set_setting('ai_api_url', INTERNAL_AI_API_URL)
    try:
        await asyncio.to_thread(local_ai_server.start)
    except Exception as exc:
        print(f'[local-ai] failed to start: {exc}')

    interval = int(db.get_setting('scan_interval', '60') or '60')
    await processor.start(interval)
    try:
        yield
    finally:
        await processor.stop()
        await asyncio.to_thread(local_ai_server.stop)


app = FastAPI(title=APP_TITLE, lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(RESOURCE_DIR / 'app' / 'static')), name='static')
templates = Jinja2Templates(directory=str(RESOURCE_DIR / 'app' / 'templates'))

AUTH_COOKIE_NAME = 'foia_session'
SESSION_MAX_AGE_SECONDS = 60 * 60 * 12
AUTH_COOKIE_SECURE = os.getenv('FOIA_AUTH_COOKIE_SECURE', '').lower() in ('1', 'true', 'yes')
PUBLIC_PATH_PREFIXES = ('/static/',)
PUBLIC_PATHS = {'/health', '/favicon.ico', '/login', '/setup'}


def _auth_secret() -> str:
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


def _admin_configured() -> bool:
    return db.any_user_exists()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    iterations = 260_000
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), iterations)
    return f'pbkdf2_sha256${iterations}${salt}${base64.b64encode(digest).decode("ascii")}'


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, digest_text = stored_hash.split('$', 3)
        if algorithm != 'pbkdf2_sha256':
            return False
        iterations = int(iterations_text)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('ascii'), iterations)
        return hmac.compare_digest(base64.b64encode(digest).decode('ascii'), digest_text)
    except Exception:
        return False


# 로그인 무차별 대입 방어. 단일 프로세스(uvicorn 워커 1개) 전제의 메모리 기반 구현이라
# 서버 재시작 시 초기화된다 — 내부 소수 사용자용 도구라 이 정도로 충분하다고 판단.
# 여러 워커/여러 서버 인스턴스로 확장한다면 DB나 공유 캐시로 옮겨야 한다.
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_LOCKOUT_SECONDS = 300
_login_attempts: dict[str, dict[str, float]] = {}


def _login_lockout_remaining(username: str) -> int:
    """이 계정이 잠겨 있으면 남은 초, 아니면 0."""
    entry = _login_attempts.get(username)
    if not entry:
        return 0
    remaining = entry.get('locked_until', 0) - time.time()
    return max(0, int(remaining))


def _register_login_failure(username: str) -> None:
    entry = _login_attempts.setdefault(username, {'count': 0, 'locked_until': 0})
    entry['count'] += 1
    if entry['count'] >= _LOGIN_MAX_ATTEMPTS:
        entry['locked_until'] = time.time() + _LOGIN_LOCKOUT_SECONDS
        entry['count'] = 0


def _register_login_success(username: str) -> None:
    _login_attempts.pop(username, None)


def _sign_session(username: str, expires_at: int) -> str:
    payload = f'{username}|{expires_at}'
    sig = hmac.new(_auth_secret().encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    token = f'{payload}|{sig}'.encode('utf-8')
    return base64.urlsafe_b64encode(token).decode('ascii')


def _read_session(token: str | None) -> str | None:
    if not token:
        return None
    try:
        decoded = base64.urlsafe_b64decode(token.encode('ascii')).decode('utf-8')
        username, expires_text, sig = decoded.rsplit('|', 2)
        expires_at = int(expires_text)
        if expires_at < int(time.time()):
            return None
        expected = hmac.new(
            _auth_secret().encode('utf-8'),
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


def _is_public_path(path: str) -> bool:
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def _safe_next_path(next_path: str | None) -> str:
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


def _set_auth_cookie(response: RedirectResponse, username: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        _sign_session(username, int(time.time()) + SESSION_MAX_AGE_SECONDS),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite='strict',
    )


def _role_home(role: str | None) -> str:
    return ROLE_HOME.get(role, '/login')


def _require_role(request: Request, *roles: str):
    """페이지 라우트 권한 가드. 통과하면 None, 막히면 자기 홈으로 리다이렉트."""
    if request.state.auth_role not in roles:
        return RedirectResponse(_role_home(request.state.auth_role), status_code=303)
    return None


def _require_role_api(request: Request, *roles: str):
    """API 라우트 권한 가드. 통과하면 None, 막히면 403 JSON."""
    if request.state.auth_role not in roles:
        return JSONResponse({'success': False, 'message': '권한이 없습니다.'}, status_code=403)
    return None


@app.middleware('http')
async def require_authentication(request: Request, call_next):
    path = request.url.path
    request.state.auth_user = _read_session(request.cookies.get(AUTH_COOKIE_NAME))
    request.state.auth_role = None
    if request.state.auth_user:
        user_row = db.get_user(request.state.auth_user)
        request.state.auth_role = user_row['role'] if user_row else None

    if not _admin_configured() and path != '/setup' and not path.startswith('/static/'):
        if path.startswith('/api/'):
            return JSONResponse({'success': False, 'error': 'ADMIN_SETUP_REQUIRED'}, status_code=403)
        return RedirectResponse('/setup', status_code=303)

    if _admin_configured() and not request.state.auth_user and not _is_public_path(path):
        if path.startswith('/api/'):
            return JSONResponse({'success': False, 'error': 'AUTH_REQUIRED'}, status_code=401)
        return RedirectResponse(f'/login?next={quote(str(request.url.path))}', status_code=303)

    return await call_next(request)


def current_settings() -> dict[str, str]:
    settings = db.get_all_settings()
    if not (settings.get('ai_api_url') or '').strip():
        settings['ai_api_url'] = INTERNAL_AI_API_URL
    settings['internal_ai_api_url'] = INTERNAL_AI_API_URL
    return settings


@app.get('/setup', response_class=HTMLResponse)
async def setup_page(request: Request):
    if _admin_configured():
        return RedirectResponse('/login', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='auth_setup.html',
        context={'request': request, 'title': '계정 생성', 'error': ''},
    )


@app.post('/setup')
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    if _admin_configured():
        return RedirectResponse('/login', status_code=303)
    username = username.strip()
    error = ''
    if len(username) < 3:
        error = '아이디는 3자 이상으로 입력해주세요.'
    elif len(password) < 8:
        error = '비밀번호는 8자 이상으로 입력해주세요.'
    elif password != password_confirm:
        error = '비밀번호 확인이 일치하지 않습니다.'
    if error:
        return templates.TemplateResponse(
            request=request,
            name='auth_setup.html',
            context={'request': request, 'title': '계정 생성', 'error': error, 'username': username},
            status_code=400,
        )

    db.create_user(username, _hash_password(password), '시스템관리자')
    response = RedirectResponse(_role_home('시스템관리자'), status_code=303)
    _set_auth_cookie(response, username)
    return response


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request, next: str = '/'):
    if not _admin_configured():
        return RedirectResponse('/setup', status_code=303)
    if request.state.auth_user:
        target = _safe_next_path(next)
        if target == '/':
            target = _role_home(request.state.auth_role)
        return RedirectResponse(target, status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='auth_login.html',
        context={'request': request, 'title': '로그인', 'error': '', 'next': _safe_next_path(next)},
    )


@app.post('/login')
async def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form('/')):
    username = username.strip()
    locked_seconds = _login_lockout_remaining(username)
    if locked_seconds > 0:
        return templates.TemplateResponse(
            request=request,
            name='auth_login.html',
            context={
                'request': request, 'title': '로그인',
                'error': f'로그인 시도가 너무 많아 계정이 잠겼습니다. {locked_seconds}초 후 다시 시도해주세요.',
                'next': _safe_next_path(next),
            },
            status_code=429,
        )
    user_row = db.get_user(username)
    if user_row is None or not _verify_password(password, user_row['password_hash']):
        _register_login_failure(username)
        return templates.TemplateResponse(
            request=request,
            name='auth_login.html',
            context={'request': request, 'title': '로그인', 'error': '아이디 또는 비밀번호가 올바르지 않습니다.', 'next': _safe_next_path(next)},
            status_code=401,
        )
    _register_login_success(username)
    target = _safe_next_path(next)
    if target == '/':
        target = _role_home(user_row['role'])
    response = RedirectResponse(target, status_code=303)
    _set_auth_cookie(response, username)
    return response


@app.post('/logout')
async def logout():
    response = RedirectResponse('/login', status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response


# ── Pages ──────────────────────────────────────────────────────────

@app.get('/', response_class=HTMLResponse)
async def dashboard(request: Request):
    guard = _require_role(request, '총괄관리자')
    if guard:
        return guard
    settings = current_settings()
    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'ai_enabled': AIClient.is_enabled(settings.get('ai_api_url', INTERNAL_AI_API_URL)),
        },
    )


@app.get('/requests', response_class=HTMLResponse)
async def request_list(
    request: Request,
    q: str = '',
    status: str = '',
    notice_type: str = '',
):
    guard = _require_role(request, '총괄관리자', '업무담당자')
    if guard:
        return guard
    role = request.state.auth_role
    assigned_to = request.state.auth_user if role == '업무담당자' else None
    rows = [_with_deadline(dict(r)) for r in db.list_requests(status=status, notice_type=notice_type, q=q, assigned_to=assigned_to)]
    return templates.TemplateResponse(
        request=request,
        name='requests.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'requests': rows,
            'filters': {'q': q, 'status': status, 'notice_type': notice_type},
            'notice_labels': foia_core.NOTICE_LABELS,
            'notice_tone': foia_core.NOTICE_TONE,
            'is_my_queue': role == '업무담당자',
        },
    )


@app.get('/requests/{request_id}', response_class=HTMLResponse)
async def request_detail(request: Request, request_id: int):
    guard = _require_role(request, '총괄관리자', '배정담당자', '업무담당자')
    if guard:
        return guard
    role = request.state.auth_role
    row = db.get_request(request_id)
    if not row:
        return RedirectResponse(_role_home(role), status_code=303)
    if role == '업무담당자' and row['assigned_to'] != request.state.auth_user:
        return RedirectResponse('/requests', status_code=303)

    decision = db.get_decision(request_id)
    trail = foia_core.build_trail(decision)
    current_step = decision['current_step'] if decision and decision['current_step'] else None
    is_finalized = bool(decision and decision['final_notice_type'])
    step_info = foia_core.get_step(current_step) if current_step and not is_finalized else None
    hints = json.loads(row['ai_hints_json']) if row['ai_hints_json'] else {}
    log_rows = db.get_decision_log(request_id)
    repeat_match_row = None
    if decision and decision['repeat_match_request_id']:
        repeat_match_row = db.get_request(decision['repeat_match_request_id'])

    can_decide = (not is_finalized) and (
        role == '총괄관리자' or (role == '업무담당자' and row['assigned_to'] == request.state.auth_user)
    )
    can_assign = (not is_finalized) and role in ('배정담당자', '총괄관리자') and not row['assigned_to']
    can_reject = (not is_finalized) and role == '업무담당자' and row['assigned_to'] == request.state.auth_user
    can_reassign = (not is_finalized) and role in ('배정담당자', '총괄관리자') and bool(row['assigned_to'])
    deadline_info = foia_core.compute_deadline_info(row['received_at'], bool(row['deadline_extended']), is_finalized)
    can_extend = can_decide and not row['deadline_extended']
    staff_directory = [dict(r) for r in db.list_directory_by_role('업무담당자')] if (can_assign or can_reject or can_reassign) else []
    if can_reject:
        staff_directory = [s for s in staff_directory if s['username'] != request.state.auth_user]
    elif can_reassign:
        staff_directory = [s for s in staff_directory if s['username'] != row['assigned_to']]
    ai_result = _load_recommendation(row) if can_assign else None

    return templates.TemplateResponse(
        request=request,
        name='request_detail.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'item': row,
            'decision': decision,
            'trail': trail,
            'step_key': current_step,
            'step_info': step_info,
            'hints': hints,
            'log_rows': log_rows,
            'notice_labels': foia_core.NOTICE_LABELS,
            'notice_tone': foia_core.NOTICE_TONE,
            'repeat_match_row': repeat_match_row,
            'can_decide': can_decide,
            'can_assign': can_assign,
            'can_reject': can_reject,
            'can_reassign': can_reassign,
            'deadline_info': deadline_info,
            'can_extend': can_extend,
            'staff_directory': staff_directory,
            'ai_result': ai_result,
        },
    )


@app.get('/requests/{request_id}/notice', response_class=HTMLResponse)
async def request_notice(request: Request, request_id: int):
    """인쇄/저장용 통지서 화면. 화면에 텍스트로만 남아있던 `notice_text`를 실제로
    청구인에게 발송할 수 있는 문서 형태로 보여준다 — 브라우저 인쇄(Ctrl+P) → PDF로
    저장하면 그대로 산출물이 된다. 별도 라이브러리(docx/pdf 생성) 없이 구현해
    "10년 전 서버에서도 최소 의존성으로 동작"이라는 프로젝트 원칙을 지킨다."""
    guard = _require_role(request, '총괄관리자', '배정담당자', '업무담당자')
    if guard:
        return guard
    role = request.state.auth_role
    row = db.get_request(request_id)
    if not row:
        return RedirectResponse(_role_home(role), status_code=303)
    if role == '업무담당자' and row['assigned_to'] != request.state.auth_user:
        return RedirectResponse('/requests', status_code=303)

    decision = db.get_decision(request_id)
    if not decision or not decision['final_notice_type']:
        return RedirectResponse(f'/requests/{request_id}', status_code=303)

    return templates.TemplateResponse(
        request=request,
        name='notice_print.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'item': row,
            'decision': decision,
            'notice_labels': foia_core.NOTICE_LABELS,
            'today': __import__('datetime').date.today().isoformat(),
        },
    )


@app.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request):
    guard = _require_role(request, '총괄관리자')
    if guard:
        return guard
    settings = current_settings()
    return templates.TemplateResponse(
        request=request,
        name='settings.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'settings': settings,
            'notice_labels_pairs': list(foia_core.NOTICE_LABELS.items()),
        },
    )


@app.post('/settings/general')
async def update_settings(request: Request, watch_dir: str = Form(...), scan_interval: int = Form(60), nondisclosure_keywords: str = Form('')):
    guard = _require_role(request, '총괄관리자')
    if guard:
        return guard
    db.set_setting('watch_dir', watch_dir.strip())
    db.set_setting('ai_api_url', INTERNAL_AI_API_URL)
    db.set_setting('scan_interval', str(scan_interval))
    db.set_setting('nondisclosure_keywords', nondisclosure_keywords.strip())
    return RedirectResponse('/settings?saved=1', status_code=303)


@app.post('/settings/notice-templates')
async def update_notice_templates(request: Request):
    guard = _require_role(request, '총괄관리자')
    if guard:
        return guard
    form = await request.form()
    for notice_type in foia_core.NOTICE_LABELS:
        key = f'notice_template_{notice_type}'
        if key in form:
            db.set_setting(key, str(form[key]).strip())
    return RedirectResponse('/settings?saved=1', status_code=303)


@app.post('/settings/test-ai')
async def test_ai_connection(request: Request, raw_text: str = Form('개인정보 관련 열람 청구 자료 요청드립니다.')):
    guard = _require_role_api(request, '총괄관리자')
    if guard:
        return guard
    payload = {'raw_text': raw_text, 'nondisclosure_keywords': [], 'history': []}
    try:
        result = await ai_client.identify(payload)
        return JSONResponse({'ok': True, 'request': payload, 'response': result})
    except Exception as exc:
        return JSONResponse({'ok': False, 'request': payload, 'error': str(exc)}, status_code=500)


# ── Account management (시스템관리자) ───────────────────────────────

@app.get('/admin/users', response_class=HTMLResponse)
async def admin_users_page(request: Request):
    guard = _require_role(request, '시스템관리자')
    if guard:
        return guard
    return templates.TemplateResponse(
        request=request,
        name='admin_users.html',
        context={'request': request, 'title': APP_TITLE, 'users': db.list_users(), 'roles': ROLES, 'error': ''},
    )


@app.post('/admin/users')
async def admin_users_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    region: str = Form(''),
    branch: str = Form(''),
    department: str = Form(''),
):
    guard = _require_role(request, '시스템관리자')
    if guard:
        return guard
    username = username.strip()
    error = ''
    if len(username) < 3:
        error = '아이디는 3자 이상으로 입력해주세요.'
    elif len(password) < 8:
        error = '비밀번호는 8자 이상으로 입력해주세요.'
    elif role not in ROLES:
        error = '올바른 역할을 선택해주세요.'
    elif db.get_user(username) is not None:
        error = f"이미 존재하는 아이디입니다: {username}"
    if error:
        return templates.TemplateResponse(
            request=request,
            name='admin_users.html',
            context={'request': request, 'title': APP_TITLE, 'users': db.list_users(), 'roles': ROLES, 'error': error},
            status_code=400,
        )
    db.create_user(username, _hash_password(password), role, region.strip(), branch.strip(), department.strip())
    return RedirectResponse('/admin/users?saved=1', status_code=303)


@app.post('/admin/users/{user_id}/delete')
async def admin_users_delete(request: Request, user_id: int):
    guard = _require_role(request, '시스템관리자')
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)
    if target['username'] == request.state.auth_user:
        return RedirectResponse('/admin/users?error=self', status_code=303)
    if target['role'] == '시스템관리자' and db.count_users_by_role('시스템관리자') <= 1:
        return RedirectResponse('/admin/users?error=lastadmin', status_code=303)
    db.delete_user(user_id)
    return RedirectResponse('/admin/users?deleted=1', status_code=303)


@app.get('/admin/users/{user_id}/edit', response_class=HTMLResponse)
async def admin_users_edit_page(request: Request, user_id: int):
    guard = _require_role(request, '시스템관리자')
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='admin_user_edit.html',
        context={'request': request, 'title': APP_TITLE, 'target': target, 'roles': ROLES, 'error': ''},
    )


@app.post('/admin/users/{user_id}/edit')
async def admin_users_edit_submit(
    request: Request,
    user_id: int,
    role: str = Form(...),
    region: str = Form(''),
    branch: str = Form(''),
    department: str = Form(''),
    password: str = Form(''),
):
    guard = _require_role(request, '시스템관리자')
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)

    error = ''
    if role not in ROLES:
        error = '올바른 역할을 선택해주세요.'
    elif password and len(password) < 8:
        error = '비밀번호는 8자 이상으로 입력해주세요(변경하지 않으려면 비워두세요).'
    elif target['role'] == '시스템관리자' and role != '시스템관리자' and db.count_users_by_role('시스템관리자') <= 1:
        error = '마지막 남은 시스템관리자 계정의 역할은 변경할 수 없습니다.'
    if error:
        return templates.TemplateResponse(
            request=request,
            name='admin_user_edit.html',
            context={'request': request, 'title': APP_TITLE, 'target': target, 'roles': ROLES, 'error': error},
            status_code=400,
        )

    password_hash = _hash_password(password) if password else None
    db.update_user(user_id, role, region.strip(), branch.strip(), department.strip(), password_hash)
    return RedirectResponse('/admin/users?saved=1', status_code=303)


# ── Dispatch (배정담당자) ───────────────────────────────────────────

@app.get('/dispatch', response_class=HTMLResponse)
async def dispatch_page(request: Request):
    guard = _require_role(request, '배정담당자')
    if guard:
        return guard
    unassigned = [_with_deadline(dict(r)) for r in db.list_requests(status='판단중', unassigned_only=True)]
    # 이미 예시 결과 파일이 준비된 건은 클릭 없이 바로 보여준다 — 나머지(예시 없는 건)만
    # "AI 판단하기" 버튼을 눌러야 하는 상태로 남는다.
    ai_results = {}
    for r in unassigned:
        result = _load_recommendation(r)
        if result:
            ai_results[r['id']] = result
    recent_assigned = db.list_recently_assigned()
    staff_directory = [dict(r) for r in db.list_directory_by_role('업무담당자')]
    return templates.TemplateResponse(
        request=request,
        name='dispatch.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'unassigned': unassigned,
            'ai_results': ai_results,
            'recent_assigned': recent_assigned,
            'staff_directory': staff_directory,
        },
    )


@app.get('/requester-history', response_class=HTMLResponse)
async def requester_history(request: Request, name: str = ''):
    """배정담당자가 전체 청구 목록(`/requests`)에는 접근하지 못하지만, 배정 판단에
    필요한 최소한의 조회 — "이 청구인이 예전에도 청구한 적 있는지"는 확인할 수 있어야
    한다는 요구로 추가. 이름이 정확히 일치하는 건만 보여주고(부분검색·원문검색 아님),
    빈 검색어로는 아무것도 보여주지 않는다 — 전체 열람으로 악용되지 않도록 하기 위함."""
    guard = _require_role(request, '배정담당자', '총괄관리자')
    if guard:
        return guard
    name = name.strip()
    results = [_with_deadline(dict(r)) for r in db.find_requests_by_requester_name(name)] if name else []
    return templates.TemplateResponse(
        request=request,
        name='requester_history.html',
        context={
            'request': request,
            'title': APP_TITLE,
            'query_name': name,
            'results': results,
            'notice_labels': foia_core.NOTICE_LABELS,
            'notice_tone': foia_core.NOTICE_TONE,
        },
    )


def _with_deadline(row: dict) -> dict:
    """청구 dict에 처리기한 정보(`deadline`)를 계산해 붙여 반환한다. 목록/배정 대기
    화면에서 재사용하기 위한 공통 헬퍼."""
    row['deadline'] = foia_core.compute_deadline_info(
        row.get('received_at'),
        bool(row.get('deadline_extended')),
        bool(row.get('final_notice_type')),
    )
    return row


def _load_ai_recommendation(row) -> dict | None:
    """청구의 접수 파일(`source_file`)과 같은 이름의 예시 결과 파일이
    `AI_RESULTS_DIR`에 있으면 파싱해서 반환하고, 없으면 None.

    실시간 계산이나 무작위 추천이 아니라 사전에 준비된 예시 txt를 그대로 읽는 것뿐이다.
    청구 목록/상세 화면 렌더링과 `/recommend` API가 이 함수 하나를 공유한다.
    """
    source_file = row['source_file']
    if not source_file:
        return None
    result_path = AI_RESULTS_DIR / source_file
    if not result_path.exists():
        return None

    text = result_path.read_text(encoding='utf-8', errors='ignore')
    staff_pool = {r['username'] for r in db.list_usernames_by_role('업무담당자')}
    recommendations: list[str] = []
    reason = ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('사유'):
            reason = line.split(':', 1)[-1].strip() if ':' in line else line
            continue
        match = re.search(r'\b(staff\d+)\b', line)
        if match and match.group(1) in staff_pool and match.group(1) not in recommendations:
            recommendations.append(match.group(1))
    return {'recommendations': recommendations, 'reason': reason, 'source': 'ai'}


def _load_reassign_candidates(row) -> dict | None:
    """업무담당자가 '거절(재배정 요청)'하며 지명한 1~3명이 있으면 반환한다.
    AI 예시 추천과 달리 실제 사람이 지명한 것이라 우선순위가 더 높다(`_load_recommendation`
    참고). 지명된 계정이 그 사이 삭제됐을 수도 있어 현재도 유효한 업무담당자인지 다시 확인한다."""
    raw = row['reassign_candidates_json'] if 'reassign_candidates_json' in row.keys() else None
    if not raw:
        return None
    try:
        candidates = json.loads(raw)
    except (ValueError, TypeError):
        return None
    staff_pool = {r['username'] for r in db.list_usernames_by_role('업무담당자')}
    recommendations = [c for c in candidates if c in staff_pool]
    if not recommendations:
        return None
    return {'recommendations': recommendations, 'reason': '', 'source': 'reassign'}


def _load_recommendation(row) -> dict | None:
    """배정 대기 화면/청구 상세에 보여줄 추천 담당자를 하나로 결정한다.
    업무담당자가 실제로 지명한 재배정 후보가 있으면 그것을 우선하고, 없으면
    사전 준비된 AI 예시 추천으로 대체한다."""
    return _load_reassign_candidates(row) or _load_ai_recommendation(row)


@app.post('/api/requests/{request_id}/recommend')
async def api_recommend(request_id: int, request: Request):
    """AI 판단 결과 조회 — 실시간 계산이나 무작위 추천을 전혀 하지 않는다.
    (배정 대기 화면은 이미 준비된 결과를 페이지 로드 시 바로 보여주고, 이 API는
    아직 표시되지 않은 나머지 건에서 "AI 판단하기"를 눌렀을 때만 호출된다.)
    """
    guard = _require_role_api(request, '배정담당자', '총괄관리자')
    if guard:
        return guard
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    if row['assigned_to']:
        return JSONResponse({'success': False, 'message': '이미 배정된 청구입니다.'}, status_code=409)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구입니다.'}, status_code=409)

    result = _load_ai_recommendation(row)
    if not result:
        return JSONResponse({
            'success': True,
            'has_result': False,
            'message': '이 청구는 아직 AI 판단 예시가 준비되지 않았습니다. "AI로 생성하기" 버튼을 눌러주세요.',
        })
    return JSONResponse({'success': True, 'has_result': True, **result})


@app.post('/api/requests/{request_id}/generate-recommendation')
async def api_generate_recommendation(request_id: int, request: Request):
    """"AI로 생성하기" 버튼 핸들러.

    이 데모에는 실제 생성 로직도, 무작위 추천도 없다 — 예시 결과 파일이 미리
    준비된 5건에 대해서만 판단 결과를 보여줄 수 있다는 점을 그대로 안내한다.
    """
    guard = _require_role_api(request, '배정담당자', '총괄관리자')
    if guard:
        return guard
    return JSONResponse({
        'success': False,
        'message': '이 데모에서는 사전에 준비된 예시 5건에 한해서만 AI 판단 결과를 확인할 수 있습니다. 실제 AI 연동은 추후 적용될 예정입니다.',
    })


@app.post('/api/requests/{request_id}/assign')
async def api_assign(request_id: int, request: Request):
    guard = _require_role_api(request, '배정담당자', '총괄관리자')
    if guard:
        return guard
    data = await request.json()
    assigned_to = (data.get('assigned_to') or '').strip()
    target_user = db.get_user(assigned_to)
    if not target_user or target_user['role'] != '업무담당자':
        return JSONResponse({'success': False, 'message': '유효한 업무담당자를 선택해주세요.'}, status_code=400)
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구는 배정할 수 없습니다.'}, status_code=409)
    previous_assignee = row['assigned_to']
    if previous_assignee == assigned_to:
        return JSONResponse({'success': False, 'message': '이미 해당 담당자에게 배정되어 있습니다.'}, status_code=409)
    if previous_assignee:
        # 이미 배정된 건을 배정담당자/총괄관리자가 담당자 동의 없이 직접 재배정하는 경우.
        # 업무담당자 본인이 거절해 재배정 후보를 지명하는 경로(reject_and_nominate)와는 별개다.
        db.reassign_request(request_id, assigned_to, assigned_by=request.state.auth_user, previous_assignee=previous_assignee)
    else:
        db.assign_request(request_id, assigned_to, assigned_by=request.state.auth_user)
    return JSONResponse({'success': True})


@app.post('/api/requests/{request_id}/reject')
async def api_reject(request_id: int, request: Request):
    """업무담당자가 잘못 배정된 청구를 거절한다. 단순 반려(담당자 없이 미배정으로만
    돌리기)는 지원하지 않는다 — 반드시 1~3명의 재배정 후보를 지명해야 하며, 그 후보들이
    배정 대기 화면에 추천으로 표시되어 배정담당자/총괄관리자가 최종 확정한다."""
    guard = _require_role_api(request, '업무담당자')
    if guard:
        return guard
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    if row['assigned_to'] != request.state.auth_user:
        return JSONResponse({'success': False, 'message': '본인에게 배정된 청구만 재배정 요청할 수 있습니다.'}, status_code=403)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구는 재배정할 수 없습니다.'}, status_code=409)

    data = await request.json()
    raw_candidates = data.get('candidates')
    if not isinstance(raw_candidates, list):
        return JSONResponse({'success': False, 'message': '재배정할 담당자를 선택해주세요.'}, status_code=400)
    candidates = [c.strip() for c in raw_candidates if isinstance(c, str) and c.strip()]
    candidates = list(dict.fromkeys(candidates))  # 순서를 유지하며 중복 제거
    if not (1 <= len(candidates) <= 3):
        return JSONResponse({'success': False, 'message': '재배정할 담당자를 1명 이상 3명 이하로 선택해주세요.'}, status_code=400)
    if request.state.auth_user in candidates:
        return JSONResponse({'success': False, 'message': '본인을 재배정 대상으로 선택할 수 없습니다.'}, status_code=400)
    for username in candidates:
        target_user = db.get_user(username)
        if not target_user or target_user['role'] != '업무담당자':
            return JSONResponse({'success': False, 'message': f'유효한 업무담당자가 아닙니다: {username}'}, status_code=400)

    db.reject_and_nominate(request_id, candidates, actor=request.state.auth_user)
    return JSONResponse({'success': True})


@app.post('/api/requests/{request_id}/extend-deadline')
async def api_extend_deadline(request_id: int, request: Request):
    """정보공개법 제11조 제2항: 부득이한 사유가 있으면 1회에 한해 10일 범위에서 처리기한을
    연장한다. 배정된 업무담당자 본인 또는 총괄관리자만 가능하고, 이미 연장했거나 완료된
    건은 다시 연장할 수 없다."""
    guard = _require_role_api(request, '총괄관리자', '업무담당자')
    if guard:
        return guard
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    if request.state.auth_role == '업무담당자' and row['assigned_to'] != request.state.auth_user:
        return JSONResponse({'success': False, 'message': '본인에게 배정된 청구만 연장할 수 있습니다.'}, status_code=403)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구는 연장할 수 없습니다.'}, status_code=409)
    if row['deadline_extended']:
        return JSONResponse({'success': False, 'message': '이미 한 차례 연장된 청구입니다.'}, status_code=409)

    data = await request.json()
    reason = (data.get('reason') or '').strip()[:200]
    db.extend_deadline(request_id, actor=request.state.auth_user, reason=reason)
    return JSONResponse({'success': True})


# ── API ────────────────────────────────────────────────────────────

@app.get('/api/settings')
async def api_settings(request: Request):
    guard = _require_role_api(request, '총괄관리자')
    if guard:
        return guard
    settings = current_settings()
    settings['ai_enabled'] = AIClient.is_enabled(settings.get('ai_api_url', INTERNAL_AI_API_URL))
    return JSONResponse(settings)


@app.get('/api/summary')
async def api_summary(request: Request):
    guard = _require_role_api(request, '총괄관리자')
    if guard:
        return guard
    return JSONResponse(db.summary())


@app.get('/api/requests')
async def api_requests(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    # 총괄관리자는 대시보드용으로 전체를 보고, 업무담당자는 "내 업무" 새 배정 감지 폴링용으로
    # 본인 배정건만 본다(request_list 페이지 라우트와 동일한 필터링 원칙).
    guard = _require_role_api(request, '총괄관리자', '업무담당자')
    if guard:
        return guard
    assigned_to = request.state.auth_user if request.state.auth_role == '업무담당자' else None
    rows = [_with_deadline(dict(r)) for r in db.list_requests(limit=limit, assigned_to=assigned_to)]
    return JSONResponse(rows)


@app.post('/api/watch/scan')
async def api_watch_scan(request: Request):
    guard = _require_role_api(request, '배정담당자', '총괄관리자')
    if guard:
        return guard
    result = await processor.scan_once()
    result['scanned_at'] = __import__('datetime').datetime.now().isoformat(timespec='seconds')
    return JSONResponse(result)


@app.post('/api/requests/{request_id}/decide')
async def api_decide(request_id: int, request: Request):
    guard = _require_role_api(request, '총괄관리자', '업무담당자')
    if guard:
        return guard

    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구 건을 찾을 수 없습니다.'}, status_code=404)
    if request.state.auth_role == '업무담당자' and row['assigned_to'] != request.state.auth_user:
        return JSONResponse({'success': False, 'message': '본인에게 배정된 청구만 처리할 수 있습니다.'}, status_code=403)

    data = await request.json()
    step_key = data.get('step')
    answer = bool(data.get('answer'))
    actor = request.state.auth_user or '담당자'

    decision = db.get_decision(request_id)
    if not decision:
        return JSONResponse({'success': False, 'message': '청구 건을 찾을 수 없습니다.'}, status_code=404)
    if decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구입니다.'}, status_code=409)
    if decision['current_step'] != step_key:
        return JSONResponse({'success': False, 'message': f"현재 단계는 '{step_key}'가 아닙니다."}, status_code=409)

    step = foia_core.get_step(step_key)
    next_step, notice_type = foia_core.advance(step_key, answer)
    db.apply_step_answer(request_id, step_key, answer, next_step, notice_type, step['article'], actor=actor)

    if notice_type:
        row = db.get_request(request_id)
        templates_map = db.get_all_settings()
        notice_text = foia_core.default_notice_text(templates_map, notice_type, row['request_target'] or '')
        db.finalize_notice(request_id, notice_text, decided_by=actor)

    return JSONResponse({
        'success': True,
        'next_step': next_step,
        'final_notice_type': notice_type,
    })


@app.get('/health')
async def health():
    settings = current_settings()
    return {
        'status': 'ok',
        'ai_enabled': AIClient.is_enabled(settings.get('ai_api_url', INTERNAL_AI_API_URL)),
    }


@app.get('/favicon.ico')
async def favicon():
    return RedirectResponse('/static/favicon.png')
