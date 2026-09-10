"""`tools/_training_data.py`의 실데이터 CSV 로딩/검증 로직.

GBM/XGBoost 학습 스크립트가 공유하는 코드다. 사용자가 직접 만드는 파일
(`data/training/staff_assignments.csv`)을 다루는 코드라 잘못된 입력을 조용히
삼키지 않고 제대로 거르는지가 특히 중요하다."""
from __future__ import annotations

import tools._training_data as train_data


def _write_csv(path, content: str):
    path.write_text(content, encoding='utf-8')


def test_load_real_examples_parses_valid_rows(tmp_path, monkeypatch):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'text,staff\n"서울지역본부 정보공개 청구",staff1\n"경기지역본부 전기요금 문의",staff3\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples = train_data.load_real_examples()
    assert examples == [
        ('서울지역본부 정보공개 청구', 'staff1'),
        ('경기지역본부 전기요금 문의', 'staff3'),
    ]


def test_load_real_examples_skips_nonexistent_staff_account(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'text,staff\n"정상 행",staff1\n"없는 계정 행",staff9999\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples = train_data.load_real_examples()
    assert examples == [('정상 행', 'staff1')]
    assert 'staff9999' in capsys.readouterr().out


def test_load_real_examples_skips_rows_with_empty_text_or_staff(tmp_path, monkeypatch):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'text,staff\n"",staff1\n"내용은 있음",\n"정상 행",staff1\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples = train_data.load_real_examples()
    assert examples == [('정상 행', 'staff1')]


def test_load_real_examples_reports_missing_columns(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'raw_text,assignee\n"열 이름이 다름",staff1\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples = train_data.load_real_examples()
    assert examples == []
    assert 'text' in capsys.readouterr().out


def test_load_training_examples_prefers_real_data_when_present(tmp_path, monkeypatch):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'text,staff\n"정상 행",staff1\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples, is_real = train_data.load_training_examples()
    assert is_real is True
    assert examples == [('정상 행', 'staff1')]


def test_load_training_examples_falls_back_to_synthetic_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', tmp_path / 'does-not-exist.csv')

    examples, is_real = train_data.load_training_examples()
    assert is_real is False
    assert len(examples) > 0


def test_load_training_examples_falls_back_to_synthetic_when_all_rows_invalid(tmp_path, monkeypatch, capsys):
    csv_path = tmp_path / 'staff_assignments.csv'
    _write_csv(csv_path, 'text,staff\n"없는 계정만",staff9999\n')
    monkeypatch.setattr(train_data, 'REAL_DATA_PATH', csv_path)

    examples, is_real = train_data.load_training_examples()
    assert is_real is False
    assert len(examples) > 0
    assert '합성 데이터로 대신' in capsys.readouterr().out
