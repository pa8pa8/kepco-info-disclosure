# 변경 기록

- 일시: 2026-09-08 01:21
- 작성자: cshs1729
- 작업번호: FOIA-0028
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
사용자 지시: "업무 담당자 배정을 LLM과 GradientBoost 두가지로 일단 하고 싶어." 지난
FOIA-0026에서 "AI 판단은 나중에 실제 AI로 연동 예정, 그 전까지 데모 로직을 다듬지
않는다"고 적어뒀던 항목을, 사용자가 직접 이 특정 기능(배정 추천)만 지금 착수하자고
결정해 실제로 시작. "AI로 생성하기" 버튼이 이제 사전 준비된 예시가 없는 청구에서
실제 GradientBoost 추천과 LLM 인터페이스를 나란히 보여준다.

## 변경 내용

### 확인한 두 가지 질문 (사전 확인, AskUserQuestion)
- LLM 연동 방식 → "지금은 인터페이스만 구축" 선택. 외부 API/로컬 LLM 중 어느 쪽을 쓸지,
  청구인 개인정보를 외부로 보내도 되는지가 아직 미정이라 실제 호출은 넣지 않음.
- GradientBoost 학습 데이터 → "합성 데이터로 일단 구조만" 선택. 실제 배정 이력이
  10건뿐이라 학습에 부족.

### 새 패키지 `app/services/recommend/`
- `base.py`: 공통 결과 모양 `RecommendResult`(`available`/`source`/`recommendations`/
  `reason`/`message`) — 어느 엔진이든 같은 모양으로 반환해 프런트가 엔진 구분 없이
  렌더링할 수 있게 함.
- `synthetic_data.py`: `app/deps.py`의 `STAFF_ORG`(부서·지역본부 구조)와 정확히
  일치하는 합성 학습 데이터 생성기. 부서별 전형 키워드(정보공개팀/고객지원팀/총무팀/
  감사팀) + 지역 언급 여부(60%만)로 문장을 만들어 부서 단위는 확실히, 부서 내 담당자는
  지역 신호가 있을 때만 구분 가능하게 설계(실제 데이터의 노이즈를 흉내).
- `gbm_recommender.py`: TF-IDF(문자 2~3-gram — 한글 형태소 분석기 없이 동작, 외부
  NLP 라이브러리 의존 안 만듦) + `GradientBoostingClassifier`. 학습된 모델 파일이
  없거나 손상됐으면 예외 없이 `available: false`(배정 화면 자체가 막히면 안 되므로).
  예측 후보 중 이미 삭제/역할 변경된 계정은 걸러냄.
- `llm_recommender.py`: 인터페이스만. `FOIA_LLM_API_KEY` 환경변수를 설정 표면으로
  잡아뒀고, 항상 "준비 중" 메시지 반환. 실제 연동 지점은 파일 안의 TODO 주석.

### 학습 스크립트 + 모델 아티팩트
- `tools/train_gbm_recommender.py`: 합성 데이터 256건 학습/64건 검증으로 분리해
  정확도 확인(학습 90.2% / 검증 68.8% — 10-클래스 분류치고 실신호 있음을 확인) 후
  전체 데이터로 재학습해 저장. `app/config.py`에 `GBM_MODEL_PATH`(env:
  `FOIA_GBM_MODEL_PATH`) 추가.
- `data/models/gbm_recommender.joblib`(1.5MB) 커밋 — 재현 가능하고 결정적(seed=42)
  이라 매 배포마다 재학습할 필요 없음. 실제 이력이 쌓이면 재학습 후 다시 커밋.

### 백엔드/프런트 연결
- `app/routers/requests.py`의 `/api/requests/{id}/generate-recommendation`을 항상
  "5건만 지원" 안내만 하던 것에서, `ENGINES`(gbm+llm)를 각각 돌려
  `{'engines': {'gbm': ..., 'llm': ...}}`로 반환하도록 교체. 권한(DISPATCHER/MANAGER)·
  CSRF·배정 상태 검증은 기존 그대로.
- `app/static/js/app.js`: `generateRecommendation()`이 `renderEngineComparison()`을
  호출해 두 엔진 결과를 순서대로(GradientBoost 먼저, LLM 다음) 카드로 보여줌. 사용
  가능한 엔진은 기존 `rank-secondary` 버튼(클릭 시 바로 배정)으로, 사용 불가능한
  엔진은 이유 메시지만 표시.
