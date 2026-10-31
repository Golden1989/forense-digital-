#!/usr/bin/env python3
"""exif_fotos.py - le o EXIF de fotos JPEG (sem instalar nada) e aponta inconsistencias.

Para cada foto mostra: marca, modelo, software, as datas do EXIF
(DateTime, DateTimeOriginal, DateTimeDigitized), fuso (OffsetTime), GPS
(coordenadas, ou "bloco GPS sem coordenadas") e as datas do arquivo no
sistema (criado/modificado), e marca com [!] o que merece atencao:

  - sem EXIF (ex.: captura de tela, imagem reenviada por app);
  - DateTime diferente de DateTimeOriginal (arquivo regravado/editado depois);
  - DateTimeDigitized diferente de DateTimeOriginal (num celular costumam ser iguais);
  - campo Software preenchido (pode indicar edicao ou apenas a versao do sistema);
  - data/hora do GPS incompativel com a data local + fuso (mais de 5 min de diferenca);
  - arquivo modificado no sistema ANTES da data de captura (mais de 1 dia).

Uso:
    python exif_fotos.py PASTA_OU_FOTO
    python exif_fotos.py PASTA --csv fotos.csv
    python exif_fotos.py PASTA --hash          (inclui SHA-256 de cada foto)
    python exif_fotos.py PASTA --so-alertas    (mostra so as fotos com [!])

Somente leitura. Entende JPEG (.jpg/.jpeg); outros formatos sao listados como
"sem leitura". As datas do EXIF sao horario LOCAL do aparelho (sem fuso, salvo
OffsetTime); as do sistema de arquivos sao outra coisa (ver README sobre os
"relogios" de um arquivo). Alertas sao PISTAS: registre como fato, nao como prova.
"""
import argparse
import csv
import hashlib
import os
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

TAMANHO = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
IFD0 = {0x010F: "make", 0x0110: "model", 0x0131: "software", 0x0132: "datetime",
        0x8769: "_exif", 0x8825: "_gps"}
EXIF = {0x9003: "original", 0x9004: "digitalizada", 0x9010: "offset", 0x9011: "offset_original",
        0x9012: "offset_digitalizada", 0xA002: "largura", 0xA003: "altura", 0xA434: "lente"}
GPS = {1: "lat_ref", 2: "lat", 3: "lon_ref", 4: "lon", 5: "alt_ref", 6: "alt", 7: "hora", 0x1D: "data"}


def ler_valor(dados, base, endian, tipo, n, campo):
    tam = TAMANHO.get(tipo, 1) * n
    if tam <= 4:
        pos = campo
    else:
        pos = base + struct.unpack(endian + "I", dados[campo:campo + 4])[0]
    bruto = dados[pos:pos + tam]
    if tipo == 2:
        return bruto.split(b"\0")[0].decode("latin-1", "replace").strip()
    if tipo == 3:
        v = struct.unpack(endian + f"{n}H", bruto)
    elif tipo == 4:
        v = struct.unpack(endian + f"{n}I", bruto)
    elif tipo == 9:
        v = struct.unpack(endian + f"{n}i", bruto)
    elif tipo in (5, 10):
        f = "I" if tipo == 5 else "i"
        t = struct.unpack(endian + f"{2 * n}{f}", bruto)
        v = tuple((t[i] / t[i + 1]) if t[i + 1] else 0.0 for i in range(0, len(t), 2))
    else:
        v = tuple(bruto)
    return v[0] if len(v) == 1 else v


def ler_ifd(dados, base, endian, offset, nomes):
    achados = {}
    try:
        n = struct.unpack(endian + "H", dados[base + offset:base + offset + 2])[0]
        for i in range(n):
            ent = base + offset + 2 + 12 * i
            tag, tipo, cont = struct.unpack(endian + "HHI", dados[ent:ent + 8])
            if tag in nomes and tipo in TAMANHO:
                achados[nomes[tag]] = ler_valor(dados, base, endian, tipo, cont, ent + 8)
    except (struct.error, IndexError):
        pass
    return achados


def ler_exif(caminho):
    """Devolve (dict com campos, motivo). dict vazio = sem EXIF legivel."""
    dados = Path(caminho).read_bytes()
    if dados[:2] != b"\xff\xd8":
        return {}, "nao e JPEG"
    pos = 2
    while pos + 4 <= len(dados) and dados[pos] == 0xFF:
        marcador = dados[pos + 1]
        tam = struct.unpack(">H", dados[pos + 2:pos + 4])[0]
        if marcador == 0xE1 and dados[pos + 4:pos + 10] == b"Exif\0\0":
            tiff = dados[pos + 10:pos + 2 + tam]
            endian = "<" if tiff[:2] == b"II" else ">"
            off0 = struct.unpack(endian + "I", tiff[4:8])[0]
            campos = ler_ifd(tiff, 0, endian, off0, IFD0)
            if "_exif" in campos:
                campos.update(ler_ifd(tiff, 0, endian, campos["_exif"], EXIF))
            if "_gps" in campos:
                campos["gps"] = ler_ifd(tiff, 0, endian, campos["_gps"], GPS)
            return campos, ""
        if marcador == 0xDA:        # inicio dos dados da imagem: acabaram os metadados
            break
        pos += 2 + tam
    return {}, "sem bloco EXIF"


def graus(valor, ref):
    if not isinstance(valor, tuple) or len(valor) != 3:
        return None
    d = valor[0] + valor[1] / 60 + valor[2] / 3600
    return -d if ref in ("S", "W") else d


