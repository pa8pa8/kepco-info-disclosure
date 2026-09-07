# 변경 기록

- 일시: 2026-09-07 13:05
- 작성자: cshs1729
- 작업번호: FOIA-0005
- 변경 유형: fix
- 상태: reviewed

## 변경 요약
KRDS 라이트 테마 적용(FOIA-0004) 후속으로 나머지 화면을 순차 정리: `/requests` 목록과
`/admin/users` 계정 목록 표의 컬럼 줄바꿈 문제를 고치고, `/requests/{id}` 상세 화면의 AI
담당자 추천 UI를 `/dispatch`와 동일한 컴포넌트로 통일.

## 변경 내용
- `app/static/css/style.css`: `.table.table-fixed`와 컬럼 유틸리티 클래스(`.col-time`,
  `.col-name`, `.col-pill`, `.col-target`, `.col-action`) 추가. `table-layout: fixed`로
  좁은 컬럼(시각·이름·상태알약·액션)은 고정 폭 + 말줄임을 적용하고, 내용이 긴 컬럼
  (요청대상/소속)만 남은 폭을 모두 가져가 자연스럽게 줄바꿈되도록 함.
- `app/templates/requests.html`: 표에 위 컬럼 클래스 적용. 청구 상태(접수/판단중/완료)
  알약 색을 통지 유형 알약과 별개로 톤 매핑(`status_tone` dict) 추가 — 이전에는 모든 상태가
  회색(`unknown`)으로만 표시됐음.
- `app/templates/admin_users.html`: 계정 목록 표에도 동일한 컬럼 클래스 적용. 폭이 좁아
  역할 라벨("시스템관리자" 등)과 "나" 배지, "삭제" 버튼이 서로 겹치거나 줄바꿈되던 문제 해결.
- `app/templates/request_detail.html`: 담당자 배정 섹션의 AI 추천 버튼을 기존
  `.ai-pick-btn` 나열 방식에서 `/dispatch`와 동일한 `.rank-primary` + `.rank-secondary-row`
  + `.assign-reason` 구성으로 교체해 두 화면의 시각 언어를 통일.

## 원인
FOIA-0004 로그의 "다음 조치"에 남긴 두 항목 처리: (1) `/requests` 표 컬럼 폭 이슈,
(2) 나머지 화면의 KRDS 톤 정리. 사용자가 "순차적으로 진행해줘"로 후속 작업 승인.

## 검증
- 확인 방법: 로컬 서버 기동 후 Playwright로 manager/admin/staff2 계정 로그인 → `/requests`,
  `/requests/{id}`(AI 추천 있는 건 포함), `/requests/new`, `/admin/users`,
  `/requests`(업무담당자 "내 업무" 뷰) 스크린샷 캡처해 육안 검증. 컬럼 폭 1차 조정 후에도
  `/admin/users`에서 역할 라벨이 말줄임되는 것을 발견해 `.col-name`/`.col-pill` 폭을
  92px/96px → 128px/118px로 재조정하고 재검증.
- 결과: 두 표 모두 헤더·역할 라벨·날짜가 줄바꿈이나 겹침 없이 표시되고, 긴 텍스트 컬럼
  (요청대상/소속)만 자연스럽게 여러 줄로 표시됨. `/requests/{id}`의 AI 추천 버튼이
  `/dispatch`와 동일한 모양으로 렌더링됨을 확인. `python -m compileall app` 통과.

## 리스크
- 영향 범위: `col-*` 유틸리티 클래스는 `.table-fixed`가 붙은 표에만 적용되므로 다른 표
  (예: 청구 상세의 "처리 이력" 표)는 영향 없음. 향후 `table-fixed`를 쓰는 표를 추가할 때
  컬럼 텍스트 길이에 따라 폭 재조정이 필요할 수 있음.
- 주의사항: 없음.

## 다음 조치
- 후속 작업: 없음(요청받은 나머지 화면 정리 완료). 추가 화면/컴포넌트가 생기면 동일한
  `col-*`/`.rank-*` 클래스를 재사용해 일관성 유지.
