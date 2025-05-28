from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from io import BytesIO
from typing import Optional
import os
import re


def remove_emojis(text):
    emoji_pattern = re.compile("["
                           u"\U0001F600-\U0001F64F"  # emoticons
                           u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                           u"\U0001F680-\U0001F6FF"  # transport & map
                           u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                           "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)


def sanitize_text(text: str) -> str:
    text = text.replace('\u00A0', ' ')  # espace insécable
    text = text.replace('\u200B', '')   # zero-width space
    text = text.replace('\u2028', '\n')  # line separator
    text = text.replace('\u2029', '\n')  # paragraph separator
    return text


class PDF(FPDF):
    def __init__(self):
        super().__init__()
        font_folder = os.path.join("fonts")
        self.add_font("DejaVu", "", os.path.join(font_folder, "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", os.path.join(font_folder, "DejaVuSans-Bold.ttf"))
        self.add_font("DejaVu", "I", os.path.join(font_folder, "DejaVuSans-Oblique.ttf"))

    def header(self):
        logo_path = os.path.join("frontend", "logo_paper_scanner_ia.png")
        if os.path.exists(logo_path):
            self.image(logo_path, 10, 8, 25)
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 10, "Résumé généré par Paper Scanner IA", new_x=XPos.LEFT, new_y=YPos.NEXT, align="C")
        self.ln(5)


def generate_pdf(title: str, summary_text: str, source: Optional[str] = None) -> BytesIO:
    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("DejaVu", "", 12)
    pdf.set_text_color(0, 0, 0)

    def section(title, content):
        title = remove_emojis(title)
        content = sanitize_text(content)
        try:
            pdf.set_font("DejaVu", "B", 12)
            pdf.cell(0, 10, title, ln=True)
            pdf.set_font("DejaVu", "", 12)
            pdf.multi_cell(0, 8, content, align='J', new_x=XPos.LEFT, new_y=YPos.NEXT)
            pdf.ln(2)
        except Exception:
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(0, 8, content[:500] + " [...]", align='J', new_x=XPos.LEFT, new_y=YPos.NEXT)

    if source:
        pdf.set_font("DejaVu", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 10, f"Source : {source}", new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(5)

    blocks = summary_text.split("\n")
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if block.lower().startswith("résumé"):
            section("Résumé", block.split(":", 1)[-1].strip())
        elif block.lower().startswith("moléc"):
            section("Molécules mentionnées", block.split(":", 1)[-1].strip())
        elif block.lower().startswith("patho"):
            section("Pathologies ciblées", block.split(":", 1)[-1].strip())
        elif block.lower().startswith("type"):
            section("Type d'étude", block.split(":", 1)[-1].strip())
        elif block.lower().startswith("auteur"):
            section("Auteurs principaux", block.split(":", 1)[-1].strip())
        else:
            pdf.multi_cell(0, 8, sanitize_text(block), align='J', new_x=XPos.LEFT, new_y=YPos.NEXT)

    # --- FIN CORRIGÉE ---
    pdf_bytes = pdf.output(dest='S')
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)
    return buffer