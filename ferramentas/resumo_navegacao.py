#!/usr/bin/env python3
"""resumo_navegacao.py - resume o arquivo History do Chrome/Edge/Brave (Chromium).

Junta as tabelas urls, visits e keyword_search_terms e responde, de uma vez, as
perguntas mais comuns de quesito:
  - primeira e ultima visita (geral, por dominio e por site escolhido);
  - visita intermediaria (a do meio da lista, ordenada por horario);
  - dominios e URLs mais visitados;
  - paginas de PASSAGEM (redirecionamentos: login unico, encurtadores, etc.);
  - termos pesquisados;
  - visitas por dia.

Uso:
    python resumo_navegacao.py History
    python resumo_navegacao.py History --fuso -3
    python resumo_navegacao.py History --site gov.br
    python resumo_navegacao.py History --por-dia
    python resumo_navegacao.py History --dia 2025-11-03
    python resumo_navegacao.py History --csv dominios.csv

O banco e COPIADO (com -wal e -shm) para uma pasta temporaria; o original
nao e tocado. Datas do Chrome: microssegundos desde 1601, UTC.

Contagens: aqui "visitas" = linhas da tabela visits (cada acesso). A coluna
visit_count da tabela urls pode diferir (ex.: apos limpeza parcial do historico).
"""
import argparse
import csv
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

UTC = timezone.utc
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)

# transition = tipo (8 bits de baixo) + qualificadores (bits de cima)
TIPOS = {0: "link", 1: "digitada", 2: "favorito automatico", 3: "subquadro automatico",
         4: "subquadro manual", 5: "gerada (omnibox)", 6: "pagina inicial",
         7: "formulario", 8: "recarregar", 9: "palavra-chave", 10: "palavra-chave gerada"}
INICIO_CADEIA = 0x10000000
FIM_CADEIA = 0x20000000
REDIR_CLIENTE = 0x40000000
REDIR_SERVIDOR = 0x80000000


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


def dominio(url):
    return urlparse(url).netloc.lower() or url.split(":")[0]


def curto(url, completa):
    return url if completa else (url[:95] + "..." if len(url) > 98 else url)


def papel_na_cadeia(transition):
    """Papel da visita numa cadeia de redirecionamento, ou '' se nao faz parte de uma."""
    inicio = bool(transition & INICIO_CADEIA)
    fim = bool(transition & FIM_CADEIA)
    redir = bool(transition & (REDIR_CLIENTE | REDIR_SERVIDOR))
    if inicio and not fim:
        return "inicio"
    if fim and not inicio:
        return "fim"
    if redir:
        return "passagem"
    return ""


def tipo_redir(transition):
    if transition & REDIR_SERVIDOR:
        return "servidor"
    if transition & REDIR_CLIENTE:
        return "cliente"
    return ""


