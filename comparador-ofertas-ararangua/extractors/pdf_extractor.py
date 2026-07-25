"""Extração de texto/preços de PDFs de encarte usando pdfplumber, com fallback OCR."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pdfplumber

logger = logging.getLogger("comparador.extractors.pdf")

# Ex: "R$ 12,99", "12,99", "R$1.234,56"
PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})")

MIN_CHARS_PER_PAGE = 20  # abaixo disso, assume PDF escaneado -> cair pro OCR


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extrai texto de todas as páginas. Levanta ValueError se o texto vier vazio/curto."""
    texts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            texts.append(page_text)

    full_text = "\n".join(texts)
    avg_chars = len(full_text) / max(len(texts), 1)
    if avg_chars < MIN_CHARS_PER_PAGE:
        raise ValueError(
            f"Texto insuficiente extraído de {pdf_path.name} "
            f"({avg_chars:.0f} chars/página) — provavelmente PDF escaneado, use OCR"
        )
    return full_text


def extract_text_from_pdf_ocr(pdf_path: Path) -> str:
    """Fallback: renderiza cada página como imagem e roda pytesseract."""
    import pytesseract
    from pdf2image import convert_from_path

    images = convert_from_path(str(pdf_path))
    texts = [pytesseract.image_to_string(img, lang="por") for img in images]
    return "\n".join(texts)


def parse_prices(text: str) -> list[dict[str, str]]:
    """Extração ingênua: para cada linha com preço, guarda a linha inteira como 'produto bruto'."""
    items = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = PRICE_RE.search(line)
        if match:
            preco_str = match.group(1)
            preco = float(preco_str.replace(".", "").replace(",", "."))
            produto = line[: match.start()].strip(" .-:")
            items.append({"produto_bruto": produto or line, "preco": preco, "linha_original": line})
    return items


def extract_from_pdf(pdf_path: Path) -> list[dict[str, str]]:
    """Ponto de entrada: tenta texto nativo, cai para OCR se necessário."""
    try:
        text = extract_text_from_pdf(pdf_path)
        logger.info("Texto nativo extraído de %s", pdf_path.name)
    except ValueError as exc:
        logger.info("%s — tentando OCR", exc)
        text = extract_text_from_pdf_ocr(pdf_path)
    return parse_prices(text)
