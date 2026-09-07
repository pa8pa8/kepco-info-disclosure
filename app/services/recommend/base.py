"""배정 추천 엔진 공통 결과 모양. LLM/GradientBoost든 나중에 추가할 다른 백엔드든
전부 이 모양으로 반환해야, 프런트엔드가 엔진 종류와 무관하게 같은 코드로 렌더링할 수 있다."""
from __future__ import annotations

from typing import Protocol, TypedDict


class RecommendResult(TypedDict):
    available: bool
    source: str
    recommendations: list[str]
    reason: str
    message: str


def unavailable(source: str, message: str) -> RecommendResult:
    """모델이 없거나, 아직 연동 전이거나, 입력이 부족해서 추천할 수 없을 때 공통으로 쓴다."""
    return {'available': False, 'source': source, 'recommendations': [], 'reason': '', 'message': message}


class Recommender(Protocol):
    source: str

    def recommend(self, row) -> RecommendResult: ...
