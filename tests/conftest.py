"""테스트 전용 환경 설정. `app.config`가 import 시점에 환경변수를 읽으므로,
app 모듈을 import하기 전에 반드시 이 값들을 먼저 세팅해야 한다."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

_TMP_DIR = Path(tempfile.mkdtemp(prefix='foia_test_'))
os.environ['FOIA_DB_PATH'] = str(_TMP_DIR / 'test.db')
os.environ['FOIA_WATCH_DIR'] = str(_TMP_DIR / 'watch')
os.environ['FOIA_AI_RESULTS_DIR'] = str(_TMP_DIR / 'ai_recommendations')
os.environ['FOIA_SKIP_AI_SERVER'] = '1'
os.environ['FOIA_SCAN_INTERVAL'] = '3600'
os.environ.setdefault('FOIA_AI_SERVER_PORT', '18099')

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.security import csrf_token_for  # noqa: E402

TRANSACTIONAL_TABLES = ('decision_log', 'request_decisions', 'disclosure_requests')


def _clear_transactional_tables() -> None:
    con = sqlite3.connect(os.environ['FOIA_DB_PATH'])
    for table in TRANSACTIONAL_TABLES:
        con.execute(f'DELETE FROM {table}')
    con.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({','.join('?' * len(TRANSACTIONAL_TABLES))})",
        TRANSACTIONAL_TABLES,
    )
    con.commit()
    con.close()


@pytest.fixture(scope='session', autouse=True)
def _lifespan():
    """세션당 한 번 lifespan을 태워 기본 계정(admin/manager/dispatcher/staff1~10)을
    시딩한다. 이 fixture 자체는 요청을 보내지 않는다 — 쿠키 격리를 위해 각 테스트는
    반드시 자신만의 TestClient(`client`/`as_*`)를 받는다."""
    with TestClient(app):
        yield


def _new_client() -> TestClient:
    """CSRF 헤더를 기본으로 얹은 새 TestClient. 폼 기반 라우트는 실제로는 hidden
    input(`csrf_token`)을 읽지만, 헤더도 대체 경로로 허용하므로(`require_csrf_form`
    참고) 테스트는 매 POST마다 폼 데이터에 토큰을 끼워넣지 않고 헤더 하나로 통일한다.
    로그인 전이라 'anonymous' 토큰으로 시작 — `login()`이 성공 후 실제 사용자명
    토큰으로 갱신한다."""
    c = TestClient(app, cookies={})
    c.headers['X-CSRF-Token'] = csrf_token_for(None)
    return c


@pytest.fixture
def client(_lifespan):
    """매 테스트마다 새 쿠키 저장소를 가진 TestClient. 청구/판단 관련 테이블도 전후로 비운다
    — 계정 테이블은 세션 내내 유지."""
    _clear_transactional_tables()
    yield _new_client()
    _clear_transactional_tables()


def login(client: TestClient, username: str, password: str) -> TestClient:
    resp = client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)
    assert resp.status_code == 303, f'login failed for {username}: {resp.status_code} {resp.text[:200]}'
    client.headers['X-CSRF-Token'] = csrf_token_for(username)
    return client


@pytest.fixture
def as_admin(client):
    s = _new_client()
    login(s, 'admin', 'admin')
    return s


@pytest.fixture
def as_manager(client):
    s = _new_client()
    login(s, 'manager', 'manager')
    return s


@pytest.fixture
def as_dispatcher(client):
    s = _new_client()
    login(s, 'dispatcher', 'dispatcher')
    return s


@pytest.fixture
def as_staff1(client):
    s = _new_client()
    login(s, 'staff1', 'staff1')
    return s


@pytest.fixture
def as_staff2(client):
    s = _new_client()
    login(s, 'staff2', 'staff2')
    return s


@pytest.fixture
def make_request(client):
    """청구 1건을 직접 시딩. `/requests/new`가 삭제되어(FOIA-0015) 감시 폴더 스캔이
    유일한 정상 접수 경로이므로, 테스트에서는 앱과 같은 `db` 싱글턴을 통해 바로 생성한다."""
    from app.deps import db as _db

    def _make(requester_name: str = '테스트청구인', raw_text: str = '테스트 청구 원문입니다.', status: str = '판단중') -> int:
        # 실제 접수 파이프라인(request_processor)이 감시 폴더 스캔 후 상태를 '판단중'으로
        # 바꾼다 — 배정 대기 화면(`/dispatch`)이 그 상태만 보여주므로 테스트도 맞춘다.
        request_id = _db.create_request(requester_name, '010-0000-0000', '이메일', raw_text)
        if status:
            _db.set_request_status(request_id, status)
        return request_id

    return _make
