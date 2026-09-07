"""배정 추천 엔진(GradientBoost 실제 동작, LLM 인터페이스만) 및 그걸 감싼 API."""
from __future__ import annotations

import time

from app.services.recommend import ENGINES
from app.services.recommend.gbm_recommender import GBMRecommender
from app.services.recommend.llm_recommender import LLMRecommender
from app.services.recommend.synthetic_data import STAFF_BY_DEPARTMENT, generate_training_examples


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


def test_gbm_recommender_reloads_model_when_file_changes_no_restart_needed(tmp_path, monkeypatch):
    """FOIA-0031 회귀 테스트: 재학습해도 서버 재시작 없이 새 모델이 반영돼야 한다."""
    import joblib
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline

    import app.services.recommend.gbm_recommender as gbm_module

    model_path = tmp_path / 'model.joblib'
    monkeypatch.setattr(gbm_module, 'GBM_MODEL_PATH', model_path)

    def _train_and_save(labels):
        texts = [f'샘플 문장 {i}' for i in range(len(labels))]
        pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=1)),
            ('gbm', GradientBoostingClassifier(random_state=42, n_estimators=5)),
        ])
        pipeline.fit(texts, labels)
        joblib.dump(pipeline, model_path)

    engine = GBMRecommender()
    assert engine.recommend({'request_target': 'x', 'raw_text': 'x'})['available'] is False  # 모델 없음

    _train_and_save(['staff1', 'staff2'])
    first_classes = set(engine._load_model().classes_)
    assert first_classes == {'staff1', 'staff2'}

    time.sleep(1.1)  # 파일시스템 mtime 해상도(1초)보다 확실히 크게
    _train_and_save(['staff1', 'staff2', 'staff3'])
    second_classes = set(engine._load_model().classes_)
    assert second_classes == {'staff1', 'staff2', 'staff3'}, '재학습 후 mtime이 바뀌었는데 이전 모델이 캐시된 채 남아있음'


def test_synthetic_training_examples_cover_every_staff_account():
    examples = generate_training_examples(per_department=20)
    labels = {staff for _, staff in examples}
    all_staff = {staff for staffs in STAFF_BY_DEPARTMENT.values() for staff, _ in staffs}
    assert labels == all_staff


def test_synthetic_training_examples_deterministic_with_same_seed():
    a = generate_training_examples(per_department=10, seed=1)
    b = generate_training_examples(per_department=10, seed=1)
    assert a == b


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
