#!/usr/bin/env python3
"""mapa_sqlite.py - mapa rapido de um banco SQLite desconhecido.

Para cada tabela mostra: numero de linhas, colunas, tipo declarado, quantas
linhas tem valor, um exemplo, e, principalmente, QUAIS COLUNAS PARECEM DATAS,
em qual formato (Unix s/ms/us, Chrome/WebKit, FILETIME, Cocoa) e o intervalo
(menor -> maior data) ja convertido.

Serve para o comeco de uma analise: "o que tem neste banco e onde estao os
horarios?" (WhatsApp, apps de mensagem, bancos de apps do Android/iOS...).

Uso:
    python mapa_sqlite.py banco.db
    python mapa_sqlite.py banco.db --fuso -3
    python mapa_sqlite.py banco.db --tabela messages --amostra 5
    python mapa_sqlite.py banco.db --so-datas

O banco e COPIADO (com -wal e -shm, se existirem) para uma pasta temporaria; o
original nao e tocado. Detecta datas pela ordem de grandeza do numero, entao e
uma PISTA, nao uma prova: confirme olhando o nome da coluna e alguns valores.
"""
import argparse
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
COCOA = 978307200
S1601 = 11644473600

# nome: (descricao curta, valor -> segundos Unix)
FORMATOS = {
    "cocoa-s":  ("Cocoa s desde 2001 (iOS)",       lambda v: v + COCOA),
    "unix-s":   ("Unix s",                          lambda v: v),
    "unix-ms":  ("Unix ms (Android)",               lambda v: v / 1e3),
    "unix-us":  ("Unix us (Firefox)",               lambda v: v / 1e6),
    "webkit":   ("WebKit us desde 1601 (Chrome)",   lambda v: v / 1e6 - S1601),
    "filetime": ("FILETIME 100ns desde 1601 (Windows)", lambda v: v / 1e7 - S1601),
    "cocoa-ns": ("Cocoa ns desde 2001 (iOS/APFS)",  lambda v: v / 1e9 + COCOA),
}
FAIXAS = [("webkit", 1.16e16, 2.0e16), ("filetime", 1.16e17, 2.0e17), ("cocoa-ns", 2.0e17, 1.0e19),
          ("unix-us", 1.0e14, 1.16e16), ("unix-ms", 1.0e11, 1.0e14), ("unix-s", 1.0e9, 1.0e11),
          ("cocoa-s", 1.0e8, 1.0e9)]
ANO_MIN, ANO_MAX = 2005, datetime.now().year + 1   # fora disso, nao e tratado como data (evita IDs)
PISTAS = ("date", "time", "stamp", "created", "modified", "updated", "expire", "last", "_at", "visit", "sent", "received")


def ler_fuso(texto):
    t = texto.strip().lower().replace("utc", "")
    if t in ("", "z"):
        return UTC, "UTC"
    horas = float(t)
    return timezone(timedelta(hours=horas)), f"UTC{horas:+g}"


def formato_de(v):
    a = abs(v)
    for nome, lo, hi in FAIXAS:
        if lo <= a < hi:
            return nome
    return None


