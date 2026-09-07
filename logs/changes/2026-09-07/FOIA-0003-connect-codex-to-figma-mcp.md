# 변경 기록

- 일시: 2026-09-07 12:28
- 작성자: Codex
- 작업번호: FOIA-0003
- 변경 유형: config
- 상태: draft

## 변경 요약
VS Code에 포함된 Codex 실행 파일로 Figma 원격 MCP 연결 등록 및 OAuth 인증 완료

## 변경 내용
- 사용자 범위 Codex 설정에 `figma` MCP 서버를 추가함. 주소는 `https://mcp.figma.com/mcp`.
- VS Code 확장에 포함된 `codex.exe`를 절대 경로로 실행함. 확인된 버전은 `codex-cli 0.153.0`.
- 브라우저의 Figma OAuth 절차를 통해 로그인 완료. 인증 URL·토큰·인증 코드는 이 로그나 프로젝트에 저장하지 않음.
- 전역 PATH, PowerShell 실행 정책, 앱 소스, DB는 변경하지 않음.

## 원인
- 사용자가 PowerShell에서 `codex mcp add`와 `codex mcp login`을 실행했으나 CommandNotFoundException이 발생함.
- 사용자 PowerShell이 실행 파일을 찾지 못하여 VS Code 확장에 포함된 실행 파일의 위치를 확인하고 직접 호출함.
- Figma 브라우저 로그인과 별도로 Codex의 MCP 계정 연결이 필요했음.

## 검증
- 실제 실행 파일 존재 및 `--version` 확인 성공.
- `mcp add figma --url https://mcp.figma.com/mcp`: `Added global MCP server 'figma'.` 확인.
- OAuth 절차: `Successfully logged in.` 확인, 프로세스 정상 종료.
- `mcp list`: 이름 `figma`, 공식 서버 URL, Status `enabled`, Auth `OAuth` 확인.
- 사용자 설정 쓰기와 브라우저 실행은 환경의 실행 승인 절차를 거쳐 수행함.
- 이번 대화에서 Figma 도구가 아직 노출되지 않아 파일 조회·캔버스 편집 호출은 실행하지 않음.

## 리스크
- 사용자 범위 Codex MCP 설정에 영향을 주며 프로젝트 런타임과는 별개임.
- 로그인 성공은 Figma 파일의 편집 권한이나 Full seat 보유를 검증한 결과가 아님.
- 확장 업데이트 시 번들 codex.exe의 경로가 바뀔 수 있음.

## 다음 조치
- VS Code/Codex에서 도구 목록을 새로 불러온 뒤 Figma 도구 노출 확인.
- 사용자 Figma 파일 URL로 접근 및 편집 권한을 확인하고 KRDS 화면 구성 작업 진행.
