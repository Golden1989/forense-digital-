#!/usr/bin/env python3
"""convert_date.py - converte um numero de timestamp em data legivel.

Descobre o formato pela ordem de grandeza (quantidade de digitos) e mostra
tambem as OUTRAS leituras plausiveis, porque alguns formatos se confundem.

Uso interativo (pergunta o valor e o fuso):
    python convert_date.py

Uso direto:
    python convert_date.py 1762202574476
    python convert_date.py 1762202574476 --fuso -3
    python convert_date.py 134159021410000000 --fuso utc
    python convert_date.py 0x198d35fa587 --fuso -3        (hexadecimal)
    python convert_date.py 134159021410000000 --formato filetime

Fuso: 'utc', horas (-3, +2, -3:30) ou nome (America/Sao_Paulo; no Windows
nomes exigem 'pip install tzdata').

Formatos (nome para --formato):
    cocoa-s    segundos desde 2001-01-01          (iOS, 9 digitos)
    unix-s     segundos desde 1970-01-01          (10 digitos)
    unix-ms    milissegundos desde 1970           (Android, 13 digitos)
    unix-us    microssegundos desde 1970          (Firefox, 16 digitos)
    webkit     microssegundos desde 1601          (Chrome/Edge, 17 digitos)
    filetime   intervalos de 100 ns desde 1601    (Windows, 18 digitos)
    cocoa-ns   nanossegundos desde 2001           (iOS/APFS, 18 digitos)
"""
import argparse
import re
from datetime import datetime, timedelta, timezone

COCOA_PARA_UNIX = 978307200          # segundos entre 1970-01-01 e 2001-01-01
SECULOS_1601 = 11644473600           # segundos entre 1601-01-01 e 1970-01-01

# nome: (descricao, funcao valor -> segundos Unix)
FORMATOS = {
    "cocoa-s":  ("iOS Cocoa (segundos desde 2001)",            lambda v: v + COCOA_PARA_UNIX),
    "unix-s":   ("Unix (segundos desde 1970)",                 lambda v: v),
    "unix-ms":  ("Android/Java (milissegundos desde 1970)",    lambda v: v / 1e3),
    "unix-us":  ("Firefox (microssegundos desde 1970)",        lambda v: v / 1e6),
    "webkit":   ("Chrome/Edge (microssegundos desde 1601)",    lambda v: v / 1e6 - SECULOS_1601),
    "filetime": ("Windows FILETIME (100 ns desde 1601)",       lambda v: v / 1e7 - SECULOS_1601),
    "cocoa-ns": ("iOS/APFS (nanossegundos desde 2001)",        lambda v: v / 1e9 + COCOA_PARA_UNIX),
}

# Faixas de valor onde cada formato e a leitura "natural" (datas de 1970 em diante).
FAIXAS = [
    ("webkit",   1.16e16, 2.0e16),
    ("filetime", 1.16e17, 2.0e17),
    ("cocoa-ns", 2.0e17,  1.0e19),
    ("unix-us",  1.0e14,  1.16e16),
    ("unix-ms",  1.0e11,  1.0e14),
    ("unix-s",   1.0e9,   1.0e11),
]


def ler_fuso(texto):
    """'utc', '-3', '+2', '-3:30' ou nome de fuso -> objeto tzinfo."""
    t = (texto or "").strip()
    if not t or t.lower() in ("utc", "z"):
        return timezone.utc
    m = re.fullmatch(r"([+-]?)(\d{1,2})(?::?(\d{2}))?", t)
    if m:
        sinal = -1 if m.group(1) == "-" else 1
        return timezone(sinal * timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0)))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(t)
    except Exception:
        print(f"Aviso: fuso '{t}' nao reconhecido (no Windows: pip install tzdata). Usando UTC.")
        return timezone.utc


def ler_numero(texto):
    """Aceita decimal, 0x... e hexadecimal sem prefixo com letras (ex.: 198d35fa587)."""
    t = texto.strip().replace("_", "").replace(" ", "")
    if t.lower().startswith("0x"):
        return int(t, 16)
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t)
    return int(t, 16)            # tem letras a-f: trata como hexadecimal


def formato_natural(v):
    """Formato mais provavel pelo tamanho do numero."""
    a = abs(v)
    for nome, lo, hi in FAIXAS:
        if lo <= a < hi:
            return nome
    return "cocoa-s"


def converter(v, nome, fuso):
    """Aplica o formato 'nome' e devolve datetime no fuso, ou None se for impossivel."""
    try:
        return datetime.fromtimestamp(FORMATOS[nome][1](v), tz=timezone.utc).astimezone(fuso)
    except (OverflowError, OSError, ValueError):
        return None


def mostrar(v, fuso, formato=None):
    escolhido = formato or formato_natural(v)
    dt = converter(v, escolhido, fuso)
    print("-" * 66)
    if dt is None:
        print(f"Formato {escolhido}: valor fora do intervalo de datas.")
    else:
        print(f"Formato: {FORMATOS[escolhido][0]}" + ("  (escolhido por voce)" if formato else ""))
        print(f"Data:    {dt:%Y-%m-%d %H:%M:%S.%f} {dt.tzname()} (UTC{dt:%z})")
    # outras leituras entre 2010 e 2035 (datas de aparelhos modernos): mostram ambiguidade real
    outras = []
    for nome in FORMATOS:
        if nome == escolhido:
            continue
        d = converter(v, nome, fuso)
        if d and 2010 <= d.year <= 2035:
            outras.append((nome, d))
    if outras:
        print("Outras leituras plausiveis (use --formato se o contexto indicar uma delas):")
        for nome, d in outras:
            print(f"  {nome:9s} {d:%Y-%m-%d %H:%M:%S}  {FORMATOS[nome][0]}")
    print("-" * 66)


def main():
    ap = argparse.ArgumentParser(description="Converte timestamps em datas legiveis")
    ap.add_argument("valor", nargs="?", help="numero (decimal, 0x... ou hex); sem ele, modo interativo")
    ap.add_argument("--fuso", help="'utc' (padrao), horas (-3) ou nome (America/Sao_Paulo)")
    ap.add_argument("--formato", choices=sorted(FORMATOS), help="forca um formato em vez de adivinhar")
    args = ap.parse_args()

    if args.valor is None:
        print("=" * 66)
        print(" Conversor de timestamps (Android, iOS, navegadores, Windows)")
        print("=" * 66)
        texto = input("Digite o valor do timestamp: ")
        fuso_txt = input("Fuso (-3, utc, America/Sao_Paulo; Enter = UTC): ")
    else:
        texto, fuso_txt = args.valor, args.fuso

    try:
        v = ler_numero(texto)
    except ValueError:
        raise SystemExit("Erro: o valor precisa ser numerico (decimal ou hexadecimal).")
    mostrar(v, ler_fuso(fuso_txt), args.formato)


if __name__ == "__main__":
    main()
