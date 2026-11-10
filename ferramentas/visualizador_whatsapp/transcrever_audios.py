#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
transcrever_audios.py - Transcreve (fala -> texto) os áudios de uma pasta, no seu computador.

A transcrição é AUTOMÁTICA e pode errar (nomes, gírias, ruído, sotaque). No laudo, trate-a como
auxílio de triagem e confirme ouvindo o áudio. O resultado é um JSON que o
visualizador_whatsapp.py mostra abaixo de cada áudio (opção --transcricoes).

Instalação (uma vez):
    pip install faster-whisper
  Na primeira execução o programa baixa o modelo (precisa de internet). Depois funciona offline.

Uso:
    python ferramentas\\visualizador_whatsapp\\transcrever_audios.py --pasta "C:\\evidencia\\ios\\Media\\files\\Audio"
    python ferramentas\\visualizador_whatsapp\\transcrever_audios.py --pasta "..." --modelo small --saida transcricoes_audio.json

Pontos importantes
  - Retomável: se parar no meio, rode de novo; os áudios já feitos são pulados.
  - Não altera nada na pasta de áudios (só lê). O JSON de saída fica onde você mandar em --saida.
  - Modelos: tiny/base (rápidos, erram mais), small (bom equilíbrio), medium (melhor, mais lento).
