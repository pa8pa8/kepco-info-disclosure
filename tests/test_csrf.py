"""CSRF 토큰 검증. SameSite=Strict 쿠키가 이미 대부분의 크로스사이트 요청을 막아주지만,
명시적 토큰 검증(synchronizer token 패턴)이 실제로 적용돼 있는지 확인한다."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_login_without_csrf_token_is_rejected():
    raw = TestClient(app, cookies={})  # _new_client()과 달리 기본 CSRF 헤더를 안 붙임
    resp = raw.post('/login', data={'username': 'manager', 'password': 'manager'}, follow_redirects=False)
    assert resp.status_code == 403


def test_login_with_wrong_csrf_token_is_rejected():
    raw = TestClient(app, cookies={})
    resp = raw.post(
        '/login',
        data={'username': 'manager', 'password': 'manager', 'csrf_token': 'not-the-real-token'},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_login_with_correct_csrf_form_field_succeeds():
    from app.security import csrf_token_for

    raw = TestClient(app, cookies={})
    resp = raw.post(
        '/login',
        data={'username': 'manager', 'password': 'manager', 'csrf_token': csrf_token_for(None)},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_json_api_post_without_csrf_header_is_rejected(as_dispatcher, make_request):
    request_id = make_request()
    resp = as_dispatcher.post(
        f'/api/requests/{request_id}/assign',
        json={'assigned_to': 'staff1'},
        headers={'X-CSRF-Token': ''},
    )
    assert resp.status_code == 403
    assert resp.json()['success'] is False


def test_json_api_post_with_stale_csrf_token_is_rejected(as_dispatcher, make_request):
    request_id = make_request()
    resp = as_dispatcher.post(
        f'/api/requests/{request_id}/assign',
        json={'assigned_to': 'staff1'},
        headers={'X-CSRF-Token': 'stale-or-forged-token'},
    )
    assert resp.status_code == 403


def test_csrf_token_differs_per_user():
    from app.security import csrf_token_for

    assert csrf_token_for('manager') != csrf_token_for('staff1')
    assert csrf_token_for(None) != csrf_token_for('manager')


def test_admin_form_post_without_csrf_is_rejected(as_admin):
    raw = TestClient(app, cookies=as_admin.cookies)  # 세션 쿠키는 재사용, CSRF 헤더는 안 붙임
    resp = raw.post('/admin/users', data={
        'username': 'shouldnotexist2', 'password': 'testpass123', 'role': '업무담당자',
    }, follow_redirects=False)
    assert resp.status_code == 403

    from app.deps import db
    assert db.get_user('shouldnotexist2') is None
