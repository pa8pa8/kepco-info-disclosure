# 변경 기록

- 일시: 2026-09-07 12:19
- 작성자: Codex
- 작업번호: FOIA-0002
- 변경 유형: docs
- 상태: draft

## 변경 요약
Figma로 가져올 수 있는 배정 대기 화면의 독립 SVG 시안과 PNG 미리보기 생성

## 변경 내용
- `docs/design/krds-dispatch-draft.svg`: 1440 × 1360 벡터 화면 시안.
- `docs/design/krds-dispatch-draft.png`: 동일 배치의 미리보기.
- `tools/build_krds_dispatch_mockup.ps1`: Windows 기본 System.Drawing으로 시안 생성. UTF-8 BOM으로 Windows PowerShell 한글 호환성을 확보함.
- `docs/design/README.md`와 프로젝트 README에 가져오기 방법과 제약 기록.
- 앱 소스, 설정, SQLite DB, 기존 청구 데이터는 변경하지 않음.

## 원인
- 사용자가 Figma에 만든 빈 배정 대기 페이지의 화면 구성을 Codex가 대신 수행하도록 요청함.
- 현재 세션에 Figma 직접 편집 도구가 연결되어 있지 않아, 계정 연결 없이 가져올 수 있는 벡터 시안을 준비함.

## 검증
- 승인된 PowerShell 실행으로 SVG/PNG 생성 성공. Windows 실행 정책 때문에 기본 실행은 차단되었고, 승인 후 해당 프로세스에만 실행 허용 옵션을 적용함.
- XML 파싱 성공: SVG viewBox `0 0 1440 1360`, 텍스트 윤곽선 그룹 64개, 외부 이미지 참조 0개.
- PNG를 직접 확인하여 한글 렌더링, 카드 영역, 담당자 검색, 추천 버튼, 최근 배정 표의 배치를 확인함.
- 실제 Figma 계정으로 가져오기 및 Figma 렌더링 검증은 수행하지 못함.
- 앱 서버 및 DB를 실행하거나 기존 청구 원문을 읽지 않음.

## 리스크
- 영향 범위: 디자인 자료와 생성 도구·문서만 추가. 운영 화면에는 적용되지 않음.
- SVG 문자는 맑은 고딕 기반 윤곽선이므로 Figma에서 일반 텍스트처럼 편집할 수 없음.
- KRDS를 참고한 시안으로, 공식 컴포넌트 인스턴스·디자인 토큰 연결·Auto Layout은 포함하지 않음.
- 청구 및 배정 사례는 모두 합성 예시임.

## 다음 조치
- 사용자 Figma 캔버스에 SVG를 가져온 뒤 표시 확인.
- 직접 편집 연결을 선택하면 Figma의 계정/좌석 권한과 편집 도구 연결을 먼저 확인.
- 최종 디자인 확정 후 별도 구현 작업에서 KRDS 공식 컴포넌트와 프로젝트 API 연결.
