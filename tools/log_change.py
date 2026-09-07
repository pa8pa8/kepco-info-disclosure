#!/usr/bin/env python3
"""Generate a standardized change log entry for the project.

This script is intentionally simple and compatible with older Python 3.8+
installations and legacy Windows/console environments.
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import re
import sys


def slugify(value: str, max_len: int = 60) -> str:
    value = value.strip().lower()
    # 한글 자모/음절(ㄱ-ㆎ, 가-힣)과 영문 소문자·숫자는 보존하고
    # 나머지만 구분자로 치환한다. 예전에는 [^a-z0-9]만 허용해서 한글 요약을 쓰면
    # 파일명이 "krds"처럼 거의 다 날아갔다(예: FOIA-0004-krds.md).
    value = re.sub(r'[^a-z0-9가-힣ㄱ-ㆎ]+', '-', value)
    value = re.sub(r'-+', '-', value).strip('-')
    value = value[:max_len].rstrip('-')
    return value or 'change'


def ensure_log_dir(base_dir: Path, dt_value: dt.date) -> Path:
    log_dir = base_dir / 'logs' / 'changes' / dt_value.isoformat()
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def build_file_name(ticket: str, summary: str) -> str:
    safe_ticket = ticket.strip().upper() if ticket else 'NO-TICKET'
    safe_summary = slugify(summary)
    return f'{safe_ticket}-{safe_summary}.md'


def render_template(ticket: str, summary: str, change_type: str, author: str) -> str:
    now = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    return (
        '# 변경 기록\n\n'
        f'- 일시: {now}\n'
        f'- 작성자: {author}\n'
        f'- 작업번호: {ticket}\n'
        f'- 변경 유형: {change_type}\n'
        '- 상태: draft\n\n'
        '## 변경 요약\n'
        f'{summary}\n\n'
        '## 변경 내용\n'
        '- 내용을 입력하세요\n'
        '- 변경 이유를 설명하세요\n\n'
        '## 원인\n'
        '- 문제 또는 요구사항을 설명하세요\n\n'
        '## 검증\n'
        '- 확인 방법: \n'
        '- 결과: \n\n'
        '## 리스크\n'
        '- 영향 범위: \n'
        '- 주의사항: \n\n'
        '## 다음 조치\n'
        '- 후속 작업: \n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a standard change log entry.')
    parser.add_argument('--ticket', default='FOIA-0000', help='Issue or task number')
    parser.add_argument('--summary', required=True, help='Short change summary')
    parser.add_argument('--type', default='fix', help='Change type: feat, fix, docs, refactor, config, test')
    parser.add_argument('--author', default='unknown', help='Author name')
    parser.add_argument('--root', default='.', help='Project root directory')
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    today = dt.date.today()
    log_dir = ensure_log_dir(project_root, today)
    file_name = build_file_name(args.ticket, args.summary)
    file_path = log_dir / file_name

    if file_path.exists():
        print(f'File already exists: {file_path}')
        return 1

    content = render_template(args.ticket, args.summary, args.type, args.author)
    file_path.write_text(content, encoding='utf-8')
    print(f'Created log: {file_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
