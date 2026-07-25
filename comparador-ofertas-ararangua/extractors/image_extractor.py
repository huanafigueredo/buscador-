"""Extração de produto/preço de imagens de encarte.

Tenta pytesseract primeiro (barato). Se a confiança média vier baixa ou o
texto reconhecido for curto/ilegível, cai para a Claude API, enviando a
imagem em base64 e pedindo JSON estrito de volta.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger("comparador.extractors.image")

PRICE_RE = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})")
MIN_OCR_CONFIDENCE = 60  # média de confiança do tesseract (0-100)
MIN_TEXT_LEN = 15

CLAUDE_MODEL = "claude-sonnet-5"
CLAUDE_PROMPT = (
    "Esta imagem é uma página de encarte de supermercado. Extraia todos os "
    "produtos com preço visíveis. Responda ESTRITAMENTE em JSON, sem texto "
    'adicional, no formato: [{"produto": "...", "preco": 0.00, "unidade": "..."}]. '
    'Use "unidade" para kg, l, un, etc quando indicado. Se não houver preço legível '
    "para um item, não o inclua. Se a imagem não tiver ofertas, responda []."
)


def _ocr_with_confidence(image_path: Path) -> tuple[str, float]:
    import pytesseract
    from PIL import Image

    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, lang="por", output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c in data["conf"] if c not in ("-1", -1)]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    text = " ".join(w for w in data["text"] if w.strip())
    return text, avg_conf


def _parse_ocr_text(text: str) -> list[dict]:
    items = []
    for line in text.splitlines():
        match = PRICE_RE.search(line)
        if match:
            preco = float(match.group(1).replace(".", "").replace(",", "."))
            produto = line[: match.start()].strip(" .-:")
            items.append({"produto": produto or line.strip(), "preco": preco, "unidade": ""})
    return items


def _extract_with_claude_api(image_path: Path) -> list[dict]:
    """Usa a Claude API (Messages API) para OCR + estruturação em JSON."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "pacote 'anthropic' não instalado — rode `pip install anthropic` "
            "para usar o fallback de Vision"
        ) from exc

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada — necessária para fallback de Vision")

    media_type = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                    },
                    {"type": "text", "text": CLAUDE_PROMPT},
                ],
            }
        ],
    )
    text_out = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text_out)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text_out, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        logger.error("Resposta da Claude API não é JSON válido: %s", text_out[:200])
        return []


def extract_from_image(image_path: Path, force_claude: bool = False) -> list[dict]:
    """Ponto de entrada: OCR local primeiro, cai pra Claude API se baixa confiança."""
    if not force_claude:
        try:
            text, confidence = _ocr_with_confidence(image_path)
            if confidence >= MIN_OCR_CONFIDENCE and len(text) >= MIN_TEXT_LEN:
                items = _parse_ocr_text(text)
                if items:
                    logger.info(
                        "%s: OCR local ok (confiança %.0f, %d itens)",
                        image_path.name, confidence, len(items),
                    )
                    return items
            logger.info(
                "%s: OCR local com baixa confiança (%.0f) ou sem itens — caindo para Claude API",
                image_path.name, confidence,
            )
        except Exception as exc:
            logger.warning("%s: OCR local falhou (%s) — caindo para Claude API", image_path.name, exc)

    return _extract_with_claude_api(image_path)
