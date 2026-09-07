from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor as PptRGB
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'INFO_DISCLOSURE_System_materials'
PPTX_PATH = OUT / 'INFO_DISCLOSURE_System_Program_Overview.pptx'

BG = '071422'
PANEL = '102A48'
ACCENT = '0F7D80'
TEAL = '4FD8D0'
AMBER = 'F59E0B'
RED = 'EF4444'
GREEN = '22C55E'
WHITE = 'F8FAFC'
MUTED = 'B8C7DA'

SLIDE_W, SLIDE_H = 13.333, 7.5


def hx(value: str) -> PptRGB:
    value = value.replace('#', '')
    return PptRGB(int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def new_slide(prs: Presentation):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = hx(BG)
    return slide


def add_text(slide, text, x, y, w, h, size=18, color=WHITE, bold=False, align='left', valign='top'):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE if valign == 'mid' else MSO_ANCHOR.TOP
    for idx, line in enumerate(str(text).split('\n')):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = line
        p.font.name = '맑은 고딕'
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = hx(color)
        p.alignment = {'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}.get(align, PP_ALIGN.LEFT)
    return box


def add_box(slide, text, x, y, w, h, fill=PANEL, stroke=ACCENT, size=14, bold=True, color=WHITE):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = hx(fill)
    shp.line.color.rgb = hx(stroke)
    shp.line.width = Pt(1.2)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.1)
    tf.margin_right = Inches(0.1)
    for idx, line in enumerate(str(text).split('\n')):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = line
        p.font.name = '맑은 고딕'
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = hx(color)
        p.alignment = PP_ALIGN.CENTER
    return shp


def slide_title(slide, kicker, title):
    add_text(slide, kicker.upper(), 0.6, 0.35, 8, 0.4, size=12, color=TEAL, bold=True)
    add_text(slide, title, 0.6, 0.7, 11.5, 0.8, size=28, color=WHITE, bold=True)


def build_pptx() -> Path:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)

    # 1. 표지
    s = new_slide(prs)
    add_text(s, '한국전력공사', 0.8, 2.15, 11.5, 0.5, size=15, color=MUTED, bold=True)
    add_text(s, 'INFO-DISCLOSURE SUPPORT SYSTEM', 0.8, 2.6, 11.5, 0.6, size=16, color=TEAL, bold=True)
    add_text(s, '정보공개 청구 처리 지원 대시보드', 0.8, 3.1, 11.5, 1.0, size=36, color=WHITE, bold=True)
    add_text(s, 'AI 요청대상 식별 · 반복 청구 자동 판정 · 법령 근거 판단 위저드', 0.8, 4.0, 11.5, 0.6, size=16, color=MUTED)

    # 2. 배경과 목적
    s = new_slide(prs)
    slide_title(s, 'Background', '왜 만들었나')
    items = [
        ('표준화', '접수·요청대상 파악·반복 청구 확인 등 여러 단계 판단을 조문 기준 절차로 통일'),
        ('속도', 'AI가 요청대상 추출과 반복 청구 판정을 자동 수행해 초기 확인 시간 단축'),
        ('근거 보존', '판단 단계별 조문·답변·담당자를 이력으로 남겨 사후 확인 용이'),
    ]
    for i, (k, v) in enumerate(items):
        add_box(s, k, 0.6 + i * 4.1, 2.0, 3.8, 0.7, fill=ACCENT, size=16)
        add_text(s, v, 0.6 + i * 4.1, 2.9, 3.8, 2.0, size=13, color=MUTED)

    # 3. 아키텍처
    s = new_slide(prs)
    slide_title(s, 'Architecture', '전체 구성')
    add_box(s, '담당자 브라우저\nhttp://127.0.0.1:8000', 0.6, 2.0, 3.4, 1.1, fill=PANEL)
    add_box(s, 'Dashboard 서버\nFastAPI · Jinja2 · SQLite', 4.6, 2.0, 3.9, 1.1, fill=ACCENT)
    add_box(s, 'Local AI API\n127.0.0.1:8011 (identify)', 9.1, 2.0, 3.4, 1.1, fill=PANEL)
    add_box(s, '감시 폴더\ndata/watch/*.txt 자동 접수', 0.6, 3.6, 3.4, 1.1, fill=PANEL)
    add_box(s, 'SQLite DB\n청구 · 판단 이력 · 통지서 템플릿', 4.6, 3.6, 3.9, 1.1, fill=PANEL)
    add_box(s, '통지서 발급\n공개/부분공개/비공개 등 6종', 9.1, 3.6, 3.4, 1.1, fill=PANEL)

    # 4. 판단 흐름
    s = new_slide(prs)
    slide_title(s, 'Decision Flow', '7단계 판단 흐름')
    steps = [
        ('1. 반복 청구', '제11조의2', RED),
        ('2. 정보 해당', '제2조', ACCENT),
        ('3. 진정·질의', '제11조5항2호', AMBER),
        ('4. 정보부존재', '제11조5항1호', AMBER),
        ('5. 대체정보', '-', PANEL),
        ('6. 비공개 대상', '제9조1항', RED),
        ('7. 부분공개', '제14조', GREEN),
    ]
    x = 0.5
    w = (12.3 / len(steps)) - 0.15
    for label, article, color in steps:
        add_box(s, label, x, 2.4, w, 0.9, fill=color, size=11)
        add_text(s, article, x, 3.4, w, 0.4, size=9, color=MUTED, align='center')
        x += w + 0.15
    add_text(s, '최종 통지: 종결 · 진정질의 · 정보부존재 · 공개 · 부분공개 · 비공개', 0.6, 4.6, 11.5, 0.5, size=14, color=WHITE, bold=True, align='center')

    # 5. AI 역할
    s = new_slide(prs)
    slide_title(s, 'AI Role', 'AI가 자동으로 하는 일 vs 담당자가 확정하는 일')
    add_box(s, 'AI 자동 처리', 0.6, 2.0, 5.8, 0.6, fill=ACCENT, size=16)
    add_text(s, '1. 청구 원문 요약\n2. 요청대상 문장 추출\n3. 과거 이력 대비 반복 청구 유사도 판정 및 자동 확정', 0.6, 2.8, 5.8, 2.2, size=13, color=MUTED)
    add_box(s, '담당자 확정 (근거 조문 표시)', 6.9, 2.0, 5.8, 0.6, fill=PANEL, stroke=TEAL, size=16)
    add_text(s, "정보 해당 여부 · 진정·질의 여부 · 정보부존재 · 대체정보 제공 가능 여부 · 비공개 대상 해당 여부 · 부분공개 가능 여부 — 6단계 모두 Y/N 버튼으로 직접 확정", 6.9, 2.8, 5.8, 2.2, size=13, color=MUTED)

    # 6. 보안
    s = new_slide(prs)
    slide_title(s, 'Security', '보안 설계')
    points = [
        '대시보드·AI API 모두 127.0.0.1 로컬 바인딩, 외부 AI 서버 주소 입력 불필요',
        '최초 실행 시 관리자 계정 생성 후 로그인 기반 접근, pbkdf2 해시 + HMAC 서명 세션',
        '판단 확정 API는 인증 세션 필요, 완료된 청구 재판단은 자동 차단',
        '모든 판단 단계·답변자·시각을 이력으로 기록해 사후 추적 가능',
    ]
    for i, t in enumerate(points):
        add_text(s, f'✔ {t}', 0.8, 2.0 + i * 0.7, 11.3, 0.6, size=15, color=WHITE)

    # 7. 로드맵
    s = new_slide(prs)
    slide_title(s, 'Roadmap', '향후 개선 항목')
    roadmap = [
        'PDF/HWPX 원문 자동 파싱(pdfplumber, olefile 등) 지원',
        '판단 확정 API CSRF 토큰 기반 구조 개선',
        '청구인 개인정보 항목 마스킹·암호화 저장',
        '로그인 실패 횟수 제한 및 계정 잠금 정책',
    ]
    for i, t in enumerate(roadmap):
        add_box(s, f'{i + 1}', 0.8, 2.0 + i * 1.0, 0.6, 0.7, fill=ACCENT, size=16)
        add_text(s, t, 1.6, 2.05 + i * 1.0, 10.5, 0.7, size=15, color=WHITE, valign='mid')

    OUT.mkdir(parents=True, exist_ok=True)
    prs.save(PPTX_PATH)
    return PPTX_PATH


if __name__ == '__main__':
    path = build_pptx()
    print(path)
