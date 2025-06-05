
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_spanish_paragraphs_v2.py

Descarga N párrafos en español, cada uno proveniente de una URL distinta, a partir de
fuentes variadas: medios de noticias, blogs, novelas de dominio público, cuentos, ensayos,
Wikipedia, Wikisource, Biblioteca Virtual Miguel de Cervantes, etc.

Los resultados se guardan en un CSV con las columnas:
    - texto
    - tipo   (noticia, blog, novela, cuento, ensayo, enciclopedia, etc.)
    - url

CONFIGURACIÓN RÁPIDA
--------------------
Modifica la variable TARGET_COUNT justo debajo para indicar cuántos párrafos quieres
(100 por defecto). También puedes pasar `--n 500` por línea de comandos para sobrescribirlo.

DEPENDENCIAS
------------
pip install requests beautifulsoup4 feedparser pandas tldextract

USO
----
python generate_spanish_paragraphs_v2.py --n 500
"""
from __future__ import annotations

import argparse
import csv
import random
import re
import time
from pathlib import Path
from typing import Dict, Generator, List, Tuple

import tldextract
import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup

###############################################################################
# === CONFIGURACIÓN MODIFICABLE ===============================================
###############################################################################

TARGET_COUNT: int = 100  # <- CAMBIA ESTE VALOR SI QUIERES MÁS O MENOS PÁRRAFOS
MIN_PARAGRAPH_LEN: int = 120  # longitud mínima en caracteres de cada párrafo

HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

# Pausa (segundos) entre descargas "pesadas" (novelas PDF/TXT)
HEAVY_DELAY_RANGE: Tuple[float, float] = (1.5, 3.5)

###############################################################################
# === UTILIDADES ===============================================================
###############################################################################

def clean_html(raw_html: str) -> str:
    """Elimina HTML y normaliza espacios."""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()

def first_long_paragraph(text: str, min_len: int = MIN_PARAGRAPH_LEN) -> str:
    """Devuelve el primer párrafo >= min_len."""
    for p in re.split(r"\n\s*\n", text):
        p = p.strip()
        if len(p) >= min_len:
            return p
    return ""

def domain(url: str) -> str:
    ext = tldextract.extract(url)
    return f"{ext.domain}.{ext.suffix}"

###############################################################################
# === FUENTES ==================================================================
###############################################################################

RSS_SOURCES: Dict[str, List[str]] = {
    "noticia": [
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/espana/rss",
        "https://www.elmundo.es/rss/elmundo/espana.xml",
        "https://www.abc.es/rss/feeds/abc_EspanaEspana.xml",
        "https://www.publico.es/rss/publico/rss/section/politica/",
        "https://www.eldiario.es/rss",
    ],
    "blog": [
        "https://www.xataka.com/rss",
        "https://hipertextual.com/feed",
        "https://blogthinkbig.com/feed",
        "https://blog.es.weforum.org/feed",
        "https://www.genbeta.com/feed",
    ],
}

GUTENBERG_IDS: List[int] = [
    2000, 16165, 59438, 4194, 39973, 43668, 45758, 57202, 18058, 18077,
    18080, 58737,
]

CERVANTES_URLS: List[str] = [
    "https://www.cervantesvirtual.com/obra-visor/don-quijote-de-la-mancha--0/html/",
    "https://www.cervantesvirtual.com/obra-visor/la-barraca-0/html/",
    "https://www.cervantesvirtual.com/obra-visor/rimas-y-leyendas/html/",
    "https://www.cervantesvirtual.com/obra-visor/pepita-jimenez-0/html/",
]

WIKISOURCE_PAGES: List[str] = [
    "https://es.wikisource.org/wiki/La_gallina_de_los_huevos_de_oro",
    "https://es.wikisource.org/wiki/El_aleph_(cuento)",
    "https://es.wikisource.org/wiki/Yo_y_mi_gato",
]

CUENTOS_RANDOM_BASE: str = "https://cuentosparadormir.com/random"

###############################################################################
# === GENERADORES ==============================================================
###############################################################################

from typing import Iterator

def paragraphs_from_rss(rss_url: str, tipo: str) -> Iterator[Tuple[str, str, str]]:
    feed = feedparser.parse(rss_url)
    for entry in feed.entries:
        link = entry.get("link")
        if not link:
            continue
        try:
            resp = requests.get(link, headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = [clean_html(p.get_text()) for p in soup.find_all("p")]
            paragraph = first_long_paragraph("\n".join(paragraphs))
            if paragraph:
                yield paragraph, tipo, link
        except Exception:
            continue

def paragraph_from_gutenberg(gid: int) -> Tuple[str, str, str]:
    urls_try = [
        f"https://www.gutenberg.org/cache/epub/{gid}/pg{gid}.txt",
        f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt",
    ]
    for url in urls_try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            paragraph = first_long_paragraph(resp.text)
            if paragraph:
                time.sleep(random.uniform(*HEAVY_DELAY_RANGE))
                return paragraph, "novela", url
    raise RuntimeError("Gutenberg falló")

def paragraph_from_cervantes(url: str) -> Tuple[str, str, str]:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "utf-8"
    if resp.status_code != 200:
        raise RuntimeError("Cervantes falló")
    soup = BeautifulSoup(resp.text, "html.parser")
    paragraphs = [clean_html(p.get_text()) for p in soup.find_all("p")]
    paragraph = first_long_paragraph("\n".join(paragraphs))
    time.sleep(random.uniform(*HEAVY_DELAY_RANGE))
    return paragraph, "novela", url

def paragraph_from_wikisource(url: str) -> Tuple[str, str, str]:
    resp = requests.get(url + "?action=raw", headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError("Wikisource falló")
    text = resp.text
    text = re.sub(r"\{\{.*?\}\}", "", text, flags=re.DOTALL)
    paragraph = first_long_paragraph(text)
    return paragraph, "cuento", url

def random_wikipedia_paragraph() -> Tuple[str, str, str]:
    api_url = "https://es.wikipedia.org/api/rest_v1/page/random/summary"
    data = requests.get(api_url, headers=HEADERS, timeout=10).json()
    extract = data.get("extract", "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    paragraph = first_long_paragraph(extract)
    if paragraph and url:
        return paragraph, "enciclopedia", url
    raise RuntimeError("Wikipedia vacío")

def random_cuento_paragraph() -> Tuple[str, str, str]:
    resp = requests.get(CUENTOS_RANDOM_BASE, headers=HEADERS, timeout=10, allow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError("Cuento corto falló")
    url = resp.url
    soup = BeautifulSoup(resp.text, "html.parser")
    paragraphs = [clean_html(p.get_text()) for p in soup.find_all("p")]
    paragraph = first_long_paragraph("\n".join(paragraphs))
    return paragraph, "cuento", url

###############################################################################
# === PRINCIPAL ================================================================
###############################################################################

def build_generators() -> List[callable]:
    gens: List[callable] = []
    for tipo, rss_list in RSS_SOURCES.items():
        for rss in rss_list:
            gens.append(lambda r=rss, t=tipo: paragraphs_from_rss(r, t))

    for gid in GUTENBERG_IDS:
        gens.append(lambda g=gid: [paragraph_from_gutenberg(g)])

    for url in CERVANTES_URLS:
        gens.append(lambda u=url: [paragraph_from_cervantes(u)])

    for url in WIKISOURCE_PAGES:
        gens.append(lambda u=url: [paragraph_from_wikisource(u)])

    gens.append(lambda: [random_wikipedia_paragraph()])
    gens.append(lambda: [random_cuento_paragraph()])

    random.shuffle(gens)
    return gens

def main() -> None:
    parser = argparse.ArgumentParser(description="Recolecta párrafos en español.")
    parser.add_argument("--n", type=int, default=TARGET_COUNT,
                        help="Número de párrafos a extraer (sobrescribe TARGET_COUNT).")
    parser.add_argument("--outfile", type=str, default="parrafos_es.csv",
                        help="Nombre del CSV de salida.")
    args = parser.parse_args()

    goal = args.n
    collected: List[Tuple[str, str, str]] = []
    seen_urls = set()

    for gen in build_generators():
        try:
            for paragraph, tipo, url in gen():
                if url in seen_urls or domain(url) in {domain(u) for u in seen_urls}:
                    continue
                if len(paragraph) < MIN_PARAGRAPH_LEN:
                    continue
                collected.append((paragraph, tipo, url))
                seen_urls.add(url)
                if len(collected) >= goal:
                    raise StopIteration
        except StopIteration:
            break
        except Exception:
            continue

    print(f"Se obtuvieron {len(collected)} párrafos (objetivo={goal}).")

    df = pd.DataFrame(collected, columns=["texto", "tipo", "url"])
    df.to_csv(args.outfile, index=False, quoting=csv.QUOTE_ALL, encoding="utf-8")
    print(f"CSV guardado en {Path(args.outfile).resolve()}")
    if len(collected) < goal:
        print("Advertencia: no se alcanzó la cifra solicitada; aumenta las fuentes o baja MIN_PARAGRAPH_LEN.")

if __name__ == "__main__":
    main()
