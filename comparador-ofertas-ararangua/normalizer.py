"""Normaliza nomes de produto pra permitir comparação entre mercados diferentes."""
from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz, process

FUZZY_MATCH_THRESHOLD = 87  # score 0-100 do rapidfuzz pra considerar "mesmo produto"

# Termos de marketing/ruído que não ajudam a identificar o produto
NOISE_WORDS = {
    "oferta", "ofertas", "promocao", "promo", "leve", "pague", "ate",
    "un", "unidade", "kg", "g", "ml", "l", "cada", "por", "de", "a",
}

UNIT_ALIASES = {
    "quilo": "kg", "kilo": "kg", "grama": "g", "gramas": "g",
    "litro": "l", "litros": "l", "mililitro": "ml", "unidade": "un",
    "unidades": "un", "pacote": "pct", "caixa": "cx",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def normalize_product_name(raw_name: str) -> str:
    """Minúsculas, sem acento, sem pontuação, sem palavras de ruído, espaços colapsados."""
    text = _strip_accents(raw_name or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    words = [UNIT_ALIASES.get(w, w) for w in text.split()]
    words = [w for w in words if w and w not in NOISE_WORDS]

    return " ".join(words).strip()


def group_by_product(items: list[dict]) -> dict[str, list[dict]]:
    """Agrupa itens de todos os mercados por produto normalizado, usando fuzzy matching
    pra juntar variações de escrita do mesmo produto (ex: 'Arroz Tio Joao 5kg' vs
    'Arroz Tio João Tipo 1 5Kg')."""
    groups: dict[str, list[dict]] = {}
    canonical_keys: list[str] = []

    for item in items:
        raw_name = item.get("produto") or item.get("produto_bruto") or ""
        norm = normalize_product_name(raw_name)
        if not norm:
            continue
        item["produto_normalizado"] = norm

        if not canonical_keys:
            groups[norm] = [item]
            canonical_keys.append(norm)
            continue

        match = process.extractOne(norm, canonical_keys, scorer=fuzz.token_sort_ratio)
        if match and match[1] >= FUZZY_MATCH_THRESHOLD:
            groups[match[0]].append(item)
        else:
            groups[norm] = [item]
            canonical_keys.append(norm)

    return groups
