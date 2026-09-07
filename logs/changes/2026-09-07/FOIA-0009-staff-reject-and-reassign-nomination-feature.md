# 변경 기록

- 일시: 2026-09-07 14:10
- 작성자: cshs1729
- 작업번호: FOIA-0009
- 변경 유형: feat
- 상태: reviewed

## 변경 요약
업무담당자용 "거절(잘못 배정됨)" 기능 신규 구현. 단순 반려는 없고, 반드시 1~3명의
재배정 후보를 지명해야 하며, 배정담당자/총괄관리자가 그중 한 명을 선택해 확정하는
방식. 역할별 화면 재점검에서 발견한 "재배정 경로 전무" 문제 중 업무담당자 쪽 절반을 해결.

## 변경 내용
- `app/db.py`: `disclosure_requests`에 `reassign_candidates_json` 컬럼 추가(마이그레이션).
  `reject_and_nominate(request_id, candidates, actor)` 신규 — 배정 해제 + 후보 목록 저장 +
  `decision_log`에 `reject` 단계 기록. `assign_request()`는 확정 배정 시
  `reassign_candidates_json`을 NULL로 정리하도록 수정. 판단 위저드 진행 상태
  (`request_decisions`)는 건드리지 않아 담당자만 바뀌고 이미 진행된 판단은 유지됨.
- `app/main.py`: `_load_ai_recommendation()` 반환값에 `source: 'ai'` 추가, 사람이 지명한
  후보를 읽는 `_load_reassign_candidates()`(`source: 'reassign'`) 신규, 둘을 우선순위대로
  합치는 `_load_recommendation()` 신규(사람 지명 > AI 예시) — `dispatch_page`/`request_detail`의
  기존 `_load_ai_recommendation()` 호출을 여기로 교체. `request_detail`에 `can_reject` 계산
  추가(배정된 본인 + 미확정일 때만), 이 경우 `staff_directory`에서 본인 제외.
  `POST /api/requests/{id}/reject` 신규(업무담당자 전용) — 본인 배정 건인지, 미확정인지,
  후보가 1~3명이고 유효한 업무담당자이며 본인이 아닌지 서버에서 전부 검증.
- `app/templates/request_detail.html`: 위저드 아래에 "잘못 배정되었나요?" 섹션 추가
  (담당자 검색 + 체크박스 다중 선택 + "선택됨: ..." + 제출 버튼). `dispatch.html`/
  `request_detail.html`의 담당자 배정 추천 라벨을 `ai.source`로 분기해 "🔁 이전 담당자가
  재배정을 요청했습니다"(사람 지명) vs "🤖 AI 판단 결과"(데모)로 구분.
- `app/static/js/app.js`: `renderRejectSearchResults`/`toggleRejectCandidate`/`submitReject`
  신규, `filterStaffSearch`/`initAllStaffSearches`가 `data-mode="reject"`일 때 이쪽으로
  분기하도록 수정.
- **버그 수정(같은 작업 중 발견)**: 체크박스를 감싼 `<label>`과 바깥 `<div>`에 각각
  onclick을 걸었더니, 라벨 영역 클릭 시 실제 클릭 이벤트 버블링 + 브라우저의
  "라벨 클릭→연결된 input에 합성 클릭 전달" 동작이 겹쳐 토글이 두 번 호출되어 선택이
  즉시 취소되는 문제 발견 → 체크박스는 `pointer-events:none` + 표시 전용으로 바꾸고
  `<div>`의 onclick 하나만 남겨 해결. Playwright 스크린샷으로 수정 전/후 확인.

## 원인
사용자 지시: "업무 담당자는 잘못 배정되었을 경우 거절 기능을 반드시 넣어줘, 거절했을때는
거절은 불가하고 다른 사람에게 넘기는 기능만 가능하게 해줘. 최소 1명 최대 3명을 선택할 수
있어." 직전 역할별 화면 재점검에서 "총괄관리자조차 재배정 불가"를 핵심 공백 중 하나로
지목했었음 — 이번 기능이 업무담당자 쪽 절반을 해결.

## 검증
- 확인 방법: 격리 환경(포트 8096/8095, 별도 DB)에서 dispatcher→staff2 배정 후, staff2로
  (1) 후보 0명/4명/본인 포함/존재하지 않는 계정으로 거절 시도 시 전부 400/403 거부되는지,
  (2) staff2가 아닌 계정이 남의 청구를 거절 시도 시 403인지, (3) 정상적으로 staff3/staff5를
  지명해 거절하면 청구가 미배정으로 돌아가고 `/dispatch`에 "🔁 이전 담당자가 재배정을
  요청했습니다"와 함께 1순위 staff3/2순위 staff5 버튼이 뜨는지, (4) dispatcher가 staff3을
  클릭해 확정하면 staff3의 "내 업무"에 해당 건이 뜨고 판단 경로(반복 청구 대상인가? 등)가
  그대로 유지되는지, (5) 원래 담당자였던 staff2는 더 이상 그 청구 상세에 접근 못 하는지
  (303 리다이렉트) 전부 curl로 확인. Playwright로 체크박스 다중 선택 UI도 시각 확인
  (수정 전 더블토글 버그 발견 → 수정 후 재확인).
- 결과: 전부 기대대로 동작. `python -m compileall app` 통과.

## 리스크
- 영향 범위: `assigned_to`가 NULL로 돌아가는 것 외에 `request_decisions`(판단 진행 상태)는
  전혀 건드리지 않으므로 기존 배정/판단 로직에 회귀 없음.
- 주의사항: 이 기능은 "업무담당자가 스스로 거절"하는 경로만 구현했다 — 배정담당자/
  총괄관리자가 이미 배정된 건을 직접(담당자 동의 없이) 재배정하는 기능은 아직 없음
  (기존 `can_assign`은 미배정 건에만 적용됨). 이건 역할별 점검에서 나온 "재배정 불가"
  공백의 나머지 절반이며, 별도 확인 후 진행 필요.

## 다음 조치
- 후속 작업: 역할별 재점검에서 나온 나머지 항목(법정 처리기한 표시, 통지서 산출물 생성,
  시스템관리자 계정 수정 기능, 배정담당자의 `/requests` 접근 제한 재검토, 총괄관리자의
  직접 재배정) 중 다음에 진행할 항목을 사용자와 확인.
