"""GradientBoost(TF-IDF + scikit-learn `GradientBoostingClassifier`) 기반 배정 추천.

학습은 `tools/train_gbm_recommender.py`가 미리 해서 `app/config.py`의 `GBM_MODEL_PATH`에
저장해두고, 여기서는 그 모델을 불러와 추론만 한다. 모델 파일이 없으면(아직 학습 전)
예외를 내지 않고 `available: False`로 응답한다 — 배정 화면 자체가 막히면 안 되므로."""
from __future__ import annotations

import logging

from ...config import GBM_MODEL_PATH
from ...deps import db
from ... import roles
from .base import RecommendResult, unavailable

logger = logging.getLogger(__name__)

_model = None
_load_attempted = False


def _load_model():
    global _model, _load_attempted
    if _load_attempted:
        return _model
    _load_attempted = True
    if not GBM_MODEL_PATH.exists():
        return None
    try:
        import joblib
        _model = joblib.load(GBM_MODEL_PATH)
    except Exception as exc:  # 모델 파일 손상 등 — 추천 기능만 비활성화하고 앱은 계속 동작
        logger.warning('[gbm-recommender] failed to load model at %s: %s', GBM_MODEL_PATH, exc)
        _model = None
    return _model


class GBMRecommender:
    source = 'gbm'

    def recommend(self, row) -> RecommendResult:
        pipeline = _load_model()
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
        ranked = sorted(zip(pipeline.classes_, proba), key=lambda pair: pair[1], reverse=True)
        # 학습 당시엔 있었지만 그 사이 삭제/역할 변경된 계정은 제외.
        ranked = [(name, p) for name, p in ranked if name in active_staff][:3]
        if not ranked:
            return unavailable(self.source, '추천할 수 있는 업무담당자 계정이 없습니다.')

        confidence = ' · '.join(f'{name} {p * 100:.0f}%' for name, p in ranked)
        return {
            'available': True,
            'source': self.source,
            'recommendations': [name for name, _ in ranked],
            'reason': f'GradientBoost 예측 신뢰도 — {confidence} (⚠ 실제 배정 이력이 아직 부족해 합성 데이터로 학습된 모델입니다)',
            'message': '',
        }