"""
import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EXTENSOES = {".opus", ".ogg", ".oga", ".aac", ".m4a", ".mp3", ".wav", ".amr"}


def sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def preparar_leitura(caminho):
    """Garante que o faster-whisper consegue abrir o áudio.

    O PyAV 19 removeu o argumento 'metadata_errors' que o faster-whisper ainda usa, e isso derruba a
    leitura de TODOS os áudios. Se for esse o caso, o programa aplica um ajuste (ignorar o argumento).
    """
    from faster_whisper.audio import decode_audio
    try:
        decode_audio(caminho, sampling_rate=16000)
        return
    except TypeError as e:
        if "metadata_errors" not in str(e):
            raise
    import av
    original = av.open

    def abrir_compativel(*args, **kwargs):
        kwargs.pop("metadata_errors", None)
        return original(*args, **kwargs)

    av.open = abrir_compativel
    decode_audio(caminho, sampling_rate=16000)      # se ainda falhar, o erro aparece para quem chamou
    print("Aviso: o PyAV instalado (v%s) é novo demais para o faster-whisper; apliquei um ajuste "
          "automático de compatibilidade." % getattr(av, "__version__", "?"))


def salvar(saida, meta, itens):
    """Grava o JSON de forma atômica (não deixa arquivo pela metade se o programa for interrompido)."""
    tmp = Path(str(saida) + ".tmp")
    tmp.write_text(json.dumps({"meta": meta, "itens": itens}, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(saida)


def main():
    try:  # console do Windows pode não aceitar acentos/emojis; troca por "?" em vez de quebrar
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Transcreve áudios (faster-whisper) e grava um JSON.")
    ap.add_argument("--pasta", required=True, help="Pasta com os áudios (ex.: ...\\Media\\files\\Audio)")
    ap.add_argument("--saida", default="transcricoes_audio.json", help="Arquivo JSON de saída")
    ap.add_argument("--modelo", default="small", help="tiny, base, small, medium, large-v3 ... (padrão: small)")
    ap.add_argument("--idioma", default="pt", help="Código do idioma falado (padrão: pt). Use 'auto' para detectar")
    ap.add_argument("--dispositivo", default="cpu", help="cpu ou cuda (placa NVIDIA)")
    ap.add_argument("--limite", type=int, default=0, help="Só os N primeiros (para testar). 0 = todos")
    a = ap.parse_args()

    pasta = Path(a.pasta)
    if not pasta.is_dir():
        sys.exit("Pasta não encontrada: %s" % pasta)
    arquivos = sorted(f for f in pasta.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES)
    if a.limite:
        arquivos = arquivos[:a.limite]
    if not arquivos:
        sys.exit("Nenhum áudio encontrado em %s" % pasta)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Falta a biblioteca. Rode no PowerShell:  pip install faster-whisper")

    saida = Path(a.saida)
    itens, meta = {}, None
    if saida.exists():
        try:
            antigo = json.loads(saida.read_text(encoding="utf-8"))
            itens, meta = antigo.get("itens", {}), antigo.get("meta")
        except ValueError:
            sys.exit("O arquivo %s existe mas não é um JSON válido. Apague ou escolha outro --saida." % saida)
        if meta and meta.get("modelo") != a.modelo:
            sys.exit("O arquivo de saída foi gerado com o modelo '%s'. Use --saida outro.json para trocar de "
                     "modelo sem misturar resultados." % meta.get("modelo"))
    meta = meta or dict(modelo=a.modelo, idioma=a.idioma, dispositivo=a.dispositivo,
                        gerado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        aviso="Transcrição automática; pode conter erros.")

    # Itens antigos que deram erro são refeitos; só pula quem já tem resultado sem erro.
    itens = {k: v for k, v in itens.items() if not v.get("erro")}
    pendentes = [f for f in arquivos if f.name not in itens]
    print("%d áudios na pasta, %d já transcritos, %d a fazer (modelo %s)."
          % (len(arquivos), len(arquivos) - len(pendentes), len(pendentes), a.modelo))
    if not pendentes:
        salvar(saida, meta, itens)
        print("Nada a fazer. Resultado em %s" % saida)
        return

    # Teste rápido: o computador consegue LER o primeiro áudio? (evita gastar tempo e falhar em todos)
    try:
        preparar_leitura(str(pendentes[0]))
    except Exception as e:
        sys.exit("Não consegui ler o áudio %s\n  %s: %s\n"
                 "Se for problema do PyAV, tente:  pip install \"av<19\"" % (pendentes[0].name, type(e).__name__, e))

    print("Carregando o modelo (na primeira vez ele é baixado)...")
    compute = "int8" if a.dispositivo == "cpu" else "float16"
    try:
        modelo = WhisperModel(a.modelo, device=a.dispositivo, compute_type=compute)
    except Exception as e:
        sys.exit("Não consegui carregar o modelo '%s' (%s: %s).\nNa primeira vez ele é baixado da internet; "
                 "confira a conexão e tente de novo." % (a.modelo, type(e).__name__, e))
    idioma = None if a.idioma == "auto" else a.idioma

    t0 = time.time()
    erros, seguidos = 0, 0
    for n, f in enumerate(pendentes, 1):
        try:
            segs, info = modelo.transcribe(str(f), language=idioma, vad_filter=True, beam_size=5)
            lista = [dict(ini=round(s.start, 2), fim=round(s.end, 2), texto=s.text.strip()) for s in segs]
            texto = " ".join(x["texto"] for x in lista if x["texto"]).strip()
            itens[f.name] = dict(
                texto=texto, segmentos=lista, idioma=info.language,
                prob_idioma=round(float(info.language_probability), 3),
                duracao=round(float(info.duration), 2), sha256=sha256_arquivo(f))
            seguidos = 0
        except Exception as e:  # um áudio ruim não derruba o lote, mas NÃO é gravado como resultado
            erros += 1
            seguidos += 1
            print("  ! ERRO em %s: %s: %s" % (f.name, type(e).__name__, e))
            if seguidos >= 3:
                salvar(saida, meta, itens)
                sys.exit("\nParei: 3 áudios seguidos deram erro, então o problema é do programa/instalação, "
                         "não dos áudios.\nÚltimo erro: %s: %s" % (type(e).__name__, e))
            continue
        salvar(saida, meta, itens)
        dec = time.time() - t0
        print("[%d/%d] %s  (%.0fs decorridos)  %s" % (n, len(pendentes), f.name, dec,
              (itens[f.name].get("texto") or "(sem fala detectada)")[:70]))
    print("\nPronto: %d transcritos, %d com erro. Resultado em %s" % (len(pendentes) - erros, erros, saida.resolve()))
    if erros:
        print("Rode o mesmo comando de novo para tentar os que deram erro.")
    print("Abra o visualizador com:  --transcricoes %s" % saida)


if __name__ == "__main__":
    main()
