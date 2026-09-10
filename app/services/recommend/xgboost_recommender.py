"""XGBoost(TF-IDF + `xgboost.XGBClassifier`) 기반 배정 추천.

학습은 `tools/train_xgboost_recommender.py`가 미리 해서 `app/config.py`의
`XGBOOST_MODEL_PATH`에 저장해두고, 여기서는 그 모델을 불러와 추론만 한다. 모델
파일이 없으면(아직 학습 전) 예외를 내지 않고 `available: False`로 응답한다 —
배정 화면 자체가 막히면 안 되므로. `gbm_recommender.py`와 거의 같은 구조이지만,
XGBoost는 문자열 레이블을 직접 못 받아들여서 학습 시 함께 저장해둔
`LabelEncoder`로 예측 결과(정수)를 다시 담당자 계정 이름으로 되돌려야 한다."""
from __future__ import annotations

from ...config import XGBOOST_MODEL_PATH
from ...deps import db
from ... import roles
from .base import CachedModelFile, RecommendResult, lazy_joblib_load, rank_and_filter, unavailable


def _load_pipeline_and_encoder(path):
    """`{'pipeline':..., 'label_encoder':...}` 형태가 아닌 파일(형식이 바뀌었거나
    손상된 경우)도 여기서 실패해야 `CachedModelFile`의 try/except가 잡아서
    `available: False`로 처리한다 — 여기 바깥에서 터지면 API가 500을 낸다."""
    saved = lazy_joblib_load(path)
    return saved['pipeline'], saved['label_encoder']


class XGBoostRecommender:
    source = 'xgboost'

    def __init__(self):
        self._cache = CachedModelFile(XGBOOST_MODEL_PATH, _load_pipeline_and_encoder, 'xgboost-recommender')

    def _load_model(self):
        """(pipeline, label_encoder) 튜플, 또는 모델이 아직 없으면 `None`."""
        return self._cache.load()

    def recommend(self, row) -> RecommendResult:
        loaded = self._load_model()
        if loaded is None:
            return unavailable(
                self.source,
                'XGBoost 모델이 아직 학습되지 않았습니다. '
                '`python tools/train_xgboost_recommender.py`로 먼저 학습해주세요.',
            )
        pipeline, label_encoder = loaded
        text = f"{row['request_target'] or ''} {row['raw_text'] or ''}".strip()
        if not text:
            return unavailable(self.source, '청구 원문이 비어 있어 추천할 수 없습니다.')

        active_staff = {r['username'] for r in db.list_usernames_by_role(roles.STAFF)}
        proba = pipeline.predict_proba([text])[0]
        classes = label_encoder.inverse_transform(pipeline.named_steps['xgb'].classes_)
        return rank_and_filter(
            self.source, classes, proba, active_staff,
            'XGBoost 추천 순위입니다. ⚠ 실제 배정 이력이 아직 부족해 합성 '
            '데이터로 학습된 모델이라 정확도가 검증되지 않았습니다 — 참고용으로만 활용하세요.',
        )
