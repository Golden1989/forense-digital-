#!/usr/bin/env python3
"""linha_do_tempo.py - junta SMS, chamadas, historico do Chrome e apps instalados
numa unica linha do tempo, ja com as datas convertidas para UTC-3 e UTC.

Uso (todas as fontes sao opcionais; use as que tiver):
    python linha_do_tempo.py --sms mmssms.db --chrome History \\
        --calls calllog.db --packages packages.xml --csv linha.csv
    python linha_do_tempo.py --sms mmssms.db --chrome History --dia 2025-11-03

Cada banco e COPIADO para uma pasta temporaria (junto com os arquivos -wal e
-shm que estiverem ao lado) antes de ser aberto. O original nao e tocado e os
dados que ainda estao no WAL entram na leitura.

Formatos de data tratados:
    SMS e chamadas ... milissegundos Unix (13 digitos)
    Chrome ........... microssegundos desde 1601 (17 digitos), sempre em UTC
    packages.xml ..... milissegundos Unix em hexadecimal
"""
import argparse
import csv
import shutil
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
UTC3 = timezone(timedelta(hours=-3))
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)

TIPO_SMS = {1: "recebido", 2: "enviado"}
TIPO_CHAMADA = {1: "recebida", 2: "feita", 3: "perdida", 5: "rejeitada"}


def de_unix_ms(ms):
    """Milissegundos Unix -> datetime em UTC."""
    return datetime.fromtimestamp(ms / 1000, UTC)


def de_webkit(us):
    """Microssegundos desde 1601-01-01 (formato Chrome) -> datetime em UTC."""
    return EPOCA_WEBKIT + timedelta(microseconds=us)


def copiar_banco(caminho, pasta_tmp):
    """Copia o banco e os arquivos -wal/-shm vizinhos; devolve o caminho da copia."""
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def consultar(caminho, sql, pasta_tmp):
    """Abre a COPIA do banco e devolve as linhas da consulta."""
    copia = copiar_banco(caminho, pasta_tmp)
    con = sqlite3.connect(copia)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def eventos_sms(caminho, tmp):
    sql = "SELECT date, type, address, body FROM sms"
    return [(de_unix_ms(d), "SMS", TIPO_SMS.get(t, f"tipo {t}"), a or "", (b or "")[:80])
            for d, t, a, b in consultar(caminho, sql, tmp)]


def eventos_chamadas(caminho, tmp):
    sql = "SELECT date, type, number, duration FROM calls"
    return [(de_unix_ms(d), "CHAMADA", TIPO_CHAMADA.get(t, f"tipo {t}"), n or "", f"{dur}s")
            for d, t, n, dur in consultar(caminho, sql, tmp)]


def eventos_chrome(caminho, tmp):
    sql = ("SELECT v.visit_time, u.title, u.url FROM visits v "
           "JOIN urls u ON u.id = v.url")
    return [(de_webkit(t), "CHROME", "visita", url[:60], titulo or "")
            for t, titulo, url in consultar(caminho, sql, tmp)]


def eventos_pacotes(caminho):
    """Primeira instalacao ('it', hex) so dos apps de usuario (/data/app)."""
    saida = []
    for p in ET.parse(caminho).getroot().findall("package"):
        if p.get("codePath", "").startswith("/data/app") and p.get("it"):
            saida.append((de_unix_ms(int(p.get("it"), 16)), "APP", "instalado",
                          p.get("name"), p.get("installer", "-")))
    return saida


def main():
    ap = argparse.ArgumentParser(description="Linha do tempo unificada")
    ap.add_argument("--sms", help="mmssms.db")
    ap.add_argument("--calls", help="calllog.db")
    ap.add_argument("--chrome", help="History (Chrome)")
    ap.add_argument("--packages", help="packages.xml")
    ap.add_argument("--dia", help="mostra so este dia em UTC-3, formato AAAA-MM-DD")
    ap.add_argument("--csv", help="salva a linha do tempo neste CSV")
    args = ap.parse_args()

    eventos = []
    with tempfile.TemporaryDirectory() as tmp:
        if args.sms:
            eventos += eventos_sms(args.sms, tmp)
        if args.calls:
            eventos += eventos_chamadas(args.calls, tmp)
        if args.chrome:
            eventos += eventos_chrome(args.chrome, tmp)
        if args.packages:
            eventos += eventos_pacotes(args.packages)

    eventos.sort(key=lambda e: e[0])
    linhas = [{
        "utc3": e[0].astimezone(UTC3).strftime("%Y-%m-%d %H:%M:%S"),
        "utc": e[0].strftime("%Y-%m-%d %H:%M:%S"),
        "fonte": e[1], "evento": e[2], "detalhe": e[3], "extra": e[4],
    } for e in eventos]

    if args.dia:
        linhas = [l for l in linhas if l["utc3"].startswith(args.dia)]

    for l in linhas:
        print(f"{l['utc3']}  {l['fonte']:8s} {l['evento']:10s} {l['detalhe']}  {l['extra']}")
    print(f"\n{len(linhas)} eventos (horario em UTC-3).")

    if args.csv and linhas:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
        print(f"CSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
