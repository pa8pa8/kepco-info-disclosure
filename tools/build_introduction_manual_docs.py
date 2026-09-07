from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT.parent / 'INFO_DISCLOSURE_System_materials'

ACCENT = RGBColor(15, 125, 128)
DARK = RGBColor(31, 41, 55)
MUTED = RGBColor(94, 109, 128)
LIGHT_TEAL = 'E4F6F4'
LIGHT_GRAY = 'F4F7FB'


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill)
    tc_pr.append(shd)


def setup_document(title: str, subtitle: str) -> Document:
    doc = Document()
    styles = doc.styles
    styles['Normal'].font.name = 'Malgun Gothic'
    styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), 'Malgun Gothic')
    styles['Normal'].font.size = Pt(10.2)

    title_p = doc.add_paragraph()
    title_run = title_p.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(22)
    title_run.font.color.rgb = DARK
    title_run.font.name = 'Malgun Gothic'

    subtitle_p = doc.add_paragraph()
    subtitle_p.paragraph_format.space_after = Pt(4)
    subtitle_run = subtitle_p.add_run(subtitle)
    subtitle_run.font.size = Pt(11)
    subtitle_run.font.color.rgb = MUTED
    subtitle_run.font.name = 'Malgun Gothic'

    org_p = doc.add_paragraph()
    org_p.paragraph_format.space_after = Pt(16)
    org_run = org_p.add_run('대상 기관: 한국전력공사')
    org_run.bold = True
    org_run.font.size = Pt(10.5)
    org_run.font.color.rgb = ACCENT
    org_run.font.name = 'Malgun Gothic'
    return doc


def add_heading(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(16)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = ACCENT
    run.font.name = 'Malgun Gothic'


def add_body(doc: Document, text: str) -> None:
    p = doc.add_paragraph(text)
    p.runs[0].font.size = Pt(10.5)
    p.paragraph_format.space_after = Pt(8)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style='List Bullet')
        p.runs[0].font.size = Pt(10.5)


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(item, style='List Number')
        p.runs[0].font.size = Pt(10.5)


def add_callout(doc: Document, label: str, text: str, fill: str = LIGHT_TEAL) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    set_cell_shading(cell, fill)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    label_run = p.add_run(f'{label}\n')
    label_run.bold = True
    label_run.font.color.rgb = ACCENT
    label_run.font.size = Pt(10.5)
    body_run = p.add_run(text)
    body_run.font.size = Pt(10.2)
    doc.add_paragraph()


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, header in zip(table.rows[0].cells, headers):
        set_cell_shading(cell, '0F7D80')
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(header)
        run.bold = True
        run.font.color.rgb = RGBColor(255, 255, 255)
    for row_idx, row_data in enumerate(rows):
        row = table.add_row()
        for idx, value in enumerate(row_data):
            cell = row.cells[idx]
            set_cell_shading(cell, 'FFFFFF' if row_idx % 2 == 0 else LIGHT_GRAY)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.add_run(value)
    doc.add_paragraph()


def add_footer(doc: Document) -> None:
    for section in doc.sections:
        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run('한국전력공사 정보공개 청구 지원 시스템')
        run.font.size = Pt(8)
        run.font.color.rgb = MUTED


