#!/usr/bin/env python3
"""analisa_packages.py - resume o packages.xml de uma imagem Android.

Uso:
    python analisa_packages.py CAMINHO\\packages.xml
    python analisa_packages.py CAMINHO\\packages.xml --so-usuario
    python analisa_packages.py CAMINHO\\packages.xml --csv saida.csv

O script apenas LE o arquivo. Nunca grava nada na pasta da evidencia.
Datas: o packages.xml guarda 'it' (primeira instalacao) e 'ut' (ultima
atualizacao) em milissegundos Unix escritos em hexadecimal.
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


def hex_para_data(valor):
    """Converte '198d35fa587' (hex, ms Unix) em 'AAAA-MM-DD HH:MM:SS' (UTC-3)."""
    if not valor:
        return ""
    ms = int(valor, 16)
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
        pacotes.append({
            "pacote": p.get("name"),
            "instalado_em": hex_para_data(p.get("it")),
            "atualizado_em": hex_para_data(p.get("ut")),
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


def main():
    ap = argparse.ArgumentParser(description="Resumo do packages.xml")
    ap.add_argument("xml", help="caminho do packages.xml")
    ap.add_argument("--so-usuario", action="store_true", help="mostra so apps de /data/app")
    ap.add_argument("--csv", help="salva a tabela completa neste arquivo CSV")
    args = ap.parse_args()

    pacotes = ler_pacotes(args.xml)
    usuario = [p for p in pacotes if eh_de_usuario(p)]
    lista = usuario if args.so_usuario else pacotes

    print(f"Total de pacotes: {len(pacotes)}")
    print(f"  de usuario (/data/app): {len(usuario)}")
    print(f"  de sistema: {len(pacotes) - len(usuario)}")

    print("\nMais recentes (primeira instalacao, UTC-3):")
    for p in sorted(lista, key=lambda x: x["instalado_em"], reverse=True)[:10]:
        print(f"  {p['instalado_em']}  {p['pacote']}  (instalador: {p['instalador']})")

    print("\nMais permissoes concedidas:")
    for p in sorted(lista, key=lambda x: x["n_concedidas"], reverse=True)[:10]:
        print(f"  {p['n_concedidas']:3d}  {p['pacote']}  {p['sensiveis']}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(lista[0].keys()))
            w.writeheader()
            w.writerows(lista)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()