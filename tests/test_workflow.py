"""배정 → 거절(재배정 지명) → 재배정 → 판단(decide) 흐름의 API 레벨 회귀 테스트."""
from __future__ import annotations


def test_dispatcher_can_assign_unassigned_request(as_dispatcher, make_request):
    request_id = make_request()
    resp = as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})
    assert resp.status_code == 200
    assert resp.json()['success'] is True

    from app.deps import db
    row = db.get_request(request_id)
    assert row['assigned_to'] == 'staff1'


def test_assign_rejects_non_staff_target(as_dispatcher, make_request):
    request_id = make_request()
    resp = as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'manager'})
    assert resp.status_code == 400


def test_staff_cannot_call_assign_api(as_staff1, make_request):
    request_id = make_request()
    resp = as_staff1.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff2'})
    assert resp.status_code == 403


def test_staff_reject_requires_one_to_three_candidates(as_dispatcher, as_staff1, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/reject', json={'candidates': []})
    assert resp.status_code == 400

    resp = as_staff1.post(f'/api/requests/{request_id}/reject', json={'candidates': ['staff2', 'staff3', 'staff4', 'staff5']})
    assert resp.status_code == 400


def test_staff_reject_cannot_nominate_self(as_dispatcher, as_staff1, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/reject', json={'candidates': ['staff1']})
    assert resp.status_code == 400


def test_staff_reject_nominates_candidates_successfully(as_dispatcher, as_staff1, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/reject', json={'candidates': ['staff2', 'staff3']})
    assert resp.status_code == 200
    assert resp.json()['success'] is True

    from app.deps import db
    row = db.get_request(request_id)
    assert row['assigned_to'] is None  # 단순 반려가 아니라 재배정 대기 상태로 감


def test_only_owning_staff_can_reject(as_dispatcher, as_staff1, as_staff2, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff2.post(f'/api/requests/{request_id}/reject', json={'candidates': ['staff3']})
    assert resp.status_code == 403


def test_dispatcher_can_directly_reassign_already_assigned_request(as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff2'})
    assert resp.status_code == 200

    from app.deps import db
    row = db.get_request(request_id)
    assert row['assigned_to'] == 'staff2'


def test_assign_same_target_twice_is_rejected(as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})
    assert resp.status_code == 409


def test_decide_single_step_finalizes_notice(as_staff1, as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/decide', json={'step': 'repeat', 'answer': True})
    assert resp.status_code == 200
    body = resp.json()
    assert body['final_notice_type'] == '종결'

    from app.deps import db
    decision = db.get_decision(request_id)
    assert decision['final_notice_type'] == '종결'
    assert decision['notice_text']


def test_decide_rejects_answer_for_wrong_step(as_staff1, as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/decide', json={'step': 'information', 'answer': True})
    assert resp.status_code == 409


def test_decide_finalized_request_cannot_be_decided_again(as_staff1, as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})
    as_staff1.post(f'/api/requests/{request_id}/decide', json={'step': 'repeat', 'answer': True})

    resp = as_staff1.post(f'/api/requests/{request_id}/decide', json={'step': 'repeat', 'answer': True})
    assert resp.status_code == 409


def test_extend_deadline_only_once(as_staff1, as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})

    resp = as_staff1.post(f'/api/requests/{request_id}/extend-deadline', json={'reason': '자료 검토 지연'})
    assert resp.status_code == 200

    resp = as_staff1.post(f'/api/requests/{request_id}/extend-deadline', json={'reason': '재요청'})
    assert resp.status_code == 409


def test_malformed_json_body_returns_400_not_500(as_dispatcher, make_request):
    """FOIA-0016에서 고친 회귀 방지: `request.json()`을 직접 부르면 잘못된 본문에
    500이 났었다 — `read_json_body`가 400으로 바꿔주는지 확인."""
    request_id = make_request()
    resp = as_dispatcher.post(
        f'/api/requests/{request_id}/assign',
        content=b'not-json',
        headers={'content-type': 'application/json'},
    )
    assert resp.status_code == 400
