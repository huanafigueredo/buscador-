"""Scraper do Super A Atacadista — página HTML simples com links diretos a PDFs."""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from extractors.pdf_extractor import extract_from_pdf
from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.supera")


class SuperAScraper(BaseScraper):
    market_name = "supera"
    base_url = "https://encartes.superaatacadista.com.br/ararangua/"

    def find_pdf_links(self) -> list[str]:
        resp = self.get(self.base_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                links.append(urljoin(self.base_url, href))
        return links

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            pdf_links = self.find_pdf_links()
        except ScraperError as exc:
            logger.error("[%s] falha ao listar encartes: %s", self.market_name, exc)
            return items

        if not pdf_links:
            logger.warning("[%s] nenhum PDF encontrado na página %s", self.market_name, self.base_url)
            return items

        for pdf_url in pdf_links:
            try:
                pdf_path = self.download_file(pdf_url)
                parsed = extract_from_pdf(pdf_path)
                for entry in parsed:
                    entry["mercado"] = self.market_name
                    entry["fonte"] = pdf_url
                items.extend(parsed)
            except Exception as exc:
                logger.error("[%s] falha ao processar %s: %s", self.market_name, pdf_url, exc)
                continue

        self.save_raw(items, date_str)
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = SuperAScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
