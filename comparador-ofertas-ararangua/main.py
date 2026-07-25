"""Orquestra a rodada completa: roda todos os scrapers (em paralelo) e gera o comparativo final.

Cada scraper é isolado: se um falhar (site fora do ar, mudança de estrutura),
os outros continuam normalmente e o pipeline segue até o comparativo final.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from comparador import build_and_save
from scrapers.abimar import AbimarScraper
from scrapers.angeloni import AngeloniScraper
from scrapers.combo import ComboScraper
from scrapers.giassi import GiassiScraper
from scrapers.lisandra import LisandraScraper
from scrapers.sete import SeteScraper
from scrapers.supera import SuperAScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("comparador.main")

SCRAPERS = [
    SuperAScraper,
    AngeloniScraper,
    GiassiScraper,
    ComboScraper,
    AbimarScraper,
    LisandraScraper,
    SeteScraper,
]


def run_scraper(scraper_cls, date_str: str) -> tuple[str, list[dict]]:
    scraper = scraper_cls()
    market_name = scraper.market_name
    try:
        items = scraper.run(date_str)
        logger.info("[%s] concluído: %d itens", market_name, len(items))
        return market_name, items
    except Exception:
        logger.exception("[%s] falhou de forma inesperada — pipeline continua sem este mercado", market_name)
        return market_name, []


def main(parallel: bool = True) -> None:
    date_str = date.today().isoformat()
    all_items: list[dict] = []
    markets: list[str] = []

    if parallel:
        with ThreadPoolExecutor(max_workers=len(SCRAPERS)) as executor:
            futures = {executor.submit(run_scraper, cls, date_str): cls for cls in SCRAPERS}
            for future in as_completed(futures):
                market_name, items = future.result()
                markets.append(market_name)
                all_items.extend(items)
    else:
        for cls in SCRAPERS:
            market_name, items = run_scraper(cls, date_str)
            markets.append(market_name)
            all_items.extend(items)

    if not all_items:
        logger.error("nenhum item extraído de nenhum mercado — comparativo não será gerado")
        return

    out_path = build_and_save(all_items, sorted(set(markets)), date_str)
    logger.info("rodada completa. comparativo: %s", out_path)


if __name__ == "__main__":
    main()
