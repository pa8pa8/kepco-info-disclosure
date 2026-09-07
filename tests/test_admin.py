"""시스템관리자 계정 관리(FOIA-0013: 계정 수정 기능 추가분 포함)."""
from __future__ import annotations

from app.deps import db


def test_admin_can_create_user(as_admin):
    resp = as_admin.post('/admin/users', data={
        'username': 'newstaff1', 'password': 'testpass123', 'role': '업무담당자',
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert db.get_user('newstaff1') is not None
    db.delete_user(db.get_user('newstaff1')['id'])


def test_admin_create_rejects_duplicate_username(as_admin):
    resp = as_admin.post('/admin/users', data={
        'username': 'staff1', 'password': 'testpass123', 'role': '업무담당자',
    }, follow_redirects=False)
    assert resp.status_code == 400
    assert '이미 존재하는' in resp.text


def test_admin_can_edit_user_role_and_password(as_admin):
    db.create_user('edittarget', 'placeholder', '업무담당자')
    user = db.get_user('edittarget')
    old_hash = user['password_hash']

    resp = as_admin.post(f"/admin/users/{user['id']}/edit", data={
        'role': '배정담당자', 'password': 'newpassword1',
    }, follow_redirects=False)
    assert resp.status_code == 303

    updated = db.get_user('edittarget')
    assert updated['role'] == '배정담당자'
    assert updated['password_hash'] != old_hash
    db.delete_user(updated['id'])


def test_admin_edit_without_password_keeps_existing_hash(as_admin):
    db.create_user('edittarget2', 'placeholder-hash', '업무담당자')
    user = db.get_user('edittarget2')

    resp = as_admin.post(f"/admin/users/{user['id']}/edit", data={'role': '업무담당자'}, follow_redirects=False)
    assert resp.status_code == 303

    updated = db.get_user('edittarget2')
    assert updated['password_hash'] == 'placeholder-hash'
    db.delete_user(updated['id'])


def test_cannot_delete_own_account(as_admin):
    admin_user = db.get_user('admin')
    # 두 번째 관리자를 만들어야 "마지막 관리자" 제약이 아니라 "본인 삭제 금지" 제약이 걸린다.
    db.create_user('admin2', 'placeholder', '시스템관리자')
    resp = as_admin.post(f"/admin/users/{admin_user['id']}/delete", follow_redirects=False)
    assert resp.status_code == 303
    assert 'error=self' in resp.headers['location']
    db.delete_user(db.get_user('admin2')['id'])


def test_non_admin_role_cannot_access_admin_users(as_manager, as_dispatcher, as_staff1):
    for client in (as_manager, as_dispatcher, as_staff1):
        resp = client.post('/admin/users', data={
            'username': 'shouldnotexist', 'password': 'testpass123', 'role': '업무담당자',
        }, follow_redirects=False)
        assert resp.status_code == 303
    assert db.get_user('shouldnotexist') is None
