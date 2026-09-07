from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from .config import AI_API_URL, DB_PATH, WATCH_DIR

STEP_LABELS = {
    'repeat': '반복 청구 대상인가?',
    'information': "이 법에서 정한 '정보'인가?",
    'petition': '진정·질의인가?',
    'info_absent': "'정보부존재' 인가?",
    'alternative': "'대체정보'로 제공할 수 있는가?",
    'nondisclosure': '비공개 대상에 해당하는가?',
    'partial': '부분공개 가능한가?',
}


ROLES = ('시스템관리자', '총괄관리자', '배정담당자', '업무담당자')


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._migrate_legacy_users_table()
        self._init_db()
        self._migrate_request_columns()
        self._migrate_user_columns()
        self._seed_settings()
        self._restrict_file_permissions()

    def _restrict_file_permissions(self):
        """이 DB 파일에는 비밀번호 해시·세션 서명키(auth_secret)·청구인 개인정보가 모두
        들어있어, 파일 하나가 유출되면 피해가 크다. 최소한 소유자만 읽고 쓸 수 있도록
        권한을 좁힌다. Windows는 POSIX 권한 비트를 그대로 쓰지 않아 완전한 제한은
        안 되지만(별도로 icacls 필요), 리눅스/맥 배포 시에는 실제로 동작한다."""
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def _migrate_legacy_users_table(self):
        """이전 3역할(관리자/운영자/담당자) 스키마의 users 테이블이 남아있으면 제거하고
        4역할(시스템관리자/총괄관리자/배정담당자/업무담당자) 스키마로 재생성되도록 한다.
        테스트용 더미 계정만 존재하는 개발 단계라 데이터 보존 없이 재생성한다."""
        with self.connect() as conn:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
            if row and row['sql'] and '시스템관리자' not in row['sql']:
                conn.execute('DROP TABLE users')

    def _migrate_request_columns(self):
        with self.connect() as conn:
            cols = {r['name'] for r in conn.execute('PRAGMA table_info(disclosure_requests)').fetchall()}
            if 'assigned_to' not in cols:
                conn.execute('ALTER TABLE disclosure_requests ADD COLUMN assigned_to TEXT')
            if 'assigned_at' not in cols:
                conn.execute('ALTER TABLE disclosure_requests ADD COLUMN assigned_at TEXT')
            if 'assigned_by' not in cols:
                conn.execute('ALTER TABLE disclosure_requests ADD COLUMN assigned_by TEXT')
            if 'reassign_candidates_json' not in cols:
                conn.execute('ALTER TABLE disclosure_requests ADD COLUMN reassign_candidates_json TEXT')

    def _migrate_user_columns(self):
        """업무담당자 소속(1차사업소/2차사업소/부서) 컬럼을 기존 users 테이블에 보강한다."""
        with self.connect() as conn:
            cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)').fetchall()}
            if 'region' not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN region TEXT')
            if 'branch' not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN branch TEXT')
            if 'department' not in cols:
                conn.execute('ALTER TABLE users ADD COLUMN department TEXT')

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self.connect() as conn:
            conn.executescript(
                '''
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('시스템관리자', '총괄관리자', '배정담당자', '업무담당자')),
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS disclosure_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requester_name TEXT NOT NULL,
                    requester_contact TEXT,
                    channel TEXT NOT NULL DEFAULT '텍스트',
                    raw_text TEXT NOT NULL,
                    request_target TEXT,
                    ai_summary TEXT,
                    ai_hints_json TEXT,
                    source_file TEXT,
                    status TEXT NOT NULL DEFAULT '접수',
                    received_at TEXT DEFAULT (datetime('now', 'localtime')),
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
                );

                CREATE TABLE IF NOT EXISTS request_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER UNIQUE NOT NULL,
                    is_repeat INTEGER,
                    repeat_match_request_id INTEGER,
                    is_information INTEGER,
                    is_petition INTEGER,
                    is_info_absent INTEGER,
                    is_alternative_available INTEGER,
                    is_nondisclosure INTEGER,
                    is_partial_possible INTEGER,
                    current_step TEXT DEFAULT 'repeat',
                    final_notice_type TEXT,
                    notice_text TEXT,
                    decided_by TEXT,
                    analyzed_at TEXT,
                    api_status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    FOREIGN KEY(request_id) REFERENCES disclosure_requests(id)
                );

                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL,
                    step_key TEXT NOT NULL,
                    step_label TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    article_ref TEXT,
                    actor TEXT,
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    FOREIGN KEY(request_id) REFERENCES disclosure_requests(id)
                );

                CREATE INDEX IF NOT EXISTS idx_requests_received ON disclosure_requests(received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_requests_status ON disclosure_requests(status);
                CREATE INDEX IF NOT EXISTS idx_decision_log_request ON decision_log(request_id, created_at);
                '''
            )

    def _seed_settings(self):
        defaults = {
            'watch_dir': str(WATCH_DIR),
            'ai_api_url': AI_API_URL,
            'scan_interval': '60',
            'notice_template_공개': '청구하신 정보를 「공공기관의 정보공개에 관한 법률」에 따라 공개합니다.',
            'notice_template_부분공개': '청구하신 정보 중 일부는 비공개 대상에 해당하여, 나머지 부분만 부분공개합니다. (제14조)',
            'notice_template_비공개': '청구하신 정보는 「공공기관의 정보공개에 관한 법률」 제9조 제1항 각 호의 비공개 대상 정보에 해당하여 비공개합니다.',
            'notice_template_정보부존재': '청구하신 정보를 공공기관이 보유·관리하고 있지 않아(정보부존재) 「민원 처리에 관한 법률」에 따라 안내합니다.',
            'notice_template_진정질의': '청구하신 내용은 「정보공개법」에 따른 정보공개 청구가 아닌 진정·질의로 판단되어 「민원 처리에 관한 법률」에 따라 답변합니다.',
            'notice_template_종결': '기존에 통지한 사항과 동일한 답변을 할 수밖에 없는 반복 청구로 판단되어 처리를 종결합니다. (제11조의2)',
            'nondisclosure_keywords': '개인정보,영업비밀,수사,재판,안전보장,의사결정과정,감사·감독,시험',
        }
        with self.connect() as conn:
            for key, value in defaults.items():
                conn.execute('INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)', (key, value))

    def get_setting(self, key: str, default: str = '') -> str:
        row = self.fetch_one('SELECT value FROM app_settings WHERE key = ?', (key,))
        return row['value'] if row else default

    def set_setting(self, key: str, value: str):
        with self.connect() as conn:
            conn.execute(
                '''INSERT INTO app_settings (key, value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP''',
                (key, value),
            )

    def get_all_settings(self) -> dict[str, str]:
        rows = self.fetch_all('SELECT key, value FROM app_settings ORDER BY key')
        return {row['key']: row['value'] for row in rows}

    def fetch_one(self, query: str, params: Iterable[Any] = ()):
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchone()

    def fetch_all(self, query: str, params: Iterable[Any] = ()):
        with self.connect() as conn:
            return conn.execute(query, tuple(params)).fetchall()

    def execute(self, query: str, params: Iterable[Any] = ()) -> int:
        with self.connect() as conn:
            cur = conn.execute(query, tuple(params))
            return int(cur.lastrowid)

    # --- Users ---

    def get_user(self, username: str):
        return self.fetch_one('SELECT * FROM users WHERE username = ?', (username,))

    def create_user(self, username: str, password_hash: str, role: str,
                     region: str = '', branch: str = '', department: str = '') -> int:
        return self.execute(
            '''INSERT INTO users (username, password_hash, role, region, branch, department)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (username, password_hash, role, region or None, branch or None, department or None),
        )

    def get_user_by_id(self, user_id: int):
        return self.fetch_one('SELECT * FROM users WHERE id = ?', (user_id,))

    def list_users(self):
        return self.fetch_all('SELECT id, username, role, region, branch, department, created_at FROM users ORDER BY id')

    def list_usernames_by_role(self, role: str):
        return self.fetch_all('SELECT username FROM users WHERE role = ? ORDER BY username', (role,))

    def list_directory_by_role(self, role: str):
        """검색용 담당자 목록 — 아이디 + 소속(1차사업소/2차사업소/부서)."""
        return self.fetch_all(
            'SELECT username, region, branch, department FROM users WHERE role = ? ORDER BY region, branch, username',
            (role,),
        )

    def count_users_by_role(self, role: str) -> int:
        row = self.fetch_one('SELECT COUNT(*) AS cnt FROM users WHERE role = ?', (role,))
        return row['cnt'] if row else 0

    def delete_user(self, user_id: int):
        self.execute('DELETE FROM users WHERE id = ?', (user_id,))

    def any_user_exists(self) -> bool:
        row = self.fetch_one('SELECT id FROM users LIMIT 1')
        return row is not None

    # --- Requests ---

    def create_request(self, requester_name: str, requester_contact: str, channel: str, raw_text: str, source_file: str | None = None) -> int:
        request_id = self.execute(
            '''INSERT INTO disclosure_requests (requester_name, requester_contact, channel, raw_text, source_file)
               VALUES (?, ?, ?, ?, ?)''',
            (requester_name, requester_contact, channel, raw_text, source_file),
        )
        self.execute('INSERT INTO request_decisions (request_id) VALUES (?)', (request_id,))
        return request_id

    def get_request(self, request_id: int):
        return self.fetch_one('SELECT * FROM disclosure_requests WHERE id = ?', (request_id,))

    def get_source_file(self, source_file: str):
        return self.fetch_one('SELECT id FROM disclosure_requests WHERE source_file = ?', (source_file,))

    def list_requests(self, status: str = '', notice_type: str = '', q: str = '', limit: int = 200,
                       assigned_to: str | None = None, unassigned_only: bool = False):
        query = '''
            SELECT r.*, d.final_notice_type, d.current_step, d.is_repeat
            FROM disclosure_requests r
            LEFT JOIN request_decisions d ON d.request_id = r.id
            WHERE 1=1
        '''
        params: list[Any] = []
        if status:
            query += ' AND r.status = ?'
            params.append(status)
        if notice_type:
            query += ' AND d.final_notice_type = ?'
            params.append(notice_type)
        if q:
            query += ' AND (r.requester_name LIKE ? OR r.raw_text LIKE ? OR r.request_target LIKE ?)'
            params.extend([f'%{q}%', f'%{q}%', f'%{q}%'])
        if assigned_to:
            query += ' AND r.assigned_to = ?'
            params.append(assigned_to)
        if unassigned_only:
            query += ' AND r.assigned_to IS NULL'
        query += ' ORDER BY r.received_at DESC LIMIT ?'
        params.append(limit)
        return self.fetch_all(query, params)

    def assign_request(self, request_id: int, assigned_to: str, assigned_by: str):
        self.execute(
            '''UPDATE disclosure_requests
               SET assigned_to = ?, assigned_by = ?, assigned_at = datetime('now', 'localtime'),
                   reassign_candidates_json = NULL, updated_at = datetime('now', 'localtime')
               WHERE id = ?''',
            (assigned_to, assigned_by, request_id),
        )
        self.execute(
            '''INSERT INTO decision_log (request_id, step_key, step_label, answer, article_ref, actor)
               VALUES (?, 'assign', '담당자 배정', ?, NULL, ?)''',
            (request_id, assigned_to, assigned_by),
        )

    def reassign_request(self, request_id: int, assigned_to: str, assigned_by: str, previous_assignee: str | None):
        """배정담당자/총괄관리자가 이미 배정된 건을 담당자 동의 없이 직접 재배정한다.
        `assign_request`(최초 배정)와 달리 이전 담당자 → 새 담당자를 로그에 남긴다."""
        self.execute(
            '''UPDATE disclosure_requests
               SET assigned_to = ?, assigned_by = ?, assigned_at = datetime('now', 'localtime'),
                   reassign_candidates_json = NULL, updated_at = datetime('now', 'localtime')
               WHERE id = ?''',
            (assigned_to, assigned_by, request_id),
        )
        answer = f'{previous_assignee} → {assigned_to}' if previous_assignee else assigned_to
        self.execute(
            '''INSERT INTO decision_log (request_id, step_key, step_label, answer, article_ref, actor)
               VALUES (?, 'reassign', '담당자 재배정', ?, NULL, ?)''',
            (request_id, answer, assigned_by),
        )

    def reject_and_nominate(self, request_id: int, candidates: list[str], actor: str):
        """업무담당자가 잘못 배정된 청구를 거절 — 단순 반려는 없고, 반드시 1~3명의
        재배정 후보를 지명해야 한다. 청구는 다시 미배정 상태가 되어 배정 대기 큐로
        돌아가며, 배정담당자/총괄관리자가 지명된 후보 중 한 명을 클릭해 확정한다.
        판단 위저드 진행 상태(request_decisions)는 건드리지 않는다 — 담당자만 바뀔 뿐,
        이미 진행된 판단 내용은 다음 담당자가 이어받는다."""
        self.execute(
            '''UPDATE disclosure_requests
               SET assigned_to = NULL, assigned_by = NULL, assigned_at = NULL,
                   reassign_candidates_json = ?, updated_at = datetime('now', 'localtime')
               WHERE id = ?''',
            (json.dumps(candidates, ensure_ascii=False), request_id),
        )
        self.execute(
            '''INSERT INTO decision_log (request_id, step_key, step_label, answer, article_ref, actor)
               VALUES (?, 'reject', '담당자 재배정 요청', ?, NULL, ?)''',
            (request_id, ', '.join(candidates), actor),
        )

    def count_unassigned_pending(self) -> int:
        row = self.fetch_one("SELECT COUNT(*) AS cnt FROM disclosure_requests WHERE status = '판단중' AND assigned_to IS NULL")
        return row['cnt'] if row else 0

    def list_recently_assigned(self, limit: int = 10):
        return self.fetch_all(
            '''SELECT r.*, d.final_notice_type
               FROM disclosure_requests r
               LEFT JOIN request_decisions d ON d.request_id = r.id
               WHERE r.assigned_to IS NOT NULL
               ORDER BY r.assigned_at DESC LIMIT ?''',
            (limit,),
        )

    def recent_raw_texts(self, exclude_id: int, limit: int = 500):
        return self.fetch_all(
            'SELECT id, requester_name, raw_text, request_target FROM disclosure_requests WHERE id != ? ORDER BY received_at DESC LIMIT ?',
            (exclude_id, limit),
        )

    def set_request_status(self, request_id: int, status: str):
        self.execute(
            "UPDATE disclosure_requests SET status = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (status, request_id),
        )

    def set_request_ai_identity(self, request_id: int, request_target: str, ai_summary: str, ai_hints_json: str = '{}'):
        self.execute(
            "UPDATE disclosure_requests SET request_target = ?, ai_summary = ?, ai_hints_json = ?, updated_at = datetime('now', 'localtime') WHERE id = ?",
            (request_target, ai_summary, ai_hints_json, request_id),
        )

    # --- Decisions ---

    def get_decision(self, request_id: int):
        return self.fetch_one('SELECT * FROM request_decisions WHERE request_id = ?', (request_id,))

    def apply_step_answer(self, request_id: int, step_key: str, answer: bool, next_step: str | None,
                           final_notice_type: str | None, article_ref: str | None, actor: str):
        column_map = {
            'repeat': 'is_repeat',
            'information': 'is_information',
            'petition': 'is_petition',
            'info_absent': 'is_info_absent',
            'alternative': 'is_alternative_available',
            'nondisclosure': 'is_nondisclosure',
            'partial': 'is_partial_possible',
        }
        column = column_map[step_key]
        with self.connect() as conn:
            conn.execute(
                f'''UPDATE request_decisions
                    SET {column} = ?, current_step = ?, final_notice_type = ?, analyzed_at = datetime('now', 'localtime')
                    WHERE request_id = ?''',
                (1 if answer else 0, next_step, final_notice_type, request_id),
            )
            conn.execute(
                '''INSERT INTO decision_log (request_id, step_key, step_label, answer, article_ref, actor)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (request_id, step_key, STEP_LABELS.get(step_key, step_key), 'Y' if answer else 'N', article_ref, actor),
            )

    def set_repeat_match(self, request_id: int, matched_request_id: int | None):
        self.execute(
            'UPDATE request_decisions SET repeat_match_request_id = ? WHERE request_id = ?',
            (matched_request_id, request_id),
        )

    def finalize_notice(self, request_id: int, notice_text: str, decided_by: str):
        self.execute(
            "UPDATE request_decisions SET notice_text = ?, decided_by = ?, api_status = 'done' WHERE request_id = ?",
            (notice_text, decided_by, request_id),
        )
        self.set_request_status(request_id, '완료')

    def set_decision_error(self, request_id: int, error_message: str):
        self.execute(
            "UPDATE request_decisions SET api_status = 'error', error_message = ? WHERE request_id = ?",
            (error_message, request_id),
        )

    def get_decision_log(self, request_id: int):
        return self.fetch_all('SELECT * FROM decision_log WHERE request_id = ? ORDER BY created_at ASC', (request_id,))

    def get_log_source_files(self, limit: int = 500):
        rows = self.fetch_all('SELECT source_file FROM disclosure_requests WHERE source_file IS NOT NULL LIMIT ?', (limit,))
        return {row['source_file'] for row in rows}

    def summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute('SELECT COUNT(*) AS cnt FROM disclosure_requests').fetchone()['cnt']
            status_counts = {row['status']: row['cnt'] for row in conn.execute('SELECT status, COUNT(*) AS cnt FROM disclosure_requests GROUP BY status').fetchall()}
            notice_counts = {row['final_notice_type']: row['cnt'] for row in conn.execute(
                "SELECT final_notice_type, COUNT(*) AS cnt FROM request_decisions WHERE final_notice_type IS NOT NULL GROUP BY final_notice_type"
            ).fetchall()}
            pending = conn.execute("SELECT COUNT(*) AS cnt FROM disclosure_requests WHERE status != '완료'").fetchone()['cnt']
            unassigned = conn.execute("SELECT COUNT(*) AS cnt FROM disclosure_requests WHERE status = '판단중' AND assigned_to IS NULL").fetchone()['cnt']
            recent = [dict(r) for r in conn.execute(
                '''SELECT r.id, r.requester_name, r.request_target, r.status, r.received_at, r.assigned_to, d.final_notice_type
                   FROM disclosure_requests r
                   LEFT JOIN request_decisions d ON d.request_id = r.id
                   ORDER BY r.received_at DESC LIMIT 10'''
            ).fetchall()]
        return {
            'total_requests': total,
            'status_counts': status_counts,
            'notice_counts': notice_counts,
            'pending_count': pending,
            'unassigned_count': unassigned,
            'recent_requests': recent,
        }
