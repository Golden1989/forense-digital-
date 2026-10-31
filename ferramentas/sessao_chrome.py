#!/usr/bin/env python3
"""sessao_chrome.py - mostra as abas e a pagina atual de um arquivo de sessao do Chrome.

Uso:
    python sessao_chrome.py CAMINHO\\Session_13422390936860763

O arquivo e lido em modo somente leitura; nada e gravado.

Formato SNSS (resumo): cabecalho 'SNSS' + versao (4 bytes), depois uma sequencia
de comandos. Cada comando: tamanho (2 bytes) + tipo (1 byte) + conteudo.
    tipo 6 = pagina navegada (aba, posicao, URL, titulo)
    tipo 7 = pagina selecionada em uma aba
    tipo 8 = aba selecionada na janela
O numero no nome do arquivo e a data de CRIACAO do arquivo de sessao
(microssegundos desde 1601, em UTC); nao e a hora do fechamento.
"""
import re
import struct
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

EPOCA = datetime(1601, 1, 1, tzinfo=timezone.utc)


def ler_texto(dados, pos):
    """Le um texto ASCII/UTF-8 com tamanho de 4 bytes na frente (alinhado a 4)."""
    n = struct.unpack("<i", dados[pos:pos + 4])[0]
    texto = dados[pos + 4:pos + 4 + n].decode("utf-8", "replace")
    return texto, pos + 4 + ((n + 3) & ~3)


def ler_texto16(dados, pos):
    """Le um texto UTF-16 com quantidade de caracteres de 4 bytes na frente."""
    n = struct.unpack("<i", dados[pos:pos + 4])[0]
    texto = dados[pos + 4:pos + 4 + n * 2].decode("utf-16le", "replace")
    return texto


def ler_comandos(dados):
    """Devolve a lista de (tipo, conteudo) de todos os comandos do arquivo."""
    pos, comandos = 8, []
    while pos + 2 <= len(dados):
        tam = struct.unpack("<H", dados[pos:pos + 2])[0]
        pos += 2
        if tam == 0 or pos + tam > len(dados):
            break
        comandos.append((dados[pos], dados[pos + 1:pos + tam]))
        pos += tam
    return comandos


def main():
    if len(sys.argv) != 2:
        sys.exit("Uso: python sessao_chrome.py CAMINHO_DO_ARQUIVO_Session_")
    caminho = Path(sys.argv[1])
    dados = caminho.read_bytes()
    if dados[:4] != b"SNSS":
        sys.exit("Este arquivo nao parece ser uma sessao do Chrome (falta o cabecalho SNSS).")

    achou = re.search(r"(\d{17})", caminho.name)
    if achou:
        criado = EPOCA + timedelta(microseconds=int(achou.group(1)))
        print(f"Arquivo de sessao criado em (UTC): {criado:%Y-%m-%d %H:%M:%S}")

    paginas, selecionada, aba_da_janela = {}, {}, None
    for tipo, conteudo in ler_comandos(dados):
        if tipo == 6:                                   # pagina navegada
            aba, indice = struct.unpack("<ii", conteudo[4:12])
            url, pos = ler_texto(conteudo, 12)
            paginas[(aba, indice)] = (url, ler_texto16(conteudo, pos))
        elif tipo == 7:                                 # pagina selecionada na aba
            aba, indice = struct.unpack("<ii", conteudo[:8])
            selecionada[aba] = indice
        elif tipo == 8:                                 # aba selecionada na janela
            aba_da_janela = struct.unpack("<ii", conteudo[:8])

    print(f"\nAbas encontradas: {len({a for a, _ in paginas})}")
    for aba in sorted({a for a, _ in paginas}):
        print(f"\nAba {aba}:")
        for (a, i), (url, titulo) in sorted(paginas.items()):
            if a == aba:
                marca = "   <-- PAGINA ATUAL" if selecionada.get(aba) == i else ""
                print(f"  [{i}] {titulo[:50]} | {url[:90]}{marca}")
    if aba_da_janela:
        print(f"\nAba selecionada na janela (janela, posicao): {aba_da_janela}")


if __name__ == "__main__":
    main()
