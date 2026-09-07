"""시스템관리자 계정 관리(`/admin/users`) — 추가·수정·삭제."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import roles
from ..config import APP_TITLE
from ..deps import db, templates
from ..security import hash_password, require_role

router = APIRouter()


@router.get('/admin/users', response_class=HTMLResponse)
async def admin_users_page(request: Request):
    guard = require_role(request, roles.ADMIN)
    if guard:
        return guard
    return templates.TemplateResponse(
        request=request,
        name='admin_users.html',
        context={'request': request, 'title': APP_TITLE, 'users': db.list_users(), 'roles': roles.ALL, 'error': ''},
    )


@router.post('/admin/users')
async def admin_users_create(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    region: str = Form(''),
    branch: str = Form(''),
    department: str = Form(''),
):
    guard = require_role(request, roles.ADMIN)
    if guard:
        return guard
    username = username.strip()
    error = ''
    if len(username) < 3:
        error = '아이디는 3자 이상으로 입력해주세요.'
    elif len(password) < 8:
        error = '비밀번호는 8자 이상으로 입력해주세요.'
    elif role not in roles.ALL:
        error = '올바른 역할을 선택해주세요.'
    elif db.get_user(username) is not None:
        error = f"이미 존재하는 아이디입니다: {username}"
    if error:
        return templates.TemplateResponse(
            request=request,
            name='admin_users.html',
            context={'request': request, 'title': APP_TITLE, 'users': db.list_users(), 'roles': roles.ALL, 'error': error},
            status_code=400,
        )
    db.create_user(username, hash_password(password), role, region.strip(), branch.strip(), department.strip())
    return RedirectResponse('/admin/users?saved=1', status_code=303)


@router.post('/admin/users/{user_id}/delete')
async def admin_users_delete(request: Request, user_id: int):
    guard = require_role(request, roles.ADMIN)
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)
    if target['username'] == request.state.auth_user:
        return RedirectResponse('/admin/users?error=self', status_code=303)
    if target['role'] == roles.ADMIN and db.count_users_by_role(roles.ADMIN) <= 1:
        return RedirectResponse('/admin/users?error=lastadmin', status_code=303)
    db.delete_user(user_id)
    return RedirectResponse('/admin/users?deleted=1', status_code=303)


@router.get('/admin/users/{user_id}/edit', response_class=HTMLResponse)
async def admin_users_edit_page(request: Request, user_id: int):
    guard = require_role(request, roles.ADMIN)
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='admin_user_edit.html',
        context={'request': request, 'title': APP_TITLE, 'target': target, 'roles': roles.ALL, 'error': ''},
    )


@router.post('/admin/users/{user_id}/edit')
async def admin_users_edit_submit(
    request: Request,
    user_id: int,
    role: str = Form(...),
    region: str = Form(''),
    branch: str = Form(''),
    department: str = Form(''),
    password: str = Form(''),
):
    guard = require_role(request, roles.ADMIN)
    if guard:
        return guard
    target = db.get_user_by_id(user_id)
    if not target:
        return RedirectResponse('/admin/users', status_code=303)

    error = ''
    if role not in roles.ALL:
        error = '올바른 역할을 선택해주세요.'
    elif password and len(password) < 8:
        error = '비밀번호는 8자 이상으로 입력해주세요(변경하지 않으려면 비워두세요).'
    elif target['role'] == roles.ADMIN and role != roles.ADMIN and db.count_users_by_role(roles.ADMIN) <= 1:
        error = '마지막 남은 시스템관리자 계정의 역할은 변경할 수 없습니다.'
    if error:
        return templates.TemplateResponse(
            request=request,
            name='admin_user_edit.html',
            context={'request': request, 'title': APP_TITLE, 'target': target, 'roles': roles.ALL, 'error': error},
            status_code=400,
        )

    password_hash = hash_password(password) if password else None
    db.update_user(user_id, role, region.strip(), branch.strip(), department.strip(), password_hash)
    return RedirectResponse('/admin/users?saved=1', status_code=303)
