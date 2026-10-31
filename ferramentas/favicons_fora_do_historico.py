#!/usr/bin/env python3
"""favicons_fora_do_historico.py - compara o banco Favicons com o History do Chrome
e mostra o que esta nos favicons mas NAO aparece no historico de navegacao.

Por que isso interessa: o Chrome guarda o icone de cada site em um banco proprio
(Favicons). Quando o usuario apaga o historico, os icones podem continuar la.

Duas comparacoes sao feitas:
  A) PAGINAS: icon_mapping.page_url (pagina que usou o icone) x History.urls.url
  B) ICONES: favicons.url (de onde o arquivo do icone foi baixado) x dominios do History
     Ex.: o icone das buscas do Google vem de www.gstatic.com, um dominio que nunca
     aparece como pagina visitada. A comparacao B mostra esses casos, junto com as
     paginas que usaram cada icone.

Atencao ao interpretar: o dominio do icone muitas vezes e um CDN (gstatic.com,
githubassets.com). Dominio do icone ausente do historico NAO quer dizer que a
pessoa visitou esse dominio, nem que algo foi apagado; e so um fato a registrar.

Uso:
    python favicons_fora_do_historico.py --favicons Favicons --history History
    python favicons_fora_do_historico.py --favicons Favicons --history History --fuso -3
    python favicons_fora_do_historico.py --favicons Favicons --history History --so-paginas
    python favicons_fora_do_historico.py --favicons Favicons --history History --csv saida.csv

Cada banco e COPIADO para uma pasta temporaria (com os arquivos -wal/-shm, se
existirem) antes de ser aberto; o original nao e tocado.
Datas do Chrome: microssegundos desde 1601-01-01, sempre em UTC.
"""
import argparse
import csv
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

UTC = timezone.utc
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)


def ler_fuso(texto):
    """Converte 'utc', '-3', '+1'... em (objeto de fuso, nome para exibir)."""
    t = texto.strip().lower().replace("utc", "")
    if t in ("", "z"):
        return UTC, "UTC"
    horas = float(t)
    return timezone(timedelta(hours=horas)), f"UTC{horas:+g}"


def data_chrome(us, fuso):
    """Microssegundos desde 1601 -> texto 'AAAA-MM-DD HH:MM:SS' no fuso escolhido."""
    if not us:
        return ""
    return (EPOCA_WEBKIT + timedelta(microseconds=us)).astimezone(fuso).strftime("%Y-%m-%d %H:%M:%S")


def copiar_banco(caminho, pasta_tmp):
    """Copia o banco e os arquivos -wal/-shm vizinhos; devolve o caminho da copia."""
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def dominio(url):
    return urlparse(url).netloc.lower()


def main():
    ap = argparse.ArgumentParser(description="Favicons que nao estao no historico")
    ap.add_argument("--favicons", required=True, help="arquivo Favicons do Chrome")
    ap.add_argument("--history", required=True, help="arquivo History do Chrome")
    ap.add_argument("--so-paginas", action="store_true", help="faz so a comparacao A (paginas)")
    ap.add_argument("--fuso", default="utc", help="'utc' ou horas em relacao ao UTC (padrao: utc)")
    ap.add_argument("--csv", help="salva o resultado neste CSV")
    args = ap.parse_args()

    fuso, nome = ler_fuso(args.fuso)
    col_atual = f"icone_atualizado ({nome})"
    col_solic = f"icone_solicitado ({nome})"

    with tempfile.TemporaryDirectory() as tmp:
        hist = sqlite3.connect(copiar_banco(args.history, tmp))
        urls_hist = {u for (u,) in hist.execute("SELECT url FROM urls")}
        hist.close()
        dominios_hist = {dominio(u) for u in urls_hist}

        fav = sqlite3.connect(copiar_banco(args.favicons, tmp))
        paginas = fav.execute(
            "SELECT m.page_url, i.url, MIN(b.last_updated), MAX(b.last_requested) "
            "FROM icon_mapping m JOIN favicons i ON i.id = m.icon_id "
            "LEFT JOIN favicon_bitmaps b ON b.icon_id = m.icon_id "
            "GROUP BY m.page_url, i.url ORDER BY m.page_url"
        ).fetchall()
        icones = fav.execute(
            "SELECT i.id, i.url, MIN(b.last_updated), MAX(b.last_requested) "
            "FROM favicons i LEFT JOIN favicon_bitmaps b ON b.icon_id = i.id "
            "GROUP BY i.id, i.url ORDER BY i.url"
        ).fetchall()
        usos = {}   # id do icone -> lista de paginas que o usam
        for icone_id, pagina in fav.execute("SELECT icon_id, page_url FROM icon_mapping"):
            usos.setdefault(icone_id, []).append(pagina)
        fav.close()

    resultado = []

    # A) paginas com favicon que nao estao no historico
    sem_hist = [p for p in paginas if p[0] not in urls_hist]
    print(f"A) PAGINAS com favicon: {len({p[0] for p in paginas})} | fora do History: {len(sem_hist)}")
    for pagina, url_icone, atual, solic in sem_hist:
        print(f"   {pagina}\n      icone: {url_icone}\n      {col_atual}: {data_chrome(atual, fuso)}")
        resultado.append({"diferenca": "pagina fora do historico", "pagina": pagina,
                          "icone_url": url_icone, "paginas_que_usam": "",
                          col_atual: data_chrome(atual, fuso), col_solic: data_chrome(solic, fuso)})

    # B) icones cujo dominio de origem nunca aparece como dominio visitado
    if not args.so_paginas:
        icones_fora = [i for i in icones if dominio(i[1]) not in dominios_hist]
        print(f"\nB) ICONES (favicons.url): {len(icones)} | dominio de origem fora do History: {len(icones_fora)}")
        for icone_id, url_icone, atual, solic in icones_fora:
            lista = usos.get(icone_id, [])
            print(f"   {url_icone}\n      dominio do icone: {dominio(url_icone)}"
                  f" | paginas que usam este icone: {len(lista)}")
            for exemplo in lista[:3]:
                print(f"      ex.: {exemplo[:100]}")
            print(f"      {col_atual}: {data_chrome(atual, fuso)}")
            resultado.append({"diferenca": "dominio do icone fora do historico",
                              "pagina": lista[0] if lista else "", "icone_url": url_icone,
                              "paginas_que_usam": len(lista),
                              col_atual: data_chrome(atual, fuso), col_solic: data_chrome(solic, fuso)})

    if args.csv and resultado:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(resultado[0].keys()))
            w.writeheader()
            w.writerows(resultado)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
