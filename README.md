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
| [`docs/smartphone.md`](docs/smartphone.md) | Perícia em Android e iOS: níveis de extração, BFU/AFU, SQLite (WAL/SHM), artefatos de cada sistema, formatos de data, Chrome, ADB, raciocínio pericial, com quiz de revisão |
| [`docs/ferramentas.md`](docs/ferramentas.md) | Scripts em Python da pasta `ferramentas/`: como rodar, opções explicadas, qual script responde qual quesito (linha do tempo, apps instalados, sessão do Chrome, favicons, datas) |

## Scripts

Pasta [`ferramentas/`](ferramentas/): scripts Python que só leem a evidência (nunca gravam nada nela) e automatizam perguntas comuns de quesito — apps instalados, linha do tempo unificada, sessão do Chrome, downloads, resumo de navegação, favicons fora do histórico, mapa de um banco SQLite desconhecido, contatos/chamadas/SMS, EXIF de fotos e conversor de datas. Passo a passo, opções de cada um e qual script usar para qual pergunta: [`docs/ferramentas.md`](docs/ferramentas.md).

## Ferramentas usadas

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager
- [DB Browser for SQLite](https://sqlitebrowser.org/)
- [Registry Explorer](https://ericzimmerman.github.io/) (Eric Zimmerman)

## Sobre

Estudante de perícia forense digital, organizando o que aprendo em aula e nos meus próprios testes. 
