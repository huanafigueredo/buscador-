"""Scraper do Combo Atacadista — mesma engine 'Virtualiza' do Giassi, domínio diferente."""
from __future__ import annotations

import logging

from scrapers.giassi import VirtualizaScraper

logger = logging.getLogger("comparador.scrapers.combo")


class ComboScraper(VirtualizaScraper):
    market_name = "combo"
    base_url = "https://www.comboatacadista.com.br"
    ofertas_path = "/ofertas"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = ComboScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
