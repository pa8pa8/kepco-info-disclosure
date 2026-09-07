"""배정담당자 화면 — 배정 대기 큐(`/dispatch`), 청구인 이력 조회(`/requester-history`),
감시 폴더 수동 스캔 트리거."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import roles
from ..config import APP_TITLE
from ..deps import db, load_recommendation, processor, templates, with_deadline
from ..security import require_csrf_api, require_role, require_role_api
from ..services import foia_core

router = APIRouter()


@router.get('/dispatch', response_class=HTMLResponse)
async def dispatch_page(request: Request):
    guard = require_role(request, roles.DISPATCHER)
    if guard:
        return guard
    unassigned = [with_deadline(dict(r)) for r in db.list_requests(status='판단중', unassigned_only=True)]
    # 이미 예시 결과 파일이 준비된 건은 클릭 없이 바로 보여준다 — 나머지(예시 없는 건)만
    # "AI 판단하기" 버튼을 눌러야 하는 상태로 남는다.
    ai_results = {}
    for r in unassigned:
        result = load_recommendation(r)
        if result:
            ai_results[r['id']] = result
    recent_assigned = db.list_recently_assigned()
    staff_directory = [dict(r) for r in db.list_directory_by_role(roles.STAFF)]
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


@router.get('/requester-history', response_class=HTMLResponse)
async def requester_history(request: Request, name: str = ''):
    """배정담당자가 전체 청구 목록(`/requests`)에는 접근하지 못하지만, 배정 판단에
    필요한 최소한의 조회 — "이 청구인이 예전에도 청구한 적 있는지"는 확인할 수 있어야
    한다는 요구로 추가. 이름이 정확히 일치하는 건만 보여주고(부분검색·원문검색 아님),
    빈 검색어로는 아무것도 보여주지 않는다 — 전체 열람으로 악용되지 않도록 하기 위함."""
    guard = require_role(request, roles.DISPATCHER, roles.MANAGER)
    if guard:
        return guard
    name = name.strip()
    results = [with_deadline(dict(r)) for r in db.find_requests_by_requester_name(name)] if name else []
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


@router.post('/api/watch/scan')
async def api_watch_scan(request: Request):
    guard = require_role_api(request, roles.DISPATCHER, roles.MANAGER)
    if guard:
        return guard
    guard = require_csrf_api(request)
    if guard:
        return guard
    result = await processor.scan_once()
    result['scanned_at'] = datetime.datetime.now().isoformat(timespec='seconds')
    return JSONResponse(result)
