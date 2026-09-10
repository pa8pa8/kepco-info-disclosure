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
# 부서마다 예시로 쓸 staff가 1명뿐이라, 부서 안에서 지역 언급으로 담당자를 구분하는
# 신호는 더 이상 없다 — generate_training_examples()의 지역 언급 여부는 이제 문장
# 표현을 다양하게 만드는 용도일 뿐이다.
STAFF_BY_DEPARTMENT: dict[str, list[tuple[str, str]]] = {
    '인사처': [('staff1', '서울지역본부')],
    '감사실': [('staff2', '서울지역본부')],
    '노사협력처': [('staff3', '경기지역본부')],
    '법무실': [('staff4', '경기지역본부')],
    '재무처': [('staff5', '인천지역본부')],
    '기획처 예산실': [('staff6', '강원지역본부')],
    '홍보처': [('staff7', '충북지역본부')],
    '기획처 국회': [('staff8', '대전세종충남지역본부')],
    '준법경영실': [('staff9', '전북지역본부')],
    '상생조달처': [('staff10', '부산울산지역본부')],
}

# 국정감사 자료요구 배부내역에서 실제로 각 부서가 처리한 요구 항목
# (data/training/raw/department_labels.csv)을 요약해 짧은 키워드로 옮긴 것.
DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    '인사처': ['임직원 징계 현황', '장애인 의무고용률 현황', '직제 외 임시조직 운영현황', '인사위원회 회의록', '기관장 업무보고서'],
    '감사실': ['감사원 감사 결과', '자체 감사 실시 현황', '출자출연기관 감사 현황', '형사 입건·수사 통보 현황', '내부통제 규정'],
    '노사협력처': ['비정규직 채용현황', '초과근무시간 현황', '시민단체 지원금 내역', '직장 보육시설 설치현황', '고소·고발·진정 건수'],
    '법무실': ['외부 고문·자문위원 계약내역', '기관 소송 및 보상 현황', '소관 지침·정관·규정집', '법제처 유권심사 의뢰현황', '입법 계획'],
    '재무처': ['예산 및 집행현황', '회계감사보고서', '자산·부채 이자지출 내역', '업무추진비 집행현황', '보유자산 임대 현황'],
    '기획처 예산실': ['예산안 편성 관련', '예비타당성조사 결과', '사고사업 지정 현황', '신규사업 사업계획서', '주요사업 세부시행 계획'],
    '홍보처': ['언론보도 해명자료', '홍보비 집행내역', '언론중재위원회 제소현황', '직원비리 관련 언론보도 조치내용'],
    '기획처 국회': ['국정감사 지적사항 조치현황', '국회 임시회 업무보고자료', '국정감사 자료요구 목록', '인사청문회 답변자료'],
    '준법경영실': ['임직원 겸직허가 현황', '정부위원회 권고·시정·제재 현황', '성희롱 예방 교육 실시 현황', '직장 내 성비위 사건 현황'],
    '상생조달처': ['용역 발주 및 용역비용 현황', '중증장애인 생산품 구매실적', '계약 및 해약현황', '계약사무 관련'],
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
    부서당 staff가 1명뿐이라 지역 언급 여부(60%)는 담당자를 구분하는 신호가 아니라
    문장 표현을 다양하게 만드는 용도일 뿐이다."""
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
