from __future__ import annotations

from typing import Any

import httpx

from ..config import INTERNAL_AI_API_URL


class AIClient:
    @staticmethod
    def is_enabled(base_url: str | None) -> bool:
        return bool((base_url or INTERNAL_AI_API_URL or '').strip())

    async def identify(self, payload: dict[str, Any], base_url: str | None = None) -> dict[str, Any]:
        url = (base_url or INTERNAL_AI_API_URL).strip()
        if not url:
            return {
                'request_target': '',
                'summary': '',
                'is_petition_hint': False,
                'nondisclosure_keywords_matched': [],
                'repeat_match': None,
                'status': 'AI_DISABLED',
            }
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                try:
                    detail = response.json().get('detail')
                except Exception:
                    detail = response.text
                raise RuntimeError(f'AI API 오류({response.status_code}): {detail}') from exc
            return response.json()
