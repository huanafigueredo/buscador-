"""Classe base compartilhada pelos scrapers: sessão HTTP, retry, download e log."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("comparador.scrapers")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
RAW_DIR = OUTPUT_DIR / "raw"
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"


class ScraperError(Exception):
    """Erro conhecido de um scraper individual (não deve derrubar o pipeline)."""


class BaseScraper:
    """Funcionalidade comum: request com retry, download de arquivos, persistência raw."""

    market_name: str = "base"
    base_url: str = ""

    def __init__(self, timeout: int = 20, max_retries: int = 3, backoff: float = 1.5):
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    def get(self, url: str, **kwargs) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "[%s] tentativa %d/%d falhou para %s: %s",
                    self.market_name, attempt, self.max_retries, url, exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.backoff ** attempt)
        raise ScraperError(f"Falha ao acessar {url}: {last_exc}") from last_exc

    def download_file(self, url: str, subdir: str | None = None) -> Path:
        """Baixa um binário (PDF/imagem) para output/downloads/<mercado>/, evita rebaixar."""
        dest_dir = DOWNLOADS_DIR / (subdir or self.market_name)
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = url.rstrip("/").split("/")[-1].split("?")[0] or "arquivo.bin"
        dest_path = dest_dir / filename

        if dest_path.exists() and dest_path.stat().st_size > 0:
            logger.info("[%s] já existe, pulando download: %s", self.market_name, dest_path.name)
            return dest_path

        resp = self.get(url)
        dest_path.write_bytes(resp.content)
        logger.info("[%s] baixado: %s (%d bytes)", self.market_name, dest_path.name, len(resp.content))
        return dest_path

    def save_raw(self, data: list[dict[str, Any]], date_str: str) -> Path:
        """Salva os dados brutos extraídos antes da normalização."""
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        path = RAW_DIR / f"{self.market_name}_{date_str}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("[%s] raw salvo: %s (%d itens)", self.market_name, path, len(data))
        return path

    def run(self, date_str: str) -> list[dict[str, Any]]:
        """Deve ser implementado por cada scraper. Retorna lista de itens brutos."""
        raise NotImplementedError