def converter(v, nome, fuso):
    try:
        dt = datetime.fromtimestamp(FORMATOS[nome][1](v), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return dt.astimezone(fuso) if ANO_MIN <= dt.year <= ANO_MAX else None


def aspas(nome):
    return '"' + nome.replace('"', '""') + '"'


def copiar_banco(caminho, pasta_tmp):
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def detectar_data(con, tabela, coluna, fuso):
    """Devolve (formato, menor, maior, fracao) se a coluna parece conter datas; senao None."""
    amostra = [r[0] for r in con.execute(
        f"SELECT {aspas(coluna)} FROM {aspas(tabela)} WHERE typeof({aspas(coluna)}) IN ('integer','real') "
        f"LIMIT 500")]
    if len(amostra) < 1:
        return None
    contagem = {}
    for v in amostra:
        f = formato_de(v)
        if f and converter(v, f, fuso):
            contagem[f] = contagem.get(f, 0) + 1
    if not contagem:
        return None
    formato, n = max(contagem.items(), key=lambda kv: kv[1])
    fracao = n / len(amostra)
    if fracao < 0.9:
        return None
    # intervalo na coluna toda, so com valores dentro da faixa do formato escolhido
    _, lo, hi = next(f for f in FAIXAS if f[0] == formato)
    menor, maior = con.execute(
        f"SELECT MIN({aspas(coluna)}), MAX({aspas(coluna)}) FROM {aspas(tabela)} "
        f"WHERE typeof({aspas(coluna)}) IN ('integer','real') AND ABS({aspas(coluna)}) >= ? AND ABS({aspas(coluna)}) < ?",
        (lo, hi)).fetchone()
    return formato, converter(menor, formato, fuso), converter(maior, formato, fuso), fracao


def data_iso_texto(valor):
    return isinstance(valor, str) and re.match(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}", valor)


def main():
    ap = argparse.ArgumentParser(description="Mapa de um banco SQLite")
    ap.add_argument("banco", help="arquivo .db / .sqlite")
    ap.add_argument("--fuso", default="utc", help="'utc' (padrao) ou horas (-3)")
    ap.add_argument("--tabela", help="mostra so esta tabela (nome exato)")
    ap.add_argument("--amostra", type=int, default=0, help="com --tabela: mostra N linhas de exemplo")
    ap.add_argument("--so-datas", action="store_true", help="lista so as colunas que parecem datas")
    args = ap.parse_args()
    fuso, nome_fuso = ler_fuso(args.fuso)

    origem = Path(args.banco)
    for sufixo in ("-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            print(f"[ok] encontrado {arq.name} ({arq.stat().st_size} bytes): sera copiado junto.")
    with tempfile.TemporaryDirectory() as tmp:
        con = sqlite3.connect(copiar_banco(args.banco, tmp))
        try:
            tabelas = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        except sqlite3.DatabaseError as e:
            raise SystemExit(f"Nao parece um banco SQLite valido ({e}).")
        if args.tabela:
            if args.tabela not in tabelas:
                raise SystemExit(f"Tabela '{args.tabela}' nao existe. Tabelas: {', '.join(tabelas)}")
            tabelas = [args.tabela]

        print(f"Banco: {args.banco} | horarios em {nome_fuso}\n")
        resumo = []
        for t in tabelas:
            try:
                n = con.execute(f"SELECT COUNT(*) FROM {aspas(t)}").fetchone()[0]
            except sqlite3.DatabaseError as e:
                print(f"== {t}: erro ao ler ({e})")
                continue
            resumo.append((t, n))
            cols = con.execute(f"PRAGMA table_info({aspas(t)})").fetchall()
            blocos, achou_data = [], False
            for _, c, tipo, _, _, pk in cols:
                nn = con.execute(f"SELECT COUNT({aspas(c)}) FROM {aspas(t)}").fetchone()[0]
                exemplo = con.execute(
                    f"SELECT {aspas(c)} FROM {aspas(t)} WHERE {aspas(c)} IS NOT NULL LIMIT 1").fetchone()
                ex = repr(exemplo[0])[:40] if exemplo else ""
                info = detectar_data(con, t, c, fuso) if n else None
                nota = ""
                if info:
                    achou_data = True
                    f, menor, maior, fr = info
                    nota = (f"  <-- DATA {f}: {menor:%Y-%m-%d %H:%M:%S} -> {maior:%Y-%m-%d %H:%M:%S}"
                            f" ({fr:.0%} da amostra)")
                    if f in ("cocoa-s", "unix-s") and not any(p in c.lower() for p in PISTAS):
                        nota += "  [9-10 digitos sem nome de data: pode ser ID/contador]"
                elif exemplo and data_iso_texto(exemplo[0]):
                    achou_data = True
                    nota = "  <-- DATA em texto (ISO)"
                elif any(p in c.lower() for p in PISTAS) and nn:
                    nota = "  (nome sugere data/hora; confira o valor)"
                if args.so_datas and not nota.startswith("  <-- DATA"):
                    continue
                blocos.append(f"   {c:28s} {tipo or '-':10s} nao-nulos={nn:<7d} ex={ex}{nota}")
            if args.so_datas and not achou_data:
                continue
            print(f"== {t}  (linhas: {n})" + ("  [vazia]" if n == 0 else ""))
            print("\n".join(blocos))
            if args.amostra and args.tabela:
                print(f"\n   Primeiras {args.amostra} linhas:")
                cur = con.execute(f"SELECT * FROM {aspas(t)} LIMIT {int(args.amostra)}")
                nomes = [d[0] for d in cur.description]
                for linha in cur:
                    print("   - " + " | ".join(f"{k}={repr(v)[:30]}" for k, v in zip(nomes, linha)))
            print()
        con.close()

    if not args.tabela and resumo:
        print("Resumo por tamanho:", ", ".join(f"{t}={n}" for t, n in sorted(resumo, key=lambda x: -x[1])[:8]))


if __name__ == "__main__":
    main()