- `request_detail.html`/`dispatch.html`의 "🤖 AI 판단하기" 버튼에 `id="recommend-btn-
  {id}"`를 붙이고, 추천 결과가 나오면 JS로 숨김 — 결과가 이미 나온 뒤에도 그 버튼이
  남아있어 다시 누르면 "결과 없음" 사이클을 반복하던 UX 군더더기를 정리.
- `krds.css`에 `.engine-result + .engine-result` 구분선 추가.

### 의존성
- `requirements.txt`에 `scikit-learn==1.3.2`/`numpy==1.24.4`/`scipy==1.10.1`/
  `joblib==1.3.2`/`threadpoolctl==3.2.0` 추가. **`docs/DEVELOPMENT_STANDARD.md`의
  "Python 3.8 이상" 호환 기준을 지키기 위해 일부러 오래된 버전으로 골랐다** — 처음
  아무 버전이나 설치했을 때 scikit-learn 1.7.x가 Python 3.10+를 요구하는 걸 발견해
  1.3.2로 낮추고, scipy도 자동 해석에 맡기면 Python 3.10+ 전용 버전이 딸려와서
  1.10.1로 명시적으로 고정(둘 다 요구사항을 직접 확인). scipy는 `<3.12` 상한이 있어
  Python 3.12+ 서버에 배포한다면 재검증 필요 — 주석으로 남김.

### 문서
- `docs/PROJECT_REVIEW.md` "확정된 향후 계획" 12번을 "지금은 착수하지 않음"에서
  실제로 착수한 내용으로 갱신(로그인/계정 항목인 11번은 그대로 미착수 유지).
- `README.md`: "배정 대기 화면의 AI 판단하기" 절에서 "AI로 생성하기"가 이제 실제
  엔진으로 연결됨을 반영, "배정 추천 엔진(LLM · GradientBoost)" 절 신규.

## 원인
사용자 직접 지시.

## 검증
- 확인 방법: `python tools/train_gbm_recommender.py` 실행 → 학습 90.2%/검증 68.8%.
  실제 청구 텍스트로 추론 테스트 — "서울지역본부 관할 정보공개 청구"→staff2 93%,
  "경기지역본부 전기요금 문의"→staff3 74%, "감사 결과 보고서"→staff7 100%(정답
  부서·지역과 일치). `pytest` 48개 전부 통과(신규 `tests/test_recommend.py` 7개
  포함 — GBM 정상/빈 텍스트 처리, LLM 미설정 응답, API 권한·CSRF·배정 상태 검증).
- 개발 서버 재기동 후 Playwright로 `/requests/{id}`와 `/dispatch` 양쪽에서 실제
  버튼 클릭 흐름(AI 판단하기 → 결과 없음 → AI로 생성하기 → 두 엔진 카드 렌더링,
  기존 "AI 판단하기" 버튼 숨김)을 확인, 콘솔 에러 없음.
- 결과: 전부 기대대로.

## 리스크
- 영향 범위: 신규 패키지 하나(`app/services/recommend/`), 기존 배정 로직·판단
  위저드·권한 체계는 건드리지 않음. `requirements.txt`에 무거운 의존성(numpy/scipy
  포함 5개) 추가 — "최소 의존성" 원칙에서 벗어난 의도적 예외.
- 주의사항: GBM이 **합성 데이터로 학습된 상태**라는 걸 배정담당자가 실제 이력 기반
  추천처럼 오인할 수 있어, 초안 작성 중 바로 반영 — 추천 사유 문구 끝에
  "⚠ 실제 배정 이력이 아직 부족해 합성 데이터로 학습된 모델입니다"를 항상 붙임
  (`gbm_recommender.py`). 회사 DB 연동으로 실제 배정 이력이 쌓이면
  `tools/train_gbm_recommender.py`의 `load_training_examples()`를 실제 이력 조회로
  바꾸고 재학습·재커밋하면서 이 경고 문구도 제거할 것.

## 다음 조치
- 후속 작업: LLM 실제 연동(공급자 선정 후 `llm_recommender.py`의 TODO 구현). 실제
  배정 이력이 쌓이면 GBM 재학습(그때 합성 데이터 경고 문구 제거).
