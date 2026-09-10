"""배정 추천 모델(GBM/XGBoost 등) 학습 스크립트가 공유하는 데이터 로딩·전처리 로직.

`tools/train_gbm_recommender.py`, `tools/train_xgboost_recommender.py`에서 쓴다.
실제 데이터 파일(`data/training/staff_assignments.csv`)은 개인정보라 `.gitignore`에
등록돼 있고, 이 저장소에는 절대 커밋되지 않는다 — 형식은
`data/training/staff_assignments.example.csv` 참고.
"""
from __future__ import annotations

import csv
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer

from app import roles
from app.deps import db
from app.services.recommend.synthetic_data import generate_training_examples

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


def build_tfidf(sample_count: int) -> TfidfVectorizer:
    """GBM/XGBoost 학습 파이프라인이 공유하는 TF-IDF 설정. 검증용과 최종 배포용이
    서로 다른 `min_df`를 쓰다 어긋나는 걸 막기 위해 한 곳으로 모았다 — 데이터가
    적으면(<50건) 어휘가 너무 걸러지지 않도록 완화."""
    return TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 3), min_df=1 if sample_count < 50 else 2)
