"""배정 추천 엔진(GradientBoost 실제 동작, LLM 인터페이스만) 및 그걸 감싼 API."""
from __future__ import annotations

from app.services.recommend import ENGINES
from app.services.recommend.gbm_recommender import GBMRecommender
from app.services.recommend.llm_recommender import LLMRecommender


def test_gbm_recommender_returns_available_result_for_known_department_text():
    engine = GBMRecommender()
    row = {
        'request_target': '정보공개 청구 처리 현황',
        'raw_text': '서울지역본부 관할 정보공개 청구 관련 자료를 공개해 주시기 바랍니다.',
    }
    result = engine.recommend(row)
    assert result['available'] is True
    assert result['source'] == 'gbm'
    assert 1 <= len(result['recommendations']) <= 3
    assert all(name.startswith('staff') for name in result['recommendations'])
    assert result['reason']


def test_gbm_recommender_unavailable_for_empty_text():
    engine = GBMRecommender()
    result = engine.recommend({'request_target': '', 'raw_text': ''})
    assert result['available'] is False
    assert result['recommendations'] == []


def test_llm_recommender_reports_not_configured_without_api_key(monkeypatch):
    monkeypatch.delenv('FOIA_LLM_API_KEY', raising=False)
    engine = LLMRecommender()
    result = engine.recommend({'request_target': 'x', 'raw_text': 'x'})
    assert result['available'] is False
    assert result['source'] == 'llm'
    assert 'FOIA_LLM_API_KEY' in result['message']


def test_engines_registry_has_both_backends():
    assert set(ENGINES.keys()) == {'gbm', 'llm'}


def test_generate_recommendation_endpoint_returns_both_engines(as_dispatcher, make_request):
    request_id = make_request(raw_text='경기지역본부에서 처리한 전기요금 문의 건에 대해 문의드립니다.')
    resp = as_dispatcher.post(f'/api/requests/{request_id}/generate-recommendation')
    assert resp.status_code == 200
    body = resp.json()
    assert body['success'] is True
    assert set(body['engines'].keys()) == {'gbm', 'llm'}
    assert body['engines']['gbm']['available'] is True
    assert body['engines']['llm']['available'] is False


def test_generate_recommendation_rejects_already_assigned_request(as_dispatcher, make_request):
    request_id = make_request()
    as_dispatcher.post(f'/api/requests/{request_id}/assign', json={'assigned_to': 'staff1'})
    resp = as_dispatcher.post(f'/api/requests/{request_id}/generate-recommendation')
    assert resp.status_code == 409


def test_generate_recommendation_requires_dispatcher_or_manager_role(as_staff1, make_request):
    request_id = make_request()
    resp = as_staff1.post(f'/api/requests/{request_id}/generate-recommendation')
    assert resp.status_code == 403
