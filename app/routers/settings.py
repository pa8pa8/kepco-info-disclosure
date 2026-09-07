"""총괄관리자 설정 화면(`/settings`) — 감시 경로, AI 연동 테스트, 통지서 템플릿,
비공개 키워드."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import roles
from ..config import APP_TITLE, INTERNAL_AI_API_URL
from ..deps import ai_client, current_settings, db, templates
from ..security import require_role, require_role_api
from ..services import foia_core
from ..services.ai_client import AIClient

router = APIRouter()


@router.get('/settings', response_class=HTMLResponse)
async def settings_page(request: Request):
    guard = require_role(request, roles.MANAGER)
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


@router.post('/settings/general')
async def update_settings(request: Request, watch_dir: str = Form(...), scan_interval: int = Form(60), nondisclosure_keywords: str = Form('')):
    guard = require_role(request, roles.MANAGER)
    if guard:
        return guard
    db.set_setting('watch_dir', watch_dir.strip())
    db.set_setting('ai_api_url', INTERNAL_AI_API_URL)
    db.set_setting('scan_interval', str(scan_interval))
    db.set_setting('nondisclosure_keywords', nondisclosure_keywords.strip())
    return RedirectResponse('/settings?saved=1', status_code=303)


@router.post('/settings/notice-templates')
async def update_notice_templates(request: Request):
    guard = require_role(request, roles.MANAGER)
    if guard:
        return guard
    form = await request.form()
    for notice_type in foia_core.NOTICE_LABELS:
        key = f'notice_template_{notice_type}'
        if key in form:
            db.set_setting(key, str(form[key]).strip())
    return RedirectResponse('/settings?saved=1', status_code=303)


@router.post('/settings/test-ai')
async def test_ai_connection(request: Request, raw_text: str = Form('개인정보 관련 열람 청구 자료 요청드립니다.')):
    guard = require_role_api(request, roles.MANAGER)
    if guard:
        return guard
    payload = {'raw_text': raw_text, 'nondisclosure_keywords': [], 'history': []}
    try:
        result = await ai_client.identify(payload)
        return JSONResponse({'ok': True, 'request': payload, 'response': result})
    except Exception as exc:
        return JSONResponse({'ok': False, 'request': payload, 'error': str(exc)}, status_code=500)


@router.get('/api/settings')
async def api_settings(request: Request):
    guard = require_role_api(request, roles.MANAGER)
    if guard:
        return guard
    settings = current_settings()
    settings['ai_enabled'] = AIClient.is_enabled(settings.get('ai_api_url', INTERNAL_AI_API_URL))
    return JSONResponse(settings)
