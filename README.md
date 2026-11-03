# Forense Digital — Notas de Estudo

[![tests](https://github.com/Golden1989/forense-digital-/actions/workflows/tests.yml/badge.svg)](https://github.com/Golden1989/forense-digital-/actions/workflows/tests.yml)

🌐 [Read in English](README.en.md)

Repositório de estudo da disciplina de perícia forense digital: guias de ferramenta, metodologia e comandos organizados enquanto eu aprendo. Nada aqui é específico de um caso — **sem imagem de disco, sem laudo preenchido, sem dado de prova**.

## Por que não tem imagem nem laudo aqui

Imagem forense e laudo resolvido ficam de fora de propósito. São material de avaliação da faculdade — publicar isso seria dar a resposta de uma prova pra quem ainda vai cursar a disciplina, mesmo anos depois (é comum a mesma imagem ser reaproveitada em outras turmas). O que fica aqui é conhecimento de ferramenta, o **"como se faz"**, nunca o **"o que essa prova específica pediu"**.

Se algum exemplo abaixo usa nome de caso, empresa ou quesito, é **fictício**, escrito só pra ilustrar o método.

**Exceção:** [`docs/caso-ficticio.md`](docs/caso-ficticio.md) usa uma imagem forense **pública** (sem relação com a disciplina) pra mostrar os scripts deste repositório funcionando numa investigação fictícia de ponta a ponta — quesitos, achados e conclusão.

## Conteúdo

| Arquivo | Conteúdo |
|---|---|
| [`docs/metodologia.md`](docs/metodologia.md) | Como abordar uma imagem "no escuro": ordem de investigação, como definir quesitos, o que faz um arquivo ser suspeito |
| [`docs/caso-ficticio.md`](docs/caso-ficticio.md) | Caso fictício completo com imagem pública (Digital Corpora): quesitos, achados e conclusão usando os scripts deste repositório |
| [`docs/hashes.md`](docs/hashes.md) | Como calcular o hash de uma imagem forense (PowerShell e WSL), MD5/SHA-1/SHA-256/SHA-512, e por que o hash do arquivo `.E01` é diferente do hash do conteúdo adquirido |
| [`docs/sleuthkit.md`](docs/sleuthkit.md) | Referência de comandos do Sleuth Kit (TSK), organizada pelas 6 camadas de uma imagem, com receitas prontas de terminal (Linux/WSL) |
| [`docs/iped.md`](docs/iped.md) | Guia do IPED: processar, analisar, marcadores, exportação, configuração, anatomia de disco |
| [`docs/registro-windows.md`](docs/registro-windows.md) | Registro do Windows: hives, UserAssist, Prefetch, RunMRU, RecentDocs, USBSTOR/MountedDevices, Event Log, Windows Search, com quiz de revisão |
| [`docs/smartphone.md`](docs/smartphone.md) | Perícia em Android e iOS: níveis de extração, BFU/AFU, SQLite (WAL/SHM), artefatos de cada sistema, formatos de data, Chrome, ADB, raciocínio pericial, com quiz de revisão |
| [`docs/ferramentas.md`](docs/ferramentas.md) | Scripts em Python da pasta `ferramentas/`: como rodar, opções explicadas, qual script responde qual quesito (linha do tempo, apps instalados, sessão do Chrome, favicons, datas) |

## Scripts

Pasta [`ferramentas/`](ferramentas/): scripts Python que só leem a evidência (nunca gravam nada nela) e automatizam perguntas comuns de quesito. Passo a passo e todas as opções de cada um: [`docs/ferramentas.md`](docs/ferramentas.md).

| Script | Responde | Exemplo de saída (fictício) |
|---|---|---|
| `analisa_packages.py` | Quando cada app foi instalado/atualizado, por quem, e quais apps de usuário têm as permissões mais sensíveis | ` 3  2025-10-30 14:02:11  com.exemplo.mensageiro  (instalador: com.android.vending)  <-- ULTIMO` |
| `linha_do_tempo.py` | O que aconteceu num dia/período, cruzando SMS, chamadas, navegação e instalação de apps numa única linha do tempo | `2025-11-03 10:00:00  CHROME  visita  https://www.exemplo.gov.br/servicos  Serviços - Exemplo Gov` |
| `sessao_chrome.py` | Quais abas estavam abertas quando o Chrome foi fechado | `[2] https://www.exemplo.com/carrinho  Meu Carrinho - Loja Exemplo` |
| `favicons_fora_do_historico.py` | Se há indício de limpeza de histórico (favicon sem página correspondente no `History`) | `pagina-removida-do-historico   icone: https://www.gstatic.com/favicon.ico` |
| `resumo_navegacao.py` | Panorama de navegação: domínios/URLs mais visitados, primeira e última visita, páginas de redirecionamento | `1. www.exemplo.gov.br  visitas=3  primeira: 2025-11-01 09:10:00 \| ultima: 2025-11-03 10:00:00` |
| `downloads_chrome.py` | O que foi baixado pelo navegador, de que URL e quando | `relatorio.pdf  [concluido, 2048 bytes]   baixado de: https://www.exemplo.gov.br/relatorio.pdf` |
| `mapa_sqlite.py` | O que tem dentro de um banco SQLite desconhecido e em quais colunas estão as datas | `visit_time  INTEGER  nao-nulos=4  <-- DATA webkit: 2025-11-01 09:10:00 -> 2025-11-03 10:00:00` |
| `contatos_merge.py` | Quem é o contato por trás de um número, e quais números aparecem em chamadas/SMS mas não estão na agenda | `#100 Fulano de Exemplo   telefones: +5511999990001 \| chamadas: 1 [feita=1] ...` |
| `exif_fotos.py` | Se os metadados EXIF de uma foto (câmera, data, GPS) são consistentes ou alterados | `IMG_0231.jpg  tirada: 2025-10-12 16:40:02  [!] data de modificacao do arquivo e anterior a da foto` |
| `convert_date.py` | Converter um número de timestamp (Android, iOS, Chrome, Windows) numa data legível | `Data: 2025-11-03 15:42:54 -03:00 (Chrome/Edge, microssegundos desde 1601)` |

## Testes

[`tests/`](tests/): testes automatizados com [pytest](https://pytest.org/), rodando cada script contra bancos SQLite e um `packages.xml` **sintéticos** (gerados em [`tests/dados_fake.py`](tests/dados_fake.py) — nomes, números e URLs fictícios, nunca evidência real). Garantem que os scripts continuam funcionando depois de qualquer alteração.

```
pip install -r requirements-dev.txt
pytest
```

## Ferramentas usadas

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager
- [DB Browser for SQLite](https://sqlitebrowser.org/)
- [Registry Explorer](https://ericzimmerman.github.io/) (Eric Zimmerman)

## Licença

[MIT](LICENSE).

## Sobre

Estudante de perícia forense digital, organizando o que aprendo em aula e nos meus próprios testes. 
