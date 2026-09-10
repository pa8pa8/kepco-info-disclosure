"""업무담당자 배정 추천 엔진들. 여러 백엔드를 나란히 시도해볼 수 있게 같은
`RecommendResult` 모양으로 결과를 돌려준다 (`base.py` 참고).

- `gbm`: TF-IDF + scikit-learn `GradientBoostingClassifier`. 실제로 동작한다
  (`tools/train_gbm_recommender.py`가 만든 모델 사용).
- `xgboost`: TF-IDF + `xgboost.XGBClassifier`. 실제로 동작한다
  (`tools/train_xgboost_recommender.py`가 만든 모델 사용).
- `llm`: 인터페이스만 구축된 상태 — 아직 실제 LLM 호출은 연결하지 않았다
  (docs/PROJECT_REVIEW.md "확정된 향후 계획" 12번 참고).
"""
from __future__ import annotations

from .gbm_recommender import GBMRecommender
from .llm_recommender import LLMRecommender
from .xgboost_recommender import XGBoostRecommender

ENGINES = {
    'gbm': GBMRecommender(),
    'xgboost': XGBoostRecommender(),
    'llm': LLMRecommender(),
}
