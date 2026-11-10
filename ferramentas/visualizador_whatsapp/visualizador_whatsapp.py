#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
visualizador_whatsapp.py - Visualizador local de conversas de WhatsApp (iOS e Android).

Abre o banco de mensagens (ChatStorage*.sqlite no iOS, msgstore*.db no Android) em modo SOMENTE LEITURA e
mostra as conversas no navegador: mensagens com dia e hora, áudios (player + transcrição automática),
imagens (miniatura, hash, EXIF), participantes de grupos, filtros (CPF, telefone, e-mail...) e exportação em CSV.

Guia completo: README.md desta pasta.

O que faz
  - Reconhece sozinho se o banco é iOS ou Android (pelas tabelas).
  - Sobe um servidor em http://127.0.0.1:PORTA (só acessível neste computador) e abre o navegador.
  - Não altera o banco nem a pasta de mídia. Mostra o SHA-256 do banco no topo da página.

Uso (de dentro da pasta do repositório)
  iOS:
    python ferramentas\\visualizador_whatsapp\\visualizador_whatsapp.py --pasta "C:\\evidencia\\ios"
    python ferramentas\\visualizador_whatsapp\\visualizador_whatsapp.py --db "C:\\evidencia\\ChatStorage.sqlite" --contatos "C:\\evidencia\\Contacts.sqlite"
  Android (o --contatos é o wa.db, com nomes e lista de bloqueados):
    python ferramentas\\visualizador_whatsapp\\visualizador_whatsapp.py --db "C:\\evidencia\\msgstore.db" --contatos "C:\\evidencia\\wa.db"
  Com transcrições geradas por transcrever_audios.py:
    ... --transcricoes transcricoes_audio.json

Só usa a biblioteca padrão do Python (nada para instalar). Pillow (opcional) habilita a leitura de EXIF.
"""
import argparse
import atexit
import csv
import hashlib
import io
import json
import mimetypes
import re
import shutil
import sqlite3
import struct
import sys
import tempfile
import threading
import unicodedata
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

COCOA_PARA_UNIX = 978307200          # segundos entre 1970-01-01 e 2001-01-01
LIMITE_DATA_REAL = 1e8               # abaixo disso o valor não é uma data (anonimização)

TIPOS = {                            # ZWAMESSAGE.ZMESSAGETYPE (WhatsApp iOS)
    0: "texto", 1: "imagem", 2: "video", 3: "audio", 4: "contato",
    5: "localizacao", 6: "evento_grupo", 7: "link", 8: "documento",
    10: "evento_sistema", 11: "gif", 14: "apagada", 15: "figurinha",
}


# msgstore.db (Android, esquema antigo 'messages'): media_wa_type -> (código usado pelo visualizador, nome)
TIPOS_ANDROID = {
    0: (0, "texto"), 1: (1, "imagem"), 2: (3, "audio"), 3: (2, "video"), 4: (4, "contato"),
    5: (5, "localizacao"), 8: (10, "chamada"), 9: (8, "documento"), 10: (10, "evento_sistema"),
    13: (11, "gif"), 20: (15, "figurinha"),
}
INVISIVEIS = re.compile("[\u2060\u200b\u200c\u200d\u200e\u200f\ufeff]")


def nome_contato_android(nomes, jid):
    return nomes.get(jid)


def limpar_jid(jid):
    """Tira os caracteres invisíveis (U+2060 etc.) que a anonimização pôs no fim dos JIDs do Android."""
    return INVISIVEIS.sub("", jid or "").strip()


def dobrar(s):
    """minúsculas e sem acento, para busca tolerante."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


_PASTAS_TEMP = []


def _limpar_temporarios():
    for d in _PASTAS_TEMP:
        shutil.rmtree(d, ignore_errors=True)


atexit.register(_limpar_temporarios)