def build_report() -> Path:
    doc = setup_document(
        '정보공개 청구 지원 시스템 프로그램 소개 보고서',
        'AI 기반 청구 내용 식별, 반복 청구 자동 판정, 법령 근거 기반 판단 위저드를 하나의 로컬 실행 파일로 통합한 처리 지원 대시보드',
    )
    add_callout(
        doc,
        '핵심 메시지',
        '본 프로그램은 담당자가 「공공기관의 정보공개에 관한 법률」에 따른 판단 절차를 빠르고 일관되게 수행하도록 돕는 로컬 통합 도구입니다. '
        '대시보드와 AI API가 동일 PC에서 함께 구동되므로 외부 AI 서버 주소 입력 및 불필요한 네트워크 노출을 줄였습니다.',
    )

    add_heading(doc, '1. 도입 목적')
    add_body(doc, '정보공개 청구 처리는 접수, 요청대상 파악, 반복 청구 확인, 정보 해당 여부, 비공개 대상 여부 등 여러 단계의 법령 근거 판단을 거칩니다. 본 프로그램은 반복적인 확인 작업을 표준화하고, AI가 식별 가능한 부분을 자동화하며, 최종 판단은 담당자가 근거 조문과 함께 승인하도록 하는 것을 목표로 합니다.')
    add_bullets(
        doc,
        [
            '접수된 청구 원문에서 AI가 요청대상을 자동 추출',
            '과거 접수 이력과 비교해 반복 청구(제11조의2) 여부를 자동 판정',
            '나머지 판단(정보 해당·진정질의·정보부존재·비공개 대상·부분공개)은 담당자가 근거 조문과 함께 Y/N으로 확정',
            '대시보드 8000번, 로컬 AI API 8011번 구조로 단일 EXE 실행 경험 제공',
        ],
    )

    add_heading(doc, '2. 전체 구성')
    add_table(
        doc,
        ['구성요소', '역할', '보안/운영 포인트'],
        [
            ['Dashboard', 'FastAPI/Jinja 기반 운영 UI 제공', '127.0.0.1:8000 로컬 바인딩'],
            ['Local AI API', '요청대상 식별 및 반복 청구 유사도 판정 API 제공', '127.0.0.1:8011 로컬 호출 전용'],
            ['SQLite DB', '청구·판단 이력·통지서 템플릿 저장', 'EXE 실행 폴더 하위 data 디렉터리 사용'],
            ['감시 폴더', '텍스트 청구서 자동 수집', '설정 화면에서 경로 변경 가능'],
        ],
    )

    add_heading(doc, '3. 주요 기능')
    add_table(
        doc,
        ['기능', '설명', '운영 효과'],
        [
            ['청구 접수', '웹 폼 또는 감시 폴더로 청구 원문 수집', '제출 형식(텍스트/PDF/HWPX/txt/excel)에 무관하게 동일 절차로 처리'],
            ['AI 식별', '요청대상 추출 및 반복 청구 여부 자동 판정', '담당자 확인 시간 단축'],
            ['판단 위저드', '단계별 Y/N 확정 및 근거 조문 표시', '판단 누락·근거 누락 방지'],
            ['통지서 템플릿', '통지 유형별 문구를 설정 화면에서 직접 편집', '통지문 작성 시간 단축'],
            ['관리자 로그인', '최초 실행 시 관리자 계정 생성 후 인증 기반 사용', '무단 실행 및 오남용 가능성 감소'],
        ],
    )

    add_heading(doc, '4. 판단 흐름')
    add_body(doc, '판단 절차는 자동 확정보다 근거 조문 표시와 담당자 확인을 우선합니다. AI는 반복 청구 여부만 자동 판정하고, 정보 해당 여부·진정질의·정보부존재·비공개 대상·부분공개 가능 여부는 담당자가 화면에서 직접 Y/N으로 확정합니다.')
    add_table(
        doc,
        ['단계', '질문', '근거 조문'],
        [
            ['1', '반복 청구 대상인가?', '제11조의2'],
            ['2', "이 법에서 정한 '정보'인가?", '제2조(정의)'],
            ['3', '진정·질의인가?', '제11조 제5항 제2호'],
            ['4', "'정보부존재' 인가?", '제11조 제5항 제1호'],
            ['5', "'대체정보'로 제공할 수 있는가?", '-'],
            ['6', '비공개 대상에 해당하는가?', '제9조 제1항 제1~8호'],
            ['7', '부분공개 가능한가?', '제14조'],
        ],
    )

    add_heading(doc, '5. 보안 운영 범위')
    add_callout(
        doc,
        '보안성 표현 예시',
        '본 프로그램은 운영 단말 로컬에서 실행되며, 청구인 개인정보는 등록된 관리자 계정으로만 열람할 수 있습니다. '
        '외부 AI 서버 의존 없이 로컬 식별 API만 사용해 청구 원문이 외부로 전송되지 않는 구조입니다.',
        fill='F3F8EE',
    )
    add_bullets(
        doc,
        [
            '대시보드와 AI API는 기본적으로 localhost에만 바인딩',
            '최초 관리자 계정 생성 후 로그인 기반 접근',
            '판단 확정 API는 인증된 관리자 세션 필요',
            'AI 식별은 로컬 규칙 기반으로 수행되어 외부 API 의존성 없음',
            '모든 판단 단계와 답변자를 이력으로 기록',
        ],
    )

    add_heading(doc, '6. 기대 효과')
    add_table(
        doc,
        ['구분', '기대 효과'],
        [
            ['처리 표준화', '담당자마다 다르던 판단 순서를 법령 조문 기준 절차로 통일'],
            ['처리 속도', '요청대상 식별과 반복 청구 확인을 자동화해 초기 확인 시간 단축'],
            ['근거 보존', '판단 단계별 조문·답변·담당자를 이력으로 남겨 사후 확인 용이'],
            ['배포성', 'EXE 하나로 대시보드와 로컬 AI API를 함께 구동'],
        ],
    )

    add_heading(doc, '7. 향후 개선 항목')
    add_bullets(
        doc,
        [
            '화면 출력 데이터의 HTML 이스케이프 전수 적용으로 XSS 방어 강화',
            '판단 확정 API에 CSRF 토큰 기반 구조 추가',
            'PDF/HWPX 원문 자동 파싱(pdfplumber, olefile 등) 지원',
            '청구인 개인정보 항목의 마스킹·암호화 저장',
            '로그인 실패 횟수 제한 및 계정 잠금 정책 추가',
        ],
    )

    add_footer(doc)
    path = OUT_DIR / 'INFO_DISCLOSURE_System_Program_Introduction_Report.docx'
    doc.save(path)
    return path


