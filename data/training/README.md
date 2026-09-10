# 실제 배정 이력으로 GradientBoost 학습하기

## ⚠️ 먼저 확인하세요 — 개인정보

이 폴더에 넣는 실제 데이터는 청구 원문(청구인이 쓴 내용)을 그대로 포함합니다.
이 프로젝트는 **GitHub 공개 저장소**에 올라가 있으므로, 실제 데이터가 담긴 파일이
실수로 커밋되면 그대로 인터넷에 공개됩니다.

- 실제 데이터 파일 이름은 반드시 `staff_assignments.csv`로 만드세요 — `.gitignore`에
  이 이름만 정확히 등록돼 있어 커밋되지 않습니다. 다른 이름으로 만들면 보호되지
  않으니 주의하세요.
- `git add`/`git status`로 커밋 전 확인하는 습관을 들이세요. `staff_assignments.csv`가
  목록에 뜨면(정상이라면 안 떠야 함) 커밋하지 말고 바로 알려주세요.

## 파일 형식

`staff_assignments.csv`를 이 폴더에 직접 만드세요(엑셀에서 "CSV UTF-8"로 저장, 또는
메모장에서 UTF-8 인코딩으로 저장). 형식은 `staff_assignments.example.csv`(가짜 예시
데이터, 그대로 커밋되어 있음)를 참고하세요.

```csv
text,staff
"실제 청구 원문 내용을 여기에 그대로 붙여넣으세요.",staff1
"다른 청구 원문...",staff3
```

- `text`: 실제 청구 원문(또는 요청대상 요약). 쉼표나 줄바꿈이 들어가면 큰따옴표로
  감싸야 합니다(엑셀에서 저장하면 자동으로 처리됨).
- `staff`: **실제로 그 청구를 처리한(또는 처리해야 했던) 담당자의 아이디**
  (`staff1`~`staff10`, `/admin/users`에서 확인 가능). 실존하지 않는 아이디는 학습
  단계에서 자동으로 걸러집니다.

몇 건부터 학습할 수 있는지는 정해진 기준이 없지만, 담당자 한 명당 최소 몇 건은
있어야 그 담당자를 구분하는 신호가 생깁니다. 데이터가 아주 적으면(예: 20건 미만)
검증(학습에 안 쓰고 정확도 확인용으로 떼어두는 부분) 없이 전체를 학습에만 씁니다 —
`tools/train_gbm_recommender.py` 실행 시 화면에 어느 경우인지 표시됩니다.

## 학습 실행

```bash
python tools/train_gbm_recommender.py
python tools/train_xgboost_recommender.py
```

두 스크립트 모두 `data/training/staff_assignments.csv`가 있으면 그 실제 데이터로,
없으면 기존처럼 합성 데이터로 학습합니다(데이터 로딩 로직은 `tools/_training_data.py`
공유). 학습이 끝나면 각각 `data/models/gbm_recommender.joblib`,
`data/models/xgboost_recommender.joblib`이 갱신되고, 서버를 재시작하면(또는 다음
요청부터) 바로 반영됩니다.
