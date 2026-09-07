from __future__ import annotations

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
