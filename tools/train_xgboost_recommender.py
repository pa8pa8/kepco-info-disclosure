#!/usr/bin/env python3
"""배정 추천용 XGBoost 모델을 학습해 `data/models/xgboost_recommender.joblib`에 저장한다.

데이터 소스는 `tools/train_gbm_recommender.py`와 동일하다 — `data/training/staff_assignments.csv`
(실제 배정 이력)가 있으면 그걸로, 없으면 합성 데이터로 학습한다(`tools/_training_data.py`).

XGBoost의 `XGBClassifier`는 문자열 레이블을 바로 못 받아들여서(정수 인코딩 필요),
`LabelEncoder`로 담당자 계정을 정수로 바꿔 학습하고, 저장할 때 파이프라인과 인코더를
함께 묶어둔다 — `app/services/recommend/xgboost_recommender.py`가 추론 시 다시 계정
이름으로 되돌리는 데 쓴다.

사용법:
    python tools/train_xgboost_recommender.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import LabelEncoder  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from app.config import XGBOOST_MODEL_PATH  # noqa: E402
from tools import _training_data  # noqa: E402

# 값을 다시 여기로 export하지 않고 매번 `_training_data.REAL_DATA_PATH`로 참조한다 —
# 그래야 테스트가 `_training_data.REAL_DATA_PATH`를 patch했을 때 실제로 반영된다
# (재바인딩된 이름을 patch하면 `_training_data` 안의 함수들은 못 본다).


def build_pipeline(sample_count: int) -> Pipeline:
    """TF-IDF 설정(`tools/_training_data.build_tfidf`, `train_gbm_recommender.py`와
    공유)에 XGBoost 분류기를 붙인다."""
    return Pipeline([
        ('tfidf', _training_data.build_tfidf(sample_count)),
        ('xgb', XGBClassifier(random_state=42, eval_metric='mlogloss')),
    ])


def main() -> None:
    examples, is_real = _training_data.load_training_examples()
    texts = [text for text, _ in examples]
    labels = [staff for _, staff in examples]
    label_counts = {label: labels.count(label) for label in set(labels)}

    label_encoder = LabelEncoder()
    encoded_labels = label_encoder.fit_transform(labels)

    real_name = _training_data.REAL_DATA_PATH.name
    print(f"학습 데이터 출처: {'실제 배정 이력 (' + real_name + ')' if is_real else '합성 데이터'}")
    print(f'총 {len(examples)}건, 담당자 {len(label_counts)}명 (담당자당 최소 {min(label_counts.values())}건)')

    can_validate = len(examples) >= _training_data.MIN_ROWS_FOR_VALIDATION_SPLIT and min(label_counts.values()) >= 2
    if can_validate:
        x_train, x_test, y_train, y_test = train_test_split(
            texts, encoded_labels, test_size=0.2, random_state=42, stratify=encoded_labels,
        )
        pipeline = build_pipeline(len(x_train))
        pipeline.fit(x_train, y_train)
        train_acc = pipeline.score(x_train, y_train)
        test_acc = pipeline.score(x_test, y_test)
        print(f'학습 데이터 {len(x_train)}건, 검증 데이터 {len(x_test)}건')
        print(f'학습 정확도: {train_acc:.1%} / 검증 정확도: {test_acc:.1%}')
        if is_real:
            print('※ 실제 데이터 기준 정확도입니다. 데이터가 늘어날수록 다시 확인해보세요.')
        else:
            print('※ 합성 데이터로 만든 규칙을 얼마나 잘 재현하는지를 잰 것이라, 실제 업무 정확도가 아닙니다.')
    else:
        print('데이터가 적어(또는 담당자당 1건뿐이라) 검증 없이 전체 데이터로만 학습합니다.')

    # 배포용 모델은 (검증했더라도) 전체 데이터로 다시 학습해 최대한 활용한다.
    pipeline = build_pipeline(len(examples))
    pipeline.fit(texts, encoded_labels)

    XGBOOST_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump({'pipeline': pipeline, 'label_encoder': label_encoder}, XGBOOST_MODEL_PATH)
    print(f'저장 완료: {XGBOOST_MODEL_PATH}')


if __name__ == '__main__':
    main()
