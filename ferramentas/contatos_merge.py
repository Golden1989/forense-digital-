#!/usr/bin/env python3
"""contatos_merge.py - junta contatos, chamadas e SMS de uma imagem Android.

Cruza, pelo numero de telefone:
  contacts2.db (raw_contacts + data + mimetypes + accounts)   -> quem e o contato
  calllog.db ou contacts2.db (tabela calls)                    -> chamadas
  mmssms.db (tabela sms)                                       -> mensagens

Para cada contato (raw_contacts agrupados pelo contact_id) mostra: nome, telefones, e-mails, conta de origem, se esta
marcado como apagado/na lixeira, apps ligados ao contato (WhatsApp, Signal,
Telegram...), e, por numero: quantidade, primeira e ultima chamada / SMS.
No fim lista os NUMEROS QUE APARECEM EM CHAMADAS/SMS MAS NAO ESTAO NA AGENDA.

Uso:
    python contatos_merge.py --contacts contacts2.db
    python contatos_merge.py --contacts contacts2.db --calls calllog.db --sms mmssms.db --fuso -3
    python contatos_merge.py --contacts contacts2.db --calls calllog.db --sms mmssms.db --csv contatos.csv
    python contatos_merge.py --contacts contacts2.db --so-apagados

Cada banco e COPIADO (com -wal e -shm). No Samsung, contacts2.db e calllog.db
ficam em com.samsung.android.providers.contacts/databases; no Android puro,
as chamadas ficam dentro do proprio contacts2.db (tabela calls).

Casamento de numeros: so os digitos, comparando os ULTIMOS 9 (ignora +55, DDD
com zero, etc.). Numeros curtos (ex.: 611) so casam se forem identicos.
Datas: milissegundos Unix. O significado de last_time_contacted/times_contacted
varia por versao do Android: confira antes de afirmar.
"""
import argparse
import csv
import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
TIPO_CHAMADA = {1: "recebida", 2: "feita", 3: "perdida", 4: "correio de voz", 5: "rejeitada", 6: "bloqueada"}
TIPO_SMS = {1: "recebido", 2: "enviado", 3: "rascunho", 4: "caixa de saida", 5: "falha", 6: "fila"}


def ler_fuso(texto):
    t = texto.strip().lower().replace("utc", "")
    if t in ("", "z"):
        return UTC, "UTC"
    horas = float(t)
    return timezone(timedelta(hours=horas)), f"UTC{horas:+g}"


def data_ms(v, fuso):
    """Milissegundos Unix (ou segundos, se o numero for pequeno) -> texto. Vazio se 0/None."""
    if not v:
        return ""
    seg = v / 1000 if v > 1e11 else v
    try:
        return datetime.fromtimestamp(seg, UTC).astimezone(fuso).strftime("%Y-%m-%d %H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return str(v)


def copiar_banco(caminho, pasta_tmp):
    origem = Path(caminho)
    for sufixo in ("", "-wal", "-shm"):
        arq = origem.with_name(origem.name + sufixo)
        if arq.exists():
            shutil.copy2(arq, Path(pasta_tmp) / arq.name)
    return Path(pasta_tmp) / origem.name


def chave_numero(numero):
    """So digitos; numeros longos ficam com os ultimos 9 (casa +55 11 9..., 011 9..., 9...)."""
    d = re.sub(r"\D", "", numero or "")
    return d[-9:] if len(d) > 9 else d


def tem_tabela(con, nome):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (nome,)).fetchone() is not None


def resumo_eventos(eventos, fuso, nomes_tipo):
    """eventos: lista de (tempo_ms, tipo). Devolve texto 'N (primeira ... | ultima ...)'."""
    if not eventos:
        return ""
    eventos = sorted(eventos)
    tipos = defaultdict(int)
    for _, t in eventos:
        tipos[nomes_tipo.get(t, f"tipo {t}")] += 1
    detalhe = ", ".join(f"{k}={n}" for k, n in tipos.items())
    return (f"{len(eventos)} [{detalhe}] primeira {data_ms(eventos[0][0], fuso)} | "
            f"ultima {data_ms(eventos[-1][0], fuso)}")


