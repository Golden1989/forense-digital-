"""Gera bancos SQLite, XML, JPEG e sessao do Chrome sinteticos (nenhum dado
real) para os testes em test_ferramentas.py. Nada aqui e evidencia: nomes,
numeros, URLs e fotos sao ficticios.
"""
import struct
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


def _ascii(texto):
    return texto.encode("ascii") + b"\0"


def _empacotar_ifd(entradas, offset_tabela, offset_dados_inicial):
    """entradas: lista de (tag, tipo, dados_externos_ou_None, valor_inline_ou_None).
    Devolve (bytes_da_tabela, bytes_externos, offset_dados_final).
    """
    tabela = bytearray(struct.pack("<H", len(entradas)))
    externos = bytearray()
    cursor = offset_dados_inicial
    for tag, tipo, dados, inline in entradas:
        if inline is not None:
            tabela += struct.pack("<HHI", tag, tipo, 1) + struct.pack("<I", inline)
            continue
        tam = len(dados)
        contagem = tam if tipo == 2 else tam // 8   # ASCII: 1 byte/unidade; RATIONAL: 8 bytes/unidade
        if tam <= 4:
            campo = dados + b"\0" * (4 - tam)
        else:
            campo = struct.pack("<I", cursor)
            externos += dados
            cursor += tam
        tabela += struct.pack("<HHI", tag, tipo, contagem) + campo
    return bytes(tabela), bytes(externos), cursor


def criar_jpeg_com_exif(caminho, make="Google", modelo="Pixel 3", software="",
                         original="2020:01:29 11:00:00", datetime_="2020:01:29 11:00:00",
                         digitalizada="2020:01:29 11:00:00"):
    """Cria um JPEG minimo (sem pixels reais) com bloco EXIF montado a mao, pra
    testar exif_fotos.py sem depender de nenhuma biblioteca de imagem.
    """
    entradas_ifd0 = [
        (0x010F, 2, _ascii(make), None),
        (0x0110, 2, _ascii(modelo), None),
        (0x0132, 2, _ascii(datetime_), None),
        (0x8769, 4, None, 0),  # ponteiro pro IFD Exif; valor real preenchido depois
    ]
    if software:
        entradas_ifd0.append((0x0131, 2, _ascii(software), None))

    entradas_exif = [
        (0x9003, 2, _ascii(original), None),
        (0x9004, 2, _ascii(digitalizada), None),
    ]

    tam_tabela_ifd0 = 2 + 12 * len(entradas_ifd0)
    tam_tabela_exif = 2 + 12 * len(entradas_exif)
    offset_ifd0 = 8
    offset_exif = offset_ifd0 + tam_tabela_ifd0
    offset_dados = offset_exif + tam_tabela_exif

    # corrige o ponteiro pro IFD Exif agora que o offset e' conhecido
    entradas_ifd0 = [(t, tp, d, offset_exif if t == 0x8769 else i) for t, tp, d, i in entradas_ifd0]

    tabela_ifd0, externos_ifd0, cursor = _empacotar_ifd(entradas_ifd0, offset_ifd0, offset_dados)
    tabela_exif, externos_exif, cursor = _empacotar_ifd(entradas_exif, offset_exif, cursor)

    tiff = (b"II" + struct.pack("<H", 42) + struct.pack("<I", offset_ifd0)
            + tabela_ifd0 + tabela_exif + externos_ifd0 + externos_exif)

    app1 = b"Exif\0\0" + tiff
    segmento = b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1
    jpeg = b"\xff\xd8" + segmento + b"\xff\xd9"
    with open(caminho, "wb") as f:
        f.write(jpeg)


def criar_jpeg_sem_exif(caminho):
    """JPEG minimo sem nenhum bloco EXIF (ex.: print de tela)."""
    with open(caminho, "wb") as f:
        f.write(b"\xff\xd8\xff\xd9")


def _texto32(texto):
    b = texto.encode("utf-8")
    pad = (-len(b)) % 4
    return struct.pack("<i", len(b)) + b + b"\0" * pad


def _texto16(texto):
    b = texto.encode("utf-16-le")
    return struct.pack("<i", len(b) // 2) + b


def criar_sessao_chrome(caminho, paginas, selecionada=None):
    """Cria um arquivo de sessao do Chrome (formato SNSS) sintetico.

    paginas: lista de (aba, indice, url, titulo).
    selecionada: dict {aba: indice} da pagina marcada como atual em cada aba.
    """
    selecionada = selecionada or {}
    dados = bytearray(b"SNSS" + struct.pack("<i", 1))

    def comando(tipo, conteudo):
        return struct.pack("<H", len(conteudo) + 1) + bytes([tipo]) + conteudo

    for aba, indice, url, titulo in paginas:
        conteudo = b"\0\0\0\0" + struct.pack("<ii", aba, indice) + _texto32(url) + _texto16(titulo)
        dados += comando(6, conteudo)
    for aba, indice in selecionada.items():
        dados += comando(7, struct.pack("<ii", aba, indice))

    with open(caminho, "wb") as f:
        f.write(bytes(dados))