def abrir_ro(caminho):
    """Abre o SQLite sem poder gravar. Se existir um arquivo -wal com dados (alterações ainda não
    incorporadas ao banco), trabalha numa CÓPIA temporária de banco + -wal + -shm, para que esses dados
    apareçam e o original não seja tocado. Sem -wal, abre o original direto, só leitura."""
    p = Path(caminho).resolve()
    wal = Path(str(p) + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        tmp = tempfile.mkdtemp(prefix="wa_visualizador_")
        _PASTAS_TEMP.append(tmp)
        for ext in ("", "-wal", "-shm"):
            origem = Path(str(p) + ext)
            if origem.exists():
                shutil.copy2(origem, Path(tmp) / (p.name + ext))
        print("  (%s tem arquivo -wal com dados: usei uma cópia de trabalho temporária; o original não foi alterado)" % p.name)
        return sqlite3.connect((Path(tmp) / p.name).as_uri() + "?mode=ro", uri=True)
    return sqlite3.connect(p.as_uri() + "?mode=ro&immutable=1", uri=True)


def formato_real(caminho):
    """Descobre o formato pelos primeiros bytes (a extensão do nome pode enganar)."""
    try:
        with open(caminho, "rb") as f:
            h = f.read(16)
    except OSError:
        return None
    if h[:4] == b"OggS":
        return "Ogg/Opus"
    if h[4:8] == b"ftyp":
        return "MP4/M4A"
    if h[:3] == b"ID3" or h[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return "MP3"
    if h[:2] in (b"\xff\xf1", b"\xff\xf9"):
        return "AAC (ADTS)"
    if h[:3] == b"\xff\xd8\xff":
        return "JPEG"
    if h[:8] == b"\x89PNG\r\n\x1a\n":
        return "PNG"
    if h[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP":
        return "WEBP"
    return "desconhecido"


def tipo_http(caminho, formato):
    if formato == "Ogg/Opus":
        return "audio/ogg"
    if formato == "MP4/M4A":
        return "audio/mp4"
    imagens = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif", "WEBP": "image/webp"}
    if formato in imagens:
        return imagens[formato]
    return mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"


EXT_ESPERADAS = {
    "Ogg/Opus": {"opus", "ogg", "oga"}, "MP4/M4A": {"m4a", "mp4", "aac"},
    "JPEG": {"jpg", "jpeg"}, "PNG": {"png"}, "GIF": {"gif"}, "WEBP": {"webp"},
}


def dimensoes(caminho, formato):
    """Largura x altura lendo só o cabeçalho (JPEG e PNG), sem depender de bibliotecas."""
    try:
        with open(caminho, "rb") as f:
            b = f.read()
        if formato == "PNG":
            w, h = struct.unpack(">II", b[16:24])
            return [w, h]
        if formato == "JPEG":
            i = 2
            while i + 9 < len(b):
                if b[i] != 0xFF:
                    i += 1
                    continue
                mk = b[i + 1]
                if mk in (0xC0, 0xC1, 0xC2, 0xC3):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9])
                    return [w, h]
                if mk == 0xD8 or mk == 0x01 or 0xD0 <= mk <= 0xD7:
                    i += 2
                    continue
                i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    except Exception:
        pass
    return None


def exif_resumo(caminho):
    """Resumo do EXIF (fabricante, modelo, datas, GPS). Só funciona se o Pillow estiver instalado."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(caminho) as im:
            ex = im.getexif()
            if not ex:
                return None
            out = {}
            for tag, nome in ((0x010F, "fabricante"), (0x0110, "modelo"), (0x0131, "software"),
                              (0x0132, "data_arquivo")):
                if tag in ex:
                    out[nome] = str(ex[tag]).strip()
            sub = ex.get_ifd(0x8769)
            for tag, nome in ((0x9003, "data_original"), (0x9004, "data_digitalizada")):
                if tag in sub:
                    out[nome] = str(sub[tag]).strip()
            gps = ex.get_ifd(0x8825)
            if gps and 2 in gps and 4 in gps:
                def grau(v, ref):
                    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
                    return -d if str(ref).upper() in ("S", "W") else d
                out["gps"] = "%.6f, %.6f" % (grau(gps[2], gps.get(1, "N")), grau(gps[4], gps.get(3, "E")))
            return out or None
    except Exception:
        return None


def numero_do_jid(jid):
    return (jid or "").split("@")[0]


class Base:
    """Carrega tudo da base para a memória (poucos MB) e responde às consultas."""

    def __init__(self, db, contatos=None, midia=None, transcricoes=None, hash_banco=None, manifesto=None):
        self.db_path = Path(db)
        self.sha256 = sha256_arquivo(self.db_path)
        self.hash_esperado = (hash_banco or "").strip().lower() or None
        self.manifesto, self.manifesto_aviso = self._ler_manifesto(manifesto)
        self._usos = {}     # chave do arquivo de mídia -> {"msgs": [ids], "tam_banco": {tamanhos}}
        con = abrir_ro(self.db_path)
        con.row_factory = sqlite3.Row
        tabelas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "ZWAMESSAGE" in tabelas:
            self.plataforma = "ios"
        elif "messages" in tabelas and "chat_list" in tabelas:
            self.plataforma = "android"
        else:
            raise SystemExit("Não reconheci este banco: não tem as tabelas do WhatsApp iOS (ZWAMESSAGE) "
                             "nem do Android (messages + chat_list).")
        self.campo_data = "ZMESSAGEDATE" if self.plataforma == "ios" else "timestamp (ms)"
        self.bloqueados = []
        self.ignoradas = 0

        if self.plataforma == "ios":
            nomes_contato = {}
            if contatos and Path(contatos).exists():
                try:
                    c2 = abrir_ro(contatos)
                    for nome, wid, fone in c2.execute(
                        "SELECT c.ZFULLNAME, p.ZWHATSAPPID, p.ZPHONE FROM ZWAPHONE p "
                        "LEFT JOIN ZWACONTACT c ON c.Z_PK = p.ZCONTACT"
                    ):
                        if nome and wid:
                            nomes_contato[wid] = nome
                    c2.close()
                except sqlite3.Error:
                    pass
            self.nomes_contato = nomes_contato

            membros = {}
            for r in con.execute(
                "SELECT Z_PK, ZCONTACTNAME, ZFIRSTNAME, ZMEMBERJID FROM ZWAGROUPMEMBER"
            ):
                membros[r["Z_PK"]] = (r["ZCONTACTNAME"] or r["ZFIRSTNAME"], r["ZMEMBERJID"])

            sessoes = {}
            for r in con.execute(
                "SELECT Z_PK, ZCONTACTJID, ZPARTNERNAME, ZSESSIONTYPE, ZARCHIVED, ZREMOVED, ZHIDDEN "
                "FROM ZWACHATSESSION"
            ):
                jid = r["ZCONTACTJID"] or ""
                eh_grupo = jid.endswith("@g.us") or r["ZSESSIONTYPE"] == 1
                nome = r["ZPARTNERNAME"] or nomes_contato.get(numero_do_jid(jid)) or numero_do_jid(jid)
                sessoes[r["Z_PK"]] = dict(
                    id=r["Z_PK"], jid=jid, nome=nome, grupo=bool(eh_grupo),
                    arquivada=bool(r["ZARCHIVED"]), removida=bool(r["ZREMOVED"]),
                    n=0, n_datadas=0, n_audio=0, n_audio_ok=0, n_img=0, n_img_ok=0, primeira=None, ultima=None, previa="", msgs=[],
                )
        else:
            nomes_contato, sessoes = self._android_sessoes(con, contatos)
            self.nomes_contato = nomes_contato

        # arquivos de mídia disponíveis na pasta (nome -> caminho)
        self.arquivos = {}
        self.midia_dir = Path(midia) if midia else None
        if self.midia_dir and self.midia_dir.exists():
            for sub_dir in ("Audio", "Image"):
                d = self.midia_dir / sub_dir
                if d.is_dir():
                    for f in d.iterdir():
                        if f.is_file():
                            self.arquivos[sub_dir + "/" + f.name] = f
        self.info_arquivo = {}   # chave -> {sha256, formato, bytes}
        for chave, caminho in self.arquivos.items():
            fmt = formato_real(caminho)
            self.info_arquivo[chave] = dict(
                sha256=sha256_arquivo(caminho), formato=fmt, bytes=caminho.stat().st_size,
                dim=dimensoes(caminho, fmt) if chave.startswith("Image/") else None,
                exif=exif_resumo(caminho) if chave.startswith("Image/") else None)

        self.transcricoes = {}
        self.transc_meta = None
        self.transc_erros = 0
        self.transc_aviso = None
        if transcricoes:
            if not Path(transcricoes).exists():
                self.transc_aviso = "Arquivo de transcrições não encontrado: %s (caminho relativo vale a partir da pasta onde você rodou o comando)" % transcricoes
            else:
                try:
                    bruto = json.loads(Path(transcricoes).read_text(encoding="utf-8"))
                    self.transcricoes = bruto.get("itens", {})
                    self.transc_meta = bruto.get("meta")
                    self.transc_erros = sum(1 for v in self.transcricoes.values() if v.get("erro"))
                    if self.transc_erros:
                        exemplo = next(v["erro"] for v in self.transcricoes.values() if v.get("erro"))
                        self.transc_aviso = ("%d dos %d itens do arquivo de transcrições têm ERRO e ficaram sem texto (ex.: %s). "
                                             "Rode transcrever_audios.py de novo para refazê-los." % (self.transc_erros, len(self.transcricoes), exemplo[:120]))
                except (ValueError, OSError) as e:
                    self.transc_aviso = "Não consegui ler %s: %s" % (transcricoes, e)

        self._membros_raw = {}      # sid -> lista de dicts (nome, jid, ativo, admin, chave)
        self._criador = {}          # sid -> jid do criador (iOS)
        if self.plataforma == "ios":
            self._ler_membros_ios(con, nomes_contato)
        else:
            self._ler_membros_android(con, nomes_contato, sessoes)
        self.todas = []
        if self.plataforma == "android":
            self._android_mensagens(con, sessoes)
            con.close()
        else:
            sql = (
                "SELECT m.Z_PK, m.ZCHATSESSION, m.ZISFROMME, m.ZMESSAGETYPE, m.ZMESSAGEDATE, "
                "m.ZFROMJID, m.ZPUSHNAME, m.ZTEXT, m.ZGROUPEVENTTYPE, m.ZGROUPMEMBER, "
                "m.ZMESSAGESTATUS, m.ZSTARRED, "
                "i.ZMEDIALOCALPATH, i.ZMOVIEDURATION, i.ZTITLE, i.ZVCARDNAME, i.ZFILESIZE, "
                "i.ZLATITUDE, i.ZLONGITUDE "
                "FROM ZWAMESSAGE m LEFT JOIN ZWAMEDIAITEM i ON i.ZMESSAGE = m.Z_PK "
                "ORDER BY m.ZCHATSESSION, m.Z_PK"
            )
            for r in con.execute(sql):
                s = sessoes.get(r["ZCHATSESSION"])
                if s is None:
                    continue
                bruto = r["ZMESSAGEDATE"]
                t = (bruto + COCOA_PARA_UNIX) if (bruto is not None and bruto >= LIMITE_DATA_REAL) else None
                eu = bool(r["ZISFROMME"])
                if eu:
                    remetente = "Você (dono do aparelho)"
                elif s["grupo"]:
                    nome_m, jid_m = membros.get(r["ZGROUPMEMBER"], (None, None))
                    remetente = (nome_m or nomes_contato.get(numero_do_jid(jid_m))
                                 or r["ZPUSHNAME"] or numero_do_jid(jid_m) or "(remetente desconhecido)")
                else:
                    remetente = s["nome"]
                arquivo = r["ZMEDIALOCALPATH"]
                arquivo_nome = Path(arquivo.replace("\\", "/")).name if arquivo else None
                m = dict(
                    id=r["Z_PK"], eu=eu, t=t, raw=bruto, tipo=r["ZMESSAGETYPE"],
                    tipo_nome=TIPOS.get(r["ZMESSAGETYPE"], "tipo_%s" % r["ZMESSAGETYPE"]),
                    ev=r["ZGROUPEVENTTYPE"], de=remetente, texto=r["ZTEXT"],
                    arquivo=arquivo_nome,
                    dur=r["ZMOVIEDURATION"], titulo=r["ZTITLE"], vcard=r["ZVCARDNAME"],
                    tam=r["ZFILESIZE"], lat=r["ZLATITUDE"], lon=r["ZLONGITUDE"],
                    estrela=bool(r["ZSTARRED"]),
                )
                pasta_tipo = {3: "Audio/", 1: "Image/"}.get(r["ZMESSAGETYPE"])
                chave = (pasta_tipo + arquivo_nome) if (pasta_tipo and arquivo_nome) else None
                m["midia"] = None
                m["transc"] = None
                if chave and chave in self.arquivos:
                    inf = self.info_arquivo[chave]
                    uso = self._usos.setdefault(chave, dict(msgs=[], tam_banco=set()))
                    uso["msgs"].append(r["Z_PK"])
                    if r["ZFILESIZE"]:
                        uso["tam_banco"].add(r["ZFILESIZE"])
                    m["midia"] = dict(url="/media/" + chave, sha256=inf["sha256"],
                                      formato=inf["formato"], bytes=inf["bytes"], dim=inf["dim"], exif=inf["exif"])
                    ext = arquivo_nome.rsplit(".", 1)[-1].lower() if "." in arquivo_nome else ""
                    esperadas = EXT_ESPERADAS.get(inf["formato"])
                    m["midia"]["ext_confere"] = (esperadas is None) or (ext in esperadas)
                    m["midia"]["tam_banco"] = r["ZFILESIZE"]
                    m["midia"]["tam_confere"] = (not r["ZFILESIZE"]) or r["ZFILESIZE"] == inf["bytes"]
                    if r["ZMESSAGETYPE"] == 3:
                        tr = self.transcricoes.get(arquivo_nome)
                        if tr:
                            m["transc"] = tr.get("texto")
                m["_gm"] = r["ZGROUPMEMBER"]
                m["_busca"] = dobrar(" ".join(x for x in (r["ZTEXT"], r["ZTITLE"], r["ZVCARDNAME"], remetente, m["transc"]) if x))
                s["msgs"].append(m)
                self.todas.append((s["id"], m))
                s["n"] += 1
                if r["ZMESSAGETYPE"] == 3:
                    s["n_audio"] += 1
                    if m["midia"]:
                        s["n_audio_ok"] += 1
                elif r["ZMESSAGETYPE"] == 1:
                    s["n_img"] += 1
                    if m["midia"]:
                        s["n_img_ok"] += 1
                if t is not None:
                    s["n_datadas"] += 1
                    s["primeira"] = t if s["primeira"] is None else min(s["primeira"], t)
                    s["ultima"] = t if s["ultima"] is None else max(s["ultima"], t)
            con.close()

        for s in sessoes.values():
            for m in reversed(s["msgs"]):
                rot = m["texto"] or m["titulo"] or ("[%s]" % m["tipo_nome"])
                if m["tipo"] in (1, 2, 3) and not m["texto"]:
                    rot = "[%s]" % m["tipo_nome"]
                s["previa"] = rot[:90]
                break
        self.sessoes = sessoes
        self._finalizar_membros()
        datas = [m["t"] for _, m in self.todas if m["t"] is not None]
        self.total = len(self.todas)
        self.datadas = len(datas)
        self.primeira = min(datas) if datas else None
        self.ultima = max(datas) if datas else None

    # ---- integridade dos arquivos --------------------------------------------------
    def _ler_manifesto(self, caminho):
        """Lê um CSV de referência (o mesmo que o botão 'Exportar CSV' do painel Integridade gera)."""
        if not caminho:
            return None, None
        if not Path(caminho).exists():
            return None, "Manifesto não encontrado: %s" % caminho
        try:
            ref = {}
            with open(caminho, encoding="utf-8-sig", newline="") as f:
                for lin in csv.DictReader(f, delimiter=";"):
                    chave, h = (lin.get("arquivo") or "").strip(), (lin.get("sha256") or "").strip().lower()
                    if chave and h:
                        ref[chave] = h
            if not ref:
                return None, "O manifesto %s não tem as colunas 'arquivo' e 'sha256'." % caminho
            return ref, None
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            return None, "Não consegui ler o manifesto %s: %s" % (caminho, e)

    def integridade(self):
        from datetime import datetime, timezone
        itens = []
        vinculo_ok = self.plataforma == "ios"      # só o iOS liga arquivo -> mensagem nesta versão
        for chave in sorted(self.arquivos):
            inf = self.info_arquivo[chave]
            pasta, nome = chave.split("/", 1)
            ext = nome.rsplit(".", 1)[-1].lower() if "." in nome else ""
            esperadas = EXT_ESPERADAS.get(inf["formato"])
            uso = self._usos.get(chave)
            tams = sorted(uso["tam_banco"]) if uso else []
            alertas = []
            ext_ok = (esperadas is None) or (ext in esperadas)
            if not ext_ok:
                alertas.append("extensão não confere com o formato real")
            tam_ok = (not tams) or inf["bytes"] in tams
            if not tam_ok:
                alertas.append("tamanho difere do registrado no banco")
            sem_msg = (uso is None) if vinculo_ok else None
            if sem_msg:
                alertas.append("nenhuma mensagem do banco aponta para este arquivo")
            situ = None
            if self.manifesto is not None:
                ref = self.manifesto.get(chave)
                situ = "novo" if ref is None else ("igual" if ref == inf["sha256"] else "ALTERADO")
                if situ == "ALTERADO":
                    alertas.append("SHA-256 diferente do manifesto de referência")
                elif situ == "novo":
                    alertas.append("não consta no manifesto de referência")
            try:
                mod = datetime.fromtimestamp(self.arquivos[chave].stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                mod = ""
            itens.append(dict(arquivo=chave, pasta=pasta, nome=nome, formato=inf["formato"], ext_confere=ext_ok,
                              bytes=inf["bytes"], tam_banco=tams, tam_confere=tam_ok, modificado=mod,
                              sha256=inf["sha256"], mensagens=(len(uso["msgs"]) if uso else 0),
                              sem_mensagem=sem_msg, manifesto=situ, alertas=alertas))
        ausentes = sorted(k for k in (self.manifesto or {}) if k not in self.arquivos)
        resumo = dict(
            total=len(itens), ext_errada=sum(1 for i in itens if not i["ext_confere"]),
            tam_difere=sum(1 for i in itens if not i["tam_confere"]),
            sem_mensagem=(sum(1 for i in itens if i["sem_mensagem"]) if vinculo_ok else None),
            vinculo_verificado=vinculo_ok, com_alerta=sum(1 for i in itens if i["alertas"]),
            manifesto=(dict(igual=sum(1 for i in itens if i["manifesto"] == "igual"),
                            alterado=sum(1 for i in itens if i["manifesto"] == "ALTERADO"),
                            novo=sum(1 for i in itens if i["manifesto"] == "novo"), ausente=len(ausentes))
                       if self.manifesto is not None else None),
            hash_banco=dict(calculado=self.sha256, esperado=self.hash_esperado,
                            confere=(self.sha256.lower() == self.hash_esperado) if self.hash_esperado else None))
        return dict(resumo=resumo, itens=itens, ausentes=ausentes, aviso=self.manifesto_aviso)

    def csv_integridade(self):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(["arquivo", "pasta", "nome", "formato_real", "extensao_confere", "tamanho_arquivo", "tamanho_no_banco",
                    "tamanho_confere", "modificado_no_disco_UTC", "sha256", "mensagens_vinculadas", "sem_mensagem",
                    "situacao_no_manifesto", "alertas"])
        d = self.integridade()
        for i in d["itens"]:
            w.writerow([i["arquivo"], i["pasta"], i["nome"], i["formato"], "sim" if i["ext_confere"] else "NAO", i["bytes"],
                        "/".join(str(x) for x in i["tam_banco"]), "sim" if i["tam_confere"] else "NAO", i["modificado"],
                        i["sha256"], i["mensagens"], "" if i["sem_mensagem"] is None else ("SIM" if i["sem_mensagem"] else "nao"),
                        i["manifesto"] or "", "; ".join(i["alertas"])])
        for k in d["ausentes"]:
            w.writerow([k, "", "", "", "", "", "", "", "", self.manifesto[k], "", "", "AUSENTE (está no manifesto, não está na pasta)", ""])
        return ("\ufeff" + buf.getvalue()).encode("utf-8")

    # ---- participantes dos grupos -------------------------------------------------
    def _ler_membros_ios(self, con, nomes_contato):
        try:
            for r in con.execute("SELECT Z_PK, ZCHATSESSION, ZISACTIVE, ZISADMIN, ZMEMBERJID, ZCONTACTNAME, ZFIRSTNAME "
                                 "FROM ZWAGROUPMEMBER ORDER BY Z_PK"):
                jid = r["ZMEMBERJID"] or ""
                self._membros_raw.setdefault(r["ZCHATSESSION"], []).append(dict(
                    chave=r["Z_PK"], jid=jid, ativo=bool(r["ZISACTIVE"]), admin=bool(r["ZISADMIN"]),
                    nome=r["ZCONTACTNAME"] or r["ZFIRSTNAME"] or nomes_contato.get(numero_do_jid(jid))))
            for r in con.execute("SELECT ZCHATSESSION, ZCREATORJID FROM ZWAGROUPINFO"):
                if r["ZCREATORJID"]:
                    self._criador[r["ZCHATSESSION"]] = r["ZCREATORJID"]
        except sqlite3.Error:
            pass

    def _ler_membros_android(self, con, nomes_contato, sessoes):
        try:
            for r in con.execute("SELECT gjid, jid, admin FROM group_participants WHERE gjid LIKE '%@g.us%'"):
                sid = self._por_jid.get(limpar_jid(r["gjid"]))
                jid = limpar_jid(r["jid"])
                if sid:
                    self._membros_raw.setdefault(sid, []).append(dict(
                        chave=jid, jid=jid, ativo=None, admin=bool(r["admin"]), nome=nome_contato_android(nomes_contato, jid)))
        except sqlite3.Error:
            pass

    def _finalizar_membros(self):
        """Junta a lista de participantes com a contagem de mensagens enviadas por cada um."""
        for sid, s in self.sessoes.items():
            if not s["grupo"]:
                continue
            est, dono = {}, 0
            for m in s["msgs"]:
                if m["tipo"] in (6, 10):
                    continue
                if m["eu"]:
                    dono += 1
                    continue
                e = est.setdefault(m.get("_gm"), [0, None, None])
                e[0] += 1
                if m["t"] is not None:
                    e[1] = m["t"] if e[1] is None else min(e[1], m["t"])
                    e[2] = m["t"] if e[2] is None else max(e[2], m["t"])
            lista, vistos = [], set()
            for mb in self._membros_raw.get(sid, []):
                n, a, b = est.get(mb["chave"], [0, None, None])
                vistos.add(mb["chave"])
                lista.append(dict(nome=mb["nome"], jid=mb["jid"], numero=numero_do_jid(mb["jid"]), ativo=mb["ativo"],
                                  admin=mb["admin"], n=n, primeira=a, ultima=b))
            for chave, (n, a, b) in est.items():     # quem enviou mensagem mas não está na lista de participantes
                if chave not in vistos and chave is not None:
                    lista.append(dict(nome=None, jid=str(chave), numero=numero_do_jid(str(chave)), ativo=None, admin=False,
                                      n=n, primeira=a, ultima=b, fora_da_lista=True))
            lista.sort(key=lambda x: (x["ativo"] is False, -x["n"], (x["nome"] or x["numero"] or "")))
            s["membros"] = lista
            s["dono_n"] = dono
            s["criador"] = self._criador.get(sid)

    # ---- leitura do WhatsApp Android (msgstore.db + wa.db) ---------------------
    def _android_sessoes(self, con, contatos):
        nomes = {}
        if not contatos:   # procura o wa*.db ao lado do msgstore
            achados = sorted(self.db_path.parent.glob("wa*.db"))
            contatos = str(achados[0]) if achados else None
        if contatos and Path(contatos).exists():
            try:
                c2 = abrir_ro(contatos)
                for jid, disp, wan, num in c2.execute("SELECT jid, display_name, wa_name, number FROM wa_contacts"):
                    nome = disp or wan
                    if jid and nome:
                        nomes[limpar_jid(jid)] = nome
                    elif jid and num:
                        nomes.setdefault(limpar_jid(jid), limpar_jid(num))
                try:
                    self.bloqueados = [nomes.get(limpar_jid(r[0])) or numero_do_jid(limpar_jid(r[0]))
                                       for r in c2.execute("SELECT jid FROM wa_block_list")]
                except sqlite3.Error:
                    pass
                c2.close()
            except sqlite3.Error:
                pass
        sessoes, por_jid = {}, {}

        def nova(jid, assunto=None, arquivada=False):
            sid = len(sessoes) + 1
            grupo = jid.endswith("@g.us")
            if jid == "status@broadcast":
                nome = "Status (broadcast)"
            else:
                nome = (assunto if grupo and assunto else None) or nomes.get(jid) or numero_do_jid(jid)
            sessoes[sid] = dict(id=sid, jid=jid, nome=nome, grupo=grupo, arquivada=bool(arquivada), removida=False,
                                n=0, n_datadas=0, n_audio=0, n_audio_ok=0, n_img=0, n_img_ok=0,
                                primeira=None, ultima=None, previa="", msgs=[])
            por_jid[jid] = sid

        for r in con.execute("SELECT key_remote_jid, subject, archived FROM chat_list ORDER BY sort_timestamp DESC"):
            jid = limpar_jid(r["key_remote_jid"])
            if jid and jid != "-1" and jid not in por_jid:
                nova(jid, r["subject"], r["archived"])
        for (bruto,) in con.execute("SELECT DISTINCT key_remote_jid FROM messages"):
            jid = limpar_jid(bruto)
            if jid and jid != "-1" and jid not in por_jid:
                nova(jid)
        self._por_jid = por_jid
        return nomes, sessoes

    def _android_mensagens(self, con, sessoes):
        for r in con.execute("SELECT * FROM messages ORDER BY _id"):
            jid = limpar_jid(r["key_remote_jid"])
            s = sessoes.get(self._por_jid.get(jid))
            if s is None:           # linha interna do app (jid '-1'), não é conversa
                self.ignoradas += 1
                continue
            bruto = r["timestamp"]
            t = (bruto / 1000.0) if (bruto is not None and bruto > 0) else None
            eu = bool(r["key_from_me"])
            try:                    # a coluna é TEXT no banco ('0', '3', ...)
                codigo = int(r["media_wa_type"])
            except (TypeError, ValueError):
                codigo = -1
            tipo, tipo_nome = TIPOS_ANDROID.get(codigo, (100 + max(codigo, 0),
                                                "tipo_%s_android_nao_confirmado" % codigo))
            if eu:
                remetente = "Você (dono do aparelho)"
            elif s["grupo"]:
                rj = limpar_jid(r["remote_resource"])
                remetente = self.nomes_contato.get(rj) or numero_do_jid(rj) or "(remetente desconhecido)"
            else:
                remetente = s["nome"]
            texto = r["data"] or r["media_caption"]
            m = dict(
                id=r["_id"], eu=eu, t=t, raw=bruto, tipo=tipo, tipo_nome=tipo_nome,
                ev=(r["media_size"] if tipo == 10 else None), de=remetente, texto=texto,
                arquivo=r["media_name"] or None, dur=r["media_duration"] or None, titulo=None, vcard=None,
                tam=(r["media_size"] if tipo not in (0, 10) else None),
                lat=(r["latitude"] if tipo == 5 else None), lon=(r["longitude"] if tipo == 5 else None),
                estrela=bool(r["starred"]), midia=None, transc=None)
            m["_gm"] = limpar_jid(r["remote_resource"]) if (s["grupo"] and not eu) else None
            m["_busca"] = dobrar(" ".join(x for x in (texto, r["media_name"], remetente) if x))
            s["msgs"].append(m)
            self.todas.append((s["id"], m))
            s["n"] += 1
            if tipo == 3:
                s["n_audio"] += 1
            elif tipo == 1:
                s["n_img"] += 1
            if t is not None:
                s["n_datadas"] += 1
                s["primeira"] = t if s["primeira"] is None else min(s["primeira"], t)
                s["ultima"] = t if s["ultima"] is None else max(s["ultima"], t)

    # ---- respostas da API -------------------------------------------------
    def info(self):
        return dict(
            plataforma=self.plataforma, campo_data=self.campo_data, bloqueados=self.bloqueados,
            registros_internos_ignorados=self.ignoradas,
            hash_esperado=self.hash_esperado,
            hash_confere=((self.sha256.lower() == self.hash_esperado) if self.hash_esperado else None),
            manifesto_aviso=self.manifesto_aviso, tem_manifesto=self.manifesto is not None,
            arquivo=self.db_path.name, sha256=self.sha256, conversas=len(self.sessoes),
            mensagens=self.total, mensagens_datadas=self.datadas,
            mensagens_sem_data=self.total - self.datadas,
            primeira=self.primeira, ultima=self.ultima,
            grupos=sum(1 for s in self.sessoes.values() if s["grupo"]),
            audios=sum(s["n_audio"] for s in self.sessoes.values()),
            audios_com_arquivo=sum(s["n_audio_ok"] for s in self.sessoes.values()),
            imagens=sum(s["n_img"] for s in self.sessoes.values()),
            imagens_com_arquivo=sum(s["n_img_ok"] for s in self.sessoes.values()),
            arquivos_imagem=sum(1 for k in self.arquivos if k.startswith("Image/")),
            imagens_ext_errada=sum(1 for k, v in self.info_arquivo.items()
                                   if k.startswith("Image/") and EXT_ESPERADAS.get(v["formato"])
                                   and k.rsplit(".", 1)[-1].lower() not in EXT_ESPERADAS[v["formato"]]),
            arquivos_audio=sum(1 for k in self.arquivos if k.startswith("Audio/")),
            transcricoes=sum(1 for _, m in self.todas if m.get("transc")),
            transc_meta=self.transc_meta,
            transc_aviso=self.transc_aviso,
        )

    def lista_conversas(self):
        saida = []
        for s in self.sessoes.values():
            saida.append({k: s[k] for k in (
                "id", "jid", "nome", "grupo", "arquivada", "removida", "n",
                "n_datadas", "n_audio", "n_audio_ok", "n_img", "n_img_ok", "primeira", "ultima", "previa")})
        return saida

    def conversa(self, sid):
        s = self.sessoes.get(sid)
        if not s:
            return None
        meta = {k: s[k] for k in (
            "id", "jid", "nome", "grupo", "arquivada", "removida", "n",
            "n_datadas", "n_audio", "n_audio_ok", "n_img", "n_img_ok", "primeira", "ultima")}
        if s["grupo"]:
            meta["membros"] = s.get("membros", [])
            meta["dono_n"] = s.get("dono_n", 0)
            meta["criador"] = s.get("criador")
            meta["plataforma"] = self.plataforma
        msgs = [{k: v for k, v in m.items() if not k.startswith("_")} for m in s["msgs"]]
        return dict(conversa=meta, mensagens=msgs)

    def busca_global(self, q, limite=300):
        alvo = dobrar(q).strip()
        if len(alvo) < 2:
            return []
        achados = []
        for sid, m in self.todas:
            if alvo in m["_busca"]:
                s = self.sessoes[sid]
                achados.append(dict(
                    conversa=sid, nome=s["nome"], grupo=s["grupo"], id=m["id"], t=m["t"],
                    eu=m["eu"], de=m["de"],
                    trecho=(m["texto"] or m["titulo"] or m["vcard"]
                            or (("[transcrição automática] " + m["transc"]) if m.get("transc") else None)
                            or "[%s]" % m["tipo_nome"])[:160]))
                if len(achados) >= limite:
                    break
        return achados

    def csv_conversa(self, sid, fuso):
        s = self.sessoes.get(sid)
        if not s:
            return None
        from datetime import datetime, timedelta, timezone
        tz = timezone(timedelta(hours=fuso))
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        w.writerow(["conversa", "jid", "id_mensagem", "direcao", "remetente",
                    "data_hora_(UTC%+d)" % fuso, "valor_bruto_da_data_(%s)" % self.campo_data, "tipo", "texto_ou_titulo", "arquivo", "arquivo_na_pasta", "sha256_arquivo",
                    "formato_real", "transcricao_automatica", "tamanho_arquivo", "tamanho_no_banco", "dimensoes"])
        for m in s["msgs"]:
            quando = (datetime.fromtimestamp(m["t"], tz).strftime("%Y-%m-%d %H:%M:%S")
                      if m["t"] is not None else "SEM DATA (anonimizada)")
            w.writerow([s["nome"], s["jid"], m["id"], "enviada" if m["eu"] else "recebida",
                        m["de"], quando, m["raw"], m["tipo_nome"],
                        (m["texto"] or m["titulo"] or m["vcard"] or ""), m["arquivo"] or "",
                        ("sim" if m["midia"] else ("não" if m["arquivo"] else "")),
                        (m["midia"] or {}).get("sha256", ""), (m["midia"] or {}).get("formato", ""),
                        m["transc"] or "", (m["midia"] or {}).get("bytes", ""),
                        (m["midia"] or {}).get("tam_banco", "") or "",
                        ("x".join(str(v) for v in (m["midia"] or {}).get("dim")) if (m["midia"] or {}).get("dim") else "")])
        return ("\ufeff" + buf.getvalue()).encode("utf-8")


# ---------------------------------------------------------------------------
PAGINA = r"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visualizador WhatsApp iOS</title>
<style>
:root{
  color-scheme:dark;
  --bg:#0f1220; --painel:#171b2d; --painel2:#1e2339; --texto:#e8eaf3; --suave:#9aa3bd;
  --linha:#2a3050; --acento:#ff4a55; --acento2:#7aa2ff; --env:#1c4a33; --rec:#222845;
  --evento:#262c48; --sel:#3a1f2c; --achado:#7a6a12; --sombra:none;
}
:root[data-tema="claro"]{
  color-scheme:light;
  --bg:#f4f5f8; --painel:#ffffff; --painel2:#eceef3; --texto:#1b1f2a; --suave:#667085;
  --linha:#dde0e8; --acento:#d3202b; --acento2:#1f4fbf; --env:#dcf3e1; --rec:#ffffff;
  --evento:#e7e9f0; --sel:#fde8ea; --achado:#ffe58a; --sombra:0 1px 2px rgba(20,24,40,.08);
}
*{box-sizing:border-box}
[hidden]{display:none !important}
html,body{height:100%;margin:0}
body{font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:var(--bg);color:var(--texto);
  display:flex;flex-direction:column}
button,input,select{font:inherit;color:inherit}
header.topo{display:flex;align-items:center;gap:14px;padding:10px 16px;background:var(--painel);
  border-bottom:3px solid var(--acento);flex-wrap:wrap}
header.topo h1{font-size:16px;margin:0;font-weight:700;letter-spacing:.2px}
header.topo h1 span{color:var(--acento)}
.info{color:var(--suave);font-size:12px;display:flex;gap:6px 14px;flex-wrap:wrap;flex:1;min-width:0}
.info b{color:var(--texto);font-weight:600}
.hash{font-family:ui-monospace,Consolas,monospace;cursor:pointer}
.ctl{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--suave)}
select,input[type=text],input[type=search],input[type=date]{background:var(--painel2);border:1px solid var(--linha);
  border-radius:8px;padding:6px 9px}
button{background:var(--painel2);border:1px solid var(--linha);border-radius:8px;padding:6px 10px;cursor:pointer}
button:hover{border-color:var(--acento)}
button.pri{background:var(--acento);border-color:var(--acento);color:#fff}
main{flex:1;display:grid;grid-template-columns:360px 1fr;min-height:0}
aside{background:var(--painel);border-right:1px solid var(--linha);display:flex;flex-direction:column;min-height:0}
.busca{padding:10px;display:flex;flex-direction:column;gap:8px;border-bottom:1px solid var(--linha)}
.busca input{width:100%}
.abas{display:flex;gap:6px;flex-wrap:wrap}
.abas button{padding:4px 9px;font-size:12px}
.abas button.on{background:var(--acento);border-color:var(--acento);color:#fff}
.linha2{display:flex;gap:8px;align-items:center;font-size:12px;color:var(--suave)}
.linha2 select{flex:1}
#lista{overflow:auto;flex:1}
.conv{padding:9px 12px;border-bottom:1px solid var(--linha);cursor:pointer;display:grid;grid-template-columns:1fr auto;gap:2px 8px}
.conv:hover{background:var(--painel2)}
.conv.sel{background:var(--sel);box-shadow:inset 3px 0 0 var(--acento)}
.conv .nome{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conv .quando{font-size:11px;color:var(--suave);white-space:nowrap;text-align:right}
.conv .previa{grid-column:1/2;font-size:12px;color:var(--suave);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.conv .qtd{grid-column:2/3;font-size:11px;text-align:right;color:var(--acento2);font-weight:600}
.conv .jid{grid-column:1/3;font-size:10.5px;color:var(--suave);font-family:ui-monospace,Consolas,monospace;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tag{display:inline-block;font-size:10px;padding:0 6px;border-radius:99px;background:var(--acento2);color:#fff;margin-left:6px;vertical-align:1px}
.vazio{padding:30px;color:var(--suave);text-align:center}
section.painel{display:flex;flex-direction:column;min-height:0;min-width:0}
.cab{padding:10px 16px;background:var(--painel);border-bottom:1px solid var(--linha);display:flex;flex-direction:column;gap:8px}
.cab h2{margin:0;font-size:16px}
#part summary{cursor:pointer;font-size:12.5px;color:var(--acento2);font-weight:600}
#part .tw{max-height:260px;overflow:auto;border:1px solid var(--linha);border-radius:8px;margin-top:6px}
#part table{border-collapse:collapse;width:100%;font-size:12px}
#part th,#part td{padding:4px 10px;text-align:left;border-bottom:1px solid var(--linha);white-space:nowrap}
#part th{position:sticky;top:0;background:var(--painel2);color:var(--suave);font-weight:600}
#part td.num{font-family:ui-monospace,Consolas,monospace;color:var(--suave)}
#part .nota{font-size:11.5px;color:var(--suave);margin:6px 0 2px}
#part .saiu{color:var(--suave)}
#part button{margin-top:6px}
.cab .meta{font-size:12px;color:var(--suave);display:flex;gap:4px 24px;flex-wrap:wrap}
.cab .meta span,#info span{white-space:nowrap}
.cab .meta b{color:var(--texto)}
.ferr{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.ferr input[type=search]{min-width:200px;flex:1;max-width:340px}
.aviso{background:var(--sel);border-left:3px solid var(--acento);padding:6px 10px;border-radius:6px;font-size:12px}
#msgs{flex:1;overflow:auto;padding:14px 18px;display:flex;flex-direction:column;gap:4px}
.dia{align-self:center;background:var(--evento);color:var(--suave);font-size:12px;padding:3px 12px;border-radius:99px;margin:10px 0 6px;font-weight:600}
.dia.sem{background:var(--sel);color:var(--texto)}
.m{max-width:min(720px,82%);display:flex;flex-direction:column}
.m.eu{align-self:flex-end}
.m.rec{align-self:flex-start}
.bolha{padding:6px 10px 4px;border-radius:12px;box-shadow:var(--sombra);overflow-wrap:anywhere}
.eu .bolha{background:var(--env);border-top-right-radius:3px}
.rec .bolha{background:var(--rec);border:1px solid var(--linha);border-top-left-radius:3px}
.m.achado .bolha{outline:2px solid var(--acento)}
.m.foco .bolha{outline:3px solid var(--acento2)}
.quem{font-size:12px;font-weight:700;color:var(--acento2);margin-bottom:1px}
.txt{white-space:pre-wrap}
.rod{display:flex;gap:8px;justify-content:flex-end;font-size:11px;color:var(--suave);margin-top:2px}
.rod .id{font-family:ui-monospace,Consolas,monospace;opacity:.8}
mark{background:var(--achado);color:inherit;border-radius:3px;padding:0 1px}
.midia{display:flex;align-items:center;gap:8px;padding:6px 8px;margin-bottom:3px;border-radius:8px;background:var(--painel2);font-size:13px}
.midia .ic{font-weight:700;color:var(--acento);font-size:11px;letter-spacing:.5px}
.midia small{color:var(--suave);font-family:ui-monospace,Consolas,monospace}
.evt{align-self:center;background:var(--evento);color:var(--suave);font-size:12px;padding:4px 12px;border-radius:10px;max-width:80%;text-align:center}
.evt small{opacity:.8}
#integ{position:fixed;inset:0;background:rgba(5,7,15,.88);z-index:40;display:flex;align-items:center;justify-content:center;padding:18px}
#integ .cx{background:var(--painel);border:1px solid var(--linha);border-radius:12px;width:min(1250px,100%);max-height:100%;display:flex;flex-direction:column;gap:8px;padding:14px 16px;min-height:0}
#integ h3{margin:0;font-size:16px}
#integ .topo2{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
#integ .res{display:flex;gap:6px 18px;flex-wrap:wrap;font-size:12.5px;color:var(--suave)}
#integ .res b{color:var(--texto)}
#integ .res .ruim{color:var(--acento);font-weight:700}
#integ .tw{overflow:auto;border:1px solid var(--linha);border-radius:8px;min-height:0}
#integ table{border-collapse:collapse;width:100%;font-size:12px}
#integ th,#integ td{padding:4px 9px;text-align:left;border-bottom:1px solid var(--linha);white-space:nowrap}
#integ th{position:sticky;top:0;background:var(--painel2);color:var(--suave)}
#integ td.mono{font-family:ui-monospace,Consolas,monospace;color:var(--suave)}
#integ tr.al td{background:rgba(255,74,85,.10)}
#integ .nota{font-size:11.5px;color:var(--suave)}
.foto{margin:2px 0 4px}
.foto img{display:block;max-width:min(320px,100%);max-height:300px;border-radius:8px;cursor:zoom-in;background:var(--painel2)}
#lb{position:fixed;inset:0;background:rgba(5,7,15,.92);z-index:50;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:16px}
#lb img{max-width:92vw;max-height:70vh;object-fit:contain;border-radius:6px;background:#000}
#lb .info{max-width:min(900px,94vw);flex:0 0 auto;background:var(--painel);border:1px solid var(--linha);border-radius:10px;padding:10px 14px;font-size:12.5px;color:var(--texto);display:block}
#lb .info div{margin:2px 0;overflow-wrap:anywhere}
#lb .info code{font-family:ui-monospace,Consolas,monospace;color:var(--suave)}
#lb .barra{display:flex;gap:8px;align-items:center;color:#fff;font-size:13px}
.player{margin:2px 0 4px}
.player audio{width:min(420px,100%);height:36px;display:block}
.arq{font-size:11px;color:var(--suave);margin-top:2px;overflow-wrap:anywhere}
.arq code{font-family:ui-monospace,Consolas,monospace}
.alerta{color:var(--acento);font-weight:600}
.transc{margin-top:4px;padding:6px 8px;border-left:3px solid var(--acento2);background:var(--painel2);border-radius:0 8px 8px 0;font-size:13px}
.transc .rot{display:block;font-size:10.5px;color:var(--suave);text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px}
.semarq{font-size:12px;color:var(--suave);font-style:italic}
.chk{display:flex;align-items:center;justify-content:flex-start;gap:6px;font-size:12px;color:var(--suave)}
.busca input[type=checkbox]{width:auto;margin:0}
a{color:var(--acento2)}
.rodape{padding:6px 16px;font-size:11px;color:var(--suave);border-top:1px solid var(--linha);background:var(--painel)}
.global{border-top:1px solid var(--linha);max-height:34%;overflow:auto}
.hit{padding:7px 12px;border-bottom:1px solid var(--linha);cursor:pointer;font-size:12px}
.hit:hover{background:var(--painel2)}
.hit b{display:block}
.hit span{color:var(--suave)}
@media (max-width:820px){
  main{grid-template-columns:1fr}
  aside{max-height:42vh;border-right:0;border-bottom:1px solid var(--linha)}
  .m{max-width:94%}
}
</style>
</head>
<body>
<header class="topo">
  <h1>Visualizador <span id="plat">WhatsApp</span> · mensagens, áudios e imagens</h1>
  <div class="info" id="info"></div>
  <label class="ctl">Fuso
    <select id="fuso" title="As datas do banco estão em UTC; escolha como exibir"></select>
  </label>
  <button id="btnint" title="Hash, formato, tamanho e alterações dos arquivos de mídia">Integridade</button>
  <button id="tema" title="Alternar tema claro/escuro">Tema</button>
</header>
<main>
  <aside>
    <div class="busca">
      <input type="search" id="q" placeholder="Filtrar conversas por nome ou número">
      <div class="abas" id="abas">
        <button data-f="todas" class="on">Todas</button>
        <button data-f="ind">Individuais</button>
        <button data-f="grp">Grupos</button>
      </div>
      <div class="linha2">Ordenar
        <select id="ordem">
          <option value="recente">Mais recente primeiro</option>
          <option value="antiga">Mais antiga primeiro</option>
          <option value="mais">Mais mensagens</option>
          <option value="nome">Nome (A-Z)</option>
        </select>
      </div>
      <div class="linha2">Mostrar
        <select id="somidia">
          <option value="">Todas as conversas</option>
          <option value="audio">Só com áudio para ouvir</option>
          <option value="img">Só com imagem para ver</option>
        </select>
      </div>
      <input type="search" id="qg" placeholder="Buscar texto em TODAS as conversas (Enter)">
    </div>
    <div id="globalres" class="global" hidden></div>
    <div id="lista"></div>
  </aside>
  <section class="painel">
    <div class="cab" id="cab" hidden>
      <h2 id="cnome"></h2>
      <div class="meta" id="cmeta"></div>
      <details id="part" hidden>
        <summary id="partsum"></summary>
        <div id="partcorpo"></div>
      </details>
      <div class="ferr">
        <input type="search" id="qc" placeholder="Buscar nesta conversa">
        <span id="qcount" class="ctl"></span>
        <button id="prev" title="Resultado anterior">&uarr;</button>
        <button id="next" title="Próximo resultado">&darr;</button>
        <select id="filtro">
          <option value="todas">Todas as mensagens</option>
          <option value="texto">Só texto</option>
          <option value="enviadas">Só enviadas</option>
          <option value="recebidas">Só recebidas</option>
          <option value="midia">Só mídia (imagem, vídeo, áudio)</option>
          <option value="audios">Só áudios (todos)</option>
          <option value="audiosok">Só áudios com arquivo na pasta</option>
          <option value="imagens">Só imagens (todas)</option>
          <option value="imagensok">Só imagens com arquivo na pasta</option>
          <option value="transc">Só áudios com transcrição</option>
          <option value="links">Só links</option>
          <option value="dados">Só com CPF, telefone ou e-mail</option>
          <option value="cpf">Só com CPF (possível)</option>
          <option value="tel">Só com número de telefone (possível)</option>
          <option value="email">Só com e-mail</option>
          <option value="eventos">Só eventos</option>
          <option value="semdata">Só sem data</option>
        </select>
        <label class="ctl">Ir para <input type="date" id="irdia"></label>
        <button id="ini">Início</button>
        <button id="fim">Fim</button>
        <button id="csv" class="pri">Exportar CSV</button>
      </div>
      <div class="aviso" id="aviso" hidden></div>
    </div>
    <div id="msgs"><div class="vazio">Escolha uma conversa na lista à esquerda.</div></div>
    <div class="rodape" id="rodape"></div>
  </section>
</main>
<div id="lb" hidden></div>
<div id="integ" hidden></div>
<script>
"use strict";
const $ = (id) => document.getElementById(id);
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const dobrar = (s) => (s || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
const pad = (n) => String(n).padStart(2, "0");
const store = {
  get(k, d){ try { const v = localStorage.getItem(k); return v === null ? d : v; } catch(e){ return d; } },
  set(k, v){ try { localStorage.setItem(k, v); } catch(e){} },
};
let fuso = parseInt(store.get("fuso", "-3"), 10);
let conversas = [], atual = null, dados = null, filtroAba = "todas", achados = [], idxAchado = -1;

function dt(t){ return new Date((t + fuso * 3600) * 1000); }
function fData(t){ const d = dt(t); return pad(d.getUTCDate()) + "/" + pad(d.getUTCMonth()+1) + "/" + d.getUTCFullYear(); }
function fHora(t){ const d = dt(t); return pad(d.getUTCHours()) + ":" + pad(d.getUTCMinutes()) + ":" + pad(d.getUTCSeconds()); }
function fCompleta(t){ return t == null ? "sem data" : fData(t) + " " + fHora(t); }
function diaChave(t){ const d = dt(t); return d.getUTCFullYear() + "-" + pad(d.getUTCMonth()+1) + "-" + pad(d.getUTCDate()); }
const SEMANA = ["domingo","segunda","terça","quarta","quinta","sexta","sábado"];
function fDiaLongo(t){ return SEMANA[dt(t).getUTCDay()] + ", " + fData(t); }

async function api(caminho){ const r = await fetch(caminho); if (!r.ok) throw new Error(caminho + " -> " + r.status); return r.json(); }

function montarFusos(){
  const s = $("fuso");
  for (let h = -12; h <= 14; h++){
    const o = el("option", null, "UTC" + (h >= 0 ? "+" : "") + h + (h === -3 ? "  (Brasília)" : h === 0 ? "  (como está no banco)" : ""));
    o.value = h; if (h === fuso) o.selected = true; s.appendChild(o);
  }
  s.onchange = () => { fuso = parseInt(s.value, 10); store.set("fuso", fuso); renderLista(); if (dados) renderMensagens(true); };
}

async function iniciar(){
  montarFusos();
  const tema = store.get("tema", "");
  if (tema) document.documentElement.dataset.tema = tema;
  $("tema").onclick = () => {
    const novo = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
    document.documentElement.dataset.tema = novo; store.set("tema", novo);
  };
  const info = await api("/api/info");
  campoData = info.campo_data;
  $("btnint").onclick = abrirIntegridade;
  $("plat").textContent = info.plataforma === "android" ? "WhatsApp Android" : "WhatsApp iOS";
  document.title = "Visualizador " + $("plat").textContent;
  const i = $("info");
  const add = (rot, val, extra) => { const s = el("span"); s.append(rot + ": "); s.append(el("b", null, val)); if (extra) s.title = extra; i.appendChild(s); };
  add("Banco", info.arquivo);
  add("Conversas", String(info.conversas) + " (" + info.grupos + " grupos)");
  add("Mensagens", info.mensagens.toLocaleString("pt-BR"));
  add("Datas", info.mensagens_datadas.toLocaleString("pt-BR") + " reais · " + info.mensagens_sem_data.toLocaleString("pt-BR") + " sem data",
      "Mensagens sem data real: valor removido/alterado pela anonimização do banco" + (info.primeira ? "\nPeríodo das datas reais: " + fData(info.primeira) + " a " + fData(info.ultima) : ""));
  add("Áudios", info.audios_com_arquivo + " para ouvir / " + info.audios + " no banco",
      "Só parte dos arquivos de mídia foi extraída para a pasta Media. Os demais áudios existem como registro no banco, mas sem o arquivo.");
  add("Imagens", info.imagens_com_arquivo + " para ver / " + info.imagens + " no banco" + (info.imagens_ext_errada ? " · " + info.imagens_ext_errada + " com extensão errada" : ""),
      "Só parte dos arquivos de mídia foi extraída para a pasta Media. As demais imagens existem como registro no banco, sem o arquivo.");
  if (info.hash_confere !== null && info.hash_confere !== undefined)
    add("Hash do banco", info.hash_confere ? "confere com o informado" : "NÃO CONFERE com o informado", "SHA-256 calculado agora comparado com o valor passado em --hash-banco");
  if (info.manifesto_aviso) add("Manifesto", info.manifesto_aviso);
  if (info.bloqueados && info.bloqueados.length) add("Bloqueados", info.bloqueados.join(", "), "Lista wa_block_list do banco de contatos");
  if (info.transc_meta) add("Transcrição", info.transcricoes + " (modelo " + info.transc_meta.modelo + ")", "Gerada automaticamente: pode conter erros");
  if (info.transc_aviso){
    const av = el("div", "aviso", "Transcrição: " + info.transc_aviso);
    av.style.margin = "0"; av.style.borderRadius = "0"; av.style.padding = "6px 16px";
    document.body.insertBefore(av, document.querySelector("main"));
  }
  const h = el("span", "hash"); h.append("SHA-256: "); const hb = el("b", null, info.sha256.slice(0, 12) + "…"); h.append(hb);
  h.title = "Clique para copiar o SHA-256 completo\n" + info.sha256;
  h.onclick = () => { try { navigator.clipboard.writeText(info.sha256); hb.textContent = "copiado"; setTimeout(() => hb.textContent = info.sha256.slice(0,12)+"…", 1200); } catch(e){} };
  i.appendChild(h);
  conversas = await api("/api/conversas");
  renderLista();
}

function ordenar(lista){
  const o = $("ordem").value;
  const c = [...lista];
  if (o === "nome") c.sort((a,b) => a.nome.localeCompare(b.nome, "pt-BR"));
  else if (o === "mais") c.sort((a,b) => b.n - a.n);
  else if (o === "antiga") c.sort((a,b) => (a.primeira ?? 9e15) - (b.primeira ?? 9e15));
  else c.sort((a,b) => (b.ultima ?? -1) - (a.ultima ?? -1) || b.n - a.n);
  return c;
}

function renderLista(){
  const alvo = dobrar($("q").value).trim();
  const soM = $("somidia").value;
  let l = conversas.filter(c => (filtroAba === "todas" || (filtroAba === "grp") === c.grupo)
      && (soM !== "audio" || c.n_audio_ok > 0) && (soM !== "img" || c.n_img_ok > 0)
      && (!alvo || dobrar(c.nome).includes(alvo) || c.jid.includes(alvo)));
  l = ordenar(l);
  const box = $("lista"); box.replaceChildren();
  if (!l.length){ box.appendChild(el("div", "vazio", "Nenhuma conversa encontrada.")); return; }
  const frag = document.createDocumentFragment();
  for (const c of l){
    const d = el("div", "conv" + (atual && atual.id === c.id ? " sel" : ""));
    const nome = el("div", "nome", c.nome);
    if (c.grupo) nome.appendChild(el("span", "tag", "grupo"));
    d.appendChild(nome);
    d.appendChild(el("div", "quando", c.ultima ? fData(c.ultima) : "sem data"));
    d.appendChild(el("div", "previa", c.previa));
    d.appendChild(el("div", "qtd", c.n.toLocaleString("pt-BR") + " msg"
      + (c.n_audio_ok ? " · " + c.n_audio_ok + " áudio" + (c.n_audio_ok > 1 ? "s" : "") + " ▶" : "")
      + (c.n_img_ok ? " · " + c.n_img_ok + " img" : "")));
    d.appendChild(el("div", "jid", c.jid + (c.n_datadas < c.n ? "  ·  " + (c.n - c.n_datadas) + " sem data" : "")));
    d.onclick = () => abrir(c.id);
    frag.appendChild(d);
  }
  box.appendChild(frag);
}

function renderParticipantes(){
  const det = $("part");
  if (!atual.grupo || !atual.membros){ det.hidden = true; return; }
  const ms = atual.membros, android = atual.plataforma === "android";
  det.hidden = false; det.open = false;
  const ativos = ms.filter(x => x.ativo === true).length;
  $("partsum").textContent = "Participantes do grupo (" + ms.length + (android ? "" : ": " + ativos + " marcados como ativos") + ")";
  const corpo = $("partcorpo"); corpo.replaceChildren();
  if (!ms.length){ corpo.appendChild(el("div", "nota", "Nenhum participante registrado no banco para este grupo.")); return; }
  const tw = el("div", "tw"), tb = el("table"), th = el("thead"), tr0 = el("tr");
  const cols = ["Nome", "Número / JID", "Papel", "Situação", "Msgs no grupo", "Primeira msg", "Última msg"];
  cols.forEach(c => tr0.appendChild(el("th", null, c))); th.appendChild(tr0); tb.appendChild(th);
  const tbody = el("tbody");
  for (const x of ms){
    const tr = el("tr");
    if (x.ativo === false) tr.className = "saiu";
    tr.appendChild(el("td", null, x.nome || (x.fora_da_lista ? "(fora da lista de participantes)" : "(sem nome salvo)")));
    const tdn = el("td", "num", x.numero || x.jid); tdn.title = x.jid; tr.appendChild(tdn);
    tr.appendChild(el("td", null, x.admin ? "admin" : "membro"));
    tr.appendChild(el("td", null, x.ativo === true ? "ativo" : x.ativo === false ? "não ativo" : "—"));
    tr.appendChild(el("td", null, String(x.n)));
    tr.appendChild(el("td", null, x.primeira != null ? fCompleta(x.primeira) : "—"));
    tr.appendChild(el("td", null, x.ultima != null ? fCompleta(x.ultima) : "—"));
    tbody.appendChild(tr);
  }
  tb.appendChild(tbody); tw.appendChild(tb); corpo.appendChild(tw);
  const nota = [];
  nota.push("Mensagens enviadas pelo dono do aparelho neste grupo: " + (atual.dono_n || 0) + " (ele não consta na lista de participantes).");
  if (atual.criador) nota.push("Criador do grupo (campo do banco): " + atual.criador + ".");
  if (!android) nota.push("\"não ativo\" é o campo ZISACTIVE = 0: é compatível com a pessoa ter saído ou sido removida, mas o banco não diz qual dos dois nem quando.");
  nota.push("Os números podem ter sufixo ~N: é efeito da anonimização (números diferentes que ficaram iguais), não faz parte do número real.");
  nota.push("Datas aparecem como \"—\" quando as mensagens do participante não têm data real.");
  for (const t of nota) corpo.appendChild(el("div", "nota", t));
  const bt = el("button", null, "Exportar participantes (CSV)");
  bt.onclick = () => {
    const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
    const linhas = [["nome","numero_ou_jid","papel","situacao","mensagens_no_grupo","primeira_msg","ultima_msg"].join(";")];
    for (const x of ms) linhas.push([x.nome, x.jid, x.admin ? "admin" : "membro", x.ativo === true ? "ativo" : x.ativo === false ? "nao_ativo" : "",
      x.n, x.primeira != null ? fCompleta(x.primeira) : "", x.ultima != null ? fCompleta(x.ultima) : ""].map(q).join(";"));
    const blob = new Blob(["\ufeff" + linhas.join("\r\n")], {type: "text/csv;charset=utf-8"});
    const a = el("a"); a.href = URL.createObjectURL(blob); a.download = "participantes_" + (atual.nome || "grupo").replace(/[^\w.-]+/g, "_").slice(0, 50) + ".csv";
    document.body.appendChild(a); a.click(); a.remove();
  };
  corpo.appendChild(bt);
}

async function abrir(id, focoMsg){
  dados = await api("/api/conversa/" + id);
  atual = dados.conversa;
  $("cab").hidden = false;
  $("cnome").textContent = atual.nome;
  $("qc").value = ""; $("filtro").value = "todas"; $("irdia").value = "";
  const meta = $("cmeta"); meta.replaceChildren();
  const add = (r, v) => { const s = el("span"); s.append(r + ": "); s.append(el("b", null, v)); meta.appendChild(s); };
  add("Tipo", atual.grupo ? "Grupo" : "Individual");
  add("Identificador", atual.jid);
  add("Mensagens", atual.n.toLocaleString("pt-BR"));
  const env = dados.mensagens.filter(m => m.eu).length;
  add("Enviadas / recebidas", env + " / " + (atual.n - env));
  if (atual.n_audio) add("Áudios", atual.n_audio + " (" + atual.n_audio_ok + " com arquivo para ouvir)");
  if (atual.n_img) add("Imagens", atual.n_img + " (" + atual.n_img_ok + " com arquivo para ver)");
  if (atual.primeira) add("Período (datas reais)", fData(atual.primeira) + " a " + fData(atual.ultima));
  renderParticipantes();
  const sem = atual.n - atual.n_datadas;
  const av = $("aviso");
  if (sem > 0){
    const semRec = dados.mensagens.filter(m => m.t == null && !m.eu).length;
    const semEnv = sem - semRec;
    av.hidden = false;
    av.textContent = sem.toLocaleString("pt-BR") + " de " + atual.n.toLocaleString("pt-BR") +
      " mensagens desta conversa não têm data real (" + semRec.toLocaleString("pt-BR") + " recebidas e " + semEnv.toLocaleString("pt-BR") +
      " enviadas): o valor foi removido/alterado na anonimização do banco. Elas aparecem na ordem do banco (ID), sem dia nem hora. " +
      "Não invente datas para elas no laudo; o intervalo mostrado no separador é só uma estimativa pela ordem.";
  } else av.hidden = true;
  renderLista();
  renderMensagens(false, focoMsg);
}

function passaFiltro(m, f){
  switch (f){
    case "texto": return m.tipo === 0;
    case "enviadas": return m.eu && m.tipo !== 6 && m.tipo !== 10;
    case "recebidas": return !m.eu && m.tipo !== 6 && m.tipo !== 10;
    case "midia": return m.tipo === 1 || m.tipo === 2 || m.tipo === 3;
    case "audios": return m.tipo === 3;
    case "audiosok": return m.tipo === 3 && !!m.midia;
    case "imagens": return m.tipo === 1;
    case "imagensok": return m.tipo === 1 && !!m.midia;
    case "transc": return m.tipo === 3 && !!m.transc;
    case "links": return m.tipo === 7;
    case "dados": case "cpf": case "tel": case "email": return acharDados(textoDaMsg(m), TIPOS_DADOS[f]).length > 0;
    case "eventos": return m.tipo === 6 || m.tipo === 10;
    case "semdata": return m.t == null;
    default: return true;
  }
}

// ---- busca de dados pessoais no texto (CPF, telefone, e-mail) ------------------------------
// São padrões de TEXTO: servem para achar candidatos. Confirme sempre lendo a mensagem.
const TIPOS_DADOS = {cpf:["cpf"], tel:["tel"], email:["email"], dados:["cpf","tel","email"]};
const ROT_DADO = {cpf:"possível CPF", tel:"possível telefone", email:"e-mail"};
let filtroDados = null;
function cpfValido(d){
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  for (const n of [9, 10]){
    let soma = 0;
    for (let i = 0; i < n; i++) soma += Number(d[i]) * (n + 1 - i);
    const dv = (soma * 10) % 11 % 10;
    if (dv !== Number(d[n])) return false;
  }
  return true;
}
function textoDaMsg(m){ return [m.texto, m.titulo, m.transc].filter(Boolean).join("\n"); }
function acharDados(texto, tipos){
  const out = [], cpfs = [];
  if (!texto) return out;
  const livre = (a, b) => !out.some(o => a < o[1] && b > o[0]);
  // CPF: 11 dígitos. Com pontos/traço (123.456.789-09) vale mesmo com dígito verificador errado; só com números, exige dígito verificador válido.
  for (const mt of texto.matchAll(/(?<![\d])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d])/g)){
    const dig = mt[0].replace(/\D/g, ""), formatado = /[.-]/.test(mt[0]);
    if (/^(\d)\1{10}$/.test(dig)) continue;
    if (formatado || cpfValido(dig)){
      cpfs.push([mt.index, mt.index + mt[0].length]);
      if (tipos.includes("cpf")) out.push([mt.index, mt.index + mt[0].length, "cpf"]);
    }
  }
  if (tipos.includes("email")){
    for (const mt of texto.matchAll(/[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g))
      if (livre(mt.index, mt.index + mt[0].length)) out.push([mt.index, mt.index + mt[0].length, "email"]);
  }
  if (tipos.includes("tel")){
    // A: com DDD (10 ou 11 dígitos, +55 opcional). B: só o número com separador, ex. 99999-1234.
    const rx = /(?<![\d])(?:\+?55[\s.-]?)?\(?0?\d{2}\)?[\s.-]?9?\d{4}[-.\s]?\d{4}(?![\d])|(?<![\d])9?\d{4}[-\s]\d{4}(?![\d])/g;
    for (const mt of texto.matchAll(rx)){
      const a = mt.index, b = a + mt[0].length;
      if (cpfs.some(c => a < c[1] && b > c[0])) continue;       // era um CPF, não telefone
      if (livre(a, b)) out.push([a, b, "tel"]);
    }
  }
  return out.sort((x, y) => x[0] - y[0]);
}
function realceDados(container, trecho, termo){
  if (!filtroDados || termo) return realce(container, trecho, termo);
  let ini = 0;
  for (const [a, b, t] of acharDados(trecho, filtroDados)){
    container.append(trecho.slice(ini, a));
    const mk = el("mark", "dado", trecho.slice(a, b)); mk.title = ROT_DADO[t]; container.appendChild(mk);
    ini = b;
  }
  container.append(trecho.slice(ini));
}

function realce(container, texto, termo){
  if (!termo){ container.textContent = texto; return; }
  const base = dobrar(texto);
  // dobrar() pode mudar o tamanho em casos raros; só realça se o comprimento bate
  if (base.length !== texto.length){ container.textContent = texto; return; }
  let ini = 0, pos;
  while ((pos = base.indexOf(termo, ini)) !== -1){
    container.append(texto.slice(ini, pos));
    container.appendChild(el("mark", null, texto.slice(pos, pos + termo.length)));
    ini = pos + termo.length;
  }
  container.append(texto.slice(ini));
}

function linkificar(container, texto, termo){
  const re = /https?:\/\/[^\s<>"']+/g;
  let ini = 0, mt;
  while ((mt = re.exec(texto)) !== null){
    if (mt.index > ini){ const sp = el("span"); realceDados(sp, texto.slice(ini, mt.index), termo); container.appendChild(sp); }
    const a = el("a", null, mt[0]); a.href = mt[0]; a.target = "_blank"; a.rel = "noopener noreferrer";
    container.appendChild(a); ini = mt.index + mt[0].length;
  }
  if (ini < texto.length){ const sp = el("span"); realceDados(sp, texto.slice(ini), termo); container.appendChild(sp); }
}

const ROTULO_TIPO = {1:"IMAGEM", 2:"VÍDEO", 3:"ÁUDIO", 4:"CONTATO", 5:"LOCALIZAÇÃO", 7:"LINK", 8:"DOCUMENTO"};
function fDur(s){ if (!s) return ""; s = Math.round(s); return Math.floor(s/60) + ":" + pad(s%60); }
function fTam(b){ if (!b) return ""; return b > 1048576 ? (b/1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b/1024)) + " KB"; }

function descEvento(m){
  // Significado exato de cada código não foi confirmado: mostramos o código e o texto bruto.
  const base = m.tipo === 6 ? "Evento de grupo" : "Evento do sistema";
  return base + " (tipo " + m.tipo + ", código " + (m.ev ?? 0) + ")";
}

function renderMensagens(manterScroll, focoMsg){
  if (!dados) return;
  const f = $("filtro").value, termo = dobrar($("qc").value).trim();
  filtroDados = TIPOS_DADOS[f] || null;
  const box = $("msgs"); const antes = box.scrollTop;
  box.replaceChildren();
  const todas = dados.mensagens;
  if (!todas._ant){
    const ant = new Array(todas.length), pos = new Array(todas.length); let u = null;
    for (let i = 0; i < todas.length; i++){ if (todas[i].t != null) u = todas[i].t; ant[i] = u; }
    u = null;
    for (let i = todas.length - 1; i >= 0; i--){ if (todas[i].t != null) u = todas[i].t; pos[i] = u; }
    todas._ant = ant; todas._pos = pos; todas._idx = new Map(todas.map((m, i) => [m.id, i]));
  }
  const lista = dados.mensagens.filter(m => passaFiltro(m, f));
  if (!lista.length){ box.appendChild(el("div", "vazio", "Nenhuma mensagem com este filtro.")); $("rodape").textContent = ""; achados = []; atualizarContagem(); return; }
  const frag = document.createDocumentFragment();
  let diaAtual = null, semAberto = false;
  achados = [];
  for (const m of lista){
    if (m.t != null){
      semAberto = false;
      const k = diaChave(m.t);
      if (k !== diaAtual){ diaAtual = k; frag.appendChild(el("div", "dia", fDiaLongo(m.t))); }
    } else if (!semAberto){
      semAberto = true; diaAtual = null;
      const i0 = todas._idx.get(m.id), a = todas._ant[i0], d = todas._pos[i0];
      let txt = "Mensagens sem data real (anonimização)";
      if (a != null && d != null) txt += " · pela ordem do banco, entre " + fCompleta(a) + " e " + fCompleta(d);
      else if (a != null) txt += " · pela ordem do banco, depois de " + fCompleta(a);
      else if (d != null) txt += " · pela ordem do banco, antes de " + fCompleta(d);
      const s = el("div", "dia sem", txt);
      s.title = "Estimativa pela posição (ID) no banco, não é data real. Valor bruto de " + campoData + " ausente ou inválido: não é uma data."; frag.appendChild(s);
    }
    if (m.tipo === 6 || m.tipo === 10){
      const e = el("div", "evt"); e.dataset.id = m.id;
      e.append(descEvento(m));
      if (m.texto){ e.append(" — "); const sp = el("span"); sp.textContent = m.texto; e.appendChild(sp); }
      e.appendChild(el("br")); e.appendChild(el("small", null, (m.t != null ? fCompleta(m.t) : "sem data") + " · #" + m.id + " · " + m.de));
      frag.appendChild(e); continue;
    }
    const w = el("div", "m " + (m.eu ? "eu" : "rec")); w.dataset.id = m.id;
    const b = el("div", "bolha");
    if (atual.grupo && !m.eu) b.appendChild(el("div", "quem", m.de));
    if (m.tipo !== 0 && ROTULO_TIPO[m.tipo]){
      const md = el("div", "midia");
      md.appendChild(el("span", "ic", ROTULO_TIPO[m.tipo]));
      const det = [];
      if (m.tipo === 4 && m.vcard) det.push(m.vcard);
      if (m.tipo === 5 && m.lat != null) det.push(m.lat.toFixed(5) + ", " + m.lon.toFixed(5));
      if (m.dur) det.push(fDur(m.dur));
      if (m.tam) det.push(fTam(m.tam));
      if (m.tipo === 7 && m.titulo) det.push(m.titulo);
      if (det.length) md.appendChild(el("span", null, det.join(" · ")));
      if (m.arquivo && m.tipo !== 7 && m.tipo !== 3) md.appendChild(el("small", null, m.arquivo));
      b.appendChild(md);
    }
    if (m.tipo === 3){
      if (m.midia){
        const pl = el("div", "player"); const au = el("audio"); au.controls = true; au.preload = "none"; au.src = m.midia.url;
        au.onplay = () => document.querySelectorAll("audio").forEach(x => { if (x !== au) x.pause(); });
        pl.appendChild(au); b.appendChild(pl);
        const ar = el("div", "arq");
        ar.append("Arquivo: "); ar.appendChild(el("code", null, m.arquivo || "")); ar.append(" · formato real: " + (m.midia.formato || "?") + " · " + fTam(m.midia.bytes));
        if (!m.midia.ext_confere){ ar.append(" · "); ar.appendChild(el("span", "alerta", "extensão não confere com o formato")); }
        ar.appendChild(el("br")); ar.append("SHA-256: "); ar.appendChild(el("code", null, m.midia.sha256));
        b.appendChild(ar);
        if (m.transc){
          const tr = el("div", "transc"); tr.appendChild(el("span", "rot", "Transcrição automática — pode conter erros; confira ouvindo o áudio"));
          const tx = el("span"); realce(tx, m.transc, termo); tr.appendChild(tx); b.appendChild(tr);
          if (termo && dobrar(m.transc).includes(termo)) { w.classList.add("achado"); achados.push(w); }
        }
      } else {
        b.appendChild(el("div", "semarq", m.arquivo ? "Arquivo deste áudio não está na pasta extraída (" + m.arquivo + ")." : "Sem arquivo registrado para este áudio."));
      }
    }
    if (m.tipo === 1){
      if (m.midia){
        const fig = el("div", "foto"); const im = el("img"); im.loading = "lazy"; im.src = m.midia.url; im.alt = "Imagem " + (m.arquivo || "");
        im.onclick = () => abrirFoto(m.id); fig.appendChild(im); b.appendChild(fig);
        const ar = el("div", "arq");
        ar.append("Arquivo: "); ar.appendChild(el("code", null, m.arquivo || "")); ar.append(" · formato real: " + (m.midia.formato || "?"));
        if (m.midia.dim) ar.append(" · " + m.midia.dim[0] + "×" + m.midia.dim[1]);
        ar.append(" · " + fTam(m.midia.bytes));
        if (!m.midia.ext_confere){ ar.append(" · "); ar.appendChild(el("span", "alerta", "extensão não confere com o formato")); }
        if (!m.midia.tam_confere){ ar.append(" · "); ar.appendChild(el("span", "alerta", "tamanho difere do registrado no banco (" + m.midia.tam_banco + " bytes)")); }
        b.appendChild(ar);
      } else {
        b.appendChild(el("div", "semarq", m.arquivo ? "Arquivo desta imagem não está na pasta extraída (" + m.arquivo + ")." : "Sem arquivo registrado para esta imagem."));
      }
    } else if (m.tipo === 2){
      b.appendChild(el("div", "semarq", "Vídeo: nenhum arquivo de vídeo foi extraído para a pasta" + (m.arquivo ? " (" + m.arquivo + ")" : "") + "."));
    }
    if (m.texto){
      const t = el("div", "txt"); linkificar(t, m.texto, termo); b.appendChild(t);
      if (termo && dobrar(m.texto).includes(termo)) { w.classList.add("achado"); achados.push(w); }
    } else if (termo && dobrar((m.titulo || "") + (m.vcard || "")).includes(termo)) { w.classList.add("achado"); achados.push(w); }
    else if (!m.texto && m.tipo === 0) b.appendChild(el("div", "txt", "(mensagem sem texto)"));
    const r = el("div", "rod");
    if (m.estrela) r.appendChild(el("span", null, "★"));
    const hora = el("span", null, m.t != null ? fHora(m.t) : "sem data");
    hora.title = m.t != null ? fCompleta(m.t) + " (UTC" + (fuso >= 0 ? "+" : "") + fuso + ")\n" + campoData + " bruto: " + m.raw
                             : "Sem data real. " + campoData + " bruto: " + m.raw;
    r.appendChild(hora);
    const idEl = el("span", "id", "#" + m.id); idEl.title = "Z_PK da mensagem em ZWAMESSAGE"; r.appendChild(idEl);
    b.appendChild(r); w.appendChild(b); frag.appendChild(w);
  }
  box.appendChild(frag);
  $("rodape").textContent = lista.length.toLocaleString("pt-BR") + " mensagens exibidas de " + dados.mensagens.length.toLocaleString("pt-BR") +
    " · Horários em UTC" + (fuso >= 0 ? "+" : "") + fuso + " · Passe o mouse na hora para ver o valor bruto do banco.";
  idxAchado = -1; atualizarContagem();
  if (focoMsg){ irParaMsg(focoMsg); }
  else if (manterScroll) box.scrollTop = antes;
  else box.scrollTop = 0;
}

let campoData = "ZMESSAGEDATE";
async function abrirIntegridade(){
  const box = $("integ"); box.replaceChildren(); box.hidden = false;
  box.onclick = (e) => { if (e.target === box) box.hidden = true; };
  const cx = el("div", "cx"); box.appendChild(cx);
  const d = await api("/api/integridade"), r = d.resumo;
  const top = el("div", "topo2"); top.appendChild(el("h3", null, "Integridade dos arquivos de mídia"));
  const csv = el("button", "pri", "Exportar CSV (serve de manifesto)"); csv.onclick = () => { location.href = "/api/integridade.csv"; };
  const fe = el("button", null, "Fechar"); fe.onclick = () => { box.hidden = true; };
  top.append(csv, fe); cx.appendChild(top);
  const res = el("div", "res");
  const add = (rot, val, ruim) => { const s = el("span"); s.append(rot + ": "); s.appendChild(el("b", ruim ? "ruim" : null, val)); res.appendChild(s); };
  add("Arquivos na pasta", String(r.total));
  add("Extensão errada", String(r.ext_errada), r.ext_errada > 0);
  add("Tamanho difere do banco", String(r.tam_difere), r.tam_difere > 0);
  if (r.vinculo_verificado) add("Sem mensagem que aponte para eles", String(r.sem_mensagem), r.sem_mensagem > 0);
  if (r.hash_banco.esperado) add("Hash do banco", r.hash_banco.confere ? "CONFERE com o informado" : "NÃO CONFERE com o informado", !r.hash_banco.confere);
  if (r.manifesto){ add("Manifesto: iguais", String(r.manifesto.igual)); add("ALTERADOS", String(r.manifesto.alterado), r.manifesto.alterado > 0);
    add("novos", String(r.manifesto.novo), r.manifesto.novo > 0); add("ausentes da pasta", String(r.manifesto.ausente), r.manifesto.ausente > 0); }
  cx.appendChild(res);
  if (d.aviso) cx.appendChild(el("div", "aviso", d.aviso));
  const lab = el("label", "chk"); const ck = el("input"); ck.type = "checkbox"; lab.append(ck, " Mostrar só arquivos com alerta"); cx.appendChild(lab);
  const tw = el("div", "tw"); cx.appendChild(tw);
  const desenhar = () => {
    tw.replaceChildren();
    const tb = el("table"), th = el("thead"), tr0 = el("tr");
    ["Arquivo", "Formato real", "Tamanho", "No banco", "Modificado no disco (UTC)", "Msgs", "Manifesto", "SHA-256", "Alertas"].forEach(c => tr0.appendChild(el("th", null, c)));
    th.appendChild(tr0); tb.appendChild(th);
    const body = el("tbody");
    for (const i of d.itens){
      if (ck.checked && !i.alertas.length) continue;
      const tr = el("tr"); if (i.alertas.length) tr.className = "al";
      tr.appendChild(el("td", "mono", i.arquivo));
      tr.appendChild(el("td", null, i.formato));
      tr.appendChild(el("td", null, i.bytes.toLocaleString("pt-BR")));
      tr.appendChild(el("td", null, i.tam_banco.length ? i.tam_banco.map(x => x.toLocaleString("pt-BR")).join(" / ") : "—"));
      tr.appendChild(el("td", null, i.modificado || "—"));
      tr.appendChild(el("td", null, r.vinculo_verificado ? String(i.mensagens) : "—"));
      tr.appendChild(el("td", null, i.manifesto || "—"));
      const h = el("td", "mono", i.sha256.slice(0, 16) + "…"); h.title = i.sha256; tr.appendChild(h);
      tr.appendChild(el("td", null, i.alertas.join("; ") || "—"));
      body.appendChild(tr);
    }
    for (const k of d.ausentes){ const tr = el("tr"); tr.className = "al"; tr.appendChild(el("td", "mono", k));
      for (let j = 0; j < 7; j++) tr.appendChild(el("td", null, "—")); tr.appendChild(el("td", null, "AUSENTE: consta no manifesto e não está na pasta")); body.appendChild(tr); }
    tb.appendChild(body); tw.appendChild(tb);
  };
  ck.onchange = desenhar; desenhar();
  const notas = ["O SHA-256 é calculado agora, a partir dos arquivos da pasta. Sem um manifesto ou hash de referência, o programa NÃO consegue dizer que um arquivo foi alterado: só aponta inconsistências (extensão, tamanho, vínculo com mensagem).",
    "\"Modificado no disco\" é a data do arquivo na cópia/extração que você abriu; ela costuma refletir a cópia, não o momento em que a mídia foi criada no aparelho.",
    "Para detectar alteração: exporte este CSV logo após a aquisição e, depois, abra o visualizador com --manifesto <esse.csv>."];
  for (const t of notas) cx.appendChild(el("div", "nota", t));
}
let fotos = [], fotoIdx = -1;
function abrirFoto(id){
  fotos = dados.mensagens.filter(m => m.tipo === 1 && m.midia);
  fotoIdx = fotos.findIndex(m => m.id === id); if (fotoIdx < 0) return;
  mostrarFoto();
}
function mostrarFoto(){
  const m = fotos[fotoIdx], lb = $("lb"); lb.replaceChildren(); lb.hidden = false;
  const barra = el("div", "barra");
  const ant = el("button", null, "←"); ant.onclick = (e) => { e.stopPropagation(); fotoIdx = (fotoIdx - 1 + fotos.length) % fotos.length; mostrarFoto(); };
  const prox = el("button", null, "→"); prox.onclick = (e) => { e.stopPropagation(); fotoIdx = (fotoIdx + 1) % fotos.length; mostrarFoto(); };
  const fec = el("button", "pri", "Fechar (Esc)"); fec.onclick = fecharFoto;
  barra.append(ant, el("span", null, (fotoIdx + 1) + " / " + fotos.length + " imagens desta conversa"), prox, fec);
  const im = el("img"); im.src = m.midia.url; im.alt = m.arquivo || ""; im.onclick = (e) => e.stopPropagation();
  const info = el("div", "info"); info.onclick = (e) => e.stopPropagation();
  const lin = (rot, val, cls) => { const d = el("div"); d.append(rot + ": "); const v = el(cls || "span", null, val); d.appendChild(v); info.appendChild(d); return d; };
  lin("Mensagem", "#" + m.id + " · " + (m.eu ? "enviada pelo dono" : "recebida de " + m.de) + " · " + (m.t != null ? fCompleta(m.t) + " (UTC" + (fuso >= 0 ? "+" : "") + fuso + ")" : "sem data real"));
  if (m.texto) lin("Legenda", m.texto);
  lin("Arquivo", m.arquivo || "", "code");
  lin("Formato real", (m.midia.formato || "?") + (m.midia.dim ? " · " + m.midia.dim[0] + "×" + m.midia.dim[1] + " px" : "") + " · " + fTam(m.midia.bytes) + " (" + m.midia.bytes + " bytes)");
  if (!m.midia.ext_confere) lin("Alerta", "a extensão do nome não confere com o formato real do arquivo").lastChild.className = "alerta";
  if (!m.midia.tam_confere) lin("Alerta", "tamanho do arquivo (" + m.midia.bytes + ") difere do registrado no banco (" + m.midia.tam_banco + "). Pode ser efeito da anonimização; confirme antes de concluir.").lastChild.className = "alerta";
  lin("SHA-256", m.midia.sha256, "code");
  if (m.midia.exif){
    const x = m.midia.exif; const partes = [];
    for (const [k, rot] of [["fabricante","fabricante"],["modelo","modelo"],["software","software"],["data_original","data original"],["data_digitalizada","data digitalizada"],["data_arquivo","data do arquivo"],["gps","GPS"]]) if (x[k]) partes.push(rot + ": " + x[k]);
    lin("EXIF", partes.join(" · ") + "  (datas do EXIF não trazem fuso)");
  } else lin("EXIF", "nenhum encontrado (ou o Pillow não está instalado: pip install pillow)");
  lb.append(barra, im, info);
  lb.onclick = fecharFoto;
}
function fecharFoto(){ $("lb").hidden = true; $("lb").replaceChildren(); }
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("integ").hidden){ $("integ").hidden = true; return; }
  if ($("lb").hidden) return;
  if (e.key === "Escape") fecharFoto();
  else if (e.key === "ArrowLeft"){ fotoIdx = (fotoIdx - 1 + fotos.length) % fotos.length; mostrarFoto(); }
  else if (e.key === "ArrowRight"){ fotoIdx = (fotoIdx + 1) % fotos.length; mostrarFoto(); }
});

function atualizarContagem(){
  $("qcount").textContent = achados.length ? (idxAchado + 1) + " / " + achados.length : ($("qc").value.trim() ? "0 resultados" : "");
}
function irAchado(delta){
  if (!achados.length) return;
  idxAchado = (idxAchado + delta + achados.length) % achados.length;
  achados[idxAchado].scrollIntoView({block: "center"});
  document.querySelectorAll(".m.foco").forEach(e => e.classList.remove("foco"));
  achados[idxAchado].classList.add("foco"); atualizarContagem();
}
function irParaMsg(id){
  const e = document.querySelector('[data-id="' + id + '"]');
  if (!e) return;
  e.scrollIntoView({block: "center"});
  e.classList.add("foco"); setTimeout(() => e.classList.remove("foco"), 3000);
}
function irParaDia(valor){
  if (!valor || !dados) return;
  for (const m of dados.mensagens){
    if (m.t != null && diaChave(m.t) >= valor){ $("filtro").value = "todas"; renderMensagens(false, m.id); return; }
  }
}

$("q").oninput = renderLista; $("ordem").onchange = renderLista; $("somidia").onchange = renderLista;
$("abas").onclick = (e) => { const b = e.target.closest("button"); if (!b) return;
  filtroAba = b.dataset.f; document.querySelectorAll("#abas button").forEach(x => x.classList.toggle("on", x === b)); renderLista(); };
let tBusca = null;
$("qc").oninput = () => { clearTimeout(tBusca); tBusca = setTimeout(() => { renderMensagens(false); if (achados.length) irAchado(1); }, 220); };
$("qc").onkeydown = (e) => { if (e.key === "Enter") irAchado(e.shiftKey ? -1 : 1); };
$("next").onclick = () => irAchado(1); $("prev").onclick = () => irAchado(-1);
$("filtro").onchange = () => renderMensagens(false);
$("irdia").onchange = (e) => irParaDia(e.target.value);
$("ini").onclick = () => { $("msgs").scrollTop = 0; };
$("fim").onclick = () => { const b = $("msgs"); b.scrollTop = b.scrollHeight; };
$("csv").onclick = () => { if (atual) location.href = "/api/csv/" + atual.id + "?fuso=" + fuso; };
$("qg").onkeydown = async (e) => {
  if (e.key !== "Enter") return;
  const q = $("qg").value.trim(); const box = $("globalres");
  if (q.length < 2){ box.hidden = true; return; }
  const r = await api("/api/busca?q=" + encodeURIComponent(q));
  box.replaceChildren(); box.hidden = false;
  const topo = el("div", "hit"); topo.appendChild(el("b", null, r.length + (r.length >= 300 ? "+" : "") + " resultado(s) para “" + q + "” (clique para abrir; clique aqui para fechar)"));
  topo.onclick = () => { box.hidden = true; }; box.appendChild(topo);
  for (const h of r){
    const d = el("div", "hit");
    d.appendChild(el("b", null, h.nome + (h.grupo ? " (grupo)" : "")));
    d.appendChild(el("span", null, (h.t != null ? fCompleta(h.t) : "sem data") + " · " + (h.eu ? "Você" : h.de) + ": " + h.trecho));
    d.onclick = () => abrir(h.conversa, h.id);
    box.appendChild(d);
  }
};
iniciar().catch(e => { document.body.prepend(el("div", "aviso", "Erro ao iniciar: " + e.message)); });
</script>
</body>
</html>
"""


class Manipulador(BaseHTTPRequestHandler):
    base = None

    def log_message(self, *a):  # silencioso
        pass

    def _enviar(self, corpo, tipo="application/json; charset=utf-8", cabecalhos=None, status=200):
        if isinstance(corpo, str):
            corpo = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (cabecalhos or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _servir_midia(self, chave):
        """Entrega um arquivo de mídia da pasta (só os que estão no índice), com Range para o player."""
        from urllib.parse import unquote
        chave = unquote(chave)
        caminho = self.base.arquivos.get(chave)      # só chaves conhecidas: bloqueia ../
        if caminho is None:
            return self._json({"erro": "arquivo não encontrado"}, 404)
        tam = caminho.stat().st_size
        tipo = tipo_http(caminho, self.base.info_arquivo[chave]["formato"])
        ini, fim, status = 0, tam - 1, 200
        rng = self.headers.get("Range")
        if rng:
            mt = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if mt and (mt.group(1) or mt.group(2)):
                if mt.group(1):
                    ini = int(mt.group(1))
                    fim = int(mt.group(2)) if mt.group(2) else tam - 1
                else:                                 # bytes=-N : últimos N bytes
                    ini = max(0, tam - int(mt.group(2)))
                fim = min(fim, tam - 1)
                if ini > fim:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % tam)
                    self.end_headers()
                    return
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fim - ini + 1))
        self.send_header("Cache-Control", "no-store")
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (ini, fim, tam))
        self.end_headers()
        with open(caminho, "rb") as f:
            f.seek(ini)
            restante = fim - ini + 1
            while restante > 0:
                bloco = f.read(min(65536, restante))
                if not bloco:
                    break
                self.wfile.write(bloco)
                restante -= len(bloco)

    def _json(self, obj, status=200):
        self._enviar(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), status=status)

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        b = self.base
        try:
            if p == "/":
                self._enviar(PAGINA, "text/html; charset=utf-8")
            elif p.startswith("/media/"):
                self._servir_midia(p[len("/media/"):])
            elif p == "/api/info":
                self._json(b.info())
            elif p == "/api/integridade":
                self._json(b.integridade())
            elif p == "/api/integridade.csv":
                self._enviar(b.csv_integridade(), "text/csv; charset=utf-8",
                             {"Content-Disposition": 'attachment; filename="integridade_arquivos.csv"'})
            elif p == "/api/conversas":
                self._json(b.lista_conversas())
            elif re.fullmatch(r"/api/conversa/\d+", p):
                r = b.conversa(int(p.rsplit("/", 1)[1]))
                self._json(r) if r else self._json({"erro": "conversa não encontrada"}, 404)
            elif p == "/api/busca":
                self._json(b.busca_global(q.get("q", [""])[0]))
            elif re.fullmatch(r"/api/csv/\d+", p):
                fuso = int(q.get("fuso", ["-3"])[0])
                sid = int(p.rsplit("/", 1)[1])
                corpo = b.csv_conversa(sid, fuso)
                if corpo is None:
                    self._json({"erro": "conversa não encontrada"}, 404)
                else:
                    nome = re.sub(r"[^\w.-]+", "_", b.sessoes[sid]["nome"])[:50] or "conversa"
                    self._enviar(corpo, "text/csv; charset=utf-8",
                                 {"Content-Disposition": 'attachment; filename="conversa_%s_%d.csv"' % (nome, sid)})
            else:
                self._json({"erro": "não encontrado"}, 404)
        except (ValueError, KeyError) as e:
            self._json({"erro": str(e)}, 400)