def data_exif(texto):
    try:
        return datetime.strptime(texto, "%Y:%m:%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def analisar(caminho, com_hash):
    st = os.stat(caminho)
    criado = st.st_ctime if os.name == "nt" else None
    campos, motivo = ler_exif(caminho)
    r = {"arquivo": str(caminho), "tamanho": st.st_size, "alertas": []}
    r["fs_modificado"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    r["fs_criado"] = datetime.fromtimestamp(criado).strftime("%Y-%m-%d %H:%M:%S") if criado else ""
    if com_hash:
        r["sha256"] = hashlib.sha256(Path(caminho).read_bytes()).hexdigest()
    if not campos:
        r["alertas"].append(f"sem EXIF ({motivo})")
        return r
    r.update({k: campos.get(k, "") for k in ("make", "model", "software", "datetime", "original",
                                             "digitalizada", "offset", "largura", "altura")})
    gps = campos.get("gps")
    r["gps"] = ""
    if gps is not None:
        lat = graus(gps.get("lat"), gps.get("lat_ref"))
        lon = graus(gps.get("lon"), gps.get("lon_ref"))
        if lat is not None and lon is not None:
            r["gps"] = f"{lat:.6f},{lon:.6f}"
        else:
            r["gps"] = "bloco GPS sem coordenadas"
        h, d = gps.get("hora"), gps.get("data")
        if isinstance(h, tuple) and len(h) == 3 and isinstance(d, str):
            try:
                r["gps_utc"] = datetime.strptime(d, "%Y:%m:%d").replace(
                    hour=int(h[0]), minute=int(h[1]), second=int(h[2])).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                r["gps_utc"] = ""

    orig, dt, dig = data_exif(r["original"]), data_exif(r["datetime"]), data_exif(r["digitalizada"])
    if orig and dt and dt != orig:
        r["alertas"].append(f"DateTime ({r['datetime']}) difere de DateTimeOriginal ({r['original']})")
    if orig and dig and dig != orig:
        r["alertas"].append(f"DateTimeDigitized ({r['digitalizada']}) difere de DateTimeOriginal")
    if r["software"]:
        r["alertas"].append(f"campo Software preenchido: {r['software']}")
    if orig and r.get("gps_utc") and r["offset"]:
        try:
            sinal = -1 if r["offset"].startswith("-") else 1
            hh, mm = r["offset"][1:].split(":")
            fuso = timezone(sinal * timedelta(hours=int(hh), minutes=int(mm)))
            local_em_utc = orig.replace(tzinfo=fuso).astimezone(timezone.utc).replace(tzinfo=None)
            gps_dt = datetime.strptime(r["gps_utc"], "%Y-%m-%d %H:%M:%S")
            dif = abs((local_em_utc - gps_dt).total_seconds()) / 60
            if dif > 5:
                r["alertas"].append(f"hora do GPS difere {dif:.0f} min da data local convertida com {r['offset']}")
        except (ValueError, IndexError):
            pass
    if orig:
        mod = datetime.fromtimestamp(st.st_mtime)
        if (orig - mod).total_seconds() > 86400:
            r["alertas"].append("arquivo modificado no sistema ANTES da captura (>1 dia)")
    return r


def listar(alvo):
    p = Path(alvo)
    if p.is_file():
        return [p]
    exts = {".jpg", ".jpeg", ".jpe", ".png", ".heic", ".webp", ".gif", ".tif", ".tiff"}
    return sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in exts)


def main():
    ap = argparse.ArgumentParser(description="EXIF de fotos e alertas de inconsistencia")
    ap.add_argument("alvo", help="foto ou pasta (busca em subpastas)")
    ap.add_argument("--hash", action="store_true", help="calcula SHA-256 de cada foto")
    ap.add_argument("--so-alertas", action="store_true", help="mostra so fotos com alerta [!]")
    ap.add_argument("--csv", help="salva a tabela neste CSV")
    args = ap.parse_args()

    arquivos = listar(args.alvo)
    resultados = []
    for f in arquivos:
        try:
            resultados.append(analisar(f, args.hash))
        except OSError as e:
            print(f"[erro] {f}: {e}")
    resultados.sort(key=lambda r: (r.get("original") or "~", r["arquivo"]))

    mostrados = [r for r in resultados if r["alertas"]] if args.so_alertas else resultados
    print(f"Arquivos de imagem: {len(resultados)} | com EXIF: {sum(1 for r in resultados if r.get('make') or r.get('original'))}"
          f" | com alerta: {sum(1 for r in resultados if r['alertas'])}\n")
    for r in mostrados:
        print(r["arquivo"])
        if r.get("original") or r.get("make"):
            print(f"   aparelho: {r.get('make', '')} {r.get('model', '')}".rstrip() + (f" | software: {r['software']}" if r.get("software") else ""))
            print(f"   EXIF: original={r['original']} | datetime={r['datetime']} | digitalizada={r['digitalizada']} | fuso={r['offset'] or '-'}")
            print(f"   GPS: {r['gps'] or 'sem bloco GPS'}" + (f" | data/hora GPS (UTC): {r['gps_utc']}" if r.get("gps_utc") else ""))
        print(f"   sistema: modificado={r['fs_modificado']}" + (f" | criado={r['fs_criado']}" if r['fs_criado'] else ""))
        for a in r["alertas"]:
            print(f"   [!] {a}")
        print()

    if args.csv and resultados:
        campos = ["arquivo", "make", "model", "software", "datetime", "original", "digitalizada",
                  "offset", "gps", "gps_utc", "largura", "altura", "fs_criado", "fs_modificado",
                  "tamanho", "sha256", "alertas"]
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for r in resultados:
                linha = dict(r)
                linha["alertas"] = " | ".join(r["alertas"])
                w.writerow(linha)
        print(f"CSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
