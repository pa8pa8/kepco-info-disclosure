# KRDS 화면 디자인

## 실제 웹 화면 적용 (2026-09-08, FOIA-0022)

공식 KRDS의 색상·타이포그래피·버튼·입력창·표·배지 스타일을 현재 웹 시스템에 맞게
적용했습니다. 기존 Jinja 템플릿과 JS를 유지하는 방식이며, 공식 HTML Component Kit
전체를 설치하거나 Figma 컴포넌트 인스턴스를 가져온 구현은 아닙니다.

- 공통 스타일: `app/static/css/krds.css`를 기존 `style.css` 다음에 로드합니다.
- 적용 화면: 로그인·초기 계정 생성·대시보드·청구 목록·청구 상세·배정 대기·청구인 이력·
  설정·계정 목록/수정. 인쇄용 통지서는 화면 미리보기에만 적용하고 인쇄 CSS는 유지합니다.
- 색상: primary 50/60/70(`#256ef4`/`#0b50d0`/`#083891`), gray 계열과 상태 색상을
  역할별 CSS 변수로 연결했습니다. 확장 컴포넌트의 일부 보조 테두리는 프로젝트 값입니다.
- 서체: Pretendard GOV 400/700 정적 WOFF2를 로컬에서 제공합니다. 본문 17px, 줄 간격
  150% 이상, `rem` 단위의 글자 크기를 사용합니다. 폰트·라이선스·원본 해시는
  [`app/static/fonts/pretendard-gov/SOURCES.md`](../../app/static/fonts/pretendard-gov/SOURCES.md)에 있습니다.
- 상호작용: 본문 바로가기·현재 메뉴 표시·키보드 포커스, 담당자 결과 버튼과
  `aria-pressed` 재배정 후보 선택을 적용했습니다. 선택 후 같은 후보에 포커스를 유지합니다.
- 반응형: 작은 화면에 업무 메뉴를 표시하고 배정 카드는 한 열로 전환합니다. 넓은 표는
  표 영역 안에서 가로 스크롤됩니다.
- 적용 대상은 실제 웹 시스템입니다. `docs/blueprint.html`은 업무 판단 흐름 문서입니다.

### 검증과 미리보기

임시 DB·감시 폴더·추천 파일과 합성 청구 3건을 사용했습니다. 프로젝트 `data/` 파일은
검증 전후 SHA-256이 일치했습니다. 브라우저 요청은 Playwright에서 FastAPI TestClient로
전달해 실제 서버 포트나 외부 AI 서버를 띄우지 않았습니다.

- 기존 pytest: **34개 통과** (`python -B -m pytest -q -p no:cacheprovider`).
- Chromium: 1440/1024/768/390px 화면을 포함한 21개 화면·폭 조합에서 페이지 가로 넘침 없음,
  로컬 폰트 로드 성공, JS 오류·정적 자산 실패 없음.
- 키보드 Enter로 담당자 배정, Space/Enter로 재배정 후보 선택·해제, 최대 3명 제한과
  포커스 유지 확인. 인쇄 모드의 도구 모음 숨김과 문서 테두리 제거 확인.
- 요약 카드 6종의 글자 대비 5.26:1~7.95:1, 비활성 입력창의 상태 색상 확인.
- 자동 검증 기록: [`krds-web-verification.json`](krds-web-verification.json).
- 캡처: [배정 대기 PC](krds-web-dispatch-desktop.png), [배정 대기 모바일](krds-web-dispatch-390.png),
  [대시보드](krds-web-dashboard.png), [로그인](krds-web-login.png), [업무담당자 상세](krds-web-detail-staff.png).

위 검증은 Chromium 기준의 구현 점검입니다. KRDS 전체 준수 인증이나 모든 브라우저에 대한
접근성 검증을 의미하지 않습니다. 폰트 원본 2개로 배포 크기가 약 4.2MB 증가합니다.

### 공식 기준

- [KRDS 색상](https://www.krds.go.kr/html/site/style/style_02.html)
- [KRDS 타이포그래피](https://www.krds.go.kr/html/site/style/style_03.html)
- [KRDS 디자인 토큰](https://www.krds.go.kr/html/site/style/style_07.html)
- [적용 시 확인한 공식 CSS 토큰, 고정 커밋](https://github.com/KRDS-uiux/krds-uiux/blob/d6bb184c823e4757f05807ea4646a23e3133b6e6/resources/css/token/krds_tokens.css)

## 초기 Figma용 배정 대기 시안 (FOIA-0002)

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
- 초기 시안 생성 당시(FOIA-0002)에는 애플리케이션 코드·설정·DB를 변경하지 않았습니다.
  이후 실제 화면 반영은 위 FOIA-0004 및 FOIA-0022 기록을 참고하세요.

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

문구와 배치는 생성 스크립트에서 변경할 수 있습니다. 이 초기 SVG는 현재 실제 웹 화면과
일부 메뉴·상태 문구가 다르므로 최신 구현을 확인할 때는 `krds-web-*.png`를 참고하세요.

## 참고

- [KRDS 디자인 리소스](https://www.krds.go.kr/html/site/outline/outline_05.html)
- [KRDS 디자이너 안내](https://www.krds.go.kr/html/site/outline/outline_02.html)
- [Figma 가져오기 안내](https://help.figma.com/hc/en-us/articles/360040027794-Guide-to-imports-in-Figma-Design)
- [Figma 직접 편집 기능과 권한](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/)
