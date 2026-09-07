from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

_TARGET_MARKERS = ['관련', '에 대한', '에대한', '현황', '자료', '내역', '목록', '결과', '기준']
_PETITION_MARKERS = ['왜', '문의', '불편', '민원', '이의', '항의', '요청드립니다만', '궁금']


def normalize_text(text: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'\s+', ' ', text)
    return text


def split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+|\n+', text)
    return [p.strip() for p in parts if p.strip()]


def extract_request_target(text: str) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ''
    sentences = split_sentences(normalized)
    for sentence in sentences:
        if any(marker in sentence for marker in _TARGET_MARKERS):
            return sentence[:200]
    return sentences[0][:200] if sentences else normalized[:200]


def summarize(text: str, max_len: int = 120) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= max_len:
        return normalized
    return normalized[:max_len].rstrip() + '…'


def is_petition_like(text: str) -> bool:
    normalized = normalize_text(text)
    return any(marker in normalized for marker in _PETITION_MARKERS)


def find_repeat_candidate(target: str, history: list[dict[str, Any]], threshold: float = 0.82):
    if not target:
        return None
    best = None
    best_ratio = 0.0
    for item in history:
        candidate = item.get('request_target') or item.get('raw_text') or ''
        if not candidate:
            continue
        ratio = SequenceMatcher(None, target, candidate[:200]).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best = item
    if best is not None and best_ratio >= threshold:
        return {'request_id': best['id'], 'similarity': round(best_ratio, 3)}
    return None


def match_nondisclosure_keywords(text: str, keywords: list[str]) -> list[str]:
    normalized = normalize_text(text)
    return [kw for kw in keywords if kw and kw in normalized]
