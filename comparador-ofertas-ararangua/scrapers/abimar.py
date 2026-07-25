"""Scraper do Abimar Supermercados — cadernos de ofertas multi-página em imagens JPEG.

/ofertas/abimar lista os cadernos ativos (ex: /ofertas/abimar/5, /7, /11, /32).
Cada caderno é um catálogo onde cada página é uma imagem (thumbs/<id>/1800/*.jpg
para a versão em alta resolução).
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from extractors.image_extractor import extract_from_image
from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.abimar")

CADERNO_RE = re.compile(r"/ofertas/abimar/(\d+)")
HIGH_RES_WIDTH = "1800"


class AbimarScraper(BaseScraper):
    market_name = "abimar"
    base_url = "https://www.abimarsupermercados.com.br"
    listing_path = "/ofertas/abimar"

    def find_caderno_ids(self) -> list[str]:
        url = urljoin(self.base_url, self.listing_path)
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        ids = set()
        for a in soup.find_all("a", href=True):
            match = CADERNO_RE.search(a["href"])
            if match:
                ids.add(match.group(1))
        return sorted(ids, key=int)

    def find_caderno_pages(self, caderno_id: str) -> list[str]:
        url = urljoin(self.base_url, f"{self.listing_path}/{caderno_id}")
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if "/thumbs/" not in src:
                continue
            # Troca a largura do thumb pela versão em alta resolução, se aplicável
            high_res = re.sub(r"/thumbs/(\d+)/\d+/", rf"/thumbs/\1/{HIGH_RES_WIDTH}/", src)
            images.append(urljoin(url, high_res))
        return images

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            caderno_ids = self.find_caderno_ids()
        except ScraperError as exc:
            logger.error("[%s] falha ao listar cadernos: %s", self.market_name, exc)
            return items

        if not caderno_ids:
            logger.warning("[%s] nenhum caderno ativo encontrado", self.market_name)
            return items

        for caderno_id in caderno_ids:
            try:
                page_images = self.find_caderno_pages(caderno_id)
            except ScraperError as exc:
                logger.error("[%s] falha ao ler caderno %s: %s", self.market_name, caderno_id, exc)
                continue

            for image_url in page_images:
                try:
                    image_path = self.download_file(image_url, subdir=f"{self.market_name}/{caderno_id}")
                    parsed = extract_from_image(image_path)
                    for entry in parsed:
                        entry["mercado"] = self.market_name
                        entry["fonte"] = image_url
                        entry["caderno"] = caderno_id
                    items.extend(parsed)
                except Exception as exc:
                    logger.error("[%s] falha ao processar imagem %s: %s", self.market_name, image_url, exc)
                    continue

        self.save_raw(items, date_str)
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = AbimarScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
