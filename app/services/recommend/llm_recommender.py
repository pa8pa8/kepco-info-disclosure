"""LLM 기반 배정 추천 — 지금은 인터페이스만 구축한 상태다.

실제 LLM 호출은 아직 연결하지 않았다(사용자 결정, 2026-09-08 — 어떤 공급자를 쓸지,
API 키를 어떻게 관리할지, 청구인 개인정보를 외부로 보내도 되는지가 아직 정해지지
않아서). `FOIA_LLM_API_KEY` 환경변수를 이 모듈의 설정 표면으로 미리 잡아뒀다 — 나중에
실제 연동할 때 `recommend()` 안의 TODO 부분만 채우면 된다.
`docs/PROJECT_REVIEW.md` "확정된 향후 계획" 12번 참고."""
from __future__ import annotations

import os

from .base import RecommendResult, unavailable


class LLMRecommender:
    source = 'llm'

    def recommend(self, row) -> RecommendResult:
        api_key = os.getenv('FOIA_LLM_API_KEY', '').strip()
        if not api_key:
            return unavailable(
                self.source,
                'LLM 연동은 아직 준비 중입니다 (FOIA_LLM_API_KEY 환경변수 미설정).',
            )
        # TODO: 실제 LLM 연동 지점. 예)
        #   1. row['raw_text']/row['request_target']와 배정 가능한 업무담당자 목록
        #      (db.list_directory_by_role(roles.STAFF))을 프롬프트에 넣어 호출
        #   2. 응답에서 1~3순위 staff 계정명과 추천 사유를 파싱
        #   3. gbm_recommender.py의 반환 모양과 동일하게
        #      {'available': True, 'source': 'llm', 'recommendations': [...], 'reason': ..., 'message': ''}
        #      형태로 반환
        return unavailable(self.source, 'LLM 연동 로직이 아직 구현되지 않았습니다.')
