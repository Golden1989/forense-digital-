"""Gera bancos SQLite e XML sinteticos (nenhum dado real) para os testes em
test_ferramentas.py. Nada aqui e evidencia: nomes, numeros e URLs sao ficticios.
"""
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

UTC = timezone.utc
EPOCA_WEBKIT = datetime(1601, 1, 1, tzinfo=UTC)


def unix_ms(ano, mes, dia, hora=12, minuto=0):
    """Data -> milissegundos Unix (formato Android: SMS, chamadas, packages.xml)."""
    return int(datetime(ano, mes, dia, hora, minuto, tzinfo=UTC).timestamp() * 1000)


def webkit_us(ano, mes, dia, hora=12, minuto=0):
    """Data -> microssegundos desde 1601 (formato Chrome/WebKit)."""
    delta = datetime(ano, mes, dia, hora, minuto, tzinfo=UTC) - EPOCA_WEBKIT
    return int(delta.total_seconds() * 1_000_000)


def criar_mmssms_db(caminho):
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE sms (_id INTEGER PRIMARY KEY, address TEXT, date INTEGER, type INTEGER, body TEXT)")
    con.executemany("INSERT INTO sms (address, date, type, body) VALUES (?, ?, ?, ?)", [
        ("+5511999990001", unix_ms(2025, 11, 1, 9, 0), 1, "oi, chegou?"),
        ("+5511999990001", unix_ms(2025, 11, 1, 9, 5), 2, "cheguei sim"),
        ("+5511999990002", unix_ms(2025, 11, 2, 20, 30), 1, "liga pra mim"),
    ])
    con.commit()
    con.close()


def criar_calllog_db(caminho):
    con = sqlite3.connect(caminho)
    con.execute("CREATE TABLE calls (_id INTEGER PRIMARY KEY, number TEXT, date INTEGER, duration INTEGER, type INTEGER)")
    con.executemany("INSERT INTO calls (number, date, duration, type) VALUES (?, ?, ?, ?)", [
        ("+5511999990001", unix_ms(2025, 11, 1, 8, 50), 120, 2),
        ("+5511999990002", unix_ms(2025, 11, 2, 20, 25), 0, 3),
    ])
    con.commit()
    con.close()


def criar_packages_xml(caminho):
    raiz = ET.Element("packages")

    def pacote(nome, code_path, it_ms, ut_ms, instalador="", perms=()):
        p = ET.SubElement(raiz, "package", {
            "name": nome, "codePath": code_path,
            "it": format(it_ms, "x"), "ut": format(ut_ms, "x"), "installer": instalador,
        })
        if perms:
            bloco = ET.SubElement(p, "perms")
            for nome_perm, concedida in perms:
                ET.SubElement(bloco, "item", {"name": nome_perm, "granted": "true" if concedida else "false"})

    pacote("com.android.systemui", "/system/app/SystemUI", unix_ms(2024, 1, 1), unix_ms(2024, 1, 1))
    pacote("com.exemplo.mensageiro", "/data/app/com.exemplo.mensageiro-1",
           unix_ms(2025, 10, 1), unix_ms(2025, 10, 30), instalador="com.android.vending",
           perms=[("android.permission.READ_SMS", True), ("android.permission.CAMERA", True)])
    pacote("com.exemplo.lanterna", "/data/app/com.exemplo.lanterna-1",
           unix_ms(2025, 10, 15), unix_ms(2025, 10, 15), instalador="com.android.vending",
           perms=[("android.permission.CAMERA", True)])

    ET.ElementTree(raiz).write(caminho, encoding="utf-8", xml_declaration=True)


