from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .utils_text import (
    extract_request_target,
    find_repeat_candidate,
    is_petition_like,
    match_nondisclosure_keywords,
    summarize,
)

app = FastAPI(title='정보공개 청구 식별 API', version='1.0.0')

LOG_PATH = Path(__file__).resolve().parent.parent.parent / 'data' / 'ai_log.jsonl'


class HistoryItem(BaseModel):
    id: int
    request_target: str | None = None
    raw_text: str | None = None


class IdentifyRequest(BaseModel):
    raw_text: str
    nondisclosure_keywords: list[str] = []
    history: list[HistoryItem] = []


def _require_local_client(request: Request):
    host = (request.client.host if request.client else '') or ''
    if host not in ('127.0.0.1', '::1', 'localhost'):
        raise HTTPException(status_code=403, detail='local access only')


@app.get('/')
async def root(request: Request):
    _require_local_client(request)
    return {'service': 'info-disclosure-identify', 'status': 'ok'}


@app.get('/health')
async def health(request: Request):
    _require_local_client(request)
    return {'status': 'ok'}


@app.post('/identify')
async def identify(payload: IdentifyRequest, request: Request):
    _require_local_client(request)
    try:
        target = extract_request_target(payload.raw_text)
        history = [item.model_dump() for item in payload.history]
        repeat_match = find_repeat_candidate(target, history)
        result = {
            'request_target': target,
            'summary': summarize(payload.raw_text),
            'is_petition_hint': is_petition_like(payload.raw_text),
            'nondisclosure_keywords_matched': match_nondisclosure_keywords(payload.raw_text, payload.nondisclosure_keywords),
            'repeat_match': repeat_match,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'timestamp': datetime.now().isoformat(timespec='seconds'),
                'client_ip': request.client.host if request.client else None,
                'input': payload.model_dump(),
                'output': result,
            }, ensure_ascii=False) + '\n')
    except Exception:
        pass

    return result
