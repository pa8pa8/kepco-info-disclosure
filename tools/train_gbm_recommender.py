#!/usr/bin/env python3
"""배정 추천용 GradientBoost 모델을 학습해 `data/models/gbm_recommender.joblib`에 저장한다.

지금은 실제 배정 이력이 너무 적어서(2026-09-08 기준 10건) 부서별 전형적인 청구
문구로 만든 합성 데이터로 학습한다(`app/services/recommend/synthetic_data.py`).
회사 DB 연동 이후 실제 배정 이력이 쌓이면, 아래 `load_training_examples()`를
`db.list_requests()`의 완료된 배정 결과를 읽어오는 방식으로 바꿔야 한다.

사용법:
    python tools/train_gbm_recommender.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402

from app.config import GBM_MODEL_PATH  # noqa: E402
from app.services.recommend.synthetic_data import generate_training_examples  # noqa: E402


def load_training_examples() -> list[tuple[str, str]]:
    # TODO(회사 DB 연동 이후): 여기를 실제 배정 이력 조회로 교체.
    return generate_training_examples()


def main() -> None:
    examples = load_training_examples()
    texts = [text for text, _ in examples]
    labels = [staff for _, staff in examples]

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels,
    )

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=2)),
        ('gbm', GradientBoostingClassifier(random_state=42)),
    ])
    pipeline.fit(x_train, y_train)

    train_acc = pipeline.score(x_train, y_train)
    test_acc = pipeline.score(x_test, y_test)
    print(f'학습 데이터 {len(x_train)}건, 검증 데이터 {len(x_test)}건')
    print(f'학습 정확도: {train_acc:.1%} / 검증 정확도: {test_acc:.1%}')

    # 배포용 모델은 전체 데이터로 다시 학습(검증 분리 없이 최대한 활용).
    pipeline.fit(texts, labels)

    GBM_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(pipeline, GBM_MODEL_PATH)
    print(f'저장 완료: {GBM_MODEL_PATH}')


if __name__ == '__main__':
    main()
