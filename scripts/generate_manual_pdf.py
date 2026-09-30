from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Preformatted, Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "MANUAL_KONEKSI.md"
OUTPUT = ROOT / "docs" / "Manual-Koneksi-SRE-Alert-Brain.pdf"


def build_story(text: str):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleId", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=25, alignment=TA_CENTER, textColor=colors.HexColor("#17365D"), spaceAfter=14))
    styles.add(ParagraphStyle(name="H2Id", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=colors.HexColor("#17365D"), spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyId", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="BulletId", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=14, leftIndent=14, firstLineIndent=-8, bulletIndent=4, spaceAfter=3))

    story = []
    code_lines = []
    in_code = False
    first_title = True

    def flush_code():
        nonlocal code_lines
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["Code"], maxLineLength=95))
            story.append(Spacer(1, 4))
            code_lines = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                flush_code()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line:
            continue
        if line.startswith("# "):
            story.append(Paragraph(line[2:], styles["TitleId"] if first_title else styles["H2Id"]))
            first_title = False
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], styles["H2Id"]))
        elif line.startswith("- "):
            story.append(Paragraph(f"• {line[2:]}", styles["BulletId"]))
        else:
            safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(safe.replace("`", ""), styles["BodyId"]))
    flush_code()
    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title="Manual Koneksi SRE Alert Brain", author="SRE Alert Brain")
    doc.build(build_story(SOURCE.read_text(encoding="utf-8")))
    print(OUTPUT)


if __name__ == "__main__":
    main()
