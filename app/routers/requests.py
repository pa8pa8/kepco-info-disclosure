"""청구 목록/상세/통지서 화면과 그에 딸린 API — 배정, 거절(재배정 지명), 판단 위저드,
처리기한 연장, AI 추천 조회."""

from __future__ import annotations

import datetime
import json

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import roles
from ..config import APP_TITLE
from ..deps import db, load_ai_recommendation, load_recommendation, templates, with_deadline
from ..security import read_json_body, require_csrf_api, require_role, require_role_api, role_home
from ..services import foia_core
from ..services.recommend import ENGINES as RECOMMEND_ENGINES

router = APIRouter()


# ── 화면 ───────────────────────────────────────────────────────────

@router.get('/requests', response_class=HTMLResponse)
async def request_list(
    request: Request,
    q: str = '',
    status: str = '',
    notice_type: str = '',
):
    guard = require_role(request, roles.MANAGER, roles.STAFF)
    if guard:
        return guard
    role = request.state.auth_role
    assigned_to = request.state.auth_user if role == roles.STAFF else None
    rows = [with_deadline(dict(r)) for r in db.list_requests(status=status, notice_type=notice_type, q=q, assigned_to=assigned_to)]
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
            'is_my_queue': role == roles.STAFF,
        },
    )


@router.get('/requests/{request_id}', response_class=HTMLResponse)
async def request_detail(request: Request, request_id: int):
    guard = require_role(request, roles.MANAGER, roles.DISPATCHER, roles.STAFF)
    if guard:
        return guard
    role = request.state.auth_role
    row = db.get_request(request_id)
    if not row:
        return RedirectResponse(role_home(role), status_code=303)
    if role == roles.STAFF and row['assigned_to'] != request.state.auth_user:
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
        role == roles.MANAGER or (role == roles.STAFF and row['assigned_to'] == request.state.auth_user)
    )
    can_assign = (not is_finalized) and role in (roles.DISPATCHER, roles.MANAGER) and not row['assigned_to']
    can_reject = (not is_finalized) and role == roles.STAFF and row['assigned_to'] == request.state.auth_user
    can_reassign = (not is_finalized) and role in (roles.DISPATCHER, roles.MANAGER) and bool(row['assigned_to'])
    # 배정담당자는 "판단은 불가" 역할이다 — 아직 배정 전(can_assign)이라 배정을 위해
    # 원문을 봐야 하는 경우를 제외하면, 자신이 관여하지 않은 청구의 판단 세부 내용
    # (AI 힌트, 반복청구 판정, 판단 경로, 최종 통지문, 처리 이력)까지 볼 이유가 없다.
    dispatcher_limited_view = role == roles.DISPATCHER and not can_assign
    if dispatcher_limited_view:
        # 배정/재배정/거절 이력은 배정담당자 본연의 업무 기록이라 남겨두고,
        # 법적 판단 단계(반복청구/정보해당/진정질의 등 Y-N 응답)만 가린다.
        log_rows = [log for log in log_rows if log['step_key'] in ('assign', 'reassign', 'reject')]
    deadline_info = foia_core.compute_deadline_info(row['received_at'], bool(row['deadline_extended']), is_finalized)
    can_extend = can_decide and not row['deadline_extended']
    staff_directory = [dict(r) for r in db.list_directory_by_role(roles.STAFF)] if (can_assign or can_reject or can_reassign) else []
    if can_reject:
        staff_directory = [s for s in staff_directory if s['username'] != request.state.auth_user]
    elif can_reassign:
        staff_directory = [s for s in staff_directory if s['username'] != row['assigned_to']]
    ai_result = load_recommendation(row) if can_assign else None

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
            'dispatcher_limited_view': dispatcher_limited_view,
            'deadline_info': deadline_info,
            'can_extend': can_extend,
            'staff_directory': staff_directory,
            'ai_result': ai_result,
        },
    )


