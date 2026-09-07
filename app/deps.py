"""라우터들이 공유하는 싱글턴 인스턴스와 헬퍼 함수.

FastAPI 앱 인스턴스(`app/main.py`)와 라우터 모듈(`app/routers/`) 양쪽에서 이 모듈의
`db`/`ai_client`/`processor`/`templates`를 그대로 가져다 쓴다 — 요청마다 새로 만들지
않고 프로세스 전체에서 하나씩만 존재해야 하는 것들이라 여기 한 곳에 모아둔다.
"""

from __future__ import annotations

import json
import re

from fastapi.templating import Jinja2Templates

from . import roles
from .config import AI_RESULTS_DIR, INTERNAL_AI_API_URL, RESOURCE_DIR
from .db import Database
from .services import foia_core
from .services.ai_client import AIClient
from .services.local_ai_server import LocalAIServer
from .services.request_processor import RequestProcessorService

db = Database()
ai_client = AIClient()
processor = RequestProcessorService(db=db, ai_client=ai_client)
local_ai_server = LocalAIServer()
templates = Jinja2Templates(directory=str(RESOURCE_DIR / 'app' / 'templates'))

ROLE_HOME = roles.HOME

# 업무담당자 예시 계정의 소속(1차사업소=지역본부 / 2차사업소=지사 / 부서).
# 담당자 배정 검색 UI에서 이 정보로 필터링할 수 있다.
STAFF_ORG = [
    ('서울지역본부', '강남지사', '정보공개팀'),
    ('서울지역본부', '종로지사', '정보공개팀'),
    ('경기지역본부', '수원지사', '고객지원팀'),
    ('경기지역본부', '성남지사', '고객지원팀'),
    ('인천지역본부', '인천지사', '정보공개팀'),
    ('강원지역본부', '춘천지사', '총무팀'),
    ('충북지역본부', '청주지사', '감사팀'),
    ('대전세종충남지역본부', '대전지사', '정보공개팀'),
    ('전북지역본부', '전주지사', '총무팀'),
    ('부산울산지역본부', '부산지사', '고객지원팀'),
]

DEFAULT_ACCOUNTS = [
    ('admin', 'admin', roles.ADMIN, '', '', ''),
    ('manager', 'manager', roles.MANAGER, '', '', ''),
    ('dispatcher', 'dispatcher', roles.DISPATCHER, '', '', ''),
] + [
    (f'staff{i}', f'staff{i}', roles.STAFF, *STAFF_ORG[i - 1])
    for i in range(1, 11)
]


def current_settings() -> dict[str, str]:
    settings = db.get_all_settings()
    if not (settings.get('ai_api_url') or '').strip():
        settings['ai_api_url'] = INTERNAL_AI_API_URL
    settings['internal_ai_api_url'] = INTERNAL_AI_API_URL
    return settings


def with_deadline(row: dict) -> dict:
    """청구 dict에 처리기한 정보(`deadline`)를 계산해 붙여 반환한다. 목록/배정 대기
    화면에서 재사용하기 위한 공통 헬퍼."""
    row['deadline'] = foia_core.compute_deadline_info(
        row.get('received_at'),
        bool(row.get('deadline_extended')),
        bool(row.get('final_notice_type')),
    )
    return row


def load_ai_recommendation(row) -> dict | None:
    """청구의 접수 파일(`source_file`)과 같은 이름의 예시 결과 파일이
    `AI_RESULTS_DIR`에 있으면 파싱해서 반환하고, 없으면 None.

    실시간 계산이나 무작위 추천이 아니라 사전에 준비된 예시 txt를 그대로 읽는 것뿐이다.
    청구 목록/상세 화면 렌더링과 `/recommend` API가 이 함수 하나를 공유한다.
    """
    source_file = row['source_file']
    if not source_file:
        return None
    result_path = AI_RESULTS_DIR / source_file
    if not result_path.exists():
        return None

    text = result_path.read_text(encoding='utf-8', errors='ignore')
    staff_pool = {r['username'] for r in db.list_usernames_by_role(roles.STAFF)}
    recommendations: list[str] = []
    reason = ''
    for line in text.splitlines():
        line = line.strip()
        if line.startswith('사유'):
            reason = line.split(':', 1)[-1].strip() if ':' in line else line
            continue
        match = re.search(r'\b(staff\d+)\b', line)
        if match and match.group(1) in staff_pool and match.group(1) not in recommendations:
            recommendations.append(match.group(1))
    return {'recommendations': recommendations, 'reason': reason, 'source': 'ai'}


def load_reassign_candidates(row) -> dict | None:
    """업무담당자가 '거절(재배정 요청)'하며 지명한 1~3명이 있으면 반환한다.
    AI 예시 추천과 달리 실제 사람이 지명한 것이라 우선순위가 더 높다(`load_recommendation`
    참고). 지명된 계정이 그 사이 삭제됐을 수도 있어 현재도 유효한 업무담당자인지 다시 확인한다."""
    raw = row['reassign_candidates_json'] if 'reassign_candidates_json' in row.keys() else None
    if not raw:
        return None
    try:
        candidates = json.loads(raw)
    except (ValueError, TypeError):
        return None
    staff_pool = {r['username'] for r in db.list_usernames_by_role(roles.STAFF)}
    recommendations = [c for c in candidates if c in staff_pool]
    if not recommendations:
        return None
    return {'recommendations': recommendations, 'reason': '', 'source': 'reassign'}


def load_recommendation(row) -> dict | None:
    """배정 대기 화면/청구 상세에 보여줄 추천 담당자를 하나로 결정한다.
    업무담당자가 실제로 지명한 재배정 후보가 있으면 그것을 우선하고, 없으면
    사전 준비된 AI 예시 추천으로 대체한다."""
    return load_reassign_candidates(row) or load_ai_recommendation(row)
