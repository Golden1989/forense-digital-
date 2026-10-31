#!/usr/bin/env python3
"""downloads_chrome.py - lista os downloads registrados no History do Chrome/Edge/Brave.

Junta as tabelas downloads e downloads_url_chains e mostra, para cada arquivo:
  - nome e pasta onde foi salvo (target_path);
  - URL USADA PARA BAIXAR (inicio da cadeia) e URL final, se houve redirecionamento;
  - pagina de origem (tab_url) e referrer;
  - inicio, fim e duracao do download;
  - tamanho, estado (concluido, cancelado...), classificacao de perigo, se foi aberto;
  - hash (quando o Chrome o guardou).

Uso:
    python downloads_chrome.py History
    python downloads_chrome.py History --fuso -3
    python downloads_chrome.py History --filtro .zip
    python downloads_chrome.py History --url-completa --csv downloads.csv

O banco e COPIADO (com -wal e -shm) para uma pasta temporaria; o original nao
e tocado. Datas do Chrome: microssegundos desde 1601, UTC.

Atencao: o History registra que o Chrome BAIXOU o arquivo. Que o arquivo ainda
exista no disco, ou que tenha sido aberto/executado, deve ser confirmado em
outras fontes (sistema de arquivos, Prefetch, etc.).
"""
import argparse
import csv
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

UTC = timezone.utc
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)

ESTADO = {0: "em andamento", 1: "concluido", 2: "cancelado", 3: "interrompido", 4: "interrompido"}
PERIGO = {0: "nao perigoso", 1: "arquivo perigoso", 2: "URL perigosa", 3: "conteudo perigoso",
          4: "possivelmente perigoso", 5: "conteudo incomum", 6: "validado pelo usuario",
          7: "host perigoso", 8: "indesejado (PUP)", 9: "permitido por politica",
          10: "analise assincrona", 11: "bloqueado (senha)", 12: "bloqueado (grande)"}


def ler_fuso(texto):
    t = texto.strip().lower().replace("utc", "")
    if t in ("", "z"):
        return UTC, "UTC"
    horas = float(t)
    return timezone(timedelta(hours=horas)), f"UTC{horas:+g}"


def data(us, fuso):
    if not us:
        return ""
    return (EPOCA_WEBKIT + timedelta(microseconds=us)).astimezone(fuso).strftime("%Y-%m-%d %H:%M:%S")


def copiar_banco(caminho, pasta_tmp):
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def main():
    ap = argparse.ArgumentParser(description="Downloads do History do Chrome")
    ap.add_argument("history", help="arquivo History")
    ap.add_argument("--fuso", default="utc", help="'utc' (padrao) ou horas (-3)")
    ap.add_argument("--filtro", help="so downloads cujo nome/URL contenham este texto")
    ap.add_argument("--url-completa", action="store_true", help="nao corta as URLs")
    ap.add_argument("--csv", help="salva a tabela neste CSV")
    args = ap.parse_args()
    fuso, nome_fuso = ler_fuso(args.fuso)

    with tempfile.TemporaryDirectory() as tmp:
        con = sqlite3.connect(copiar_banco(args.history, tmp))
        colunas = {r[1] for r in con.execute("PRAGMA table_info(downloads)")}
        if not colunas:
            raise SystemExit("Tabela 'downloads' nao encontrada: este nao parece ser um History do Chromium.")
        quer = lambda c: c if c in colunas else f"NULL AS {c}"   # colunas variam entre versoes
        linhas = con.execute(
            f"SELECT id, target_path, start_time, end_time, received_bytes, total_bytes, state, "
            f"danger_type, opened, last_access_time, referrer, tab_url, {quer('site_url')}, "
            f"{quer('mime_type')}, {quer('hash')}, {quer('interrupt_reason')} "
            f"FROM downloads ORDER BY start_time").fetchall()
        cadeias = {}
        for did, url in con.execute("SELECT id, url FROM downloads_url_chains ORDER BY id, chain_index"):
            cadeias.setdefault(did, []).append(url)
        con.close()

    def curto(u):
        u = u or ""
        return u if args.url_completa or len(u) <= 100 else u[:97] + "..."

    registros = []
    for (did, alvo, ini, fim, rec, tot, est, per, aberto, acesso, ref, tab, site, mime,
         hsh, motivo) in linhas:
        cadeia = cadeias.get(did, [])
        win = PureWindowsPath(alvo or "")
        reg = {
            "id": did, "arquivo": win.name, "pasta": str(win.parent), "url_download": cadeia[0] if cadeia else "",
            "url_final": cadeia[-1] if len(cadeia) > 1 else "", "saltos": len(cadeia),
            "pagina_origem": tab or "", "referrer": ref or "",
            f"inicio ({nome_fuso})": data(ini, fuso), f"fim ({nome_fuso})": data(fim, fuso),
            "duracao_s": round((fim - ini) / 1e6, 1) if ini and fim and fim >= ini else "",
            "bytes_recebidos": rec, "bytes_total": tot, "estado": ESTADO.get(est, f"estado {est}"),
            "perigo": PERIGO.get(per, f"tipo {per}"), "aberto": "sim" if aberto else "nao",
            f"ultimo_acesso ({nome_fuso})": data(acesso, fuso), "mime": mime or "",
            "hash": hsh.hex() if isinstance(hsh, (bytes, bytearray)) and hsh else "",
            "interrupcao": motivo or "",
        }
        registros.append(reg)

    if args.filtro:
        chave = args.filtro.lower()
        registros = [r for r in registros
                     if chave in r["arquivo"].lower() or chave in r["url_download"].lower()
                     or chave in r["pagina_origem"].lower()]

    print(f"Arquivo: {args.history} | horarios em {nome_fuso}")
    print(f"Downloads: {len(registros)}")
    if not registros:
        return
    ini_k, fim_k = f"inicio ({nome_fuso})", f"fim ({nome_fuso})"
    print(f"primeiro download: {registros[0][ini_k]}  {registros[0]['arquivo']}")
    print(f"ultimo download:   {registros[-1][ini_k]}  {registros[-1]['arquivo']}\n")
    for n, r in enumerate(registros, 1):
        print(f"{n:2d}. {r['arquivo']}   [{r['estado']}, {r['bytes_total']} bytes, perigo: {r['perigo']}]")
        print(f"      salvo em:   {r['pasta']}")
        print(f"      baixado de: {curto(r['url_download'])}")
        if r["url_final"]:
            print(f"      URL final:  {curto(r['url_final'])}   ({r['saltos']} URLs na cadeia)")
        print(f"      pagina:     {curto(r['pagina_origem'])}")
        print(f"      inicio: {r[ini_k]} | fim: {r[fim_k]} | duracao: {r['duracao_s']}s | aberto: {r['aberto']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(registros[0].keys()))
            w.writeheader()
            w.writerows(registros)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
