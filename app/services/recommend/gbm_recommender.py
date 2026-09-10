"""GradientBoost(TF-IDF + scikit-learn `GradientBoostingClassifier`) 기반 배정 추천.

학습은 `tools/train_gbm_recommender.py`가 미리 해서 `app/config.py`의 `GBM_MODEL_PATH`에
저장해두고, 여기서는 그 모델을 불러와 추론만 한다. 모델 파일이 없으면(아직 학습 전)
예외를 내지 않고 `available: False`로 응답한다 — 배정 화면 자체가 막히면 안 되므로."""
from __future__ import annotations

from ...config import GBM_MODEL_PATH
from ...deps import db
from ... import roles
from .base import CachedModelFile, RecommendResult, lazy_joblib_load, rank_and_filter, unavailable


class GBMRecommender:
    source = 'gbm'

    def __init__(self):
        self._cache = CachedModelFile(GBM_MODEL_PATH, lazy_joblib_load, 'gbm-recommender')

    def _load_model(self):
        return self._cache.load()

    def recommend(self, row) -> RecommendResult:
        pipeline = self._load_model()
        if pipeline is None:
            return unavailable(
                self.source,
                'GradientBoost 모델이 아직 학습되지 않았습니다. '
                '`python tools/train_gbm_recommender.py`로 먼저 학습해주세요.',
            )
        text = f"{row['request_target'] or ''} {row['raw_text'] or ''}".strip()
        if not text:
            return unavailable(self.source, '청구 원문이 비어 있어 추천할 수 없습니다.')

        active_staff = {r['username'] for r in db.list_usernames_by_role(roles.STAFF)}
        proba = pipeline.predict_proba([text])[0]
        # 순위(1·2·3순위)까지만 보여준다. 모델이 내놓는 확률 수치는 실제 배정 이력이
        # 아니라 우리가 직접 만든 합성 데이터를 얼마나 잘 재현하는지를 반영할 뿐이라,
        # "78%" 같은 숫자를 화면에 보여주면 실제 정확도처럼 오해하기 쉽다 — 그래서 뺐다.
        return rank_and_filter(
            self.source, pipeline.classes_, proba, active_staff,
            'GradientBoost 추천 순위입니다. ⚠ 실제 배정 이력이 아직 부족해 합성 '
            '데이터로 학습된 모델이라 정확도가 검증되지 않았습니다 — 참고용으로만 활용하세요.',
        )