def main():
    ap = argparse.ArgumentParser(description="Resumo do History do Chrome")
    ap.add_argument("history", help="arquivo History")
    ap.add_argument("--fuso", default="utc", help="'utc' (padrao) ou horas (-3)")
    ap.add_argument("--site", help="detalha so URLs que contenham este texto (ex.: gov.br)")
    ap.add_argument("--dia", help="considera so este dia (AAAA-MM-DD, no fuso escolhido)")
    ap.add_argument("--top", type=int, default=10, help="tamanho dos rankings (padrao 10)")
    ap.add_argument("--por-dia", action="store_true", help="mostra a contagem de visitas por dia")
    ap.add_argument("--url-completa", action="store_true", help="nao corta as URLs")
    ap.add_argument("--csv", help="salva a tabela por dominio neste CSV")
    args = ap.parse_args()
    fuso, nome_fuso = ler_fuso(args.fuso)

    with tempfile.TemporaryDirectory() as tmp:
        con = sqlite3.connect(copiar_banco(args.history, tmp))
        visitas = con.execute(
            "SELECT v.id, v.url, v.visit_time, v.from_visit, v.transition, u.url, u.title "
            "FROM visits v JOIN urls u ON u.id = v.url ORDER BY v.visit_time").fetchall()
        buscas = con.execute(
            "SELECT k.term, u.url, u.last_visit_time FROM keyword_search_terms k "
            "JOIN urls u ON u.id = k.url_id").fetchall()
        con.close()

    # (id, url_id, tempo, de, transicao, url, titulo) -> filtros
    def dia_ok(v):
        return not args.dia or data(v[2], fuso).startswith(args.dia)
    visitas = [v for v in visitas if dia_ok(v)]
    if args.site:
        chave = args.site.lower()
        visitas_site = [v for v in visitas if chave in v[5].lower()]
    else:
        visitas_site = visitas

    print(f"Arquivo: {args.history} | horarios em {nome_fuso}"
          + (f" | dia {args.dia}" if args.dia else ""))
    if not visitas:
        print("Nenhuma visita encontrada.")
        return
    print(f"\n== VISAO GERAL ==\nvisitas: {len(visitas)} | URLs distintas: {len({v[5] for v in visitas})}"
          f" | dominios: {len({dominio(v[5]) for v in visitas})}")
    print(f"primeira visita: {data(visitas[0][2], fuso)}  {curto(visitas[0][5], args.url_completa)}")
    print(f"ultima visita:   {data(visitas[-1][2], fuso)}  {curto(visitas[-1][5], args.url_completa)}")

    # ---- por dominio
    por_dom = defaultdict(list)
    for v in visitas:
        por_dom[dominio(v[5])].append(v)
    ranking = sorted(por_dom.items(), key=lambda kv: len(kv[1]), reverse=True)
    print(f"\n== DOMINIOS MAIS VISITADOS (top {args.top}) ==")
    for pos, (dom, lista) in enumerate(ranking[:args.top], 1):
        meio = lista[len(lista) // 2]
        print(f"{pos:2d}. {dom}  visitas={len(lista)}")
        print(f"      primeira: {data(lista[0][2], fuso)} | intermediaria: {data(meio[2], fuso)}"
              f" | ultima: {data(lista[-1][2], fuso)}")

    # ---- URLs mais visitadas
    cont = Counter(v[5] for v in visitas)
    print(f"\n== URLs MAIS VISITADAS (top {args.top}) ==")
    for pos, (url, n) in enumerate(cont.most_common(args.top), 1):
        lista = [v for v in visitas if v[5] == url]
        print(f"{pos:2d}. visitas={n}  {curto(url, args.url_completa)}")
        print(f"      primeira: {data(lista[0][2], fuso)} | ultima: {data(lista[-1][2], fuso)}")

    # ---- paginas de passagem (redirecionamentos)
    papeis = defaultdict(Counter)
    for v in visitas:
        p = papel_na_cadeia(v[4])
        if p:
            papeis[v[5]][p] += 1
    passagem = sorted(papeis.items(), key=lambda kv: sum(kv[1].values()), reverse=True)
    print(f"\n== PAGINAS DE PASSAGEM (redirecionamentos) - top {args.top} ==")
    if not passagem:
        print("nenhuma visita marcada como redirecionamento.")
    for url, c in passagem[:args.top]:
        det = ", ".join(f"{k}={n}" for k, n in c.items())
        print(f"  {sum(c.values()):3d}x  {curto(url, args.url_completa)}\n        papel na cadeia: {det}")

    # ---- buscas
    print(f"\n== TERMOS PESQUISADOS ({len(buscas)}) ==")
    for termo, url, ultima in sorted(buscas, key=lambda b: b[2])[:args.top * 3]:
        print(f"  {data(ultima, fuso)}  {termo}  [{dominio(url)}]")

    # ---- por dia
    if args.por_dia:
        dias = Counter(data(v[2], fuso)[:10] for v in visitas)
        print("\n== VISITAS POR DIA ==")
        for d in sorted(dias):
            print(f"  {d}  {dias[d]:4d}  {'#' * min(60, dias[d] // max(1, max(dias.values()) // 60))}")

    # ---- site escolhido
    if args.site:
        print(f"\n== SITE '{args.site}' ==")
        if not visitas_site:
            print("nenhuma visita com esse texto na URL.")
        else:
            n = len(visitas_site)
            meio = visitas_site[n // 2]
            print(f"visitas: {n} | URLs distintas: {len({v[5] for v in visitas_site})}")
            print(f"primeira:       {data(visitas_site[0][2], fuso)}  {curto(visitas_site[0][5], args.url_completa)}")
            print(f"intermediaria:  {data(meio[2], fuso)}  {curto(meio[5], args.url_completa)}"
                  f"   (visita n.{n // 2 + 1} de {n}, por horario)")
            print(f"ultima:         {data(visitas_site[-1][2], fuso)}  {curto(visitas_site[-1][5], args.url_completa)}")
            tipos = Counter(TIPOS.get(v[4] & 0xFF, f"tipo {v[4] & 0xFF}") for v in visitas_site)
            print("tipos de navegacao: " + ", ".join(f"{k}={c}" for k, c in tipos.most_common()))
            redirs = Counter(tipo_redir(v[4]) for v in visitas_site if tipo_redir(v[4]))
            if redirs:
                print("redirecionamentos: " + ", ".join(f"{k}={c}" for k, c in redirs.items()))
            print("URLs deste site, da mais visitada:")
            for url, c in Counter(v[5] for v in visitas_site).most_common(args.top):
                print(f"  {c:3d}x  {curto(url, args.url_completa)}")

    # ---- csv por dominio
    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["dominio", "visitas", f"primeira ({nome_fuso})",
                        f"intermediaria ({nome_fuso})", f"ultima ({nome_fuso})"])
            for dom, lista in ranking:
                w.writerow([dom, len(lista), data(lista[0][2], fuso),
                            data(lista[len(lista) // 2][2], fuso), data(lista[-1][2], fuso)])
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
