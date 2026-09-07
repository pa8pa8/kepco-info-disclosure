"""역할 이름 상수 — 단일 출처.

리팩터 전에는 `'시스템관리자'`/`'총괄관리자'`/`'배정담당자'`/`'업무담당자'` 문자열
리터럴이 `app/main.py` 한 파일에만 54번 넘게 흩어져 있었다. 오타가 나도 파이썬은
그냥 조용히 "권한 없음"으로 처리해버려서, 이런 곳일수록 이름 있는 상수가 필요하다.
"""

from __future__ import annotations

ADMIN = '시스템관리자'
MANAGER = '총괄관리자'
DISPATCHER = '배정담당자'
STAFF = '업무담당자'

ALL = (ADMIN, MANAGER, DISPATCHER, STAFF)

# 로그인 성공 시 이동할 역할별 첫 화면.
HOME = {
    ADMIN: '/admin/users',
    MANAGER: '/',
    DISPATCHER: '/dispatch',
    STAFF: '/requests',
}
