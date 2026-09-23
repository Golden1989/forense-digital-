# Hash de uma imagem forense

## Duas coisas diferentes que se chamam "hash da imagem"

Numa imagem `.E01` (EnCase/EWF), existem **dois hashes possíveis**, e eles **nunca vão bater entre si** — isso é esperado, não erro:

| O que você hasheia | O que prova | Como calcular |
|---|---|---|
| **Conteúdo adquirido** (os dados do disco, sem o container) | "os dados que estou analisando são os mesmos do disco original" | `ewfverify` (ver abaixo) |
| **Arquivo `.E01`** em si (o container, com compressão e metadados) | "esse arquivo não mudou desde que eu recebi" | `Get-FileHash` / `sha256sum` no `.E01` |

O formato E01 já guarda, da própria aquisição, o hash **MD5** e **SHA-1** do conteúdo (não SHA-256 — é um formato antigo). Pra ver esse valor:

```bash
# WSL — precisa do pacote ewf-tools (sudo apt install ewf-tools)
ewfinfo image.E01
```

Isso mostra a data de aquisição, a ferramenta usada e os hashes gravados. Pra **recalcular** o hash do conteúdo e conferir se ele ainda bate (integridade), ou pra pedir um SHA-256 do conteúdo (que o formato não guarda por padrão):

```bash
ewfverify -d sha256 image.E01
```

Ele relê a imagem inteira, compara com o hash gravado na aquisição e imprime o SHA-256 extra no fim.

## Hash do arquivo `.E01` (o mais simples, mas com ressalva)

Se o objetivo é só "prove que esse arquivo específico não foi alterado", basta hashear o arquivo. Dois jeitos, mesmo resultado:

### PowerShell (Windows)

```powershell
Get-FileHash .\image.E01 -Algorithm SHA256 | Tee-Object -FilePath image.E01.sha256
```

### WSL (Ubuntu / Linux)

```bash
sha256sum image.E01 | tee image.E01.sha256
```

`Tee-Object` e `tee` fazem o mesmo papel: mostram o resultado na tela **e** gravam num arquivo ao mesmo tempo.

O valor é idêntico nos dois terminais — só muda a aparência: o PowerShell mostra o hash em **maiúsculas** numa tabela; o `sha256sum` mostra `hash  nome-do-arquivo` em **minúsculas**. Na hora de comparar, ignore essa diferença de caixa.

Pra conferir depois que o hash ainda bate:

```bash
sha256sum -c image.E01.sha256
```

## MD5, SHA-1, SHA-256, SHA-512 — o que muda

O comando é o mesmo, só o algoritmo muda:

| Algoritmo | Tamanho do hash | PowerShell | WSL |
|---|---|---|---|
| **MD5** | 32 caracteres | `Get-FileHash arquivo -Algorithm MD5` | `md5sum arquivo` |
| **SHA-1** | 40 caracteres | `Get-FileHash arquivo -Algorithm SHA1` | `sha1sum arquivo` |
| **SHA-256** | 64 caracteres | `Get-FileHash arquivo -Algorithm SHA256` | `sha256sum arquivo` |
| **SHA-512** | 128 caracteres | `Get-FileHash arquivo -Algorithm SHA512` | `sha512sum arquivo` |

O que muda entre eles, na prática:

- **MD5 e SHA-1** são mais antigos e têm colisões conhecidas — ou seja, já foi demonstrado ser possível, com esforço deliberado, criar dois arquivos diferentes com o mesmo hash. Mesmo assim, continuam sendo **os mais usados em perícia** por herança histórica: é o que o formato E01 grava na aquisição, é o que a maioria das ferramentas de perícia (Sleuth Kit, FTK, EnCase) usa por padrão, e pra detectar corrupção acidental (não um ataque deliberado) eles continuam perfeitamente confiáveis.
- **SHA-256** é o padrão atual recomendado onde a ferramenta permitir — mais resistente a colisão, sem custo prático relevante de tempo de cálculo.
- **SHA-512** é o mais longo; usado quando se quer margem extra, mas não é padrão em perícia.

Pra gravar qualquer um deles em arquivo, o final do comando é sempre o mesmo:

```powershell
# PowerShell
Get-FileHash arquivo -Algorithm MD5 | Tee-Object -FilePath arquivo.md5
```

```bash
# WSL
md5sum arquivo | tee arquivo.md5
```

Se pedirem vários hashes de uma vez, é um cálculo separado por algoritmo — não existe um comando que calcule todos juntos numa passada só.
