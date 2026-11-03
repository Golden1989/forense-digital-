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
python ferramentas/linha_do_tempo.py --sms mmssms.db --calls calllog.db --chrome History --fuso -5 --dia 2020-01-29
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

**Inconclusivo pelo `History` isoladamente.** As duas tentativas de download aparecem como **"cancelado"** na tabela `downloads` — o que, à primeira vista, sugeriria que o app nunca chegou a ser instalado por essa via. Esse é exatamente o tipo de achado que não pode ser fechado com um único artefato: o `History` registra o que o *Chrome* sabe sobre o download, não se o APK foi de fato instalado depois (isso ficaria em artefatos como o log de instalação de pacotes do sistema, fora do escopo dos scripts atuais). Vale registrar a ressalva: "download cancelado" não equivale a "ferramenta não instalada".

### Quesito 3 — apps instalados e permissões sensíveis

`analisa_packages.py packages.xml --fuso -5` (sem `--so-usuario`, pra ver o ranking completo) mostra, entre os apps de usuário, vários com a permissão `SYSTEM_ALERT_WINDOW` (desenhar sobre outros apps) concedida — inclusive apps de mensageria (`com.facebook.orca`, `com.viber.voip`) e o próprio discador do aparelho (`com.google.android.dialer`).

Rodando com `--so-usuario --fuso -5`, chama atenção que **a maioria dos 82 apps de usuário tem a mesma data de instalação** (29/01/2020, por volta das 19h UTC-5 — hora de ativação do aparelho), e não datas espalhadas pelo período investigado:

```
 1  2008-12-31 19:00:00  com.google.android.youtube  (instalador: com.android.vending)   <-- PRIMEIRO
 2  2008-12-31 19:00:00  com.google.android.googlequicksearchbox  (instalador: com.android.vending)
 ...
```

**Achado relevante, mas com ressalva.** Isso é exatamente o aviso que já está documentado no próprio script: apps empurrados durante o provisionamento inicial da conta Google compartilham a data de ativação, não a data real de uso/instalação pelo usuário. Antes de apontar "o usuário instalou N apps no dia X", é preciso separar esse lote inicial dos apps genuinamente instalados depois (ex.: os de mensageria instantânea, que o `packages.xml` mostra como instalados minutos depois, já na janela de interesse).

### Quesito 4 — linha do tempo de 29/01/2020

`linha_do_tempo.py --dia 2020-01-29` junta Chrome, SMS e chamadas numa sequência só:

```
11:33:27  CHROME  visita   google.com/search?q=magisk
11:33:35  CHROME  visita   magiskmanager.com
11:33:59  CHROME  visita   magiskmanager.com/downloading-magisk-manager
13:20:45  SMS     recebido  ...233205525   [codigo de verificacao do LINE, redigido]
13:30:46  SMS     recebido  732873          [codigo de verificacao do Telegram, redigido]
13:31:36  SMS     recebido  ...437514985   [codigo de verificacao do Signal, redigido]
```

(Os números completos e os códigos de verificação foram retirados deste documento — já expiraram e vêm de uma imagem pública, mas não acrescentam nada ao argumento.)

**Duas atividades distintas no mesmo dia, sem ligação direta entre si:** a pesquisa e navegação até a ferramenta de root, às 11h33, e uma sequência de SMS de verificação (LINE, Telegram, Signal) às 13h20–13h32. O quesito 3 já mostrou que 29/01/2020 é o dia de **ativação** do aparelho — então esses SMS e a instalação dos respectivos apps são exatamente o que se espera de um celular recém-ativado, e nada nos artefatos do Chrome, SMS ou `packages.xml` liga essa sequência de cadastros à pesquisa por "magisk" feita horas antes. A única evidência direta de interesse em *root*, neste quesito, continua sendo a navegação em si (quesito 1); o resto da atividade do dia é consistente com o uso normal de um aparelho novo.

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

**Indício de interesse em root; instalação não confirmada; a atividade do restante do dia é compatível com ativação normal do aparelho.**

O único achado que aponta diretamente para a suspeita do caso é a busca e navegação explícitas até uma ferramenta de *root* (Magisk) na manhã de 29/01/2020 (quesito 1). Os dois pontos a seguir pesam contra fechar a conclusão como "root confirmado":

1. O `History` marca as duas tentativas de download do Magisk Manager como "canceladas" (quesito 2) — sem uma fonte adicional (log de instalação de pacotes, por exemplo), não é possível confirmar se o *root* de fato ocorreu por essa via.
2. O restante da atividade do dia — a maior parte dos apps de usuário "instalados" (quesito 3) e os SMS de verificação de LINE/Telegram/Signal (quesito 4) — coincide com o dia de **ativação** do aparelho, não com a janela de root propriamente dita. Essa atividade tem uma explicação alternativa simples (configuração inicial de um celular novo) que não depende da hipótese de root, e os artefatos não mostram nenhuma ligação direta entre ela e a busca por "magisk". Tratar esses dois grupos de evidência como uma coisa só superestimaria o que de fato se sustenta.

**Recomendação:** preservar a imagem, buscar confirmação de root por outra via (ex.: binário `su`, propriedades de build, arquivos do Magisk no sistema de arquivos) antes de afirmar a violação de política, e aprofundar a investigação sobre o número `...195121037` (quesito 5), que não se encaixa no padrão de cadastro do dia 29/01.