def main():
    ap = argparse.ArgumentParser(description="Visualizador local de conversas de WhatsApp (iOS e Android). Só leitura.")
    ap.add_argument("--pasta", help="Pasta com o banco (ChatStorage*.sqlite ou msgstore*.db) e os contatos; a mídia é procurada em <pasta>/Media/files")
    ap.add_argument("--db", help="Caminho do banco: ChatStorage*.sqlite (iOS) ou msgstore*.db (Android)")
    ap.add_argument("--contatos", help="Contacts*.sqlite (iOS) ou wa*.db (Android) - nomes e bloqueados (opcional)")
    ap.add_argument("--midia", help="Pasta Media/files (com Audio/ e Image/). Padrão: <pasta>/Media/files")
    ap.add_argument("--transcricoes", help="JSON gerado por transcrever_audios.py (opcional)")
    ap.add_argument("--hash-banco", help="SHA-256 do banco registrado na aquisição: o programa compara com o calculado e avisa se NÃO confere")
    ap.add_argument("--manifesto", help="CSV de referência com 'arquivo' e 'sha256' (gerado pelo painel Integridade): aponta arquivos ALTERADOS, novos e ausentes")
    ap.add_argument("--porta", type=int, default=8765, help="Porta local (padrão 8765). Mude se já estiver em uso")
    ap.add_argument("--sem-navegador", action="store_true", help="Não abre o navegador sozinho")
    a = ap.parse_args()

    db, contatos, midia = a.db, a.contatos, a.midia
    if a.pasta:
        pasta = Path(a.pasta)
        if not db:
            achados = sorted(pasta.glob("ChatStorage*.sqlite")) or sorted(pasta.glob("msgstore*.db"))
            db = str(achados[0]) if achados else None
        if not contatos:
            achados = sorted(pasta.glob("Contacts*.sqlite")) or (sorted(pasta.glob("wa*.db")) if db and Path(db).name.startswith("msgstore") else [])
            contatos = str(achados[0]) if achados else None
        if not midia and (pasta / "Media" / "files").is_dir():
            midia = str(pasta / "Media" / "files")
    if not db or not Path(db).exists():
        ap.error("Informe --pasta (com o ChatStorage ou o msgstore) ou --db com o caminho do banco.")

    print("Lendo %s (somente leitura) ..." % db)
    Manipulador.base = Base(db, contatos, midia, a.transcricoes, a.hash_banco, a.manifesto)
    i = Manipulador.base.info()
    print("  Banco reconhecido como WhatsApp %s" % ("Android" if i["plataforma"] == "android" else "iOS"))
    print("  %d conversas, %d mensagens (%d sem data real)" % (i["conversas"], i["mensagens"], i["mensagens_sem_data"]))
    print("  SHA-256 do banco: %s" % i["sha256"])
    print("  Áudios: %d mensagens, %d com arquivo na pasta, %d transcrições carregadas"
          % (i["audios"], i["audios_com_arquivo"], i["transcricoes"]))
    print("  Imagens: %d mensagens, %d com arquivo na pasta (%d arquivos)"
          % (i["imagens"], i["imagens_com_arquivo"], i["arquivos_imagem"]))
    if i["transc_aviso"]:
        print("  ATENÇÃO: " + i["transc_aviso"])
    if i["manifesto_aviso"]:
        print("  ATENÇÃO: " + i["manifesto_aviso"])
    if i["hash_confere"] is not None:
        print("  Hash do banco: %s" % ("CONFERE com o informado" if i["hash_confere"] else "NÃO CONFERE com o informado (!)"))

    srv = ThreadingHTTPServer(("127.0.0.1", a.porta), Manipulador)
    url = "http://127.0.0.1:%d/" % a.porta
    print("\nAbra no navegador: %s\n(Ctrl+C para encerrar)" % url)
    if not a.sem_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    sys.exit(main())
