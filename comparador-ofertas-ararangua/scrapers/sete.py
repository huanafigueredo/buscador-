"""Scraper do Sete Supermercados — uma única imagem JPEG de encarte.

ATENÇÃO: o site é tecnologia antiga (HTTP puro, encoding não-UTF8) e o nome do
arquivo do encarte observado durante a inspeção tinha data de 2019, o que sugere
que a página pode estar desatualizada e não ser mais mantida semanalmente. Este
scraper verifica isso a cada execução (`is_stale`) e loga um aviso claro em vez
de assumir silenciosamente que o encarte é válido — decida manualmente se vale
manter esse alvo no comparativo.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from extractors.image_extractor import extract_from_image
from scrapers.base import BaseScraper, ScraperError

logger = logging.getLogger("comparador.scrapers.sete")

# Nomes de arquivo observados no padrão encarte_fotos_DDMMYYYY.jpg (ajustar se necessário)
DATE_IN_FILENAME_RE = re.compile(r"(\d{2})[-_]?(\d{2})[-_]?(\d{4})")
STALE_THRESHOLD_DAYS = 14


class SeteScraper(BaseScraper):
    market_name = "sete"
    base_url = "http://setesupermercados.com.br"
    ofertas_path = "/ofertas"
    encoding = "windows-1252"

    def find_encarte_image(self) -> str | None:
        url = urljoin(self.base_url, self.ofertas_path)
        resp = self.get(url)
        resp.encoding = self.encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        for img in soup.find_all("img"):
            src = img.get("src") or ""
            if "encarte" in src.lower() or "/fotos/" in src.lower():
                return urljoin(url, src)
        return None

    @staticmethod
    def extract_date_from_filename(filename: str) -> date | None:
        match = DATE_IN_FILENAME_RE.search(filename)
        if not match:
            return None
        d, m, y = match.groups()
        try:
            return date(int(y), int(m), int(d))
        except ValueError:
            return None

    def is_stale(self, image_url: str) -> bool:
        """Retorna True se a data embutida no nome do arquivo estiver muito velha
        (ou se a data for inconsistente), indicando que o site provavelmente
        não é mais mantido semanalmente."""
        filename = image_url.rstrip("/").split("/")[-1]
        embedded_date = self.extract_date_from_filename(filename)
        if embedded_date is None:
            logger.info("[%s] sem data no nome do arquivo (%s) — não dá pra checar atualização", self.market_name, filename)
            return False
        age_days = (datetime.now().date() - embedded_date).days
        if age_days > STALE_THRESHOLD_DAYS:
            logger.warning(
                "[%s] encarte parece desatualizado: data no arquivo é %s (%d dias atrás). "
                "Considere excluir este alvo do comparativo.",
                self.market_name, embedded_date.isoformat(), age_days,
            )
            return True
        return False

    def run(self, date_str: str) -> list[dict]:
        items: list[dict] = []
        try:
            image_url = self.find_encarte_image()
        except ScraperError as exc:
            logger.error("[%s] site parece fora do ar: %s", self.market_name, exc)
            return items

        if not image_url:
            logger.warning("[%s] nenhuma imagem de encarte encontrada — site pode ter mudado ou saído do ar", self.market_name)
            return items

        self.is_stale(image_url)  # apenas loga aviso, não bloqueia a extração

        try:
            image_path = self.download_file(image_url)
            parsed = extract_from_image(image_path)
            for entry in parsed:
                entry["mercado"] = self.market_name
                entry["fonte"] = image_url
            items.extend(parsed)
        except Exception as exc:
            logger.error("[%s] falha ao processar imagem %s: %s", self.market_name, image_url, exc)

        self.save_raw(items, date_str)
        return items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from datetime import date as date_

    scraper = SeteScraper()
    result = scraper.run(date_.today().isoformat())
    print(f"{len(result)} itens extraídos")
