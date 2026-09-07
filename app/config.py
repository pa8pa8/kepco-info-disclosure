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
AI_SERVER_HOST = os.getenv('FOIA_AI_SERVER_HOST', '127.0.0.1').strip()
AI_SERVER_PORT = int(os.getenv('FOIA_AI_SERVER_PORT', '8011'))
INTERNAL_AI_API_URL = f'http://{AI_SERVER_HOST}:{AI_SERVER_PORT}/identify'
AI_BUNDLE_DIR = Path(os.getenv('FOIA_AI_BUNDLE_DIR', str(RESOURCE_DIR / 'ai_bundle')))
SCAN_INTERVAL = int(os.getenv('FOIA_SCAN_INTERVAL', '60'))
APP_TITLE = '한국전력공사 정보공개 청구 지원 시스템'
