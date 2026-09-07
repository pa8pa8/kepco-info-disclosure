"""총괄관리자 대시보드(`/`)와 그 화면이 폴링하는 요약 API."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import roles
from ..config import APP_TITLE, INTERNAL_AI_API_URL
from ..deps import current_settings, db, templates
from ..security import require_role, require_role_api
from ..services.ai_client import AIClient

router = APIRouter()


@router.get('/', response_class=HTMLResponse)
async def dashboard(request: Request):
    guard = require_role(request, roles.MANAGER)
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


@router.get('/api/summary')
async def api_summary(request: Request):
    guard = require_role_api(request, roles.MANAGER)
    if guard:
        return guard
    return JSONResponse(db.summary())
