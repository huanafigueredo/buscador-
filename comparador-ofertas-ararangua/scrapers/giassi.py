"""Scraper do Giassi Supermercados (engine 'Virtualiza').

/ofertas lista seções (Ofertas do dia, Encarte Giassi, Bazar Giassi, ...),
cada uma linkando pra uma subpágina com uma galeria de imagens JPEG
(padrão .../slir/.../upload/weekend_image/*.jpeg).

Escrito para ser reaproveitado pelo scraper do Combo Atacadista (mesma engine),
bastando trocar base_url/ofertas_path na subclasse.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from extractors.image_extractor import extract_from_image
from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.giassi")

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")


class VirtualizaScraper(BaseScraper):
    """Base para sites rodando a engine Virtualiza (Giassi, Combo)."""

    market_name = "virtualiza_base"
    base_url = ""
    ofertas_path = "/ofertas"

    def find_section_links(self) -> list[str]:
        url = urljoin(self.base_url, self.ofertas_path)
        resp = self.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "ofertas" in href.lower() or "encarte" in href.lower() or "bazar" in href.lower():
                links.add(urljoin(self.base_url, href))
        links.discard(url)
        return sorted(links)

    def find_gallery_images(self, section_url: str) -> list[str]:
        resp = self.get(section_url)
        soup = BeautifulSoup(resp.text, "html.parser")

        images = set()
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if any(src.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                images.add(urljoin(section_url, src))
        return sorted(images)

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            sections = self.find_section_links()
        except ScraperError as exc:
            logger.error("[%s] falha ao listar seções: %s", self.market_name, exc)
            return items

        if not sections:
            logger.warning("[%s] nenhuma seção de ofertas encontrada", self.market_name)
            return items

        for section_url in sections:
            try:
                image_urls = self.find_gallery_images(section_url)
            except ScraperError as exc:
                logger.error("[%s] falha ao ler seção %s: %s", self.market_name, section_url, exc)
                continue

            for image_url in image_urls:
                try:
                    image_path = self.download_file(image_url)
                    parsed = extract_from_image(image_path)
                    for entry in parsed:
                        entry["mercado"] = self.market_name
                        entry["fonte"] = image_url
                    items.extend(parsed)
                except Exception as exc:
                    logger.error("[%s] falha ao processar imagem %s: %s", self.market_name, image_url, exc)
                    continue

        self.save_raw(items, date_str)
        return items


class GiassiScraper(VirtualizaScraper):
    market_name = "giassi"
    base_url = "https://institucional.giassi.com.br"
    ofertas_path = "/ofertas"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = GiassiScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
