# 변경 기록

- 일시: 2026-09-10 13:56
- 작성자: pa8pa8
- 작업번호: FOIA-0035
- 변경 유형: fix
- 상태: reviewed

## 변경 요약
"모든 가능성을 놓고 정밀검진"이라는 요청에 따라 실제로 `pyinstaller`로 onefile exe를
빌드해서 띄워봤고, 배포용 exe에서만 나타나는(테스트/dev 서버로는 못 잡는) 버그 3건을
발견해 고쳤다: (1) GBM/XGBoost 모델을 못 찾아 배정 추천 두 엔진이 항상 "학습 안 됨"으로
나오는 문제, (2) 로컬 AI 사이드카가 조용히 죽는 문제, (3) `data;data`로 통째로 묶는
방식이 `data/training/raw/`(실제 개인정보 가능성 있는 국정감사 원본 문서)를 배포용 exe
안에 그대로 박제할 수 있는 위험. 추가로, README가 안내하는 "가장 쉬운 실행 방법"인
`실행.bat`이 저장소에 아예 없다는 것(git 이력에도 없음)도 발견해 복구했다.

## 변경 내용
- `app/config.py`: `GBM_MODEL_PATH`/`XGBOOST_MODEL_PATH`를 `DATA_DIR`(exe 옆, 쓰기가능)
  기준에서 `RESOURCE_DIR`(onefile 번들, 읽기전용) 기준으로 변경. 일반 실행(venv)에서는
  두 경로가 같아 차이가 안 보이지만, onefile exe에서는 모델 파일이 `RESOURCE_DIR`
  쪽에만 존재해 `DATA_DIR` 기준으로는 항상 "파일 없음"이었다 — 실제 빌드로 재현·확인.
  GBM은 이 버그가 XGBoost 도입 이전부터 있었던 기존 결함.
- `BUILD_ONEFILE.txt`, `INFO_DISCLOSURE_System.spec`: 실제 동작하는 빌드 명령으로 갱신.
  - `app.ai_runtime.api` 등을 `--hidden-import`로 추가(문자열 경로로 uvicorn에 넘기는
    모듈이라 PyInstaller 정적 분석이 못 찾음 — 없으면 로컬 AI 사이드카 스레드가
    `ModuleNotFoundError`로 조용히 죽음).
  - `--collect-all sklearn`, `--hidden-import xgboost` + `--collect-data/--collect-binaries
    xgboost` 추가(두 모델 다 `joblib.load()`로만 읽고 `import sklearn`/`import xgboost`를
    직접 안 해서 PyInstaller가 못 찾음 — 없으면 모델 파일은 번들에 있어도 역직렬화 시
    `No module named 'sklearn.pipeline'`로 실패). `xgboost`는 `--collect-all`을 쓰면
    안 됨(`xgboost.testing`이 테스트 전용 의존성을 요구해 빌드 자체가 실패) — 세부
    옵션 조합으로 대체.
  - `--add-data "data;data"`(전체) → `--add-data "data/models;data/models"`(모델만)로
    축소. `data/` 전체를 묶으면 `.gitignore`로 커밋만 막아둔 `data/training/raw/`,
    `data/training/staff_assignments.csv`가 git 보호를 그대로 우회해 배포 exe 안에
    박제된다 — 지금 저장소에 실제로 `data/training/raw/`(AI TF자료 원본 11개 파일)가
    있는 상태였어서 재현 가능한 실제 위험이었음.
- `실행.bat` 신규 복구: Python PATH 확인 → `.installed` 마커로 최초 1회만 `pip install`
  → `python launcher.py` 실행. 콘솔 메시지는 CHANGELOG.md v1.1 기록에 남아있던 교훈대로
  영문으로만 작성(한글 콘솔 메시지가 코드페이지 문제로 깨졌던 전례).

## 원인
- 사용자 요청: "다시 모든 가능성을 놓고 정밀검진 해줘 / 디렉토리가 전문가가 쓰는 것
  처럼 정리되어있는지 확인해줘." 코드 리뷰만으로는 이 3가지를 못 잡는다 판단해 실제로
  `pip install pyinstaller` 후 문서화된 빌드 명령을 그대로 실행해 exe를 띄우고, 스크립트로
  로그인 → 배정 추천 API까지 실제 호출해 검증했다.
- `실행.bat`은 디렉토리 점검 중 README가 "가장 쉬운 방법"으로 안내하는 파일이 실제로는
  없다는 걸 발견 — `git log --all -- '*.bat'`로 확인해도 이력에 전혀 없어 커밋이 누락된
  것으로 판단, CHANGELOG.md v1.1 기록(추가했다는 기록은 있음)을 근거로 복구.

## 검증
- 확인 방법: 문서화된 명령 그대로 `pyinstaller --onefile ...`을 3~4회 반복 빌드하며
  단계별로 원인을 좁혀 확인(모델 경로 → sklearn/xgboost 언패킹 → ai_runtime 사이드카 →
  데이터 번들 범위). 매 수정 후 실제로 `dist/INFO_DISCLOSURE_System.exe`를 띄워 `/health`
  확인 후, DB에 직접 청구를 만들고 로그인·CSRF 토큰을 스크립트로 계산해
  `/api/requests/{id}/generate-recommendation`을 실제 호출.
  `실행.bat`도 별도로 직접 실행해 서버가 뜨는지 확인(PowerShell에서 백그라운드 실행 후
  `/health` 폴링).
  최종 빌드에서 `build/.../Analysis-00.toc`에 `data/training` 관련 항목이 0건인 것도
  확인.
- 결과: 최종 빌드에서 `gbm`/`xgboost` 둘 다 `available: true`로 실제 추천 반환 확인.
  로컬 AI 사이드카가 `ModuleNotFoundError` 없이 8011 포트에서 응답 확인. `실행.bat`
  실행 후 `/health` 정상 응답 확인. `pytest` 64개 전체 통과(dev 경로는 영향 없음 —
  `RESOURCE_DIR`가 non-frozen 환경에서는 기존 `DATA_DIR`와 같은 경로라 동작 동일).
- 빌드/실행 테스트에 쓴 `build/`·`dist/` 산출물은 검증 후 전부 삭제(`.gitignore`에 이미
  포함되어 있어 커밋 대상 아님).

## 리스크
- 영향 범위: onefile 배포 빌드 경로에만 영향(일반 `uvicorn`/`실행.bat` dev 실행은
  `RESOURCE_DIR == BASE_DIR`라 동일하게 동작). `실행.bat`는 신규 파일이라 기존 사용자
  워크플로에 영향 없음.
- 주의사항: `BUILD_ONEFILE.txt`에 "`data;data`로 되돌리지 말 것" 경고를 명시했다 —
  나중에 exe에 새 데이터를 추가로 번들해야 하면 반드시 개별 경로로만 추가해야 한다.

## 다음 조치
- 후속 작업: `data/watch/`·`data/ai_recommendations/`의 데모 예시 파일들도 `DATA_DIR`
  기준이라, onefile exe를 새로 빌드하면 그 데모가 처음부터 안 보인다(빌드 시점에
  번들해도 앱이 읽는 경로가 아님 — 이번 점검에서 발견했으나 개인정보 위험은 아니라서
  이번 수정 범위에서는 제외). 필요하면 "첫 실행 시 번들 리소스를 DATA_DIR로 복사"하는
  로직을 별도로 추가해야 함.
