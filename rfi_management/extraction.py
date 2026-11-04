from pathlib import Path

import pymupdf
import pytesseract


TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_pdf_text(pdf_path):
    """
    Extract selectable text from every page of a PDF.
    """

    pdf_path = Path(pdf_path)

    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text")

        pages.append({
            "page": page_number,
            "text": text,
        })

    document.close()

    return pages