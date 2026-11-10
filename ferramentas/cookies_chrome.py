#!/usr/bin/env python3
"""cookies_chrome.py - lista os cookies de um banco "Cookies" (Chrome, WebView, Edge, Brave).

Mostra, para cada cookie: dominio, nome, caminho, criado, ultimo acesso, ultima
atualizacao, expira em, e as marcas Secure / HttpOnly / Persistente / SameSite.

O VALOR do cookie NAO e exibido nem gravado: cookies de sessao funcionam como
senha (quem tem o valor pode se passar pelo usuario). So se informa se o valor
existe e se esta criptografado. Para o laudo bastam dominio, nome e datas.

Uso:
    python cookies_chrome.py Cookies
    python cookies_chrome.py Cookies --fuso -3
    python cookies_chrome.py Cookies --filtro microsoft
    python cookies_chrome.py Cookies --por-dominio
    python cookies_chrome.py Cookies --csv cookies.csv

O banco e COPIADO (com -wal, -shm e -journal) para uma pasta temporaria; o
original nao e tocado. Datas: microssegundos desde 1601 (WebKit), UTC.

Onde ficam:
    Chrome (Android): .../com.android.chrome/app_chrome/Default/Cookies
    WebView de um app: .../<app>/app_webview/Default/Cookies  (ou app_webview_auth)
    Chrome (Windows): ...\\User Data\\Default\\Network\\Cookies
Cookie ausente nao prova que o site nao foi usado; o app pode nao usar cookies.
"""
import argparse
import csv
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)
SAMESITE = {-1: "nao definido", 0: "None", 1: "Lax", 2: "Strict"}


def ler_fuso(texto):
    t = texto.strip().lower().replace("utc", "")
    if t in ("", "z"):
        return UTC, "UTC"
    horas = float(t)
    return timezone(timedelta(hours=horas)), f"UTC{horas:+g}"


def data(us, fuso):
    """Microssegundos desde 1601 -> texto; 0 vira vazio (cookie de sessao nao expira)."""
    if not us:
        return ""
    try:
        return (EPOCA_WEBKIT + timedelta(microseconds=us)).astimezone(fuso).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, ValueError):
        return "fora do intervalo"


def copiar_banco(caminho, pasta_tmp):
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm", "-journal"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def main():
    ap = argparse.ArgumentParser(description="Cookies do Chrome/WebView (sem mostrar valores)")
    ap.add_argument("cookies", help="arquivo Cookies")
    ap.add_argument("--fuso", default="utc", help="'utc' (padrao) ou horas (-3)")
    ap.add_argument("--filtro", help="so cookies cujo dominio ou nome contenham este texto")
    ap.add_argument("--por-dominio", action="store_true", help="resume por dominio (quantidade, primeiro e ultimo)")
    ap.add_argument("--csv", help="salva a tabela neste CSV (sem valores)")
    args = ap.parse_args()
    fuso, nome_fuso = ler_fuso(args.fuso)

    with tempfile.TemporaryDirectory() as tmp:
        con = sqlite3.connect(copiar_banco(args.cookies, tmp))
        colunas = {r[1] for r in con.execute("PRAGMA table_info(cookies)")}
        if not colunas:
            raise SystemExit("Tabela 'cookies' nao encontrada: nao parece um banco Cookies do Chromium.")
        q = lambda c, padrao="NULL": c if c in colunas else f"{padrao} AS {c}"
        linhas = con.execute(
            f"SELECT creation_utc, host_key, name, path, expires_utc, {q('last_access_utc')}, "
            f"{q('last_update_utc')}, is_secure, is_httponly, {q('is_persistent')}, {q('samesite', '-1')}, "
            f"LENGTH(value), LENGTH(encrypted_value) FROM cookies ORDER BY creation_utc").fetchall()
        con.close()

    registros = []
    for cri, host, nome, caminho, exp, acesso, atual, sec, http, pers, same, lv, le in linhas:
        valor = "criptografado" if le else ("presente (nao criptografado)" if lv else "vazio")
        registros.append({
            "dominio": host, "nome": nome, "caminho": caminho,
            f"criado ({nome_fuso})": data(cri, fuso), f"ultimo_acesso ({nome_fuso})": data(acesso, fuso),
            f"ultima_atualizacao ({nome_fuso})": data(atual, fuso),
            f"expira ({nome_fuso})": data(exp, fuso) or "sessao",
            "secure": "sim" if sec else "nao", "httponly": "sim" if http else "nao",
            "persistente": "sim" if pers else "nao", "samesite": SAMESITE.get(same, str(same)),
            "valor": valor,
        })
    if args.filtro:
        chave = args.filtro.lower()
        registros = [r for r in registros if chave in r["dominio"].lower() or chave in r["nome"].lower()]

    cri_k, ace_k = f"criado ({nome_fuso})", f"ultimo_acesso ({nome_fuso})"
    print(f"Arquivo: {args.cookies} | horarios em {nome_fuso}")
    print(f"Cookies: {len(registros)} (valores nao exibidos)")
    if not registros:
        return
    criados = [r[cri_k] for r in registros if r[cri_k]]
    if criados:
        print(f"primeiro criado: {min(criados)} | ultimo criado: {max(criados)}")
    print()

    if args.por_dominio:
        grupos = defaultdict(list)
        for r in registros:
            grupos[r["dominio"]].append(r)
        for dom, lista in sorted(grupos.items(), key=lambda kv: min(x[cri_k] for x in kv[1])):
            cs = [x[cri_k] for x in lista if x[cri_k]]
            ac = [x[ace_k] for x in lista if x[ace_k]]
            print(f"{dom}  cookies={len(lista)}  criados {min(cs) if cs else '-'} a {max(cs) if cs else '-'}"
                  f"  ultimo acesso {max(ac) if ac else '-'}")
            print("    nomes: " + ", ".join(sorted({x['nome'] for x in lista}))[:150])
    else:
        for r in registros:
            print(f"{r[cri_k]}  {r['dominio']}  {r['nome']}")
            print(f"    acesso: {r[ace_k] or '-'} | expira: {r[f'expira ({nome_fuso})']} | "
                  f"secure={r['secure']} httponly={r['httponly']} persistente={r['persistente']} "
                  f"samesite={r['samesite']} | valor: {r['valor']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(registros[0].keys()))
            w.writeheader()
            w.writerows(registros)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
