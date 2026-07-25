"""Scraper do Angeloni (super.angeloni.com.br) — melhor alvo: e-commerce estruturado.

Estratégia: tenta primeiro a API pública VTEX (catalog_system/pub/products/search),
que é mais estável que parsear HTML. Se a API não responder no formato esperado
(o site pode não ser VTEX puro, ou o endpoint pode estar bloqueado/mudado),
cai para parsing de HTML da página de ofertas.
"""
from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.angeloni")

PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})")


def _parse_price(text: str) -> float | None:
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    return float(match.group(1).replace(".", "").replace(",", "."))


class AngeloniScraper(BaseScraper):
    market_name = "angeloni"
    base_url = "https://super.angeloni.com.br"
    ofertas_path = "/super-ofertas"
    # Endpoint padrão VTEX; ajustar fq/collection conforme categoria real de ofertas
    vtex_search_url = (
        "https://super.angeloni.com.br/api/catalog_system/pub/products/search"
        "?fq=productClusterIds:{cluster_id}&_from={start}&_to={end}"
    )
    vtex_page_size = 50

    # -------- Estratégia 1: API VTEX --------
    def try_vtex_api(self, cluster_id: str = "1") -> list[dict]:
        items: list[dict] = []
        start = 0
        while True:
            end = start + self.vtex_page_size - 1
            url = self.vtex_search_url.format(cluster_id=cluster_id, start=start, end=end)
            resp = self.get(url, headers={"Accept": "application/json"})
            try:
                data = resp.json()
            except ValueError as exc:
                raise ScraperError(f"resposta da API VTEX não é JSON: {exc}")

            if not isinstance(data, list) or not data:
                break

            for product in data:
                name = product.get("productName", "")
                brand = product.get("brand", "")
                for sku_item in product.get("items", []):
                    for seller in sku_item.get("sellers", []):
                        offer = seller.get("commertialOffer", {})
                        preco_de = offer.get("ListPrice")
                        preco_por = offer.get("Price")
                        if preco_por is None:
                            continue
                        items.append(
                            {
                                "produto": name,
                                "marca": brand,
                                "preco_de": preco_de,
                                "preco_por": preco_por,
                                "desconto_pct": (
                                    round((1 - preco_por / preco_de) * 100, 1)
                                    if preco_de and preco_de > preco_por
                                    else 0.0
                                ),
                                "preco_unidade": None,
                                "mercado": self.market_name,
                                "fonte": "vtex_api",
                            }
                        )
            if len(data) < self.vtex_page_size:
                break
            start += self.vtex_page_size

        if not items:
            raise ScraperError("API VTEX retornou 0 itens — provavelmente cluster_id incorreto ou API indisponível")
        return items

    # -------- Estratégia 2: parsing de HTML --------
    def scrape_html(self) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            url = f"{self.base_url}{self.ofertas_path}?page={page}"
            resp = self.get(url)
            soup = BeautifulSoup(resp.text, "html.parser")

            # Seletores genéricos de vitrine de e-commerce; ajustar após inspecionar
            # o HTML real (classes costumam mudar entre deploys de VTEX/loja).
            cards = soup.select("[class*='product-item'], [class*='shelf-item'], article")
            if not cards:
                break

            found_on_page = 0
            for card in cards:
                name_el = card.select_one("[class*='product-name'], h3, h2")
                price_por_el = card.select_one("[class*='selling-price'], [class*='price-value']")
                price_de_el = card.select_one("[class*='list-price'], [class*='price-from']")
                unit_el = card.select_one("[class*='price-unit'], [class*='per-unit']")

                if not name_el or not price_por_el:
                    continue

                preco_por = _parse_price(price_por_el.get_text())
                preco_de = _parse_price(price_de_el.get_text()) if price_de_el else None
                if preco_por is None:
                    continue

                found_on_page += 1
                items.append(
                    {
                        "produto": name_el.get_text(strip=True),
                        "marca": None,
                        "preco_de": preco_de,
                        "preco_por": preco_por,
                        "desconto_pct": (
                            round((1 - preco_por / preco_de) * 100, 1)
                            if preco_de and preco_de > preco_por
                            else 0.0
                        ),
                        "preco_unidade": unit_el.get_text(strip=True) if unit_el else None,
                        "mercado": self.market_name,
                        "fonte": url,
                    }
                )

            if found_on_page == 0:
                break
            page += 1
            if page > 30:  # trava de segurança (~592 produtos esperados)
                break

        return items

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            items = self.try_vtex_api()
            logger.info("[%s] API VTEX ok: %d itens", self.market_name, len(items))
        except ScraperError as exc:
            logger.warning("[%s] API VTEX falhou (%s) — caindo para parsing de HTML", self.market_name, exc)
            try:
                items = self.scrape_html()
                logger.info("[%s] HTML parsing ok: %d itens", self.market_name, len(items))
            except ScraperError as exc2:
                logger.error("[%s] parsing de HTML também falhou: %s", self.market_name, exc2)
                return []

        self.save_raw(items, date_str)
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date

    scraper = AngeloniScraper()
    result = scraper.run(date.today().isoformat())
    print(f"{len(result)} itens extraídos")
