# Caso fictício: celular corporativo rooteado?

> **Isto é diferente da imagem da disciplina.** O resto deste repositório evita propositalmente qualquer dado de caso real (veja o porquê no [README](../README.md)), porque a imagem usada na matéria é material de avaliação. Este documento é o oposto: usa uma **imagem pública**, que qualquer pessoa pode baixar e conferir, criada especificamente para treino da comunidade de forense digital — não tem relação com a disciplina nem com nenhuma prova. A **empresa e a suspeita abaixo são fictícias**; o **aparelho e os artefatos técnicos são reais**.

## Fonte dos dados

- **Imagem:** "Android 10 Image" — Google Pixel 3 (modelo G013A), Android 10.
- **Criada por:** Joshua Hickman ([thebinaryhick.blog](https://thebinaryhick.blog)), doada ao [Digital Corpora](https://digitalcorpora.org/corpora/cell-phones/android-10/), um acervo público mantido para pesquisa, educação e treinamento em forense digital.
- **Download usado:** extração de arquivos ("Non-Cellebrite Extraction"), sem precisar de ferramenta paga.
- **Documentação oficial:** a imagem vem com um PDF de 36 páginas descrevendo, minuto a minuto, cada ação feita no aparelho durante a criação (apps instalados, mensagens, chamadas, navegação). Os quesitos abaixo foram respondidos **só com os scripts deste repositório**, sem consultar esse "gabarito" — ele serve apenas como contexto de proveniência da imagem.
- Todos os horários da imagem original são UTC-5 (Eastern Standard Time); os comandos abaixo usam `--fuso -5` para bater com a documentação oficial.

## Cenário (fictício)

A TI da **Exemplo Tecnologia Ltda.** encontrou no aplicativo de MDM um alerta de "dispositivo não íntegro" num Google Pixel 3 corporativo. A suspeita: o funcionário teria feito *root* do aparelho (prática proibida pela política de segurança da empresa) para instalar aplicativos fora da loja corporativa. O aparelho foi recolhido e uma extração foi realizada.

## Quesitos

1. Há indício de que o usuário pesquisou ou tentou obter uma ferramenta de *root* no aparelho?
2. Essa ferramenta foi de fato baixada? O download foi concluído?
3. Quais aplicativos de usuário foram instalados no período, e algum deles tem permissões sensíveis (câmera, SMS, sobrepor outros apps) que mereçam atenção?
4. Reconstitua a linha do tempo do primeiro dia de uso após a suspeita de root (29/01/2020): o que o usuário fez, em que ordem?
5. Existem números em chamadas ou SMS que não constam na agenda de contatos do aparelho?
6. Há contatos marcados como apagados que devam ser preservados para a investigação?

## Metodologia

Todos os comandos abaixo foram rodados com os scripts de [`ferramentas/`](../ferramentas/) direto sobre os arquivos extraídos (`History`, `Favicons`, `Cookies` do Chrome; `mmssms.db`, `calllog.db`, `contacts2.db`; `packages.xml`), sem nenhuma alteração nos arquivos originais:

```
python ferramentas/resumo_navegacao.py History --site magisk --fuso -5
python ferramentas/downloads_chrome.py History --fuso -5
python ferramentas/analisa_packages.py packages.xml --so-usuario --fuso -5
python ferramentas/linha_do_tempo.py --sms mmssms.db --calls calllog.db --chrome History --packages packages.xml --fuso -5 --dia 2020-01-29
python ferramentas/contatos_merge.py --contacts contacts2.db --calls calllog.db --sms mmssms.db --fuso -5
python ferramentas/favicons_fora_do_historico.py --favicons Favicons --history History --fuso -5
```

## Achados

### Quesito 1 — pesquisa por ferramenta de root

`resumo_navegacao.py --site magisk` mostra a primeira atividade do período, uma busca direta no Google:

```
primeira:       2020-01-29 11:33:27  https://www.google.com/search?q=magisk&oq=magisk...
intermediaria:  2020-01-29 11:33:55  https://magiskmanager.com/#How_to_Download_Magisk_Manager...
ultima:         2020-02-14 16:58:15  https://magiskmanager.com/downloading-magisk-manager
```

**Sim.** Há busca explícita pelo termo "magisk" (ferramenta de *root* conhecida) às 11:33:27, seguida de navegação até `magiskmanager.com` e à página de download, no mesmo minuto.

### Quesito 2 — o download foi concluído?

`downloads_chrome.py` registra dois downloads do arquivo (via redirecionamento até um pacote de release do GitHub), mas ambos com o mesmo resultado:

```
1. [cancelado, 2143331 bytes, perigo: nao perigoso]
   baixado de: https://magiskmanager.com/downloading-magisk-manager
   URL final:  https://github-production-release-asset-.../...  (3 URLs na cadeia)
   inicio: 2020-01-31 21:11:22
2. [cancelado, 2143331 bytes, perigo: nao perigoso]
   baixado de: https://magiskmanager.com/downloading-magisk-manager
   inicio: 2020-02-14 16:58:20
```

Pelo `History` isoladamente, as duas tentativas de download aparecem como **"cancelado"** na tabela `downloads` — o que, sozinho, sugeriria que o app nunca chegou a ser instalado por essa via. Mas `analisa_packages.py packages.xml --fuso -5` mostra outra coisa: o próprio pacote do Magisk está instalado no aparelho, com instalação **1 minuto e 4 segundos** depois da última visita à página de download:

```
53  2020-01-29 11:35:03  com.topjohnwu.magisk  (instalador: com.google.android.packageinstaller)
```

**Sim, confirmado — mas só ao cruzar duas fontes.** O instalador é `com.google.android.packageinstaller`, não a Play Store (`com.android.vending`), exatamente o que se espera de um APK baixado e instalado manualmente, e não houve atualização posterior (`atualizado_em` é igual a `instalado_em`). Isso ilustra bem por que não se deve fechar uma resposta com um único artefato: o `History` registra apenas o que o *Chrome* sabe sobre o download (e aqui ele mostra "cancelado", possivelmente porque o arquivo foi retomado ou finalizado por outro caminho que o `History` não captura); o `packages.xml` é quem confirma que o APK foi, de fato, instalado.

### Quesito 3 — apps instalados e permissões sensíveis

`analisa_packages.py packages.xml --fuso -5` (sem `--so-usuario`, pra ver o ranking completo) mostra, entre os apps de usuário, vários com a permissão `SYSTEM_ALERT_WINDOW` (desenhar sobre outros apps) concedida — inclusive apps de mensageria (`com.facebook.orca`, `com.viber.voip`) e o próprio discador do aparelho (`com.google.android.dialer`).

Rodando com `--so-usuario --fuso -5`, a lista mistura dois grupos bem diferentes de data:

```
 1  2008-12-31 19:00:00  com.google.android.youtube  (instalador: com.android.vending)   <-- PRIMEIRO
 2  2008-12-31 19:00:00  com.google.android.googlequicksearchbox  (instalador: com.android.vending)
 ...
58  2020-01-29 12:02:47  com.discord  (instalador: com.android.vending)
 ...
```

**Atenção ao ler essas datas: `2008-12-31`/`2009` não é uma instalação real.** É o valor-padrão que o próprio Android grava no `packages.xml` quando o app não tem uma data de instalação individual registrada (de novo, típico dos apps pré-instalados pelo fabricante/Google, mesmo os que ficam tecnicamente em `/data/app`) — é só uma coincidência de fuso que, em UTC-5, esse valor-padrão cai em 31/12/2008 às 19h em vez de já virar 2009. A maioria dos 82 apps de usuário tem essa data-padrão; são os poucos com data real de **29/01/2020** (como `com.discord` acima, ou o próprio `com.topjohnwu.magisk` do quesito 2) que de fato dizem algo sobre o que o usuário instalou nesse dia. Antes de apontar "o usuário instalou N apps no dia X", é preciso separar esse lote de data-padrão dos apps genuinamente instalados depois.

### Quesito 4 — linha do tempo de 29/01/2020

`linha_do_tempo.py --packages packages.xml --dia 2020-01-29` junta Chrome, SMS, chamadas e instalação de apps numa sequência só:

```
11:33:27  CHROME  visita     google.com/search?q=magisk
11:33:35  CHROME  visita     magiskmanager.com
11:33:59  CHROME  visita     magiskmanager.com/downloading-magisk-manager
11:35:03  APP     instalado  com.topjohnwu.magisk  com.google.android.packageinstaller
12:02:47  APP     instalado  com.discord  com.android.vending
   ... (mais 30 apps de mensagem/rede social instalados entre 12:02 e 12:12)
13:20:45  SMS     recebido  ...233205525   [codigo de verificacao do LINE, redigido]
13:30:46  SMS     recebido  732873          [codigo de verificacao do Telegram, redigido]
13:31:36  SMS     recebido  ...437514985   [codigo de verificacao do Signal, redigido]
```

(Os números completos e os códigos de verificação foram retirados deste documento — já expiraram e vêm de uma imagem pública, mas não acrescentam nada ao argumento.)

**Duas fases bem distintas no mesmo dia.** A primeira (11h33–11h35) é uma sequência direta e confirmada: pesquisa por "magisk", navegação até a página de download, e instalação do pacote 1 minuto e 4 segundos depois — isso é a materialização do quesito 2. A segunda fase, quase meia hora depois (12h02–13h32), é uma instalação em lote de mais de 30 apps de mensagem/rede social pela Play Store, seguida dos SMS de verificação correspondentes — um padrão de configuração inicial de aparelho, não de uso contínuo. Nada nos artefatos liga causalmente essa segunda fase à pesquisa por "magisk": são leituras separadas da mesma linha do tempo, e tratá-las como uma coisa só superestimaria o que os dados sustentam.

### Quesito 5 — números fora da agenda

`contatos_merge.py` cruza `contacts2.db` com `calllog.db`/`mmssms.db` e lista, ao final, os números que aparecem em chamadas ou SMS mas não batem com nenhum contato salvo:

```
NUMEROS EM CHAMADAS/SMS QUE NAO ESTAO NA AGENDA: 16
  ...32665     SMS: 8 [recebido=8] primeira 2020-01-29 13:50:24 | ultima 2020-02-13 16:12:24
  ...195121037 chamadas: 2 [perdida=1, correio de voz=1] primeira 2020-02-12 10:37:29
  ...233205525 SMS: 1 [recebido=1] primeira 2020-01-29 13:20:45
```

**Sim, 16 números.** A maioria são remetentes curtos (códigos de verificação de apps como os do quesito 4) — esperado ao cadastrar vários mensageiros no mesmo dia — mas o número `...195121037`, com uma chamada perdida e uma de correio de voz vários dias depois (12/02), não se encaixa nesse padrão e mereceria confirmação com o usuário do aparelho.

### Quesito 6 — contatos apagados

```
python ferramentas/contatos_merge.py --contacts contacts2.db --so-apagados
```

```
#raw6 Josh Hickman  [APAGADO]   telefones: +990841016803084  contas: 858233690 (org.telegram.messenger)
#raw7 Josh Hickman  [APAGADO]   telefones: +990841016803084  contas: 858233690 (org.telegram.messenger)
```

**Sim, 2 registros** marcados como apagados (`deleted=1` em `raw_contacts`), ambos sincronizados via Telegram. Como o `contatos_merge.py` só lê o que ainda está no banco, a recomendação de laudo aqui é preservar a imagem sem alterações — um registro marcado como apagado no provedor de contatos pode ainda ser recuperável por completo em ferramentas de análise de SQLite não alocado (fora do escopo dos scripts atuais).

## Bônus: um alerta do próprio método

Rodando `favicons_fora_do_historico.py` no mesmo `History`, 13 páginas aparecem com favicon salvo mas **sem visita correspondente** (ESPN, Wikipedia, eBay, Amazon, Facebook, YouTube...), todas com o mesmo horário de atualização do ícone (11:33:09, poucos segundos antes da busca por "magisk"). Isso **não é indício de limpeza de histórico** — é o conjunto de sites de sugestão/atalho que o Chrome do Android pré-carrega na primeira abertura. Serve de exemplo real do próprio aviso que já está no docstring do script: "ausência no histórico não prova que a página foi visitada e depois apagada".

## Conclusão (fictícia)

**Instalação da ferramenta de root confirmada por duas fontes cruzadas; a atividade do restante do dia é configuração normal de aparelho novo, sem ligação demonstrada com o root.**

Pesquisa, navegação e instalação do Magisk formam uma sequência direta e confirmada entre 11h33 e 11h35 de 29/01/2020: busca pelo termo (quesito 1), download pela página oficial e, 1 minuto e 4 segundos depois da última visita, o pacote `com.topjohnwu.magisk` aparece instalado via `packageinstaller` (quesito 2). O `History` isolado mostrava os downloads como "cancelados" — só cruzando com o `packages.xml` a instalação fica confirmada, o que já é em si um achado metodológico: nenhuma fonte única bastava.

O restante do dia é uma atividade separada: mais de 30 apps de mensagem/rede social instalados pela Play Store entre 12h02 e 12h12, seguidos dos SMS de verificação correspondentes (quesitos 3 e 4). Esse padrão é típico de configuração inicial de um aparelho recém-ativado, e nenhum artefato liga essa fase à pesquisa por "magisk" feita antes. Separar as duas fases evita a leitura exagerada de "o usuário instalou N apps suspeitos no mesmo dia do root" quando, na prática, a maioria é configuração normal.

**Recomendação:** confirmar com o usuário o motivo da instalação do Magisk — já que a política da empresa proíbe root, o achado do quesito 2 sozinho já sustenta a abertura de um processo interno — e aprofundar a investigação sobre o número `...195121037` (quesito 5), que não se encaixa no padrão de cadastro do dia 29/01.
