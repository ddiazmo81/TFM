#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"generate_spanish_paragraphs.py
Extrae 100 párrafos en español de fuentes variadas (novelas de dominio público, 
noticias, blogs, Wikipedia, cuentos…), asegurando que cada párrafo procede de
una URL distinta.  Guarda el resultado en un CSV con las columnas:
    - texto
    - tipo
    - url

DEPENDENCIAS:
    pip install requests beautifulsoup4 feedparser pandas

USO:
    python generate_spanish_paragraphs.py
El CSV se guardará como 'parrafos_es.csv' en el mismo directorio.
\"\"\"

import csv
import random
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple, Generator, Dict

import requests
import feedparser
from bs4 import BeautifulSoup
import pandas as pd

################################################################################
# Utilidades generales
################################################################################

def clean_html(raw_html: str) -> str:
    \"\"\"Elimina etiquetas HTML y espacios extras.\"\"\"
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=' ', strip=True)
    # normaliza espacios
    text = re.sub(r'\\s+', ' ', text).strip()
    return text

def first_long_paragraph(text: str, min_len: int = 120) -> str:
    \"\"\"Devuelve el primer párrafo con longitud >= min_len.\"\"\"
    for p in text.split('\\n'):
        p = p.strip()
        if len(p) >= min_len:
            return p
    return ""

################################################################################
# Obtención de noticias y blogs vía RSS
################################################################################

RSS_SOURCES: Dict[str, List[str]] = {
    "noticia": [
        "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/rss",
        "https://www.abc.es/rss/feeds/abc_Internacional.xml",
        "https://e00-elmundo.uecdn.es/elmundo/rss/espana.xml",
        "https://www.elperiodico.com/es/rss/rss_portada.xml",
        "https://www.eldiario.es/rss"  # general
    ],
    "blog": [
        "https://hipertextual.com/feed",
        "https://blogthinkbig.com/feed",
        "https://www.xataka.com/rss",
        "https://blog.uoc.edu/blog/feed",
        "https://blog.es.weforum.org/feed"
    ]
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ParagraphBot/1.0; +https://example.com/bot)"
}

def paragraphs_from_rss(rss_url: str, tipo: str) -> Generator[Tuple[str, str, str], None, None]:
    \"\"\"Devuelve (texto, tipo, url) desde un RSS dado.\"\"\"
    feed = feedparser.parse(rss_url)
    for entry in feed.entries:
        link = entry.get("link")
        if not link:
            continue
        try:
            resp = requests.get(link, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = [clean_html(p.get_text()) for p in soup.find_all("p")]
            paragraph = first_long_paragraph("\\n".join(paragraphs))
            if paragraph:
                yield paragraph, tipo, link
        except Exception:
            continue

################################################################################
# Wikipedia aleatoria en español
################################################################################

def random_wikipedia_paragraph() -> Tuple[str, str, str]:
    resp = requests.get("https://es.wikipedia.org/api/rest_v1/page/random/summary", headers=HEADERS, timeout=10)
    data = resp.json()
    extract = data.get("extract", "")
    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    paragraph = first_long_paragraph(extract)
    if paragraph and url:
        return paragraph, "enciclopedia", url
    raise RuntimeError("No se pudo obtener párrafo de Wikipedia.")

################################################################################
# Proyecto Gutenberg (novelas dominio público en español)
################################################################################

GUTENBERG_IDS = [
    2000,   # Don Quijote de la Mancha
    16165,  # La gitanilla
    59438,  # Fortunata y Jacinta tomo I
    4194,   # Cuentos de Andersen (español)
    39973,  # Marianela
    43668,  # Doña Perfecta
    45758,  # Rimas y Leyendas
    57202,  # El Sombrero de Tres Picos
    18058,  # El Comendador Mendoza
    18077,  # La Barraca
    18080,  # Cañas y barro
    58737,  # Pepita Jiménez
]

def paragraph_from_gutenberg(gid: int) -> Tuple[str, str, str]:
    url = f"https://www.gutenberg.org/files/{gid}/{gid}-0.txt"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError("No se pudo descargar Gutenber.")
    text = resp.text
    paragraph = first_long_paragraph(text)
    return paragraph, "novela", url

################################################################################
# Cuentos cortos (web)
################################################################################

def random_cuento_paragraph() -> Tuple[str, str, str]:
    base = "https://cuentosparadormir.com/random"
    resp = requests.get(base, headers=HEADERS, timeout=10, allow_redirects=True)
    if resp.status_code != 200:
        raise RuntimeError("No se pudo descargar cuento corto.")
    url = resp.url  # redirect final
    soup = BeautifulSoup(resp.text, "html.parser")
    paragraphs = [clean_html(p.get_text()) for p in soup.find_all("p")]
    paragraph = first_long_paragraph("\\n".join(paragraphs))
    return paragraph, "cuento", url

################################################################################
# Función principal
################################################################################

def main():
    random.seed(time.time())
    collected: List[Tuple[str, str, str]] = []
    seen_urls = set()

    # Generadores
    generators = []

    # Añade generadores RSS
    for tipo, rss_list in RSS_SOURCES.items():
        for rss in rss_list:
            generators.append(lambda r=rss, t=tipo: paragraphs_from_rss(r, t))

    # Añade generador Wikipedia
    generators.append(lambda: [random_wikipedia_paragraph()])

    # Añade generadores Gutenberg individuales
    for gid in GUTENBERG_IDS:
        generators.append(lambda g=gid: [paragraph_from_gutenberg(g)])

    # Añade generador cuento
    generators.append(lambda: [random_cuento_paragraph()])

    # Mezcla generadores
    random.shuffle(generators)

    for gen in generators:
        try:
            for paragraph, tipo, url in gen():
                if url not in seen_urls and len(paragraph.split()) > 20:
                    collected.append((paragraph, tipo, url))
                    seen_urls.add(url)
                    if len(collected) >= 100:
                        raise StopIteration
        except StopIteration:
            break
        except Exception:
            continue

    if len(collected) < 100:
        print(f"Advertencia: solo se recolectaron {len(collected)} párrafos.")
    else:
        print("Se recolectaron 100 párrafos.")

    # Guardar CSV
    df = pd.DataFrame(collected, columns=["texto", "tipo", "url"])
    csv_path = Path("parrafos_es.csv")
    df.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL, encoding="utf-8")
    print(f"CSV guardado en {csv_path.resolve()}")

if __name__ == "__main__":
    main()
