# 변경 기록

- 일시: 2026-09-10 13:56
- 작성자: pa8pa8
- 작업번호: FOIA-0033
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
배정 추천에 XGBoost 엔진을 GBM/LLM과 나란히 추가하고, 예시용 부서 체계(정보공개팀 등
4개 가상 부서)를 실제 KEPCO 본사 조직 데이터 기반 10개 부서로 교체했다. 두 학습
스크립트가 공유하는 데이터 로딩/전처리 로직을 `tools/_training_data.py`로,
GBM/XGBoost 추천기의 모델 캐싱·순위 필터링 로직을 `app/services/recommend/base.py`로
공통화했다.

## 변경 내용
- `app/services/recommend/xgboost_recommender.py` 신규: TF-IDF + `xgboost.XGBClassifier`.
  문자열 레이블을 못 받는 XGBoost 특성 때문에 학습 시 `LabelEncoder`를 함께 저장해두고
  추론 시 역변환한다.
- `app/services/recommend/base.py`: `CachedModelFile`(mtime 기준 모델 재로딩, 재학습해도
  서버 재시작 불필요 — FOIA-0031과 같은 이유), `rank_and_filter`(순위 정렬+활성 계정
  필터링 공통화), `lazy_joblib_load`(joblib import 실패해도 앱 전체가 안 죽게) 추가.
  `gbm_recommender.py`/`xgboost_recommender.py` 둘 다 이걸 쓰도록 리팩터링.
- `app/services/recommend/__init__.py`: `ENGINES`에 `xgboost` 등록.
- `app/deps.py`(`STAFF_ORG`), `app/services/recommend/synthetic_data.py`
  (`STAFF_BY_DEPARTMENT`/`DEPARTMENT_KEYWORDS`): 부서명을 국정감사 자료요구 배부내역
  원본(`data/training/raw/`, AI TF자료)에서 실제 건수가 많은 상위 10개 본사 부서
  (인사처/감사실/노사협력처/법무실/재무처/기획처 예산실/홍보처/기획처 국회/준법경영실/
  상생조달처)로 교체. staff1~10을 부서당 1명씩 매핑(기존엔 4개 부서에 여러 명씩).
- `tools/_training_data.py` 신규: `load_training_examples`/`load_real_examples`/
  `build_tfidf`를 `train_gbm_recommender.py`/`train_xgboost_recommender.py`가 공유.
- `tools/train_xgboost_recommender.py` 신규.
- `tools/convert_raw_training_data.py`, `tools/build_department_labels.py` 신규:
  AI TF자료(hwp/xlsx)를 표 손실 없이 텍스트로 변환하고(`hwp5proc` XML 파싱, 표 안
  내용도 보존 — `hwp5txt`는 표를 버려서 안 씀), 부서명 taxonomy 산정에 쓴
  `data/training/raw/department_labels.csv`(327건, 실제 부서 31개)를 생성.
  변환 후 한글 음절 수 비교로 손실 여부를 자동 검증.
- `requirements.txt`: `xgboost==2.1.4` 추가(3.2.0은 Requires-Python >=3.10라 프로젝트의
  Python 3.8+ 호환 기준 위반 — 다운그레이드로 해결, `docs/DEVELOPMENT_STANDARD.md` §5.1).
- 테스트: `tests/test_recommend.py`에 xgboost 엔진 테스트 3개 추가, `tests/test_training_data.py`
  신규(공유 데이터 로딩 로직), `tests/test_train_xgboost_recommender.py` 신규.

## 원인
- 사용자 요청: "클로드로 xgboost 학습할 수 있게 해줘" — GBM 외 두 번째 실동작 추천
  엔진을 추가해 비교 가능하게 함.
- 부서 체계는 이전 작업(담당자 배정 학습 데이터 준비)에서 확보한 실제 KEPCO 부서명
  데이터를, 기존에 예시로 만들어뒀던 가상 4개 부서 대신 쓰기로 결정(사용자 지시).

## 검증
- 확인 방법: `pytest`(64개) 전체 통과, `python tools/train_gbm_recommender.py`/
  `train_xgboost_recommender.py` 재학습 성공, `/code-review`를 여러 차례 돌려 발견한
  버그(joblib 즉시 import 회귀, hwp5proc FileNotFoundError 미처리, xgboost 문자열
  레이블 언패킹 시 예외 미차단, 정규식 콜론 파싱 버그, 프런트엔드 엔진 목록 하드코딩
  누락 등) 전부 수정 확인.
- 결과: `data/models/xgboost_recommender.joblib` 생성, `/api/requests/{id}/
  generate-recommendation`이 `gbm`/`xgboost`/`llm` 세 엔진을 정상 반환.

## 리스크
- 영향 범위: 배정 추천 화면(dispatcher/manager), 학습 스크립트, 부서 관련 예시 데이터.
  로컬 개발 DB의 staff 계정은 department가 비어 있어(NULL) 기존 배정 로직에 영향 없음.
- 주의사항: 두 모델 다 아직 실제 배정 이력이 아닌 합성 데이터로 학습됨 — 화면에 노출되는
  "정확도"는 실제 업무 정확도가 아니라는 경고 문구가 각 엔진 응답에 포함되어 있음.

## 다음 조치
- 후속 작업: 실제 정보공개청구 배정 이력이 쌓이면 `data/training/staff_assignments.csv`를
  채워 재학습(FOIA-0030 경로 재사용). `data/training/raw/department_labels.csv`(국정감사
  자료요구 기반)는 이 앱이 다루는 시민 청구와 도메인이 달라 그대로 학습에 못 쓴다는 점
  계속 유의.
