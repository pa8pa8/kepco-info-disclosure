#!/usr/bin/env python3
"""`data/training/raw/converted/`의 텍스트에서 (청구 내용, 부서) 쌍을 뽑아
`data/training/raw/department_labels.csv`로 모은다. 담당자(개인) 매핑보다 먼저
부서 단위 매핑을 만들기 위한 중간 산출물이다.

두 종류의 원본에서 뽑는다:
- hwp 배부내역이 변환된 `converted/*.txt` 전부: "번호. 내용 : 부서" 형태의 줄을
  정규식으로 찾는다. 하위 설명줄("- ...")은 항목 번호가 없어 매칭되지 않으므로
  자동으로 제외된다. (청구내용 목록 CSV도 이 디렉터리에 있지만 확장자가 달라
  이 glob에는 안 걸린다.)
- xlsx 청구내용 목록(`1-2. 청구내용(71건) 목록__Sheet1.csv`): 이미 "내용,배부처"
  두 컬럼이라 그대로 쓴다.

부서 칸에는 실제 부서명 외에 "해당사항 없음", "기제출자료 활용" 같은 비-부서
문구가 섞여 있어, 실제 조직 단위 접미어(처/실/원/단/국/부/팀/센터/회)로 끝나는
토큰만 부서로 인정해 걸러낸다.
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / 'data' / 'training' / 'raw'
CONVERTED_DIR = RAW_DIR / 'converted'
OUT_PATH = RAW_DIR / 'department_labels.csv'


# 내용 그룹을 욕심쟁이(greedy)로 둬서 시각(10:00)처럼 내용 중간에 콜론이 있어도
# 실제 부서는 마지막 콜론 뒤에 오게 만든다 — lazy로 하면 첫 콜론에서 잘려 내용 뒷부분이
# 부서 칸으로 새어들어갈 수 있다.
ITEM_LINE = re.compile(r'^\s*\d+(?:-\d+)?\.\s*(.+)[:：]\s*(.+)$')
DEPT_SUFFIXES = ('처', '실', '원', '단', '국', '부', '팀', '센터', '회')


def normalize_departments(raw: str) -> list[str]:
    """부서 칸 원문에서 실제 부서명만 뽑는다. 괄호 설명은 버리고, 콤마/가운뎃점/
    슬래시로 나열된 여러 부서를 각각 분리한다."""
    no_paren = re.sub(r'\([^)]*\)', '', raw)
    parts = re.split(r'[,·/]', no_paren)
    depts = []
    for p in parts:
        p = p.strip()
        if p and p.endswith(DEPT_SUFFIXES):
            depts.append(p)
    return depts


def from_hwp_texts() -> list[tuple[str, str, str]]:
    rows = []
    for path in sorted(CONVERTED_DIR.glob('*.txt')):
        for line in path.read_text(encoding='utf-8').splitlines():
            m = ITEM_LINE.match(line.strip())
            if not m:
                continue
            text, dept_raw = m.group(1).strip(), m.group(2).strip()
            for dept in normalize_departments(dept_raw):
                rows.append((text, dept, path.stem))
    return rows


def from_claim_list_csv() -> list[tuple[str, str, str]]:
    csv_path = CONVERTED_DIR / '1-2. 청구내용(71건) 목록__Sheet1.csv'
    rows = []
    if not csv_path.exists():
        print(f'{csv_path.name}이 없어 건너뜁니다 '
              '(tools/convert_raw_training_data.py를 먼저 실행했는지 확인).')
        return rows
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)  # 헤더
        for row in reader:
            if len(row) < 2:
                continue
            text, dept_raw = row[0].strip(), row[1].strip()
            if not text or not dept_raw:
                continue
            for dept in normalize_departments(dept_raw):
                rows.append((text, dept, csv_path.stem))
    return rows


def main() -> None:
    rows = from_hwp_texts() + from_claim_list_csv()
    seen = set()
    unique_rows = []
    for row in rows:
        key = (row[0], row[1])
        if key not in seen:
            seen.add(key)
            unique_rows.append(row)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['text', 'department', 'source'])
        writer.writerows(unique_rows)

    dept_counts = Counter(r[1] for r in unique_rows)
    print(f'총 {len(unique_rows)}건, 부서 {len(dept_counts)}개 -> {OUT_PATH}')
    for dept, cnt in dept_counts.most_common():
        print(f'  {cnt:3d}  {dept}')


if __name__ == '__main__':
    main()
