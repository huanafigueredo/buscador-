"""Junta os dados de todos os scrapers, agrupa por produto normalizado e gera o CSV comparativo."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from normalizer import group_by_product

logger = logging.getLogger("comparador.comparador")

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _item_price(item: dict) -> float | None:
    for key in ("preco_por", "preco", "preco_de"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def build_comparison_rows(all_items: list[dict], markets: list[str]) -> list[dict]:
    """Uma linha por produto normalizado, uma coluna de preço por mercado, mais 'mais_barato'."""
    groups = group_by_product(all_items)
    rows = []

    for norm_name, group_items in groups.items():
        row = {"produto": norm_name}
        prices_by_market: dict[str, float] = {}

        for market in markets:
            row[market] = ""

        for item in group_items:
            market = item.get("mercado", "desconhecido")
            price = _item_price(item)
            if price is None:
                continue
            if market not in prices_by_market or price < prices_by_market[market]:
                prices_by_market[market] = price

        for market, price in prices_by_market.items():
            row[market] = f"{price:.2f}"

        if prices_by_market:
            cheapest_market = min(prices_by_market, key=prices_by_market.get)
            row["mais_barato"] = f"{cheapest_market} (R$ {prices_by_market[cheapest_market]:.2f})"
        else:
            row["mais_barato"] = ""

        rows.append(row)

    return rows


def write_comparison_csv(rows: list[dict], markets: list[str], date_str: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"comparativo_{date_str}.csv"
    fieldnames = ["produto", *markets, "mais_barato"]

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    logger.info("comparativo salvo em %s (%d produtos)", out_path, len(rows))
    return out_path


def build_and_save(all_items: list[dict], markets: list[str], date_str: str) -> Path:
    rows = build_comparison_rows(all_items, markets)
    return write_comparison_csv(rows, markets, date_str)
