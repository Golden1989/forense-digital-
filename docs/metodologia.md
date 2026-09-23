🌐 [Read in English](en/methodology.md)

# Por onde começar numa imagem

Quando entregam uma imagem "no escuro", sem contexto, é porque na perícia real ninguém entrega o caso mastigado. Você recebe um disco e uma pergunta vaga — e é você quem transforma isso em hipóteses, exames, achados e respostas.

> Os quesitos e o cenário usados como exemplo neste arquivo são **fictícios**, escritos só pra ilustrar o método — não são de nenhuma prova ou caso real.

## A cadeia de raciocínio

Todo exame que você faz precisa servir pra responder um quesito:

```
Fatos → Objetivo → Quesitos → Material → Metodologia → Achados → Discussão (nexo) → Respostas
```

O **nome da imagem** costuma ser a primeira pista. `image_empresa` → caso corporativo (vazamento de dados, fraude, uso indevido, acesso não autorizado). Nome de pessoa → caso pessoal. Não prova nada, mas já levanta as hipóteses que guiam a busca.

## Defina os quesitos primeiro

Se o enunciado não traz as perguntas, você as deriva do cenário. Exemplo pra um caso corporativo:

| # | Quesito |
|---|---|
| 1 | Há indício de cópia/transferência de dados da empresa pra fora (USB, nuvem, e-mail pessoal, upload)? |
| 2 | Quais arquivos foram acessados ou copiados, e qual a relevância deles (confidencial, clientes, financeiro, código-fonte)? |
| 3 | É possível identificar quando ocorreu e qual usuário praticou? |
| 4 | Há indício de ocultação ou destruição de evidências (exclusão, wiping, criptografia, renomeação)? |
| 5 | Há comunicação (e-mail, chat) relacionada ao fato? |
| 6 | O dispositivo foi usado para acesso não autorizado a sistemas ou contas? |

Ajuste depois de olhar a imagem — mas comece com um rascunho, porque é ele que direciona tudo.

## Ao ler o caso, anote

Antes de abrir a imagem, leia a história do caso com caneta na mão. Cada item abaixo vira termo de busca, filtro de data ou categoria pra olhar depois:

- **Nomes, apelidos e empresas citados** — todos, inclusive apelido e nome só de empresa. Viram busca de texto e ajudam a achar remetente e destinatário.
- **Datas e o período do fato** — define a janela de tempo: filtre datas de criação, modificação e acesso por ela.
- **Valores e palavras-chave** — em casos de corrupção, por exemplo, o dinheiro costuma aparecer disfarçado. Vale testar termos como "comissão", "mesada", "cafezinho", "agrado", "consultoria", "taxa", além de "propina" e "pagamento". São só exemplos: a história do caso pode usar outros termos.
- **Tipos de arquivo prováveis** — planilhas, e-mails, documentos, imagens. Diz quais categorias descer primeiro na árvore.

## A ordem das operações

Nunca comece clicando em arquivo aleatório. Vá do panorama pro detalhe:

1. **Preservação — antes de abrir qualquer coisa.** Confirme o hash da imagem (veja [`hashes.md`](hashes.md)). A partir daqui, só se trabalha na imagem, nunca no original.
2. **O terreno (lay of the land).** Antes de procurar crime, entenda a máquina: sistema operacional e versão, nome do computador, fuso horário (define se as datas são locais ou UTC), data de instalação do SO, último desligamento, contas de usuário (quantas, nomes, qual é a do suspeito, último logon), partições (o tamanho bate? sobra espaço não particionado?).
3. **A janela de tempo.** Todo caso tem um período de interesse. Às vezes vem no enunciado; às vezes você infere: última semana de trabalho, data do pedido de demissão, pico de atividade estranha. Definida a janela, quase tudo passa a se filtrar por ela.
4. **Varredura por artefato, guiada pelos quesitos.** Agora sim, artefato por artefato — cada bloco responde uma pergunta (tabela abaixo).
5. **Linha do tempo.** Junte tudo que tem data e ordene. Você quer a sequência: *USB inserido 14h02 → pasta "Clientes" aberta 14h03 → planilha copiada 14h05 → `backup.rar` criado 14h09 → 3 arquivos pra Lixeira 14h11 → USB removido 14h12*. Isso não é cinco achados soltos — é uma história com nexo temporal e autoria.
6. **Correlação.** Um artefato sozinho é fraco ("tinha um pendrive"). Três no mesmo minuto são fortes. Sempre pergunte: o que mais aconteceu nesse timestamp?

