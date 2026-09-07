"""최초 관리자 생성(`/setup`)과 로그인/로그아웃(`/login`, `/logout`)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from .. import roles
from ..deps import db, templates
from ..security import (
    AUTH_COOKIE_NAME,
    admin_configured,
    hash_password,
    login_lockout_remaining,
    register_login_failure,
    register_login_success,
    require_csrf_form,
    role_home,
    safe_next_path,
    set_auth_cookie,
    verify_password,
)

router = APIRouter()


@router.get('/setup', response_class=HTMLResponse)
async def setup_page(request: Request):
    if admin_configured():
        return RedirectResponse('/login', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='auth_setup.html',
        context={'request': request, 'title': '계정 생성', 'error': ''},
    )


@router.post('/setup')
async def setup_admin(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(''),
):
    if admin_configured():
        return RedirectResponse('/login', status_code=303)
    guard = require_csrf_form(request, csrf_token)
    if guard:
        return guard
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

    db.create_user(username, hash_password(password), roles.ADMIN)
    response = RedirectResponse(role_home(roles.ADMIN), status_code=303)
    set_auth_cookie(response, username)
    return response


@router.get('/login', response_class=HTMLResponse)
async def login_page(request: Request, next: str = '/'):
    if not admin_configured():
        return RedirectResponse('/setup', status_code=303)
    if request.state.auth_user:
        target = safe_next_path(next)
        if target == '/':
            target = role_home(request.state.auth_role)
        return RedirectResponse(target, status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='auth_login.html',
        context={'request': request, 'title': '로그인', 'error': '', 'next': safe_next_path(next)},
    )


@router.post('/login')
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form('/'),
    csrf_token: str = Form(''),
):
    guard = require_csrf_form(request, csrf_token)
    if guard:
        return guard
    username = username.strip()
    locked_seconds = login_lockout_remaining(username)
    if locked_seconds > 0:
        return templates.TemplateResponse(
            request=request,
            name='auth_login.html',
            context={
                'request': request, 'title': '로그인',
                'error': f'로그인 시도가 너무 많아 계정이 잠겼습니다. {locked_seconds}초 후 다시 시도해주세요.',
                'next': safe_next_path(next),
            },
            status_code=429,
        )
    user_row = db.get_user(username)
    if user_row is None or not verify_password(password, user_row['password_hash']):
        register_login_failure(username)
        return templates.TemplateResponse(
            request=request,
            name='auth_login.html',
            context={'request': request, 'title': '로그인', 'error': '아이디 또는 비밀번호가 올바르지 않습니다.', 'next': safe_next_path(next)},
            status_code=401,
        )
    register_login_success(username)
    target = safe_next_path(next)
    if target == '/':
        target = role_home(user_row['role'])
    response = RedirectResponse(target, status_code=303)
    set_auth_cookie(response, username)
    return response


@router.post('/logout')
async def logout(request: Request, csrf_token: str = Form('')):
    guard = require_csrf_form(request, csrf_token)
    if guard:
        return guard
    response = RedirectResponse('/login', status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME)
    return response