def build_manual() -> Path:
    doc = setup_document(
        '정보공개 청구 지원 시스템 운영자 매뉴얼',
        '설치, 최초 관리자 설정, 청구 접수, 판단 위저드, 통지서 템플릿 관리를 위한 실무형 사용 안내서',
    )
    add_callout(
        doc,
        '사용 전 확인',
        '본 매뉴얼은 단일 EXE 실행 기준입니다. 운영 전 감시 폴더 경로와 통지서 템플릿 문구를 현장 기준에 맞게 확인한 뒤 사용하십시오.',
    )

    add_heading(doc, '1. 실행 및 최초 설정')
    add_numbered(
        doc,
        [
            'INFO_DISCLOSURE_System.exe를 실행합니다. 첫 실행은 onefile 압축 해제로 인해 시간이 걸릴 수 있습니다.',
            '브라우저에서 http://127.0.0.1:8000 접속을 확인합니다.',
            '최초 실행 시 관리자 계정 생성 화면에서 관리자 아이디와 비밀번호를 등록합니다.',
            '등록 이후에는 로그인 화면에서 동일 계정으로 접속합니다.',
        ],
    )
    add_table(
        doc,
        ['항목', '기본값/위치', '비고'],
        [
            ['대시보드', '127.0.0.1:8000', '운영 UI'],
            ['로컬 AI API', '127.0.0.1:8011', '대시보드 내부 호출'],
            ['DB', '실행 폴더/data/info_disclosure.db', '청구·판단 이력 저장'],
            ['감시 폴더', '실행 폴더/data/watch', '설정 화면에서 변경 가능'],
        ],
    )

    add_heading(doc, '2. 화면 구성')
    add_table(
        doc,
        ['메뉴', '주요 용도'],
        [
            ['대시보드', '통지 유형별 현황, 판단 대기 청구, 최근 접수 청구 확인'],
            ['청구 목록', '접수된 청구 검색·필터·상세 이동'],
            ['청구 접수', '청구인 정보와 원문을 입력해 신규 접수'],
            ['청구 상세', 'AI 식별 결과 확인, 판단 위저드 진행, 최종 통지 확인'],
            ['설정', '감시 경로, 스캔 주기, 비공개 키워드, 통지서 템플릿 관리'],
        ],
    )

    add_heading(doc, '3. 청구 접수 및 AI 식별 절차')
    add_numbered(
        doc,
        [
            '청구 접수 화면에서 청구인 성명·연락처·제출 형식·청구 내용을 입력합니다.',
            '접수 즉시 AI가 요청대상을 추출하고 과거 이력과 비교해 반복 청구 여부를 판정합니다.',
            '반복 청구로 판정되면 즉시 종결 통지로 확정되며, 그렇지 않으면 판단 위저드로 이동합니다.',
            '감시 폴더에 형식에 맞는 텍스트 파일을 넣으면 자동 스캔 시 동일하게 접수됩니다.',
        ],
    )

    add_heading(doc, '4. 판단 위저드 사용법')
    add_body(doc, '청구 상세 화면 하단의 "다음 판단" 카드에 현재 단계의 질문과 근거 조문이 표시됩니다. 예(Y)/아니오(N) 버튼을 누르면 흐름도 규칙에 따라 다음 단계로 이동하거나 최종 통지 유형이 확정됩니다.')
    add_table(
        doc,
        ['단계', '질문', 'Y일 때', 'N일 때'],
        [
            ['반복 청구', '반복 청구 대상인가?', '종결 확정', "'정보' 해당 여부 판단으로"],
            ["'정보' 해당", "이 법에서 정한 '정보'인가?", "'정보부존재' 판단으로", '진정·질의 판단으로'],
            ['진정·질의', '진정·질의인가?', '진정·질의 확정', "'정보부존재' 판단으로"],
            ['정보부존재', "'정보부존재' 인가?", '정보부존재 확정', "'대체정보' 판단으로"],
            ['대체정보', "'대체정보'로 제공할 수 있는가?", '비공개 대상 판단으로', '비공개 대상 판단으로'],
            ['비공개 대상', '비공개 대상에 해당하는가?', '부분공개 판단으로', '공개 확정'],
            ['부분공개', '부분공개 가능한가?', '부분공개 확정', '비공개 확정'],
        ],
    )

    add_heading(doc, '5. 통지서 템플릿 관리')
    add_numbered(
        doc,
        [
            '설정 화면 하단 "통지서 문구 템플릿" 항목에서 6종 통지 유형별 기본 문구를 확인합니다.',
            '현장 기준에 맞게 문구를 수정한 뒤 저장하면 이후 확정되는 통지서부터 반영됩니다.',
            '청구 상세 화면에서는 확정 시점의 문구가 청구 요청대상과 함께 저장되어 이후 문구를 변경해도 기존 통지 내용은 유지됩니다.',
        ],
    )

    add_heading(doc, '6. 반복 청구 판정 확인')
    add_callout(
        doc,
        '판단 기준',
        'AI는 새 청구의 요청대상 문장을 과거 청구들과 문자열 유사도로 비교합니다. 유사도가 임계값 이상이면 반복 청구로 자동 판정하고, 청구 상세 화면에서 유사 청구 링크를 함께 제공합니다.',
        fill='FFF7E6',
    )

    add_heading(doc, '7. 운영 체크리스트')
    add_table(
        doc,
        ['체크', '확인 항목', '상태'],
        [
            ['1', '관리자 계정이 생성되어 있는가', '□'],
            ['2', '감시 경로가 실제 청구서 위치로 설정되어 있는가', '□'],
            ['3', '비공개 사유 키워드 목록이 현장 기준에 맞는가', '□'],
            ['4', '통지서 템플릿 문구가 최신 기준으로 반영되어 있는가', '□'],
            ['5', '반복 청구 판정 결과를 담당자가 주기적으로 확인하는가', '□'],
        ],
    )

    add_heading(doc, '8. 문제 해결')
    add_table(
        doc,
        ['증상', '확인 사항', '조치'],
        [
            ['브라우저가 바로 안 열림', 'onefile 압축 해제 시간이 길 수 있음', '1~3분 대기 후 http://127.0.0.1:8000 직접 접속'],
            ['AI 식별이 안 됨', '8011 포트 사용 여부 확인', '기존 프로세스 종료 후 EXE 재실행'],
            ['청구가 자동 접수되지 않음', '파일명이 숫자6~8자리_이름.txt 형식인지 확인', '형식에 맞게 파일명 변경 후 재스캔'],
            ['판단 버튼이 동작하지 않음', '이미 완료된 청구이거나 세션 만료', '목록에서 상태 확인 후 재로그인'],
        ],
    )

    add_heading(doc, '9. 보안 운영 권고')
    add_bullets(
        doc,
        [
            'EXE와 data 폴더는 운영자 권한이 있는 사용자만 접근 가능한 위치에 보관합니다.',
            '관리자 비밀번호는 운영 기준에 맞게 관리하고, 공유 계정 사용을 지양합니다.',
            '대시보드는 localhost 운영을 기본으로 하며, 포트 포워딩이나 외부 공개를 하지 않습니다.',
            '청구인 개인정보가 포함된 원문은 접근 권한이 있는 담당자만 열람합니다.',
        ],
    )

    add_footer(doc)
    path = OUT_DIR / 'INFO_DISCLOSURE_System_Operator_Manual.docx'
    doc.save(path)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report()
    manual = build_manual()
    print(report)
    print(manual)


if __name__ == '__main__':
    main()