@router.get('/requests/{request_id}/notice', response_class=HTMLResponse)
async def request_notice(request: Request, request_id: int):
    """인쇄/저장용 통지서 화면. 화면에 텍스트로만 남아있던 `notice_text`를 실제로
    청구인에게 발송할 수 있는 문서 형태로 보여준다 — 브라우저 인쇄(Ctrl+P) → PDF로
    저장하면 그대로 산출물이 된다. 별도 라이브러리(docx/pdf 생성) 없이 구현해
    "10년 전 서버에서도 최소 의존성으로 동작"이라는 프로젝트 원칙을 지킨다.

    배정담당자는 제외한다 — "판단은 불가" 역할인데 최종 통지문 전체를 인쇄/저장까지
    할 수 있는 건 명백히 과도한 권한이다(`/requests/{id}` 상세 화면에서도 통지 내용
    자체는 안 보여주는 것과 일관)."""
    guard = require_role(request, roles.MANAGER, roles.STAFF)
    if guard:
        return guard
    role = request.state.auth_role
    row = db.get_request(request_id)
    if not row:
        return RedirectResponse(role_home(role), status_code=303)
    if role == roles.STAFF and row['assigned_to'] != request.state.auth_user:
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
            'today': datetime.date.today().isoformat(),
        },
    )


# ── API ────────────────────────────────────────────────────────────

@router.post('/api/requests/{request_id}/recommend')
async def api_recommend(request_id: int, request: Request):
    """AI 판단 결과 조회 — 실시간 계산이나 무작위 추천을 전혀 하지 않는다.
    (배정 대기 화면은 이미 준비된 결과를 페이지 로드 시 바로 보여주고, 이 API는
    아직 표시되지 않은 나머지 건에서 "AI 판단하기"를 눌렀을 때만 호출된다.)
    """
    guard = require_role_api(request, roles.DISPATCHER, roles.MANAGER)
    if guard:
        return guard
    guard = require_csrf_api(request)
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

    result = load_ai_recommendation(row)
    if not result:
        return JSONResponse({
            'success': True,
            'has_result': False,
            'message': '이 청구는 아직 AI 판단 예시가 준비되지 않았습니다. "AI로 생성하기" 버튼을 눌러주세요.',
        })
    return JSONResponse({'success': True, 'has_result': True, **result})


@router.post('/api/requests/{request_id}/generate-recommendation')
async def api_generate_recommendation(request_id: int, request: Request):
    """"AI로 생성하기" 버튼 핸들러 — 예시 파일이 없는 청구에서 실제 추천 엔진을 돌린다.

    `app/services/recommend/ENGINES`에 등록된 엔진들을 각각 시도해 나란히 반환한다
    (다 비교해볼 수 있게). GradientBoost·XGBoost는 실제로 동작하고(합성 또는 실제
    데이터로 학습, `tools/train_gbm_recommender.py`/`tools/train_xgboost_recommender.py`),
    LLM은 아직 인터페이스만 있어 항상 `available: false`를 반환한다
    (`app/services/recommend/llm_recommender.py` 참고).
    """
    guard = require_role_api(request, roles.DISPATCHER, roles.MANAGER)
    if guard:
        return guard
    guard = require_csrf_api(request)
    if guard:
        return guard
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    if row['assigned_to']:
        return JSONResponse({'success': False, 'message': '이미 배정된 청구입니다.'}, status_code=409)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구는 배정할 수 없습니다.'}, status_code=409)

    engines = {name: engine.recommend(row) for name, engine in RECOMMEND_ENGINES.items()}
    return JSONResponse({'success': True, 'engines': engines})


@router.post('/api/requests/{request_id}/assign')
async def api_assign(request_id: int, request: Request):
    guard = require_role_api(request, roles.DISPATCHER, roles.MANAGER)
    if guard:
        return guard
    guard = require_csrf_api(request)
    if guard:
        return guard
    data = await read_json_body(request)
    if data is None:
        return JSONResponse({'success': False, 'message': '잘못된 요청 형식입니다.'}, status_code=400)
    assigned_to = (data.get('assigned_to') or '').strip()
    target_user = db.get_user(assigned_to)
    if not target_user or target_user['role'] != roles.STAFF:
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


