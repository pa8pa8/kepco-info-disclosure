# 배정 대기 화면 디자인 초안

`krds-dispatch-draft.svg`는 Figma의 빈 캔버스에 드래그해 가져올 수 있는 1440 × 1360 벡터 시안입니다. `krds-dispatch-draft.png`는 같은 시안의 미리보기입니다.

> **반영 상태 (2026-09-07, FOIA-0004)**: 이 시안의 밝은 배경·흰 카드·파란 포인트 톤은
> `app/static/css/style.css`의 전역 색상 토큰과 `app/templates/dispatch.html`의 좌(청구 원문)/
> 우(업무담당자 배정, 1·2·3순위) 2단 레이아웃으로 실제 화면 코드에 반영되었습니다. 전역 토큰을
> 바꾼 것이라 `/dispatch`뿐 아니라 대시보드·청구 목록·설정 등 다른 화면도 같은 라이트 테마로
> 함께 바뀌었습니다. 공식 KRDS 컴포넌트 라이브러리 인스턴스를 그대로 가져온 것은 아니며,
> 색상·레이아웃 토큰 수준의 근사치 반영입니다. 상세 내용은
> `logs/changes/2026-09-07/FOIA-0004-krds.md` 참고.

- 현재 `dispatch.html`의 메뉴, 청구 원문, 사전 추천, 담당자 검색·배정, 최근 배정 이력을 기준으로 구성했습니다.
- 모든 청구인·접수 내용·배정 이력은 합성 예시입니다. 데이터베이스와 접수 파일을 사용하지 않았습니다.
- KRDS의 밝은 표면, 파란색 주요 동작, 카드·입력창 스타일을 참고한 초안입니다. 공식 KRDS 컴포넌트가 적용되거나 준수 검증된 화면은 아닙니다.
- 한글 글꼴 누락을 피하기 위해 SVG의 문자는 맑은 고딕 기반 벡터 윤곽선으로 저장했습니다. Figma에서 텍스트 입력으로 문구를 바꾸는 방식, 공식 라이브러리 인스턴스, Auto Layout은 포함하지 않습니다.
- Figma 계정에 직접 가져오지는 않았습니다. Figma에서 SVG 가져오기와 화면 표시를 확인하는 단계가 남아 있습니다.
- 애플리케이션 코드·설정·DB는 변경하지 않았습니다. 이 파일은 실행되는 업무 화면이 아닌 디자인 검토 자료입니다.

## 가져오기

1. Figma에서 `정보공개_배정대기` 페이지를 엽니다.
2. 파일 탐색기에서 `krds-dispatch-draft.svg`를 캔버스로 끌어 놓습니다.
3. 전체 시안을 선택하고 화면에 맞게 확대하여 배치를 확인합니다.

## 재생성

Windows PowerShell에서 다음을 실행합니다. 추가 패키지를 설치하거나 앱 서버를 실행하지 않습니다.

```powershell
powershell -NoProfile -File tools/build_krds_dispatch_mockup.ps1
```

이번 환경에서는 Windows 실행 정책이 기본 명령을 차단하여, 실행 승인을 받은 뒤 해당
프로세스에만 `-ExecutionPolicy Bypass`를 적용해 생성했습니다. 영구 실행 정책은
변경하지 않았습니다. 재생성 시에도 사용 환경의 실행 정책을 따라야 합니다.

문구와 배치는 생성 스크립트에서 변경할 수 있습니다. 최종 구현 시에는 KRDS의 Pretendard GOV 서체와 공식 컴포넌트·디자인 토큰을 별도로 적용해야 합니다.

## 참고

- [KRDS 디자인 리소스](https://www.krds.go.kr/html/site/outline/outline_05.html)
- [KRDS 디자이너 안내](https://www.krds.go.kr/html/site/outline/outline_02.html)
- [Figma 가져오기 안내](https://help.figma.com/hc/en-us/articles/360040027794-Guide-to-imports-in-Figma-Design)
- [Figma 직접 편집 기능과 권한](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/)
