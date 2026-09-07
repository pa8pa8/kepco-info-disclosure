#!/usr/bin/env python3
"""배정 추천용 GradientBoost 모델을 학습해 `data/models/gbm_recommender.joblib`에 저장한다.

`data/training/staff_assignments.csv`(실제 배정 이력 — `data/training/README.md` 참고)가
있으면 그걸로, 없으면 부서별 전형적인 청구 문구로 만든 합성 데이터로 학습한다
(`app/services/recommend/synthetic_data.py`). 실제 데이터 파일은 개인정보라 `.gitignore`
에 등록돼 있고, 이 저장소에는 절대 커밋되지 않는다.

사용법:
    python tools/train_gbm_recommender.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402

from app import roles  # noqa: E402
from app.config import GBM_MODEL_PATH  # noqa: E402
from app.deps import db  # noqa: E402
from app.services.recommend.synthetic_data import generate_training_examples  # noqa: E402

REAL_DATA_PATH = Path(__file__).resolve().parent.parent / 'data' / 'training' / 'staff_assignments.csv'
MIN_ROWS_FOR_VALIDATION_SPLIT = 10


def load_real_examples() -> list[tuple[str, str]]:
    """`data/training/staff_assignments.csv`를 읽는다. `text`/`staff` 두 컬럼이 필요하고,
    `staff`는 실제로 존재하는 업무담당자 계정이어야 한다(그 외 행은 건너뛰고 경고)."""
    active_staff = {r['username'] for r in db.list_usernames_by_role(roles.STAFF)}
    examples: list[tuple[str, str]] = []
    with REAL_DATA_PATH.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or {'text', 'staff'} - set(reader.fieldnames):
            print(f'경고: {REAL_DATA_PATH.name}에 "text"/"staff" 컬럼이 없습니다. '
                  'data/training/staff_assignments.example.csv 형식을 참고하세요.')
            return []
        for i, row in enumerate(reader, start=2):  # 2행부터(1행은 헤더)
            text = (row.get('text') or '').strip()
            staff = (row.get('staff') or '').strip()
            if not text or not staff:
                print(f'  {i}행 건너뜀: text 또는 staff가 비어 있음')
                continue
            if staff not in active_staff:
                print(f'  {i}행 건너뜀: "{staff}"는 존재하는 업무담당자 계정이 아님')
                continue
            examples.append((text, staff))
    return examples


def load_training_examples() -> tuple[list[tuple[str, str]], bool]:
    """(학습 데이터, 실제 데이터 여부)를 반환한다."""
    if REAL_DATA_PATH.exists():
        real_examples = load_real_examples()
        if real_examples:
            return real_examples, True
        print(f'{REAL_DATA_PATH.name}이 있지만 유효한 행이 없어 합성 데이터로 대신합니다.')
    return generate_training_examples(), False


def main() -> None:
    examples, is_real = load_training_examples()
    texts = [text for text, _ in examples]
    labels = [staff for _, staff in examples]
    label_counts = {label: labels.count(label) for label in set(labels)}

    print(f"학습 데이터 출처: {'실제 배정 이력 (' + REAL_DATA_PATH.name + ')' if is_real else '합성 데이터'}")
    print(f'총 {len(examples)}건, 담당자 {len(label_counts)}명 (담당자당 최소 {min(label_counts.values())}건)')

    can_validate = len(examples) >= MIN_ROWS_FOR_VALIDATION_SPLIT and min(label_counts.values()) >= 2
    if can_validate:
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
        if is_real:
            print('※ 실제 데이터 기준 정확도입니다. 데이터가 늘어날수록 다시 확인해보세요.')
        else:
            print('※ 합성 데이터로 만든 규칙을 얼마나 잘 재현하는지를 잰 것이라, 실제 업무 정확도가 아닙니다.')
    else:
        print('데이터가 적어(또는 담당자당 1건뿐이라) 검증 없이 전체 데이터로만 학습합니다.')

    # 배포용 모델은 (검증했더라도) 전체 데이터로 다시 학습해 최대한 활용한다.
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=1 if len(examples) < 50 else 2)),
        ('gbm', GradientBoostingClassifier(random_state=42)),
    ])
    pipeline.fit(texts, labels)

    GBM_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import joblib
    joblib.dump(pipeline, GBM_MODEL_PATH)
    print(f'저장 완료: {GBM_MODEL_PATH}')


if __name__ == '__main__':
    main()
