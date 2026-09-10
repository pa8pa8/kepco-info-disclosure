from __future__ import annotations

import os
import sys
from pathlib import Path


def get_app_root() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_resource_root() -> Path:
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_app_root()
RESOURCE_DIR = get_resource_root()
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

WATCH_DIR = Path(os.getenv('FOIA_WATCH_DIR', str(DATA_DIR / 'watch')))
WATCH_DIR.mkdir(parents=True, exist_ok=True)

# 배정 화면의 "AI 판단하기" 결과 예시 파일 저장 위치.
# data/watch/{source_file}과 같은 파일명으로 여기에 결과 txt를 넣어두면 그대로 불러와 보여준다.
# (실시간 AI 계산이나 무작위 추천이 아니라 사전에 준비된 예시를 그대로 읽는 방식)
AI_RESULTS_DIR = Path(os.getenv('FOIA_AI_RESULTS_DIR', str(DATA_DIR / 'ai_recommendations')))
AI_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv('FOIA_DB_PATH', str(DATA_DIR / 'info_disclosure.db')))

# 배정 추천 모델 위치. `tools/train_gbm_recommender.py`/`tools/train_xgboost_recommender.py`가
# 빌드 전 소스 트리의 `data/models/`에 미리 만들어두고, 앱은 읽기만 한다 — 그래서
# 실행 중 쓰기 가능해야 하는 DATA_DIR(exe 옆, 사용자별로 유지되는 DB 등)가 아니라
# RESOURCE_DIR(onefile 빌드 시 `--add-data`로 묶여 들어가는 읽기전용 번들) 기준으로
# 잡는다. 일반 실행(비-frozen)에서는 RESOURCE_DIR == BASE_DIR라 동작이 같다 — onefile
# exe에서 DATA_DIR을 썼다가 모델 파일을 못 찾던 문제가 있었다(실제 빌드로 재현·확인).
GBM_MODEL_PATH = Path(os.getenv('FOIA_GBM_MODEL_PATH', str(RESOURCE_DIR / 'data' / 'models' / 'gbm_recommender.joblib')))
XGBOOST_MODEL_PATH = Path(os.getenv('FOIA_XGBOOST_MODEL_PATH', str(RESOURCE_DIR / 'data' / 'models' / 'xgboost_recommender.joblib')))
AI_SERVER_HOST = os.getenv('FOIA_AI_SERVER_HOST', '127.0.0.1').strip()
AI_SERVER_PORT = int(os.getenv('FOIA_AI_SERVER_PORT', '8011'))
INTERNAL_AI_API_URL = f'http://{AI_SERVER_HOST}:{AI_SERVER_PORT}/identify'
AI_BUNDLE_DIR = Path(os.getenv('FOIA_AI_BUNDLE_DIR', str(RESOURCE_DIR / 'ai_bundle')))
SCAN_INTERVAL = int(os.getenv('FOIA_SCAN_INTERVAL', '60'))
APP_TITLE = '한국전력공사 정보공개 청구 지원 시스템'
