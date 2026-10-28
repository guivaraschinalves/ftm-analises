# FtM Análises

Análises de macroeconomia, finanças, economia monetária e política econômica,
uma por assunto, com os gráficos desenhados no navegador — sem build:
`index.html` + `app.js` + `styles.css`, e **um arquivo de dados por assunto** em
`dados/`.

No ar: <https://guivaraschinalves.github.io/ftm-analises/>

| Assunto | Dados | De onde vêm |
|---|---|---|
| **A bolsa nas eleições presidenciais** | `dados/eleicoes.json` | Baixados da API aberta do Ipeadata (Ibovespa diário desde 1993); `scripts/eleicoes.py`, rodado à mão |
| **Os quatro quadrantes de Charles Gave** | `dados/gave.json` | Shiller (Yale), FRED, Banco Mundial e Ken French; `scripts/gave.py`, **sozinho** todo dia |
| **Análise de Cenário: 28/10/26 - Decisão do FOMC** | `dados/cenario-2026-10-28-fomc.json` | FRED, BLS, Fed de San Francisco, ISM (investing.com), Tesouro (MTS e TIC), Census e BIS; `scripts/cenario_fomc.py`, rodado à mão |
| **A defasagem dos combustíveis** | `dados/defasagem-combustiveis.json` | Montados a partir das planilhas de [`planilhas/`](planilhas/); `scripts/defasagem_combustiveis.py`, rodado à mão |

O assunto **Petróleo, derivados e comércio exterior** junta, ainda sem texto,
os gráficos de petróleo, derivados, contas externas e pauta do comércio exterior: `dados/petroleo.json`, montado por
`scripts/petroleo.py` (rodado à mão) a partir dos arquivos anuais do **Comex
Stat**, da produção de petróleo e das refinarias da **ANP**, do refino mundial
da **JODI**, das contas nacionais do **IBGE** (SIDRA), do IC-Br em dólar do
**SGS**, do Brent do **FRED** e das planilhas de oferta de
[`planilhas/`](planilhas/). As contas e as armadilhas de cada fonte estão no
cabeçalho de `scripts/petroleo.py` e de `scripts/petroleo_extra.py`. O agregado
mensal do Comex fica em `dados/.cache-comex/` (versionado, 2 MB): sem ele a
primeira rodada baixa 5 GB e leva uma hora.

Fora do site, em **[`planilhas/`](planilhas/)**, ficam sete planilhas de
petróleo, derivados e Petrobras: oferta de diesel e de gasolina, defasagem
contra o PPI, composição do preço na bomba e o modelo contábil do represamento
no IPCA. Elas não alimentam gráfico nenhum daqui, são material de análise, e
têm o próprio [README](planilhas/README.md).

