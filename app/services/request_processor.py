from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from ..config import WATCH_DIR
from ..db import Database
from . import foia_core
from .ai_client import AIClient

FILE_PATTERN = re.compile(r'^\d{6,8}_.+\.txt$')

# 청구인 성명·연락처·원문 길이 상한. 감시 폴더(data/watch) 자동 접수는 별도 검증을
# 거치지 않고 바로 이 함수로 들어오므로, DB에 과도하게 큰 값이 쌓이지 않도록 여기서 자른다.
MAX_NAME_LEN = 100
MAX_CONTACT_LEN = 200
MAX_RAW_TEXT_LEN = 20000


class RequestProcessorService:
    def __init__(self, db: Database, watch_dir: Path = WATCH_DIR, ai_client: AIClient | None = None):
        self.db = db
        self.default_watch_dir = watch_dir
        self.ai_client = ai_client or AIClient()
        self._task: asyncio.Task | None = None

    async def start(self, interval: int):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop(interval))

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _loop(self, interval: int):
        while True:
            try:
                await self.scan_once()
            except Exception as exc:  # pragma: no cover
                print(f'[request-processor] error: {exc}')
            await asyncio.sleep(interval)

    def _get_watch_dir(self) -> Path:
        path = self.db.get_setting('watch_dir', str(self.default_watch_dir)).strip() or str(self.default_watch_dir)
        watch_dir = Path(path)
        try:
            watch_dir.mkdir(parents=True, exist_ok=True)
            return watch_dir
        except OSError:
            self.default_watch_dir.mkdir(parents=True, exist_ok=True)
            return self.default_watch_dir

    @staticmethod
    def _parse_watch_file(text: str) -> dict[str, str]:
        requester_name = '미상'
        requester_contact = ''
        body = text
        header_match = re.match(r'^청구인:\s*(.*)\n연락처:\s*(.*)\n-+\n(.*)$', text, re.DOTALL)
        if header_match:
            requester_name = header_match.group(1).strip() or requester_name
            requester_contact = header_match.group(2).strip()
            body = header_match.group(3)
        return {'requester_name': requester_name, 'requester_contact': requester_contact, 'raw_text': body.strip()}

    async def scan_once(self) -> dict[str, Any]:
        watch_dir = self._get_watch_dir()
        known_files = self.db.get_log_source_files()
        new_count = 0
        for file_path in sorted(watch_dir.glob('*.txt')):
            if not FILE_PATTERN.match(file_path.name):
                continue
            if file_path.name in known_files:
                continue
            text = file_path.read_text(encoding='utf-8', errors='ignore')
            parsed = self._parse_watch_file(text)
            await self.ingest(
                requester_name=parsed['requester_name'],
                requester_contact=parsed['requester_contact'],
                channel='txt',
                raw_text=parsed['raw_text'],
                source_file=file_path.name,
            )
            new_count += 1
        return {'new_requests': new_count, 'watch_dir': str(watch_dir)}

    async def ingest(self, requester_name: str, requester_contact: str, channel: str, raw_text: str, source_file: str | None = None) -> int:
        requester_name = (requester_name or '')[:MAX_NAME_LEN]
        requester_contact = (requester_contact or '')[:MAX_CONTACT_LEN]
        raw_text = (raw_text or '')[:MAX_RAW_TEXT_LEN]
        request_id = self.db.create_request(requester_name, requester_contact, channel, raw_text, source_file)
        await self._run_ai_identify(request_id)
        return request_id

    async def _run_ai_identify(self, request_id: int):
        row = self.db.get_request(request_id)
        keywords = [k.strip() for k in self.db.get_setting('nondisclosure_keywords', '').split(',') if k.strip()]
        history = [
            {'id': h['id'], 'request_target': h['request_target'], 'raw_text': h['raw_text']}
            for h in self.db.recent_raw_texts(exclude_id=request_id)
        ]
        payload = {'raw_text': row['raw_text'], 'nondisclosure_keywords': keywords, 'history': history}
        ai_url = self.db.get_setting('ai_api_url', '')
        try:
            res = await self.ai_client.identify(payload, base_url=ai_url)
            target = res.get('request_target') or ''
            summary = res.get('summary') or ''
            hints = {
                'is_petition_hint': bool(res.get('is_petition_hint')),
                'nondisclosure_keywords_matched': res.get('nondisclosure_keywords_matched') or [],
            }
            self.db.set_request_ai_identity(request_id, target, summary, json.dumps(hints, ensure_ascii=False))

            repeat_match = res.get('repeat_match')
            is_repeat = bool(repeat_match)
            next_step, notice_type = foia_core.advance('repeat', is_repeat)
            self.db.apply_step_answer(
                request_id, 'repeat', is_repeat, next_step, notice_type,
                foia_core.get_step('repeat')['article'], actor='AI',
            )
            if is_repeat:
                self.db.set_repeat_match(request_id, repeat_match.get('request_id'))

            if notice_type:
                templates = self.db.get_all_settings()
                notice_text = foia_core.default_notice_text(templates, notice_type, target)
                self.db.finalize_notice(request_id, notice_text, decided_by='AI')
            else:
                self.db.set_request_status(request_id, '판단중')
        except Exception as exc:
            self.db.set_decision_error(request_id, str(exc))
            self.db.set_request_status(request_id, '판단중')
