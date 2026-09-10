"""`tools/train_xgboost_recommender.py`에만 있는 로직(파이프라인 구성).

실데이터 CSV 로딩/검증 로직은 `tools/_training_data.py`로 옮겨졌으므로
`tests/test_training_data.py`에서 다룬다."""
from __future__ import annotations

import tools.train_xgboost_recommender as train_module


def test_build_pipeline_uses_looser_min_df_for_small_datasets():
    small = train_module.build_pipeline(sample_count=10)
    large = train_module.build_pipeline(sample_count=100)
    assert small.named_steps['tfidf'].min_df == 1
    assert large.named_steps['tfidf'].min_df == 2
