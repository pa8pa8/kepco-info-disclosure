"""로그인/로그아웃/세션 보호 경로."""
from __future__ import annotations


def test_login_success_redirects_to_role_home(client):
    resp = client.post('/login', data={'username': 'manager', 'password': 'manager'}, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == '/'


def test_login_wrong_password_shows_401(client):
    resp = client.post('/login', data={'username': 'manager', 'password': 'wrong-password'}, follow_redirects=False)
    assert resp.status_code == 401


def test_protected_page_without_session_redirects_to_login(client):
    resp = client.get('/requests', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'].startswith('/login')


def test_protected_api_without_session_returns_401_json(client):
    resp = client.get('/api/requests')
    assert resp.status_code == 401
    assert resp.json()['error'] == 'AUTH_REQUIRED'


def test_account_locks_after_repeated_failures(client):
    username = 'staff9'
    for _ in range(5):
        client.post('/login', data={'username': username, 'password': 'wrong'}, follow_redirects=False)
    resp = client.post('/login', data={'username': username, 'password': 'wrong'}, follow_redirects=False)
    assert resp.status_code == 429

    # 잠긴 동안에는 올바른 비밀번호로도 로그인할 수 없다.
    resp = client.post('/login', data={'username': username, 'password': 'staff9'}, follow_redirects=False)
    assert resp.status_code == 429


def test_logout_clears_session(as_manager):
    resp = as_manager.post('/logout', follow_redirects=False)
    assert resp.status_code == 303
    resp2 = as_manager.get('/requests', follow_redirects=False)
    assert resp2.status_code == 303
    assert resp2.headers['location'].startswith('/login')
