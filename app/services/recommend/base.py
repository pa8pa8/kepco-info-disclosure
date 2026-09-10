"""배정 추천 엔진 공통 결과 모양. LLM/GradientBoost든 나중에 추가할 다른 백엔드든
전부 이 모양으로 반환해야, 프런트엔드가 엔진 종류와 무관하게 같은 코드로 렌더링할 수 있다."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Protocol, TypedDict


class RecommendResult(TypedDict):
    available: bool
    source: str
    recommendations: list[str]
    reason: str
    message: str


def unavailable(source: str, message: str) -> RecommendResult:
    """모델이 없거나, 아직 연동 전이거나, 입력이 부족해서 추천할 수 없을 때 공통으로 쓴다."""
    return {'available': False, 'source': source, 'recommendations': [], 'reason': '', 'message': message}


def rank_and_filter(source: str, classes, proba, active_staff: set[str], reason: str) -> RecommendResult:
    """모델이 내놓은 클래스별 확률을 순위로 정렬하고, 학습 당시엔 있었지만 그 사이
    삭제/역할 변경된 계정은 제외한 뒤 상위 3명까지 추린다 — `GBMRecommender`/
    `XGBoostRecommender`가 공통으로 쓴다."""
    ranked = sorted(zip(classes, proba), key=lambda pair: pair[1], reverse=True)
    ranked = [(name, p) for name, p in ranked if name in active_staff][:3]
    if not ranked:
        return unavailable(source, '추천할 수 있는 업무담당자 계정이 없습니다.')
    return {
        'available': True,
        'source': source,
        'recommendations': [name for name, _ in ranked],
        'reason': reason,
        'message': '',
    }


def lazy_joblib_load(path):
    """joblib을 호출 시점에야 import한다 — joblib import 자체가 실패해도(의존성
    충돌 등) 추천 기능만 비활성화되고 앱 시작 자체는 막히지 않게 하려고."""
    import joblib
    return joblib.load(path)


class Recommender(Protocol):
    source: str

    def recommend(self, row) -> RecommendResult: ...


class CachedModelFile:
    """모델 파일을 파일 수정시각(mtime) 기준으로 캐싱해서 불러온다. 재학습해도
    서버를 재시작할 필요 없이 다음 요청부터 바로 새 모델이 반영되게 하려고
    (FOIA-0031 회귀 배경) `GBMRecommender`/`XGBoostRecommender`가 공통으로 쓴다."""

    def __init__(self, path: Path, loader: Callable[[Path], object], label: str):
        self._path = path
        self._loader = loader
        self._label = label
        self._value: object | None = None
        self._mtime: float | None = None

    def load(self) -> object | None:
        if not self._path.exists():
            self._value = None
            self._mtime = None
            return None
        mtime = self._path.stat().st_mtime
        if self._value is not None and mtime == self._mtime:
            return self._value
        try:
            self._value = self._loader(self._path)
            self._mtime = mtime
        except Exception as exc:  # 모델 파일 손상 등 — 추천 기능만 비활성화하고 앱은 계속 동작
            logging.getLogger(__name__).warning(
                '[%s] failed to load model at %s: %s', self._label, self._path, exc,
            )
            self._value = None
            self._mtime = None
            return None
        return self._value
