"""역할별 접근 통제. 특히 FOIA-0019에서 고친 "배정담당자가 관여하지 않은 청구의
판단 세부 내용을 열람 가능했던" 문제의 회귀 테스트를 포함한다."""
from __future__ import annotations


def _finalize_with_notice(request_id: int):
    from app.deps import db

    db.assign_request(request_id, 'staff1', assigned_by='dispatcher')
    db.apply_step_answer(request_id, 'repeat', True, None, '종결', '제11조의2', actor='staff1')
    db.finalize_notice(request_id, '요청하신 정보를 처리했습니다. (테스트 통지문)', decided_by='staff1')


def test_dispatcher_cannot_access_notice_route_even_by_direct_url(as_dispatcher, make_request):
    request_id = make_request()
    _finalize_with_notice(request_id)

    resp = as_dispatcher.get(f'/requests/{request_id}/notice', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == '/dispatch'


def test_dispatcher_detail_view_hides_final_notice_and_judgement_trail(as_dispatcher, make_request):
    request_id = make_request()
    _finalize_with_notice(request_id)

    resp = as_dispatcher.get(f'/requests/{request_id}')
    assert resp.status_code == 200
    assert '통지서 보기' not in resp.text
    assert '요청하신 정보를 처리했습니다' not in resp.text


def test_manager_detail_view_still_shows_full_notice(as_manager, make_request):
    request_id = make_request()
    _finalize_with_notice(request_id)

    resp = as_manager.get(f'/requests/{request_id}')
    assert resp.status_code == 200
    assert '요청하신 정보를 처리했습니다' in resp.text


def test_owning_staff_can_open_notice_route(as_staff1, make_request):
    request_id = make_request()
    _finalize_with_notice(request_id)

    resp = as_staff1.get(f'/requests/{request_id}/notice')
    assert resp.status_code == 200
    assert '요청하신 정보를 처리했습니다' in resp.text


def test_other_staff_cannot_open_unassigned_notice_route(as_staff2, make_request):
    request_id = make_request()
    _finalize_with_notice(request_id)  # 배정 대상은 staff1

    resp = as_staff2.get(f'/requests/{request_id}/notice', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == '/requests'


def test_dispatcher_cannot_open_requests_list(as_dispatcher):
    resp = as_dispatcher.get('/requests', follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers['location'] == '/dispatch'


def test_requester_history_requires_exact_name_and_scoped_to_dispatcher_manager(as_dispatcher, as_staff1, make_request):
    make_request(requester_name='홍길동')
    make_request(requester_name='홍길동전')

    # 빈 검색어는 아무것도 보여주지 않는다 — 전체 열람 악용 방지.
    resp = as_dispatcher.get('/requester-history')
    assert resp.status_code == 200
    assert '테스트 청구 원문입니다' not in resp.text

    resp = as_dispatcher.get('/requester-history', params={'name': '홍길동'})
    assert resp.status_code == 200
    assert '홍길동전' not in resp.text  # 정확 일치만 — 부분 일치인 '홍길동전'은 제외

    # 업무담당자는 이 화면에 접근할 수 없다.
    resp2 = as_staff1.get('/requester-history', follow_redirects=False)
    assert resp2.status_code == 303


def test_admin_only_routes_reject_other_roles(as_manager, as_dispatcher, as_staff1):
    for client in (as_manager, as_dispatcher, as_staff1):
        resp = client.get('/admin/users', follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers['location'] != '/admin/users'
