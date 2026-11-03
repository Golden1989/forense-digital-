"""Testes de fumaca dos scripts em ferramentas/, usando so dados sinteticos
(ver dados_fake.py). Nenhum arquivo aqui e prova real; o objetivo e garantir
que cada script roda e responde o esperado nos formatos que ele trata.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dados_fake as fake  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
FERRAMENTAS = RAIZ / "ferramentas"


def rodar(script, *args):
    r = subprocess.run([sys.executable, str(FERRAMENTAS / script), *args],
                        capture_output=True, text=True)
    assert r.returncode == 0, f"{script} falhou:\n{r.stderr}"
    return r.stdout


def test_convert_date_unix_ms():
    saida = rodar("convert_date.py", "1762202574476", "--fuso", "-3")
    assert "2025-11-" in saida


def test_analisa_packages(tmp_path):
    xml = tmp_path / "packages.xml"
    fake.criar_packages_xml(xml)
    saida = rodar("analisa_packages.py", str(xml), "--so-usuario")
    assert "com.exemplo.mensageiro" in saida
    assert "PRIMEIRO" in saida and "ULTIMO" in saida


def test_linha_do_tempo(tmp_path):
    sms, calls, history = tmp_path / "mmssms.db", tmp_path / "calllog.db", tmp_path / "History"
    fake.criar_mmssms_db(sms)
    fake.criar_calllog_db(calls)
    fake.criar_history_db(history)
    saida = rodar("linha_do_tempo.py", "--sms", str(sms), "--calls", str(calls),
                  "--chrome", str(history), "--fuso", "-3")
    assert "SMS" in saida and "CHAMADA" in saida and "CHROME" in saida
    assert "eventos" in saida


def test_resumo_navegacao(tmp_path):
    history = tmp_path / "History"
    fake.criar_history_db(history)
    saida = rodar("resumo_navegacao.py", str(history), "--site", "gov.br")
    assert "exemplo.gov.br" in saida
    assert "VISAO GERAL" in saida


def test_downloads_chrome(tmp_path):
    history = tmp_path / "History"
    fake.criar_history_db(history)
    saida = rodar("downloads_chrome.py", str(history))
    assert "relatorio.pdf" in saida
    assert "concluido" in saida


def test_favicons_fora_do_historico(tmp_path):
    history, favicons = tmp_path / "History", tmp_path / "Favicons"
    fake.criar_history_db(history)
    fake.criar_favicons_db(favicons)
    saida = rodar("favicons_fora_do_historico.py", "--favicons", str(favicons), "--history", str(history))
    assert "pagina-removida-do-historico" in saida


def test_contatos_merge(tmp_path):
    contacts, calls, sms = tmp_path / "contacts2.db", tmp_path / "calllog.db", tmp_path / "mmssms.db"
    fake.criar_contacts2_db(contacts)
    fake.criar_calllog_db(calls)
    fake.criar_mmssms_db(sms)
    saida = rodar("contatos_merge.py", "--contacts", str(contacts), "--calls", str(calls), "--sms", str(sms))
    assert "Fulano de Exemplo" in saida
    assert "999990002" in saida  # numero que so aparece em SMS/chamada, fora da agenda


def test_mapa_sqlite(tmp_path):
    history = tmp_path / "History"
    fake.criar_history_db(history)
    saida = rodar("mapa_sqlite.py", str(history), "--so-datas")
    assert "visit_time" in saida
    assert "DATA webkit" in saida
