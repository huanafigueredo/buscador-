# Comparador de Ofertas — Araranguá/SC

Scraper e comparador de preços de encartes de supermercados de Araranguá/SC.

## Mercados cobertos

| Mercado | Formato de origem | Extração |
|---|---|---|
| Super A Atacadista | PDF direto | pdfplumber (+ OCR fallback) |
| Angeloni | HTML/API VTEX | tenta API `catalog_system/pub/products/search`, cai para parsing de HTML |
| Giassi | Galeria de imagens (Virtualiza) | OCR (pytesseract) / Claude API |
| Combo Atacadista | Galeria de imagens (Virtualiza) | mesmo parser do Giassi |
| Abimar | Cadernos multi-página em imagem | OCR / Claude API |
| Supermercados Lisandra | SPA (Playwright) | OCR / Claude API ou parsing de texto do DOM |
| Sete Supermercados | Imagem única, site possivelmente desatualizado | OCR / Claude API, com checagem de "staleness" |

## Instalação

```bash
pip install -r requirements.txt
playwright install chromium   # necessário só para o scraper do Lisandra
```

Para o fallback de Vision (quando o OCR local não é suficiente), defina:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Para OCR local, o `pytesseract` requer o binário `tesseract` instalado no sistema
(`apt install tesseract-ocr tesseract-ocr-por` no Debian/Ubuntu) e `pdf2image`
requer `poppler-utils` para converter PDFs escaneados em imagem.

## Uso

Rodar a coleta completa (todos os mercados em paralelo) e gerar o comparativo:

```bash
python main.py
```

Rodar um scraper isoladamente (útil para validar/depurar um alvo específico):

```bash
python -m scrapers.supera
python -m scrapers.angeloni
```

Para o Lisandra, antes de confiar na extração, rode o dump de DOM pra confirmar
os seletores (a estrutura da SPA ainda não foi confirmada em detalhe):

```python
from scrapers.lisandra import LisandraScraper
LisandraScraper().debug_dump_dom("lisandra_dom.html")
```

## Saída

- `output/raw/<mercado>_<data>.json` — dados brutos de cada scraper, salvos antes
  da normalização (permite reprocessar sem rebaixar tudo).
- `output/comparativo_<data>.csv` — uma linha por produto normalizado, uma coluna
  de preço por mercado, e a coluna `mais_barato` com o vencedor.

## Notas de manutenção

- **Angeloni**: se o cluster ID usado na chamada à API VTEX (`try_vtex_api`) não
  corresponder à coleção real de "Super Ofertas", ajuste `cluster_id` ou os
  seletores de fallback em `scrape_html()` após inspecionar o HTML atual.
- **Giassi/Combo**: os seletores de imagem em `find_gallery_images` assumem tags
  `<img>` com `src`/`data-src` terminando em `.jpg/.jpeg/.png`; ajuste se o site
  passar a usar lazy-loading com outro atributo.
- **Sete Supermercados**: o scraper loga um aviso se a data embutida no nome do
  arquivo do encarte estiver com mais de 14 dias, sinalizando que o alvo pode
  estar desatualizado e merecer exclusão do comparativo.
- **Lisandra**: os seletores em `PRODUCT_CARD_SELECTORS`/`IMAGE_SELECTORS` são
  candidatos genéricos — confirme contra o DOM renderizado real antes de
  confiar nos dados extraídos.
