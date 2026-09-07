# 변경 기록

- 일시: 2026-09-08 01:37
- 작성자: cshs1729
- 작업번호: FOIA-0030
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
사용자 질문: "내가 데이터를 넣고 학습을 시키려면 어떻게 해야해??" — 지금까지는
`tools/train_gbm_recommender.py`가 합성 데이터만 학습할 수 있었고, 실제 데이터를
넣는 경로가 코드 안에 TODO 주석으로만 있었다(직접 파이썬을 고쳐야 하는 상태).
비개발자도 CSV 파일 하나 채워 넣는 것만으로 실제 데이터를 학습시킬 수 있게 만들었다.

## 변경 내용
- `data/training/staff_assignments.csv`(사용자가 직접 만드는 실제 데이터 파일,
  `text`/`staff` 두 컬럼)가 있으면 `tools/train_gbm_recommender.py`가 합성 데이터
  대신 그걸 우선 사용하도록 `load_training_examples()`를 재작성. 유효하지 않은 행
  (담당자 컬럼이 실존하지 않는 계정 등)은 건너뛰고 몇 번째 행인지 경고 출력.
- 데이터가 적을 때(10건 미만이거나 담당자 1명당 1건뿐)는 학습/검증 분리를 건너뛰고
  전체 데이터로만 학습 — `train_test_split(..., stratify=...)`가 클래스당 표본이
  2개 미만이면 예외를 내는 문제를 피하면서, 적은 데이터로도 일단 동작하게 함.
- **개인정보 보호**: 실제 데이터 파일은 청구인의 실제 원문(개인정보)을 담으므로
  `.gitignore`에 `data/training/staff_assignments.csv`(정확히 이 이름만) 추가 — 이
  저장소는 GitHub 공개 저장소라 실수로 커밋되면 그대로 노출된다. 대신 가짜 데이터로
  만든 `data/training/staff_assignments.example.csv`(형식 예시, 커밋됨)와
  `data/training/README.md`(작성 방법 + 개인정보 경고)를 추가.
- `README.md`의 "배정 추천 엔진" 절에 실제 데이터로 재학습하는 방법과 파일명을
  반드시 지켜야 하는 이유(개인정보 보호)를 추가.

## 원인
사용자 직접 질문. 실제 배정 이력을 학습에 반영하고 싶어도 지금은 코드를 직접 고쳐야
가능했는데, 그건 비개발자가 하기엔 진입장벽이 너무 높다.

## 검증
- 확인 방법: 가짜 테스트용 CSV 4행(유효 3행 + 존재하지 않는 계정 1행)을 만들어
  실행 → 4번째 행이 "staff99는 존재하는 업무담당자 계정이 아님"으로 정확히
  걸러지는 것 확인, "학습 데이터 출처: 실제 배정 이력" 정상 표시, 데이터가 적어
  검증 분리 없이 전체 학습으로 넘어가는 경로 확인. 테스트 파일 삭제 후 합성
  데이터로 재학습해 커밋용 모델 아티팩트 복원(`data/models/gbm_recommender.joblib`).
- `git check-ignore -v data/training/staff_assignments.csv`로 그 파일명이 실제로
  무시되는지 확인(exit 0, `.gitignore:11` 규칙에 매치).
- `python -m pytest -q` 48개 전부 통과.
- 결과: 전부 기대대로.

## 리스크
- 영향 범위: `tools/train_gbm_recommender.py`(학습 스크립트, 앱 실행 경로와 무관)와
  문서만 변경. 추론 코드(`gbm_recommender.py`)는 건드리지 않음.
- 주의사항: `.gitignore`는 파일명이 정확히 `staff_assignments.csv`일 때만 보호한다
  — 다른 이름으로 저장하면 보호되지 않으므로 `data/training/README.md`에서 이름을
  반드시 지키라고 강조해뒀다. 실수를 완전히 막을 수는 없으니, 커밋 전 `git status`로
  확인하는 습관이 여전히 필요.

## 다음 조치
- 후속 작업: 실제 데이터가 충분히 쌓이면(README에서 안내한 "담당자당 최소 몇 건"
  기준 참고) `gbm_recommender.py`의 "합성 데이터로 학습된 모델" 경고 문구를
  제거할 것(FOIA-0029에서 넣은 경고).