@router.post('/api/requests/{request_id}/reject')
async def api_reject(request_id: int, request: Request):
    """업무담당자가 잘못 배정된 청구를 거절한다. 단순 반려(담당자 없이 미배정으로만
    돌리기)는 지원하지 않는다 — 반드시 1~3명의 재배정 후보를 지명해야 하며, 그 후보들이
    배정 대기 화면에 추천으로 표시되어 배정담당자/총괄관리자가 최종 확정한다."""
    guard = require_role_api(request, roles.STAFF)
    if guard:
        return guard
    guard = require_csrf_api(request)
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

    data = await read_json_body(request)
    if data is None:
        return JSONResponse({'success': False, 'message': '잘못된 요청 형식입니다.'}, status_code=400)
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
        if not target_user or target_user['role'] != roles.STAFF:
            return JSONResponse({'success': False, 'message': f'유효한 업무담당자가 아닙니다: {username}'}, status_code=400)

    db.reject_and_nominate(request_id, candidates, actor=request.state.auth_user)
    return JSONResponse({'success': True})


@router.post('/api/requests/{request_id}/extend-deadline')
async def api_extend_deadline(request_id: int, request: Request):
    """정보공개법 제11조 제2항: 부득이한 사유가 있으면 1회에 한해 10일 범위에서 처리기한을
    연장한다. 배정된 업무담당자 본인 또는 총괄관리자만 가능하고, 이미 연장했거나 완료된
    건은 다시 연장할 수 없다."""
    guard = require_role_api(request, roles.MANAGER, roles.STAFF)
    if guard:
        return guard
    guard = require_csrf_api(request)
    if guard:
        return guard
    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구를 찾을 수 없습니다.'}, status_code=404)
    if request.state.auth_role == roles.STAFF and row['assigned_to'] != request.state.auth_user:
        return JSONResponse({'success': False, 'message': '본인에게 배정된 청구만 연장할 수 있습니다.'}, status_code=403)
    decision = db.get_decision(request_id)
    if decision and decision['final_notice_type']:
        return JSONResponse({'success': False, 'message': '이미 처리가 완료된 청구는 연장할 수 없습니다.'}, status_code=409)
    if row['deadline_extended']:
        return JSONResponse({'success': False, 'message': '이미 한 차례 연장된 청구입니다.'}, status_code=409)

    data = await read_json_body(request) or {}
    reason = (data.get('reason') or '').strip()[:200]
    db.extend_deadline(request_id, actor=request.state.auth_user, reason=reason)
    return JSONResponse({'success': True})


@router.get('/api/requests')
async def api_requests(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    # 총괄관리자는 대시보드용으로 전체를 보고, 업무담당자는 "내 업무" 새 배정 감지 폴링용으로
    # 본인 배정건만 본다(request_list 페이지 라우트와 동일한 필터링 원칙).
    guard = require_role_api(request, roles.MANAGER, roles.STAFF)
    if guard:
        return guard
    assigned_to = request.state.auth_user if request.state.auth_role == roles.STAFF else None
    rows = [with_deadline(dict(r)) for r in db.list_requests(limit=limit, assigned_to=assigned_to)]
    return JSONResponse(rows)


@router.post('/api/requests/{request_id}/decide')
async def api_decide(request_id: int, request: Request):
    guard = require_role_api(request, roles.MANAGER, roles.STAFF)
    if guard:
        return guard
    guard = require_csrf_api(request)
    if guard:
        return guard

    row = db.get_request(request_id)
    if not row:
        return JSONResponse({'success': False, 'message': '청구 건을 찾을 수 없습니다.'}, status_code=404)
    if request.state.auth_role == roles.STAFF and row['assigned_to'] != request.state.auth_user:
        return JSONResponse({'success': False, 'message': '본인에게 배정된 청구만 처리할 수 있습니다.'}, status_code=403)

    data = await read_json_body(request)
    if data is None:
        return JSONResponse({'success': False, 'message': '잘못된 요청 형식입니다.'}, status_code=400)
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
