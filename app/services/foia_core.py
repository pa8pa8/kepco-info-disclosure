from __future__ import annotations

import datetime as dt
from typing import Any

# 흐름도(docs/blueprint.jpeg -> docs/blueprint.html) 그대로 인코딩한 판단 그래프.
# 각 단계: 질문 / 근거 조문 / Y·N일 때 다음 단계(다음 단계가 없으면 최종 통지 유형 확정)
FLOW_STEPS: dict[str, dict[str, Any]] = {
    'repeat': {
        'label': '반복 청구 대상인가?',
        'article': '제11조의2',
        'note': '기존 통지한 사항과 동일한 답변을 할 수밖에 없는 경우',
        'on_yes': {'notice': '종결'},
        'on_no': 'information',
    },
    'information': {
        'label': "이 법에서 정한 '정보'인가?",
        'article': '제2조(정의)',
        'note': 'ex) 기록물, 매체, 영상 등',
        'on_yes': 'info_absent',
        'on_no': 'petition',
    },
    'petition': {
        'label': '진정·질의인가?',
        'article': '제11조 제5항 제2호',
        'note': "이 법에 따른 '정보'로 볼 수 없는, 진정·질의에 해당하는 경우",
        'on_yes': {'notice': '진정질의'},
        'on_no': 'info_absent',
    },
    'info_absent': {
        'label': "'정보부존재' 인가?",
        'article': '제11조 제5항 제1호(부존재)',
        'note': '공공기관이 정보를 1.생산·접수하지 않은 경우 2.가공·취합해야 하는 경우 3.포괄적 청구인 경우 4.기록물 관리법 등 기타 기한이 만료된 경우',
        'on_yes': {'notice': '정보부존재'},
        'on_no': 'alternative',
    },
    'alternative': {
        'label': "'대체정보'로 제공할 수 있는가?",
        'article': None,
        'note': None,
        'on_yes': 'nondisclosure',
        'on_no': 'nondisclosure',
    },
    'nondisclosure': {
        'label': '비공개 대상에 해당하는가?',
        'article': '제9조 제1항 제1~8호(비공개)',
        'note': None,
        'on_yes': 'partial',
        'on_no': {'notice': '공개'},
    },
    'partial': {
        'label': '부분공개 가능한가?',
        'article': '제14조(부분공개)',
        'note': None,
        'on_yes': {'notice': '부분공개'},
        'on_no': {'notice': '비공개'},
    },
}

FIRST_STEP = 'repeat'

NOTICE_LABELS = {
    '종결': '종결 통지서',
    '진정질의': '진정·질의 통지서',
    '정보부존재': '정보부존재 통지서',
    '공개': '공개 통지서',
    '부분공개': '부분공개 통지서',
    '비공개': '비공개 통지서',
}

NOTICE_TONE = {
    '종결': 'unknown',
    '진정질의': 'info',
    '정보부존재': 'precursor',
    '공개': 'normal',
    '부분공개': 'warning',
    '비공개': 'fault',
}


def get_step(step_key: str) -> dict[str, Any]:
    return FLOW_STEPS[step_key]


def advance(step_key: str, answer: bool) -> tuple[str | None, str | None]:
    """현재 단계에서 Y/N 답변을 적용한 결과.

    반환값: (다음 단계 key 또는 None, 최종 통지 유형 또는 None)
    다음 단계가 None이면 흐름이 종료된 것이며 최종 통지 유형이 채워진다.
    """
    step = FLOW_STEPS[step_key]
    branch = step['on_yes'] if answer else step['on_no']
    if isinstance(branch, dict):
        return None, branch['notice']
    return branch, None


def build_trail(decision_row) -> list[dict[str, Any]]:
    """DB에 저장된 각 단계 답변으로부터 판단 경로(조문 근거 포함)를 재구성."""
    trail = []
    column_map = [
        ('repeat', 'is_repeat'),
        ('information', 'is_information'),
        ('petition', 'is_petition'),
        ('info_absent', 'is_info_absent'),
        ('alternative', 'is_alternative_available'),
        ('nondisclosure', 'is_nondisclosure'),
        ('partial', 'is_partial_possible'),
    ]
    for step_key, column in column_map:
        value = decision_row[column] if decision_row else None
        if value is None:
            continue
        step = FLOW_STEPS[step_key]
        trail.append({
            'step': step_key,
            'label': step['label'],
            'article': step['article'],
            'answer': bool(value),
        })
    return trail


def default_notice_text(templates: dict[str, str], notice_type: str, request_target: str) -> str:
    key = f'notice_template_{notice_type}'
    base = templates.get(key, '')
    if request_target:
        return f'{base}\n\n(청구 요청대상: {request_target})'
    return base


# 정보공개법 제11조: 청구를 받은 날부터 10일 이내 공개 여부 결정, 부득이한 사유가 있으면
# 1회에 한해 10일 범위에서 연장 가능(제11조 제2항). 역일(달력일) 기준으로 계산한다 —
# 실제로는 공휴일 등을 뺀 근무일 기준으로 볼 여지도 있어 참고용이며 법률 자문이 아니다
# (README "알려진 제약사항" 참고).
STATUTORY_DAYS = 10
EXTENSION_DAYS = 10


def compute_deadline_info(received_at: str | None, extended: bool, is_finalized: bool) -> dict[str, Any] | None:
    """접수시각 문자열('YYYY-MM-DD HH:MM:SS' 형식)로부터 처리기한 정보를 계산한다.
    접수시각을 파싱할 수 없으면 None을 반환해 화면에서 조용히 생략할 수 있게 한다."""
    if not received_at:
        return None
    try:
        received_date = dt.datetime.strptime(received_at[:10], '%Y-%m-%d').date()
    except ValueError:
        return None

    total_days = STATUTORY_DAYS + (EXTENSION_DAYS if extended else 0)
    deadline_date = received_date + dt.timedelta(days=total_days)
    days_remaining = (deadline_date - dt.date.today()).days

    if is_finalized:
        tone = 'unknown'
        short_label = '완료'
        label = f"{deadline_date.isoformat()} 기한 내 완료" if days_remaining >= 0 else f"{deadline_date.isoformat()} 기한 초과 후 완료"
    elif days_remaining < 0:
        tone = 'fault'
        short_label = f"기한초과 D+{-days_remaining}"
        label = f"기한 초과 D+{-days_remaining} ({deadline_date.isoformat()})"
    elif days_remaining == 0:
        tone = 'fault'
        short_label = '오늘마감'
        label = f"오늘 마감 ({deadline_date.isoformat()})"
    elif days_remaining <= 3:
        tone = 'warning'
        short_label = f"D-{days_remaining}"
        label = f"D-{days_remaining} ({deadline_date.isoformat()})"
    else:
        tone = 'normal'
        short_label = f"D-{days_remaining}"
        label = f"D-{days_remaining} ({deadline_date.isoformat()})"

    return {
        'deadline_date': deadline_date.isoformat(),
        'days_remaining': days_remaining,
        'extended': extended,
        'tone': tone,
        'short_label': short_label,
        'label': label,
    }
