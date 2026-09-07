"""GradientBoost 배정 추천 모델 학습용 합성 데이터.

실제 배정 이력이 아직 거의 없어서(2026-09-08 기준 완료된 배정 10건뿐, 학습에 쓰기엔
너무 적음) 부서별로 전형적인 청구 문구를 조합해 합성 데이터를 만들어 파이프라인부터
검증한다. 회사 DB 연동 이후 실제 배정 이력이 쌓이면, 이 모듈 대신
`db.list_requests()`의 완료된 배정 결과로 재학습해야 한다
(`tools/train_gbm_recommender.py`가 그 시점에 바뀔 부분).

`app/deps.py`의 `STAFF_ORG`(및 그걸로 만들어지는 `staff1`~`staff10` 계정)와 반드시
같은 구조를 유지해야 한다 — 여기서 다른 부서 배정을 새로 만들면 안 됨.
"""
from __future__ import annotations

import random

# app/deps.py의 STAFF_ORG를 그대로 부서별로 묶은 것 (staff번호, 지역본부).
STAFF_BY_DEPARTMENT: dict[str, list[tuple[str, str]]] = {
    '정보공개팀': [
        ('staff1', '서울지역본부'),
        ('staff2', '서울지역본부'),
        ('staff5', '인천지역본부'),
        ('staff8', '대전세종충남지역본부'),
    ],
    '고객지원팀': [
        ('staff3', '경기지역본부'),
        ('staff4', '경기지역본부'),
        ('staff10', '부산울산지역본부'),
    ],
    '총무팀': [
        ('staff6', '강원지역본부'),
        ('staff9', '전북지역본부'),
    ],
    '감사팀': [
        ('staff7', '충북지역본부'),
    ],
}

DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    '정보공개팀': ['정보공개 청구', '자료 공개', '문서 사본 발급', '공문서 열람', '보유 자료 제공', '회의록 공개'],
    '고객지원팀': ['전기요금 문의', '검침 오류', '정전 민원', '전기차 충전시설', '고객센터 상담 이력', '설비 고장 신고'],
    '총무팀': ['사무실 임대 계약', '비품 구매 현황', '조직도', '인사 발령 현황', '시설 관리 계약'],
    '감사팀': ['감사 결과 보고서', '내부통제 규정', '청렴도 평가', '부정 신고 처리 현황', '감사 지적 사항'],
}

TEMPLATES_WITH_REGION = [
    '{region} 관할 {keyword} 관련 자료를 공개해 주시기 바랍니다.',
    '{region}에서 처리한 {keyword} 건에 대해 문의드립니다.',
    '{region} 소관 {keyword} 현황을 알려주시기 바랍니다.',
    '{region} 대상 {keyword} 세부 내역 공개를 요청합니다.',
]
TEMPLATES_NO_REGION = [
    '{keyword}에 대한 최근 현황 자료를 요청드립니다.',
    '{keyword} 관련하여 세부 내역을 알고 싶습니다.',
    '최근 {keyword} 처리 결과를 공개해 주세요.',
    '{keyword}에 관한 자료를 정보공개 청구합니다.',
]


def generate_training_examples(per_department: int = 80, seed: int = 42) -> list[tuple[str, str]]:
    """(청구 원문, 정답 staff 계정) 쌍의 리스트. 부서마다 `per_department`건씩 만든다.
    같은 부서 안에서는 지역 언급 여부(60%)로만 담당자를 구분할 신호를 주기 때문에,
    지역이 언급 안 된 건은 모델이 부서 단위로만 정확히 맞히는 게 자연스럽다."""
    rng = random.Random(seed)
    examples: list[tuple[str, str]] = []
    for department, keywords in DEPARTMENT_KEYWORDS.items():
        staff_options = STAFF_BY_DEPARTMENT[department]
        for _ in range(per_department):
            keyword = rng.choice(keywords)
            staff, region = rng.choice(staff_options)
            if rng.random() < 0.6:
                text = rng.choice(TEMPLATES_WITH_REGION).format(region=region, keyword=keyword)
            else:
                text = rng.choice(TEMPLATES_NO_REGION).format(keyword=keyword)
            examples.append((text, staff))
    rng.shuffle(examples)
    return examples
