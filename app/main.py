"""FastAPI 앱 조립부. 실제 라우트는 전부 `app/routers/`에 있다 — 이 파일은
싱글턴 기동(lifespan), 인증 미들웨어, 라우터 등록만 담당한다.

원래는 이 파일 하나에 인증·대시보드·청구·배정·설정·계정관리·API가 전부 1,000줄
넘게 들어있었다. `app/security.py`(인증/인가), `app/deps.py`(공유 싱글턴·헬퍼),
`app/roles.py`(역할 이름 상수), `app/routers/*.py`(도메인별 라우트)로 분리했다.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import quote

import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .config import APP_TITLE, INTERNAL_AI_API_URL, RESOURCE_DIR
from .deps import DEFAULT_ACCOUNTS, current_settings, db, local_ai_server, processor
from .routers import admin, auth, dashboard, dispatch, requests as requests_router, settings as settings_router
from .security import AUTH_COOKIE_NAME, admin_configured, hash_password, is_public_path, read_session
from .services.ai_client import AIClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 계정별로 없을 때만 생성 — 기존 계정 비밀번호는 건드리지 않고, 새로 추가된
    # 기본 계정(예: staff1~staff10)만 다음 실행 시 자동으로 채워지도록 한다.
    for username, password, role, region, branch, department in DEFAULT_ACCOUNTS:
        if db.get_user(username) is None:
            db.create_user(username, hash_password(password), role, region, branch, department)
    db.set_setting('ai_api_url', INTERNAL_AI_API_URL)
    # 자동화 테스트에서는 별도 uvicorn 스레드/사이드카 exe를 띄우는 로컬 AI 서버를
    # 기동하지 않는다 — 테스트가 실제 포트 바인딩·프로세스 생성에 의존하지 않게 한다.
    if not os.getenv('FOIA_SKIP_AI_SERVER'):
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

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(requests_router.router)
app.include_router(dispatch.router)
app.include_router(admin.router)
app.include_router(settings_router.router)


@app.middleware('http')
async def require_authentication(request: Request, call_next):
    path = request.url.path
    request.state.auth_user = read_session(request.cookies.get(AUTH_COOKIE_NAME))
    request.state.auth_role = None
    if request.state.auth_user:
        user_row = db.get_user(request.state.auth_user)
        request.state.auth_role = user_row['role'] if user_row else None

    if not admin_configured() and path != '/setup' and not path.startswith('/static/'):
        if path.startswith('/api/'):
            return JSONResponse({'success': False, 'error': 'ADMIN_SETUP_REQUIRED'}, status_code=403)
        return RedirectResponse('/setup', status_code=303)

    if admin_configured() and not request.state.auth_user and not is_public_path(path):
        if path.startswith('/api/'):
            return JSONResponse({'success': False, 'error': 'AUTH_REQUIRED'}, status_code=401)
        return RedirectResponse(f'/login?next={quote(str(request.url.path))}', status_code=303)

    return await call_next(request)


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
