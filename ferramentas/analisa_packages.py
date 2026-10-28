#!/usr/bin/env python3
"""analisa_packages.py - resume o packages.xml de uma imagem Android.

Uso:
    python analisa_packages.py CAMINHO\\packages.xml
    python analisa_packages.py CAMINHO\\packages.xml --so-usuario
    python analisa_packages.py CAMINHO\\packages.xml --csv saida.csv

O script apenas LE o arquivo. Nunca grava nada na pasta da evidencia.
Datas: o packages.xml guarda 'it' (primeira instalacao) e 'ut' (ultima
atualizacao) em milissegundos Unix escritos em hexadecimal.

PRIMEIRO e ULTIMO: sao calculados so entre os apps de USUARIO (/data/app).
Os apps de sistema vem do firmware e quase todos tem a mesma data, entao
"o primeiro instalado" entre eles nao diz nada sobre o dono do aparelho.
"""
import argparse
import csv
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FUSO = timezone(timedelta(hours=-3))  # UTC-3 (Brasilia)

# Permissoes que costumam interessar a uma pericia (nome curto, sem o prefixo).
SENSIVEIS = {
    "READ_SMS", "SEND_SMS", "RECEIVE_SMS", "READ_CONTACTS", "READ_CALL_LOG",
    "RECORD_AUDIO", "CAMERA", "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION",
    "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE", "SYSTEM_ALERT_WINDOW",
    "BIND_ACCESSIBILITY_SERVICE", "REQUEST_INSTALL_PACKAGES",
}

# Colunas do CSV, na ordem em que aparecem.
CAMPOS = [
    "ordem_instalacao", "marca", "pacote", "instalado_em", "atualizado_em",
    "instalador", "caminho", "n_permissoes", "n_concedidas", "sensiveis",
]


def hex_para_ms(valor):
    """Converte '198d35fa587' (hexadecimal) em milissegundos Unix (inteiro)."""
    return int(valor, 16) if valor else 0


def ms_para_data(ms):
    """Converte milissegundos Unix em 'AAAA-MM-DD HH:MM:SS' (UTC-3)."""
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, FUSO).strftime("%Y-%m-%d %H:%M:%S")


def ler_pacotes(caminho):
    """Le o XML e devolve uma lista de dicionarios, um por <package>."""
    raiz = ET.parse(caminho).getroot()
    pacotes = []
    for p in raiz.findall("package"):
        perms = p.find("perms")
        itens = list(perms) if perms is not None else []
        concedidas = [i.get("name") for i in itens if i.get("granted") == "true"]
        sensiveis = sorted({n.split(".")[-1] for n in concedidas} & SENSIVEIS)
        instalado = hex_para_ms(p.get("it"))
        pacotes.append({
            "ordem_instalacao": "",   # preenchido depois, so para apps de usuario
            "marca": "",              # PRIMEIRO ou ULTIMO, idem
            "pacote": p.get("name"),
            "instalado_ms": instalado,  # uso interno (ordenacao exata), nao vai ao CSV
            "instalado_em": ms_para_data(instalado),
            "atualizado_em": ms_para_data(hex_para_ms(p.get("ut"))),
            "instalador": p.get("installer", "-"),
            "caminho": p.get("codePath", ""),
            "n_permissoes": len(itens),
            "n_concedidas": len(concedidas),
            "sensiveis": ";".join(sensiveis),
        })
    return pacotes


def eh_de_usuario(pacote):
    """Apps instalados pelo usuario ficam em /data/app; os do sistema, em /system etc."""
    return pacote["caminho"].startswith("/data/app")


def marcar_ordem(pacotes):
    """Numera os apps de usuario por data de instalacao e marca o primeiro e o ultimo.

    Devolve a lista de apps de usuario ja em ordem cronologica.
    """
    usuario = sorted((p for p in pacotes if eh_de_usuario(p)),
                     key=lambda p: p["instalado_ms"])
    for numero, p in enumerate(usuario, start=1):
        p["ordem_instalacao"] = numero
    if usuario:
        usuario[0]["marca"] = "PRIMEIRO"
        usuario[-1]["marca"] = "ULTIMO"
    return usuario


def main():
    ap = argparse.ArgumentParser(description="Resumo do packages.xml")
    ap.add_argument("xml", help="caminho do packages.xml")
    ap.add_argument("--so-usuario", action="store_true", help="mostra so apps de /data/app")
    ap.add_argument("--csv", help="salva a tabela completa neste arquivo CSV")
    args = ap.parse_args()

    pacotes = ler_pacotes(args.xml)
    usuario = marcar_ordem(pacotes)
    lista = usuario if args.so_usuario else pacotes

    print(f"Total de pacotes: {len(pacotes)}")
    print(f"  de usuario (/data/app): {len(usuario)}")
    print(f"  de sistema: {len(pacotes) - len(usuario)}")

    if usuario:
        print("\nApps de usuario em ordem de instalacao (UTC-3):")
        for p in usuario:
            sufixo = f"   <-- {p['marca']}" if p["marca"] else ""
            print(f"  {p['ordem_instalacao']:2d}  {p['instalado_em']}  {p['pacote']}"
                  f"  (instalador: {p['instalador']}){sufixo}")
        if len({p["instalado_ms"] // 1000 for p in usuario}) < len(usuario):
            print("  Obs.: ha apps com o mesmo segundo de instalacao; a ordem entre eles"
                  " e so de leitura.")

    print("\nApps de usuario com mais permissoes concedidas:")
    for p in sorted(usuario, key=lambda x: x["n_concedidas"], reverse=True)[:10]:
        print(f"  {p['n_concedidas']:3d}  {p['pacote']}  {p['sensiveis']}")

    if args.csv:
        if not lista:
            print("\nNada para salvar no CSV.")
            return
        # CSV em ordem cronologica; extrasaction="ignore" descarta 'instalado_ms'.
        linhas = sorted(lista, key=lambda p: p["instalado_ms"])
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
            w.writeheader()
            w.writerows(linhas)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
