# Forense Digital — Notas de Estudo

🌐 [Read in English](README.en.md)

Repositório de estudo da disciplina de perícia forense digital: guias de ferramenta, metodologia e comandos organizados enquanto eu aprendo. Nada aqui é específico de um caso — **sem imagem de disco, sem laudo preenchido, sem dado de prova**.

## Por que não tem imagem nem laudo aqui

Imagem forense e laudo resolvido ficam de fora de propósito. São material de avaliação da faculdade — publicar isso seria dar a resposta de uma prova pra quem ainda vai cursar a disciplina, mesmo anos depois (é comum a mesma imagem ser reaproveitada em outras turmas). O que fica aqui é conhecimento de ferramenta, o **"como se faz"**, nunca o **"o que essa prova específica pediu"**.

Se algum exemplo abaixo usa nome de caso, empresa ou quesito, é **fictício**, escrito só pra ilustrar o método.

## Conteúdo

| Arquivo | Conteúdo |
|---|---|
| [`docs/metodologia.md`](docs/metodologia.md) | Como abordar uma imagem "no escuro": ordem de investigação, como definir quesitos, o que faz um arquivo ser suspeito |
| [`docs/hashes.md`](docs/hashes.md) | Como calcular o hash de uma imagem forense (PowerShell e WSL), MD5/SHA-1/SHA-256/SHA-512, e por que o hash do arquivo `.E01` é diferente do hash do conteúdo adquirido |
| [`docs/sleuthkit.md`](docs/sleuthkit.md) | Referência de comandos do Sleuth Kit (TSK), organizada pelas 6 camadas de uma imagem, com receitas prontas de terminal (Linux/WSL) |
| [`docs/iped.md`](docs/iped.md) | Guia do IPED: processar, analisar, marcadores, exportação, configuração, anatomia de disco |
| [`docs/registro-windows.md`](docs/registro-windows.md) | Registro do Windows: hives, UserAssist, Prefetch, RunMRU, RecentDocs, USBSTOR/MountedDevices, Event Log, Windows Search, com quiz de revisão |

## Scripts

| Script | O que faz |
|---|---|
| [`ferramentas/analisa_packages.py`](ferramentas/analisa_packages.py) | Resume o `packages.xml` de uma extração Android: total de pacotes, quantos são de usuário vs. de sistema, os apps de usuário numerados em ordem cronológica de instalação (primeiro e último marcados — só entre os de usuário, já que os de firmware têm quase todos a mesma data) e os 10 de usuário com mais permissões concedidas. Exporta CSV (abre direto no Excel), já em ordem cronológica mas reordenável por qualquer coluna. Só lê o arquivo — nunca grava nada na pasta da evidência. |
| [`ferramentas/linha_do_tempo.py`](ferramentas/linha_do_tempo.py) | Junta SMS, chamadas, histórico do Chrome e apps instalados numa única linha do tempo, com os horários já convertidos para UTC e UTC-3. Cada fonte é opcional — usa as que você tiver. Antes de abrir, copia cada banco (junto com os arquivos `-wal`/`-shm` vizinhos) para uma pasta temporária, então o original nunca é tocado e os dados ainda no WAL entram na leitura. Pode filtrar por um dia específico e exportar CSV. |

```bash
python ferramentas/analisa_packages.py caminho/packages.xml
python ferramentas/analisa_packages.py caminho/packages.xml --so-usuario
python ferramentas/analisa_packages.py caminho/packages.xml --csv saida.csv

python ferramentas/linha_do_tempo.py --sms mmssms.db --chrome History --calls calllog.db --packages packages.xml --csv linha.csv
python ferramentas/linha_do_tempo.py --sms mmssms.db --chrome History --dia 2025-11-03
```

## Ferramentas usadas

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager

## Sobre

Estudante de perícia forense digital, organizando o que aprendo em aula e nos meus próprios testes. Notas escritas com ajuda do Claude enquanto eu usava as ferramentas pela primeira vez.