## A varredura por artefato — detalhe do passo 4

| O que olhar | Responde | Onde procurar |
|---|---|---|
| USB conectados (marca, série, 1ª/última conexão) | saiu dado em pendrive? | Registro do Windows (`USBSTOR`, `MountedDevices`, `setupapi`) |
| Recentes / LNK / Jump Lists / shellbags | o que abriu, e de onde | Artefatos de atividade recente do usuário |
| Execução de programas (Prefetch, Amcache, SRUM, UserAssist) | rodou WinRAR? CCleaner? cliente de nuvem? | Registro do Windows, pasta Prefetch |
| Navegador (histórico, downloads, buscas, uploads) | subiu pra Drive / WeTransfer? webmail? | Histórico de navegação |
| E-mail e chat | comunicação do fato | Caixas de e-mail, apps de mensagem |
| Documentos de interesse (Desktop, Documentos, Downloads, temp) | quais arquivos, qual relevância | Pastas do perfil do usuário |
| Compactados (zip / rar / 7z) | bundling pra exfiltração | Qualquer local, mas note datas de criação |
| Lixeira + apagados + carving | tentou destruir? | Itens deletados e recuperados por assinatura |
| Pastas de nuvem (OneDrive, Google Drive, Dropbox) | sync pra fora | Perfil do usuário |
| Anti-forense (CCleaner, Eraser, BleachBit, VeraCrypt) | ocultação | Programas instalados, histórico de execução |

## O que faz um arquivo ser "suspeito"

- **Local:** Desktop, Downloads, Documentos, `Temp`, raiz de pendrive, pastas ocultas, `AppData` (onde navegador e chat guardam dados).
- **Nome:** "confidencial", "salários", "clientes", "senhas", "cópia de", "backup", "pessoal", nome da empresa, nome de concorrente.
- **Extensão ≠ conteúdo:** ferramentas de perícia marcam divergência de assinatura — `.txt` que é `.jpg`, `.jpg` que é `.rar`. Clássico de coisa escondida.
- **Compactados** grandes criados perto da janela de tempo.
- **Timestamps** agrupados no período de interesse, ou incoerentes (criado depois de modificado, acesso "no futuro", metadado alterado sem mudança de conteúdo = possível *timestomping*).
- **Apagado / carved / na Lixeira / no não alocado.**
- **Criptografado ou com senha.**
- **Órfão** (sem pasta-pai) — veio do espaço não alocado.
- **Contas, tarefas agendadas ou entradas de inicialização** criadas recentemente.

## A regra de ouro

Tudo que você procura tem que responder um quesito. Achou algo que não responde nenhum? Ou é contexto, ou você descobriu um quesito novo.

## Esqueleto de laudo (estrutura, sem conteúdo preenchido)

| Seção | O que entra ali |
|---|---|
| **Preâmbulo** | Data e local do exame, quem requisitou, seu nome como perito |
| **Histórico / Resumo dos fatos** | O cenário do caso |
| **Objetivos e Quesitos** | As perguntas que o exame precisa responder |
| **Descrição do Material** | Tipo de imagem, tamanho, nome do arquivo, hash e resultado da verificação de integridade |
| **Cadeia de Custódia** | Como a evidência foi recebida; hash na aquisição vs. na verificação |
| **Metodologia** | Ferramentas usadas e os passos seguidos |
| **Achados Relevantes** | Lista objetiva — cada achado com nome, caminho, hash, datas, situação (ativo/apagado/carved) e por que é relevante |
| **Discussão** | Onde se argumenta o nexo: linha do tempo, correlação entre achados, coerência das datas |
| **Respostas aos Quesitos** | Cada quesito: SIM / NÃO / PARCIALMENTE / PREJUDICADO, sempre apontando o achado que sustenta a resposta |
| **Encerramento** | Número de páginas, local, data, assinatura |

Regra que vale sempre: **nunca responda um quesito sem apontar a evidência.** "SIM" sozinho não vale; "SIM, conforme itens 3 e 5 dos Achados" vale.