O motor de desenho é o mesmo do [ftm-dados](https://github.com/guivaraschinalves/ftm-dados):

- **Menu na lateral** — um assunto retrátil por arquivo de dados, com as seções
  dentro e os gráficos dentro delas. A página tem a mesma árvore e **tudo abre
  fechado**: a tela inicial é o índice.
- **Tela cheia** — da página inteira (botão na lateral) e de um gráfico só
  (botão **Tela cheia** no cartão). Ali os controles viram um menu de
  hambúrguer e somem sozinhos depois de uns segundos parados.
- **Anotar à mão** — no gráfico ampliado, ligue **Desenhar** e arraste para
  rabiscar por cima; o **Baixar PNG** do visor sai com as anotações dentro.
- **Modo escuro/claro**, **baixar** (PNG, JPG, PDF, SVG e CSV, em tamanho de
  apresentação 16:9 ou de Instagram) e **período** (Tudo / 20 / 10 / 5 / 2 / 1
  ano) como no ftm-dados.

## Como mudar o texto de uma análise

A prosa não mora no código. Ela fica em **[`textos/`](textos/)**, um arquivo
por assunto, e dá para editar pelo editor do próprio GitHub, no navegador ou
no celular. Ao salvar, a Action **Publica o texto** costura o texto novo no
JSON de `dados/` e o site sai atualizado sozinho.

O formato é pobre de propósito, e são cinco regras:

| | |
|---|---|
| `# Título` | o nome do assunto, uma vez no topo |
| `## Título` | abre uma seção; `##` sozinho é uma seção **sem** título, que não aparece no índice |
| `chave: nome` | liga a seção aos gráficos que o script monta para ela |
| `fonte: id \| rótulo \| url` | uma linha por fonte |
| `[trecho](fonte:id)` | sublinha o trecho e puxa a fonte para a margem, na altura dele, com uma linha de chamada |
| `figura: id \| arquivo \| legenda \| crédito \| url` | declara uma imagem; `[figura:id]` num parágrafo sozinho é onde ela entra |

No corpo: linha em branco separa parágrafo e `**assim**` fica em negrito. Nada
mais. Não é Markdown de verdade, e é melhor assim, porque o que o site aceita
é exatamente isto.

**O que a Action NÃO faz:** ela não recalcula número nenhum. Não abre
planilha, não baixa PDF da Petrobras, não consulta o SIDRA. Roda em segundos e
nunca quebra porque uma fonte saiu do ar. Quando os números mudarem, rode o
gerador completo à mão:

```bash
python scripts/defasagem_combustiveis.py
```

## Para acrescentar um assunto

1. `scripts/<assunto>.py` gera `dados/<assunto>.json` (só biblioteca padrão,
   como os outros repos);
2. acrescente o arquivo à lista `FONTES` no começo de `app.js` — **a ordem ali é
   a ordem da página**;
3. um passo novo em `.github/workflows/atualizar.yml`, se o dado se atualiza
   sozinho;
4. uma linha na tabela deste README.

O formato do JSON:

```jsonc
{
  "assunto": "Taxa de 10 anos dos EUA",   // o nome retrátil do menu
  "fonte": "FRED (…) e FtM",              // vai no rodapé e no canto do gráfico
  "referencia": "2026-09-25",             // AAAA-MM-DD ou AAAA-MM: até quando vai o dado
  "atualizado": "2026-09-29",
  "apresentacao": "…",                    // parágrafo de abertura do assunto (opcional)
  "secoes": [{
    "titulo": "História",
    "graficos": [{
      "id": "eua-10a",                    // âncora do link no menu
      "titulo": "…", "subtitulo": "…",
      "unidade": "%",                      // "%", "bi" (R$ bilhões) ou "anos"
      "diario": true,                      // eixo X em dias; sem isso, mensal
      "intradiario": true,                 // eixo X em blocos de 15 min (chave "AAAA-MM-DDTHH:MM")
      "eventos": [{ "em": "2026-09-16T14:00", "rot": "Fed sobe o juro",
                    "quando": "16 de setembro, 14h", "texto": "…" }],
      "series": [{ "nome": "10 anos", "cor": "#FFFFFF",
                   "dados": [["1962-01-02", 4.06]],
                   "rotulo": true,          // valor do último ponto na ponta da linha
                   "legenda": false }],     // linha única não precisa de legenda
      "nota": "…"                          // linha de texto embaixo do cartão
    }]
  }]
}
```

Outras opções que o `app.js` entende, todas herdadas do ftm-dados: `variantes`
(recortes do mesmo cartão, um por vez — o recorte escolhido entra no subtítulo,
então a imagem baixada diz qual é), `categorias` (eixo X de rótulos, não de
tempo), `tipo: "barra"` (empilhada), `eixo: {min, max}`, `buracoMax`, `passoX`,
`periodoPadrao` e `barra`.

`index.html` chama `app.js?v=N` e `styles.css?v=N`: **suba o N** a cada mudança
de código, senão quem já visitou o site continua vendo a versão em cache.

## Testar localmente

```bash
python3 -m http.server 8000   # http://localhost:8000
```

## Estrutura

```
index.html  styles.css  app.js
assets/     fundo.jpg (fundo dos slides do FtM), logo-ftm.svg, favicon.svg
dados/      um JSON por assunto (gerado pelos scripts)
scripts/    um gerador por assunto; gave.py roda sozinho na Action
.github/workflows/atualizar.yml
```

### Cartão de tabela, e as duas marcações da nota

Nem todo achado é uma linha ou uma barra. `tipo: "tabela"` no gráfico troca o
SVG por uma tabela HTML dentro do mesmo `.frame`: `colunas` é a lista de
cabeçalhos (`{rot, num}` — `num` alinha à direita e usa algarismos de largura
fixa, para as casas decimais caírem umas sobre as outras) e `linhas` é uma lista
de listas, com cada célula em texto ou `{t, cor, forte}`. Tabela não tem tela
cheia nem PNG — não há desenho para ampliar nem para rasterizar —, mas o **CSV
sai igual** ao de qualquer cartão.

A **nota** passou a aceitar duas marcações, e só duas: linha em branco separa
parágrafo e `**assim**` fica em negrito. É o bastante para definir um termo
técnico no meio da explicação sem o texto virar um bloco só, e de propósito não
é Markdown — não quero abrir a porta a HTML vindo do arquivo de dados.

## Análise de Cenário

**Comentários (só na análise de cenário)**: escritos em
`textos/comentarios/cenario-2026-10-28-fomc.md`, um bloco por gráfico:

```
## Votos dissidentes no FOMC
Texto do comentário, com **negrito** se precisar.

Outro parágrafo.
```

**Pelo próprio site:** cada gráfico da análise de cenário tem, à direita, a
aba "Comentar" / "Comentário". Abre, escreve, "Salvar": o site grava neste
mesmo arquivo pela API do GitHub. Na primeira gravação ele pede uma chave do
GitHub (token *fine-grained* com **Contents: Read and write** só no
ftm-analises), que fica no `localStorage` do navegador
(`ftm_analises_github`). Até a Action publicar, o navegador de quem escreveu
mostra a versão nova (`ftm_analises_comentarios_pendentes`, 15 min).

O `##` é o título do gráfico como aparece no site (ou o id dele). Editou e deu
push (dá pelo próprio GitHub, até do celular), a Action "Publica o texto"
costura no JSON e o comentário aparece à direita do gráfico, num painel que
abre e fecha. Título que não casa com nenhum gráfico faz a Action falhar e
listar os títulos certos. Apagar o bloco apaga o comentário.

**Votos dissidentes do FOMC**: planilha de Thornton e Wheelock que o St. Louis
Fed mantém (`fomc_dissents_data.xlsx`, desde 1936; baixa só **sem**
User-Agent de navegador, como o FRED). Reunião que a planilha ainda não tem
entra à mão em `DISSIDENTES_MANUAL` no `cenario_fomc.py`, lida do comunicado;
a planilha ganha quando trouxer a data.

Um retrato da economia numa data, um arquivo por cenário. O campo `"grupo":
"Análise de Cenário"` no JSON junta esses assuntos sob um cabeçalho no índice
e põe o nome do grupo acima do título do artigo. O próximo cenário é outro
arquivo com o mesmo `grupo`, acrescentado ao fim de `FONTES`.

O primeiro, **28/10/26 - Decisão do FOMC**, sai de `scripts/cenario_fomc.py` e
tem nove seções: inflação, mercado de trabalho, atividade, moeda, contas do
governo, crédito, data centers, fluxo de capital e juros. As fontes e as
armadilhas de cada uma estão no cabeçalho do script. As principais:

- **FRED sem User-Agent, uma série por pedido.** Num lote, um id que não existe
  derruba o lote inteiro com 404.
- **CPI em 12 meses pelo índice sem ajuste sazonal**, que é o oficial. Com
  ajuste, set/26 dá 4,0% em vez de 3,7%.
- **ISM** não está mais no FRED: vem do gráfico de eventos do investing.com,
  com a data da divulgação (o mês de referência é o anterior).
- **TIC**: dois arquivos emendados, o antigo (`s1_globl`, de 1977 a jan/2023)
  e o novo (SLT, de fev/2023 em diante). Bate com o investimento em carteira do
  balanço de pagamentos (correlação de 0,90 nos totais anuais), menos em 2020,
  quando a compra foi de T-bills, que são de curto prazo.
- **Breakeven do payroll** segue o método do St. Louis Fed: crescimento da
  população de 16+ × participação × (1 − desemprego) × razão entre o emprego do
  payroll e o da pesquisa domiciliar. A população é a realizada, sem os meses
  de janeiro, que trazem o ajuste anual do Census. A faixa cinza é a
  estimativa do próprio St. Louis Fed para 2026 (15 a 87 mil).
- **CPI e PCE por componente** vêm dos Excels do Fed de San Francisco; o link
  muda a cada atualização e o script o acha na página.

Duas opções novas no `app.js` vieram com ele: `sombras` (faixas de fundo,
`[{de, ate}]`, usadas para as recessões do NBER) e as unidades `mil`, `h` e `pb` (pontos-base).
Depois veio `eixoDireita` (uma chave de unidade): o eixo da direita repete a
mesma escala com outra unidade, um para um. É o gráfico dos ativos do Fed, com US$
trilhões à esquerda e % à direita. A série que usa a unidade da direita leva
`unidade` própria, que vale para o rótulo do último ponto e para a caixa do mouse.

## Os quatro quadrantes de Charles Gave

`python3 scripts/gave.py` grava `dados/gave.json` (roda na Action diária). É o
método do livro *The General Theory of Portfolio Construction* (Charles Gave,
Gavekal, 2024), capítulos 3, 4 e 6: cada razão contra a própria média móvel de
7 anos (84 meses), +1 acima e -1 abaixo.

| Razão | Eixo |
|---|---|
| S&P 500 / WTI | eficiência energética (direita ou esquerda) |
| retorno total do título de 10 anos / ouro | moeda boa ou ruim (baixo ou cima) |
| S&P 500 / ouro | mercado de alta ou de baixa |
| ouro / WTI | antecede recessões (cap. 6) |

Fontes: S&P 500 e juro longo do Shiller (Yale, até ago/2023; o arquivo parou
ali) emendados com SP500 e GS10 do FRED (a diferença nos meses comuns é zero);
WTISPLC do FRED; ouro do `datasets/gold-prices` (Pink Sheet do Banco Mundial
desde 1960, média anual antes). O retorno total do título é calculado do juro
(título ao par, vendido um mês depois ao juro novo). O mês corrente fica de
fora. A cópia do arquivo de Yale fica em `dados/.cache-gave/` para quando o
site não responder.

A seção "A carteira de Gave" simula, desde jan/1970 e com rebalanceamento
mensal, a permanente de Browne (25% em ações, título, ouro e caixa), a de três
ativos (título ou ouro pela regra), a com energia e a Browne dinâmica. Caixa é
o TB3MS; ações de energia, a carteira "Enrgy" das 12 indústrias do Ken French
(o XLE só começa em 1998); dividendos do Shiller até jun/2023 e, depois, o
último rendimento. Os retornos reais batem com o livro (4,1 / 5,6 / 5,1 / 6,4%
contra 4,1 / 5,5 / ~5 / 6,1%); volatilidade e queda saem menores porque os
preços são médias mensais. Out/2025 não tem CPI e é interpolado.

## A bolsa nas eleições presidenciais

`python3 scripts/eleicoes.py` baixa da API OData aberta do Ipeadata (sem chave)
e grava `dados/eleicoes.json`. Não entra na Action: a amostra só muda de quatro
em quatro anos.

| Série | O que é |
|---|---|
| `GM366_IBVSP366` | Ibovespa, fechamento diário, desde 27/04/1993 |
| `GM366_IBVSPV366` | Ibovespa, volatilidade — **só conferência**, ver abaixo |

São 9 eleições e **15 turnos já realizados**, contra 8.315 pregões de base.
1994 e 1998 foram decididas no 1º turno (não têm segundo); o 2º turno de 2026
está marcado para 25/10 e ainda não aconteceu.

**Janela que não fechou vira `None`, e o gráfico não desenha o ponto.** O 1º
turno de 2026 tem dois pregões de vida: a reação dele existe, a volatilidade dos
21 pregões seguintes não, e o retorno de 60 pregões muito menos. Ele aparece no
gráfico da reação e some dos outros três — cada um filtra por conta própria, e
as notas dizem por quê. Inventar a conta com os dias que há seria comparar um
mês com dois dias.

### Quatro decisões de método que mudam o resultado

- **A volatilidade do Ipea não entra nas contas.** Ela é desvio-padrão móvel de
  ~21 pregões — o script confere isso a cada rodada (correlação 1,000 com o
  nosso cálculo) e aborta se deixar de ser. Como olha um mês para trás, no dia
  seguinte à eleição ela ainda é quase toda feita de dias anteriores a ela. A
  volatilidade usada aqui é recalculada dos fechamentos, com janelas
  explícitas.
- **A janela do 2º turno se sobrepõe ao 1º.** Os turnos distam 13 a 18 pregões,
  então "os 21 pregões antes do 2º turno" incluem o 1º turno e sua agitação.
  Comparar esse "antes" contaminado com um "depois" limpo faz a volatilidade
  parecer cair por construção: na janela suja ela cai em **5 de 6** segundas
  voltas, na limpa em **3 de 6**. O gráfico mostra os dois recortes.
- **Tudo é normalizado pelo desvio-padrão do próprio ano.** Um movimento de 3%
  em 1994, quando a bolsa andava 3,9% por dia, não é o mesmo que 3% em 2010,
  quando andava 1,3%. Sem essa correção os anos 1990 dominam qualquer média.
- **Nada de teste t.** Com 6 a 8 casos por grupo, os testes são de sinal
  (binomial) e de permutação, que não supõem formato de distribuição. As
  comparações de retorno são contra a distribuição de **todas** as janelas do
  mesmo tamanho desde 1993, por percentil.

### O que a análise achou — e o que não achou

Não existe: direção previsível (8/15 altas, p=1,00), volatilidade elevada antes
da eleição (8/14 acima do normal do ano, p=0,79), rali entre os turnos (+1,45%
contra base de +2,18%) nem retorno anormal em qualquer janela de −60 a +60
pregões (percentis 46 a 58).

Existe: o dia seguinte é um dia grande (mediana de 1,42 desvios-padrão do ano;
só 13% dos pregões do ano se mexem mais), e **o 1º turno de 2026 é o maior
movimento da série** — +7,70%, ou +6,06 desvios-padrão, quase o dobro do recorde
anterior (+3,28 dp em 2018) e, o principal, **a agitação sobe
quando o 1º turno não resolve a disputa** — razão de 1,27 contra 0,92 nas
votações que definiram o presidente, permutação p=0,029. A incerteza se resolve
quando o presidente é definido, não quando há eleição.

### O ano eleitoral partido em dois

Dois cartões respondem "quanto rendeu até a eleição e quanto depois dela": o
ano é cortado na **véspera do 1º turno**, e os anos sem eleição levam o mesmo
corte de calendário (a véspera do 1º domingo de outubro) para servir de régua.

Nas duas metades os números são quase iguais — **+5,4%** contra **+7,1%** até a
votação, **+5,8%** contra **+5,0%** depois. A coluna do ano todo parece dizer
outra coisa (**+1,0%** nos anos de eleição contra **+19,9%** nos demais), mas a
diferença **não resiste ao teste**: por permutação ela aparece em 43% das vezes
só por acaso. São sete anos completos, dois deles de crise (1998 e 2002).

**1994 fica fora destes dois cartões.** Do fim de 1993 à véspera da eleição o
índice subiu **1.360%** — isso é a inflação do ano em que o Real estreou, não o
mercado; em termos reais ele caiu. Um número desses não divide eixo com +6%, e
qualquer média que o inclua vira um número sobre 1994. Nos outros cartões ele
continua, porque lá a medida é de um dia e a inflação de um fim de semana é
irrelevante.

### Por que não há gráfico do preço em torno da eleição

Porque não há o que mostrar. O retorno acumulado em qualquer janela ao redor da
votação cai entre os percentis 46 e 58 de todas as janelas do mesmo tamanho —
indistinguível de um trecho qualquer da série. Desenhar o caminho médio do
índice produziria uma linha serrilhada que o leitor leria como padrão, e os
testes negam que haja um. O gráfico de caminho é o da **volatilidade**, que é
onde a diferença aparece e que é lisa por construção.
