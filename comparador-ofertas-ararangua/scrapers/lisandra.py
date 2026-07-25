"""Scraper do Supermercados Lisandra — SPA, precisa de Playwright pra renderizar.

O HTML vem vazio no fetch simples. Este scraper usa Playwright (Chromium headless)
para renderizar a página e então procura ofertas no DOM já montado.

IMPORTANTE: a estrutura exata do DOM renderizado (se as ofertas aparecem como
imagens de encarte ou como lista de produtos com preço) ainda não foi confirmada
— os seletores abaixo (`SELECTOR_CANDIDATES`) cobrem os padrões mais comuns e
devem ser ajustados após rodar `debug_dump_dom()` uma vez contra o site real.
"""
from __future__ import annotations

import logging
import re

from extractors.image_extractor import extract_from_image
from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.lisandra")

PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")

# Seletores candidatos pra produtos com preço em texto (ajustar após inspeção real)
PRODUCT_CARD_SELECTORS = [
    "[class*='produto']",
    "[class*='product']",
    "[class*='oferta']",
    "[class*='card']",
]
IMAGE_SELECTORS = ["img[src*='encarte']", "img[src*='oferta']", "[class*='encarte'] img"]


class LisandraScraper(BaseScraper):
    market_name = "lisandra"
    base_url = "https://mercadolisandra.com.br/"

    def _render_page(self):
        from playwright.sync_api import sync_playwright

        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(user_agent=self.session.headers["User-Agent"])
        page.goto(self.base_url, wait_until="networkidle", timeout=30000)
        return playwright, browser, page

    def debug_dump_dom(self, out_path: str = "lisandra_dom.html") -> None:
        """Utilitário manual: salva o HTML renderizado pra inspecionar a estrutura real."""
        playwright, browser, page = self._render_page()
        try:
            html = page.content()
            from pathlib import Path

            Path(out_path).write_text(html, encoding="utf-8")
            logger.info("DOM renderizado salvo em %s (%d bytes)", out_path, len(html))
        finally:
            browser.close()
            playwright.stop()

    def _extract_product_cards(self, page) -> list[dict]:
        items = []
        for selector in PRODUCT_CARD_SELECTORS:
            cards = page.query_selector_all(selector)
            if not cards:
                continue
            for card in cards:
                text = card.inner_text().strip()
                match = PRICE_RE.search(text)
                if not match:
                    continue
                preco = float(match.group(1).replace(".", "").replace(",", "."))
                produto = text[: match.start()].strip(" \n.-:")
                items.append({"produto": produto or text.splitlines()[0], "preco": preco, "unidade": ""})
            if items:
                break
        return items

    def _extract_offer_images(self, page) -> list[str]:
        urls = set()
        for selector in IMAGE_SELECTORS:
            for img in page.query_selector_all(selector):
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if src:
                    urls.add(src)
        return sorted(urls)

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            playwright, browser, page = self._render_page()
        except Exception as exc:
            logger.error("[%s] falha ao renderizar via Playwright: %s", self.market_name, exc)
            return items

        try:
            product_items = self._extract_product_cards(page)
            if product_items:
                for entry in product_items:
                    entry["mercado"] = self.market_name
                    entry["fonte"] = self.base_url
                items.extend(product_items)
            else:
                image_urls = self._extract_offer_images(page)
                if not image_urls:
                    logger.warning(
                        "[%s] nenhum produto nem imagem de oferta encontrado no DOM renderizado "
                        "— rode debug_dump_dom() pra inspecionar a estrutura real",
                        self.market_name,
                    )
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
        except ScraperError as exc:
            logger.error("[%s] erro durante extração: %s", self.market_name, exc)
        finally:
            browser.close()
            playwright.stop()

        self.save_raw(items, date_str)
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = LisandraScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