def criar_history_db(caminho):
    """History do Chrome: urls + visits + keyword_search_terms + downloads."""
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE urls (
            id INTEGER PRIMARY KEY, url TEXT, title TEXT,
            visit_count INTEGER, typed_count INTEGER, last_visit_time INTEGER, hidden INTEGER DEFAULT 0
        );
        CREATE TABLE visits (
            id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER,
            from_visit INTEGER, transition INTEGER, segment_id INTEGER, visit_duration INTEGER DEFAULT 0
        );
        CREATE TABLE keyword_search_terms (keyword_id INTEGER, url_id INTEGER, term TEXT, lower_term TEXT);
        CREATE TABLE downloads (
            id INTEGER PRIMARY KEY, target_path TEXT, start_time INTEGER, end_time INTEGER,
            received_bytes INTEGER, total_bytes INTEGER, state INTEGER, danger_type INTEGER,
            opened INTEGER, last_access_time INTEGER, referrer TEXT, tab_url TEXT, mime_type TEXT
        );
        CREATE TABLE downloads_url_chains (id INTEGER, chain_index INTEGER, url TEXT);
    """)

    paginas = [
        (1, "https://www.exemplo.gov.br/servicos", "Servicos - Exemplo Gov", 3, 1),
        (2, "https://buscador.exemplo.com/search?q=teste", "teste - Buscador Exemplo", 1, 1),
        (3, "https://www.gstatic.com/favicon.ico", "", 1, 0),
    ]
    con.executemany(
        "INSERT INTO urls (id, url, title, visit_count, typed_count, last_visit_time) VALUES (?, ?, ?, ?, ?, ?)",
        [(i, u, t, vc, tc, webkit_us(2025, 11, 3, 10, 0)) for i, u, t, vc, tc in paginas],
    )
    con.executemany(
        "INSERT INTO visits (url, visit_time, from_visit, transition) VALUES (?, ?, 0, 0)",
        [
            (1, webkit_us(2025, 11, 1, 9, 10)),
            (1, webkit_us(2025, 11, 2, 11, 0)),
            (1, webkit_us(2025, 11, 3, 10, 0)),
            (2, webkit_us(2025, 11, 2, 15, 30)),
        ],
    )
    con.execute("INSERT INTO keyword_search_terms (keyword_id, url_id, term, lower_term) "
                "VALUES (1, 2, 'teste', 'teste')")
    con.execute(
        "INSERT INTO downloads (id, target_path, start_time, end_time, received_bytes, total_bytes, state, "
        "danger_type, opened, last_access_time, referrer, tab_url, mime_type) VALUES "
        "(1, 'C:\\Users\\exemplo\\Downloads\\relatorio.pdf', ?, ?, 2048, 2048, 1, 0, 1, ?, "
        "'https://www.exemplo.gov.br/servicos', 'https://www.exemplo.gov.br/servicos', 'application/pdf')",
        (webkit_us(2025, 11, 1, 9, 15), webkit_us(2025, 11, 1, 9, 16), webkit_us(2025, 11, 1, 9, 20)),
    )
    con.execute("INSERT INTO downloads_url_chains (id, chain_index, url) VALUES "
                "(1, 0, 'https://www.exemplo.gov.br/relatorio.pdf')")
    con.commit()
    con.close()


def criar_favicons_db(caminho):
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE favicons (id INTEGER PRIMARY KEY, url TEXT, icon_type INTEGER);
        CREATE TABLE favicon_bitmaps (
            id INTEGER PRIMARY KEY, icon_id INTEGER, last_updated INTEGER,
            last_requested INTEGER, image_data BLOB, width INTEGER, height INTEGER
        );
        CREATE TABLE icon_mapping (id INTEGER PRIMARY KEY, page_url TEXT, icon_id INTEGER);
    """)
    con.execute("INSERT INTO favicons (id, url, icon_type) VALUES "
                "(1, 'https://www.exemplo.gov.br/favicon.ico', 1)")
    con.execute("INSERT INTO favicons (id, url, icon_type) VALUES "
                "(2, 'https://www.gstatic.com/favicon.ico', 1)")
    con.execute("INSERT INTO favicon_bitmaps (icon_id, last_updated, last_requested, width, height) "
                "VALUES (1, ?, ?, 16, 16)", (webkit_us(2025, 11, 1, 9, 10), webkit_us(2025, 11, 3, 10, 0)))
    con.execute("INSERT INTO favicon_bitmaps (icon_id, last_updated, last_requested, width, height) "
                "VALUES (2, ?, ?, 16, 16)", (webkit_us(2025, 10, 20, 8, 0), webkit_us(2025, 11, 2, 15, 30)))
    con.execute("INSERT INTO icon_mapping (page_url, icon_id) VALUES "
                "('https://www.exemplo.gov.br/servicos', 1)")
    con.execute("INSERT INTO icon_mapping (page_url, icon_id) VALUES "
                "('https://www.exemplo.gov.br/pagina-removida-do-historico', 2)")
    con.commit()
    con.close()


def criar_contacts2_db(caminho):
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE accounts (_id INTEGER PRIMARY KEY, account_name TEXT, account_type TEXT);
        CREATE TABLE raw_contacts (
            _id INTEGER PRIMARY KEY, display_name TEXT, deleted INTEGER DEFAULT 0,
            contact_id INTEGER, account_id INTEGER,
            creation_time INTEGER, last_time_contacted INTEGER, times_contacted INTEGER, starred INTEGER DEFAULT 0
        );
        CREATE TABLE mimetypes (_id INTEGER PRIMARY KEY, mimetype TEXT);
        CREATE TABLE data (_id INTEGER PRIMARY KEY, raw_contact_id INTEGER, mimetype_id INTEGER, data1 TEXT, data4 TEXT);
        CREATE TABLE calls (_id INTEGER PRIMARY KEY, number TEXT, date INTEGER, type INTEGER);
    """)
    con.execute("INSERT INTO accounts (_id, account_name, account_type) VALUES "
                "(1, 'conta@exemplo.com', 'com.google')")
    con.execute("INSERT INTO raw_contacts (_id, display_name, contact_id, account_id, creation_time, "
                "last_time_contacted, times_contacted) VALUES (1, 'Fulano de Exemplo', 100, 1, ?, ?, 3)",
                (unix_ms(2024, 5, 1), unix_ms(2025, 11, 1)))
    con.execute("INSERT INTO mimetypes (_id, mimetype) VALUES (1, 'vnd.android.cursor.item/phone_v2')")
    con.execute("INSERT INTO data (raw_contact_id, mimetype_id, data1) VALUES (1, 1, '+5511999990001')")
    con.execute("INSERT INTO calls (number, date, type) VALUES (?, ?, 2)",
                ("+5511999990001", unix_ms(2025, 11, 1, 8, 50)))
    con.commit()
    con.close()
