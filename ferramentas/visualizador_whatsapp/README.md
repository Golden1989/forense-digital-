🌐 [Read in English](README.en.md)

# Visualizador de WhatsApp (iOS e Android)

Ferramenta local, em Python, para **ler e analisar as conversas de WhatsApp de uma extração forense** (banco SQLite) numa interface web que roda no próprio computador. Ela existe para facilitar a triagem: escolher uma conversa, ler as mensagens com dia e hora, ouvir os áudios, ver as imagens, listar os participantes de um grupo e exportar o que for relevante para o laudo.

- **Só leitura.** O banco e a pasta de mídia nunca são alterados. O SHA-256 do banco aparece no topo da página, para registrar no laudo.
- **Tudo local.** O servidor só responde em `127.0.0.1` (este computador). Nada é enviado para a internet pelo visualizador.
- **Sem instalar nada** para o visualizador (só a biblioteca padrão do Python). A transcrição de áudio e a leitura de EXIF são opcionais e precisam de bibliotecas extras (veja [Instalação](#instalação)).
- **Não vem com dado de caso.** Este repositório não contém banco, mídia nem transcrição de nenhum caso. Você aponta a ferramenta para a *sua* evidência.

> **Transparência:** o código desta pasta foi desenvolvido com auxílio de IA (Claude, da Anthropic) e testado com bancos anonimizados de exemplo (não incluídos aqui). Revise antes de usar em um trabalho real: confira sempre o que a ferramenta mostra contra o banco original.

## Conteúdo da pasta

| Arquivo | Para que serve |
|---|---|
| `visualizador_whatsapp.py` | O visualizador (servidor local + interface no navegador) |
| `transcrever_audios.py` | Gera a transcrição automática dos áudios (fala → texto), opcional |
| `requirements.txt` | Bibliotecas opcionais (`faster-whisper`, `pillow`) |
| `README.md` / `README.en.md` | Este guia, em português e em inglês |

## O que você precisa ter

Python 3.8 ou superior (testado com 3.13). Para conferir a versão, no PowerShell:

```powershell
python --version
```

Se aparecer "não é reconhecido", tente `py --version` e use `py` no lugar de `python` nos comandos abaixo.

E os arquivos da extração (a ferramenta **não** os traz):

| Sistema | Banco de mensagens | Contatos (opcional, dá nome aos números) | Mídia (opcional) |
|---|---|---|---|
| **iOS** | `ChatStorage.sqlite` | `Contacts.sqlite` | pasta `Media/files/` (com `Audio/` e `Image/`) |
| **Android** | `msgstore.db` | `wa.db` | não suportada nesta versão |

Se o banco vier com os arquivos `-wal` e `-shm` ao lado (ex.: `ChatStorage.sqlite-wal`), **deixe-os na mesma pasta**: o WAL guarda alterações recentes que ainda não foram para o banco principal. Quando o `-wal` tem dados, o programa trabalha numa cópia temporária dos três arquivos (apagada ao encerrar), para que esses dados apareçam e o original continue intacto.

## Instalação

```powershell
cd C:\forense-digital
```

`cd` significa *change directory* (mudar de pasta): entre na pasta onde está o repositório.

- **Visualizador:** não precisa instalar nada.
- **Leitura de EXIF das imagens (opcional):** `pip install pillow`
- **Transcrição de áudio (opcional):** `pip install faster-whisper`

Ou instale as duas de uma vez: `pip install -r ferramentas\visualizador_whatsapp\requirements.txt`.

## Como rodar

Todos os comandos abaixo são rodados a partir da pasta do repositório. Troque os caminhos pelos da sua evidência.

**iOS**, com tudo numa pasta (o programa acha o banco, os contatos e a mídia sozinho):

```powershell
python ferramentas\visualizador_whatsapp\visualizador_whatsapp.py --pasta "C:\evidencia\ios"
```

**iOS**, apontando cada arquivo:

```powershell
python ferramentas\visualizador_whatsapp\visualizador_whatsapp.py --db "C:\evidencia\ChatStorage.sqlite" --contatos "C:\evidencia\Contacts.sqlite" --midia "C:\evidencia\Media\files"
```

**Android:**

```powershell
python ferramentas\visualizador_whatsapp\visualizador_whatsapp.py --db "C:\evidencia\msgstore.db" --contatos "C:\evidencia\wa.db"
```

O navegador abre sozinho em `http://127.0.0.1:8765/`. Para encerrar, volte ao PowerShell e aperte `Ctrl+C`.

### Anatomia do comando

| Parte | O que é |
|---|---|
| `python` | o programa que executa o script |
| `ferramentas\visualizador_whatsapp\visualizador_whatsapp.py` | qual script rodar (o caminho dele) |
| `--db "..."` | uma **opção** (começa com `--`) seguida do seu **valor** |
| `--sem-navegador` | opção sem valor: liga um comportamento |

### Opções

| Opção | O que faz |
|---|---|
| `--pasta` | Pasta com o banco (`ChatStorage*.sqlite` ou `msgstore*.db`) e os contatos. A mídia é procurada em `<pasta>\Media\files` |
| `--db` | Caminho do banco de mensagens (iOS ou Android; o tipo é reconhecido sozinho) |
| `--contatos` | `Contacts*.sqlite` (iOS) ou `wa*.db` (Android): nomes dos contatos e, no Android, a lista de bloqueados |
| `--midia` | Pasta `Media/files` (com `Audio/` e `Image/`), se não estiver no lugar padrão |
| `--transcricoes` | JSON gerado por `transcrever_audios.py` (mostra o texto abaixo de cada áudio) |
| `--hash-banco` | SHA-256 do banco registrado na aquisição. O programa compara com o hash calculado e avisa se **confere** ou **NÃO confere** |
| `--manifesto` | CSV de referência (gerado pelo painel **Integridade**) para apontar arquivos de mídia **alterados**, novos e ausentes |
| `--porta` | Porta local (padrão `8765`). Mude se já estiver em uso, ou para abrir dois bancos ao mesmo tempo |
| `--sem-navegador` | Não abre o navegador sozinho (abra o endereço manualmente) |

## Como usar a interface

**Topo da página.** Mostra o banco aberto, quantas conversas e mensagens existem, quantas têm data real, quantos áudios e imagens têm arquivo para ouvir/ver, e o **SHA-256 do banco** (clique para copiar). À direita: **fuso horário** (padrão UTC-3) e botão de **tema** claro/escuro.

**Integridade (botão no topo).** Abre uma tabela com **todos os arquivos de mídia da pasta**: formato real, tamanho do arquivo e tamanho registrado no banco, data de modificação no disco, quantas mensagens apontam para o arquivo, SHA-256 e alertas (extensão que não confere, tamanho diferente do banco, arquivo que nenhuma mensagem referencia). O botão *Exportar CSV* gera um **manifesto** (lista de hashes).

Como saber quais arquivos foram **alterados**:
1. Logo após a aquisição, abra o painel e exporte o CSV (ex.: `manifesto_aquisicao.csv`); guarde-o junto da evidência.
2. Mais tarde, rode o visualizador com `--manifesto manifesto_aquisicao.csv` (e, se tiver, `--hash-banco <SHA-256 da aquisição>`). O painel passa a marcar cada arquivo como **igual**, **ALTERADO** (hash diferente), **novo** (não estava no manifesto) e lista os **ausentes** (estavam no manifesto e sumiram da pasta).

Sem manifesto, o programa **não consegue afirmar** que um arquivo foi alterado: ele só aponta inconsistências.

**Lista de conversas (esquerda).**
- Caixa de filtro por nome ou número; botões *Todas / Individuais / Grupos*.
- *Ordenar* por mais recente, mais antiga, mais mensagens ou nome.
- *Mostrar* só conversas com áudio para ouvir ou com imagem para ver.
- *Buscar texto em TODAS as conversas* (Enter): procura em todas as mensagens (e nas transcrições) e mostra onde achou; clique num resultado para abrir a conversa naquele ponto.

**Conversa (direita).**
- **Cabeçalho:** tipo (grupo/individual), identificador, número de mensagens, enviadas/recebidas, áudios, imagens e período.
- **Participantes do grupo:** em grupos, a linha "Participantes do grupo" abre uma tabela com nome, número, papel (admin/membro), situação, mensagens enviadas no grupo e primeira/última mensagem. Há botão para exportar em CSV.
- **Buscar nesta conversa** (com setas ↑ ↓ entre os resultados).
- **Filtro de mensagens:** todas, só texto, só enviadas, só recebidas, só mídia, só áudios (todos / com arquivo / com transcrição), só imagens (todas / com arquivo), só links, **só com CPF, telefone ou e-mail** (juntos ou separados), só eventos, só sem data.
- **Ir para** um dia específico, e botões *Início* e *Fim*.
- **Exportar CSV** da conversa (direção, remetente, data/hora, valor bruto da data, tipo, texto, arquivo, SHA-256 do arquivo, formato real, transcrição, tamanho, dimensões). Abre bem no Excel.

**Mensagens.**
- Separador por dia; balões diferentes para enviadas e recebidas; hora ao lado de cada mensagem (passe o mouse para ver o valor bruto gravado no banco); ID da mensagem; ★ para mensagens marcadas; links clicáveis.
- **Eventos** (entrada/saída de grupo, mudanças de assunto etc.) aparecem como linhas separadas.
- **Áudios:** player embutido, nome do arquivo, SHA-256, formato real e, se houver `--transcricoes`, o texto transcrito (marcado como automático).
- **Imagens:** miniatura; clique para ampliar. Na tela ampliada: setas ← → e `Esc`, mensagem de origem, nome do arquivo, formato real (lido dos primeiros bytes, não da extensão), dimensões, tamanho, SHA-256 e EXIF (câmera, datas, GPS) se existir e o Pillow estiver instalado.
- Alertas em vermelho quando a **extensão do arquivo não confere com o formato real** ou quando o **tamanho do arquivo difere do registrado no banco**.

### Transcrição de áudios (opcional)

A transcrição é feita **no seu computador** (a primeira execução baixa o modelo, depois funciona offline) e demora: use `--limite 5` para testar. Pode ser interrompida e retomada.

```powershell
python ferramentas\visualizador_whatsapp\transcrever_audios.py --pasta "C:\evidencia\ios\Media\files\Audio" --saida transcricoes_audio.json
```

| Opção | O que faz |
|---|---|
| `--pasta` | Pasta com os áudios (obrigatória) |
| `--saida` | Arquivo JSON de saída (padrão `transcricoes_audio.json`) |
| `--modelo` | `tiny`, `base`, `small` (padrão), `medium`, `large-v3`: quanto maior, melhor e mais lento |
| `--idioma` | Idioma falado (padrão `pt`); `auto` detecta |
| `--dispositivo` | `cpu` (padrão) ou `cuda` (placa NVIDIA) |
| `--limite` | Só os N primeiros, para testar |

Depois, abra o visualizador com `--transcricoes transcricoes_audio.json`.

> A transcrição é **automática e pode errar** (nomes, gírias, ruído, sotaque). Use como auxílio de triagem e **confirme ouvindo o áudio**. No laudo, não cite a transcrição como se fosse a fala literal.

## Como ler o que a ferramenta mostra (cuidados periciais)

- **O visualizador mostra o que o banco registra**, não o que de fato aconteceu. Ausência de um dado não prova que ele não existiu.
- **Bancos anonimizados** (como os usados em estudo) podem ter dados alterados de propósito: datas removidas (as mensagens aparecem na ordem do banco, **sem dia nem hora; não invente datas para elas**), números encurtados e sufixos `~N` quando dois números ficaram iguais, e caracteres invisíveis no fim de números do Android (o programa os remove para agrupar as conversas).
- **Datas.** iOS guarda segundos desde 01/01/2001 (Cocoa); Android, milissegundos desde 01/01/1970. O programa converte e mostra no fuso escolhido; o valor bruto aparece ao passar o mouse na hora.
- **"Possível" CPF/telefone:** o filtro acha *padrões de texto* (CPF com dígitos verificadores válidos ou formatado; números com DDD; e-mails). Pode ter falso positivo e falso negativo. Confirme lendo a mensagem; no laudo, escreva "sequência *compatível com* CPF".
- **Participante "não ativo"** (iOS, `ZISACTIVE = 0`) é *compatível com* ter saído ou sido removido; o banco não diz qual dos dois nem quando.
- **Tipos de mensagem do Android** sem confirmação aparecem como `tipo_N_android_nao_confirmado`. Não tire conclusão sobre eles sem verificar.
- **"Modificado no disco"** (painel Integridade) é a data do arquivo na cópia que você abriu; costuma refletir a cópia/extração, não a criação da mídia no aparelho.
- **Alteração de arquivo:** só dá para afirmar com um manifesto ou hash de referência. Extensão ou tamanho que não conferem são *indícios* (podem ser efeito da anonimização, de conversão ou de extração incompleta), não prova de adulteração.
- **Mídia:** só o que está na pasta aparece para ouvir/ver. É comum o banco registrar milhares de mídias e a extração conter só uma parte. Os demais aparecem como "arquivo não está na pasta extraída".
- **Citações, encaminhamentos, chamadas, vídeos e mensagens apagadas** ainda não são mostrados nesta versão.

## Privacidade e GitHub

**Nunca suba para o GitHub** o banco, a mídia, o CSV exportado nem o JSON de transcrição: são dados de caso. O `.gitignore` da raiz já bloqueia `*.db`, `*.sqlite*`, `*.csv` e `transcricoes*.json`. Rode `git status` antes de cada commit e confira o que vai subir.

## Solução de problemas

| Sintoma | O que fazer |
|---|---|
| `python` "não é reconhecido" | Use `py` no lugar de `python`, ou instale o Python marcando "Add to PATH" |
| Porta em uso / não abre | Use `--porta 8766` (ou outra) e abra `http://127.0.0.1:8766/` |
| "Não reconheci este banco" | O `--db` precisa ser o `ChatStorage*.sqlite` (iOS) ou o `msgstore*.db` (Android) |
| Conversas sem nome (só número) | Passe também `--contatos` (ou deixe o `wa.db` ao lado do `msgstore.db`) |
| Imagens/áudios "não estão na pasta" | Confira `--midia` (deve apontar para `Media\files`, com `Image\` e `Audio\` dentro) |
| "Falta a biblioteca" na transcrição | `pip install faster-whisper` |
| Transcrição dá erro de `metadata_errors` | O PyAV está novo demais; o script aplica um ajuste sozinho. Se persistir: `pip install "av<19"` |
| Aviso de erro nas transcrições no topo da página | Rode de novo o mesmo comando de `transcrever_audios.py`: ele refaz só os que falharam |
| Acentos viram `?` no PowerShell | Só afeta o texto do console; a página do navegador não é afetada |

## Licença

Ver [`LICENSE`](../../LICENSE) na raiz do repositório.
