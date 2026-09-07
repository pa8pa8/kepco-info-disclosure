"""`app/db.py`의 `Database` 메서드 단위 테스트 — 라우트를 거치지 않고 직접 검증해야
하는 것들(대량 데이터에서의 쿼리 정확성 등)."""
from __future__ import annotations


def test_get_log_source_files_returns_all_files_beyond_old_500_limit(client):
    """FOIA-0032 회귀 테스트: `get_log_source_files`가 예전에는 `LIMIT 500`을
    `ORDER BY` 없이 걸어서, 500건을 넘는 순간부터 일부 파일이 결과에서 빠져
    감시 폴더 재스캔 시 중복 접수를 유발했다. 지금은 전부 반환해야 한다."""
    from app.deps import db

    total = 520
    for i in range(total):
        db.execute(
            "INSERT INTO disclosure_requests (requester_name, raw_text, source_file) VALUES (?, ?, ?)",
            ('테스트', '내용', f'file_{i:04d}.txt'),
        )

    known_files = db.get_log_source_files()
    assert len(known_files) == total
    assert 'file_0000.txt' in known_files  # 예전 버그라면 정렬 순서에 따라 이런 초반 파일이 빠질 수 있었음
    assert f'file_{total - 1:04d}.txt' in known_files  # 가장 나중에 넣은 파일도 반드시 포함돼야 함