def main():
    ap = argparse.ArgumentParser(description="Contatos + chamadas + SMS")
    ap.add_argument("--contacts", required=True, help="contacts2.db")
    ap.add_argument("--calls", help="calllog.db (ou outro banco com tabela calls)")
    ap.add_argument("--sms", help="mmssms.db")
    ap.add_argument("--fuso", default="utc", help="'utc' (padrao) ou horas (-3)")
    ap.add_argument("--so-apagados", action="store_true", help="so contatos marcados como apagados/na lixeira")
    ap.add_argument("--csv", help="salva a tabela de contatos neste CSV")
    args = ap.parse_args()
    fuso, nome_fuso = ler_fuso(args.fuso)

    with tempfile.TemporaryDirectory() as tmp:
        con = sqlite3.connect(copiar_banco(args.contacts, tmp))
        cols = {r[1] for r in con.execute("PRAGMA table_info(raw_contacts)")}
        if not cols:
            raise SystemExit("Tabela raw_contacts nao encontrada: isto nao parece um contacts2.db.")
        extra = lambda c: f"r.{c}" if c in cols else "NULL"
        contatos = con.execute(
            f"SELECT r._id, r.display_name, r.deleted, {extra('sec_in_trash')}, {extra('creation_time')}, {extra('contact_id')}, "
            f"{extra('last_time_contacted')}, {extra('times_contacted')}, {extra('starred')}, "
            f"a.account_name, a.account_type FROM raw_contacts r LEFT JOIN accounts a ON a._id = r.account_id "
            f"ORDER BY r._id").fetchall()
        dados = con.execute(
            "SELECT d.raw_contact_id, m.mimetype, d.data1, d.data4 FROM data d "
            "JOIN mimetypes m ON m._id = d.mimetype_id").fetchall()
        chamadas_no_contacts = []
        if tem_tabela(con, "calls"):
            chamadas_no_contacts = con.execute("SELECT number, date, type FROM calls").fetchall()
        con.close()

        chamadas = list(chamadas_no_contacts)
        if args.calls:
            c2 = sqlite3.connect(copiar_banco(args.calls, tmp))
            if tem_tabela(c2, "calls"):
                chamadas += c2.execute("SELECT number, date, type FROM calls").fetchall()
            else:
                print("[aviso] a tabela 'calls' nao existe neste banco; se houver -wal ao lado, "
                      "confira se foi copiado junto.")
            c2.close()
        sms = []
        if args.sms:
            c3 = sqlite3.connect(copiar_banco(args.sms, tmp))
            if tem_tabela(c3, "sms"):
                sms = c3.execute("SELECT address, date, type FROM sms").fetchall()
            c3.close()

    # organiza dados por contato
    tel, mail, apps = defaultdict(list), defaultdict(list), defaultdict(set)
    for rid, mime, d1, d4 in dados:
        if mime.endswith("/phone_v2") and d1:
            tel[rid].append(d1)
        elif mime.endswith("/email_v2") and d1:
            mail[rid].append(d1)
        elif any(k in mime.lower() for k in ("whatsapp", "securesms", "telegram", "viber", "messenger", "instagram")):
            apps[rid].add(mime.split("/")[-1])

    por_chamada, por_sms = defaultdict(list), defaultdict(list)
    for num, dt, tp in chamadas:
        por_chamada[chave_numero(num)].append((dt, tp))
    for num, dt, tp in sms:
        por_sms[chave_numero(num)].append((dt, tp))

    # Um mesmo contato aparece como VARIOS raw_contacts (um por conta: telefone, Google, Signal...).
    # Agrupa pelo contact_id para nao contar a mesma pessoa e as mesmas chamadas duas vezes.
    grupos = {}
    for rid, nome, apagado, lixeira, criado, cid, ult, vezes, estrela, conta, tipo_conta in contatos:
        g = grupos.setdefault(cid if cid else f"raw{rid}", {
            "ids": [], "nomes": [], "tel": [], "mail": [], "contas": [], "apps": set(),
            "apagado": False, "lixeira": False, "criado": [], "ult": [], "vezes": 0})
        g["ids"].append(rid)
        if nome and nome not in g["nomes"]:
            g["nomes"].append(nome)
        g["tel"] += [n for n in tel[rid] if n not in g["tel"]]
        g["mail"] += [m for m in mail[rid] if m not in g["mail"]]
        txt = f"{conta or ''} ({tipo_conta or ''})"
        if txt not in g["contas"]:
            g["contas"].append(txt)
        g["apps"] |= apps[rid]
        g["apagado"] |= bool(apagado)
        g["lixeira"] |= bool(lixeira)
        g["criado"].append(criado or 0)
        g["ult"].append(ult or 0)
        g["vezes"] += vezes or 0

    conhecidos, linhas = set(), []
    for cid, g in grupos.items():
        chaves = {chave_numero(n) for n in g["tel"] if chave_numero(n)}
        conhecidos |= chaves
        ev_c = [e for k in chaves for e in por_chamada.get(k, [])]
        ev_s = [e for k in chaves for e in por_sms.get(k, [])]
        status = (["APAGADO"] if g["apagado"] else []) + (["NA LIXEIRA"] if g["lixeira"] else [])
        menor_criado = min((c for c in g["criado"] if c), default=0)
        linhas.append({
            "contact_id": cid, "raw_contacts": ",".join(map(str, g["ids"])),
            "nome": " / ".join(g["nomes"]) or "(sem nome)", "telefones": "; ".join(g["tel"]),
            "emails": "; ".join(g["mail"]), "contas": " + ".join(g["contas"]),
            "status": ",".join(status), "apps": ",".join(sorted(g["apps"])),
            f"criado ({nome_fuso})": data_ms(menor_criado, fuso),
            f"ultimo_contato_agenda ({nome_fuso})": data_ms(max(g["ult"]), fuso), "vezes_agenda": g["vezes"],
            "chamadas": resumo_eventos(ev_c, fuso, TIPO_CHAMADA), "sms": resumo_eventos(ev_s, fuso, TIPO_SMS),
        })

    mostrar = [l for l in linhas if l["status"]] if args.so_apagados else linhas
    print(f"Contatos (agrupados por contact_id): {len(linhas)} (raw_contacts: {len(contatos)}) | apagados/lixeira: {sum(1 for l in linhas if l['status'])}"
          f" | chamadas: {len(chamadas)} | SMS: {len(sms)} | horarios em {nome_fuso}\n")
    for l in mostrar:
        marca = f"  [{l['status']}]" if l["status"] else ""
        print(f"#{l['contact_id']} {l['nome']}{marca}   (raw_contacts: {l['raw_contacts']})")
        print(f"    telefones: {l['telefones'] or '-'}" + (f" | e-mails: {l['emails']}" if l["emails"] else ""))
        print(f"    contas: {l['contas']}" + (f" | apps: {l['apps']}" if l["apps"] else ""))
        if l[f"criado ({nome_fuso})"]:
            print(f"    criado na agenda: {l[f'criado ({nome_fuso})']}")
        if l["chamadas"]:
            print(f"    chamadas: {l['chamadas']}")
        if l["sms"]:
            print(f"    SMS: {l['sms']}")

    # numeros fora da agenda
    if not args.so_apagados:
        fora = {}
        for origem, mapa, nomes in (("chamadas", por_chamada, TIPO_CHAMADA), ("SMS", por_sms, TIPO_SMS)):
            for k, ev in mapa.items():
                if k and k not in conhecidos:
                    fora.setdefault(k, {})[origem] = resumo_eventos(ev, fuso, nomes)
        print(f"\nNUMEROS EM CHAMADAS/SMS QUE NAO ESTAO NA AGENDA: {len(fora)}")
        for k, d in sorted(fora.items()):
            print(f"  ...{k}")
            for origem, texto in d.items():
                print(f"      {origem}: {texto}")

    if args.csv and linhas:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(mostrar)
        print(f"\nCSV salvo em: {args.csv}")


if __name__ == "__main__":
    main()
