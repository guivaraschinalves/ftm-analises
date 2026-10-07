# FtM Análises

Análises de macroeconomia, finanças, economia monetária e política econômica,
uma por assunto, com os gráficos desenhados no navegador — sem build:
`index.html` + `app.js` + `styles.css`, e **um arquivo de dados por assunto** em
`dados/`.

No ar: <https://guivaraschinalves.github.io/ftm-analises/>

| Assunto | Dados | De onde vêm |
|---|---|---|
| **Taxa de 10 anos dos EUA** | `dados/juros-eua.json` | Baixados **sozinhos** todo dia do FRED (St. Louis Fed), séries `DGS10` e `GS10`, e do investing.com (intradiário) |
| **A bolsa nas eleições presidenciais** | `dados/eleicoes.json` | Baixados da API aberta do Ipeadata (Ibovespa diário desde 1993); `scripts/eleicoes.py`, rodado à mão |

O acervo intradiário fica à parte, em `dados/intradiario-10a.json`: é o arquivo
que **acumula** as cotações de 15 em 15 minutos (veja abaixo).

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

## A taxa de 10 anos dos EUA

Três gráficos: a história inteira, o ano corrente e o mês em detalhe. Os dois
primeiros vêm do **FRED**; o terceiro é intradiário e vem de outra fonte.

**Por que o CSV e não a API.** O FRED tem duas portas para o mesmo dado: a API
JSON (`api.stlouisfed.org`), que **exige chave** — sem `api_key` ela responde
`400 Variable api_key is not set` —, e o CSV público do gráfico
(`fredgraph.csv?id=SERIE`), que não exige nada e devolve a série inteira. O
script usa o CSV. Se um dia precisarmos de *vintages* (o que o mercado via em
cada data, no ALFRED) ou dos metadados da série, é trocar `baixar_serie` por uma
chamada à API com a chave num segredo do repositório — o resto do arquivo não
muda.

**Armadilha do FRED:** ele **trava** (timeout, não 403) quando a requisição se
identifica como navegador. Sem headers, com o `User-Agent` do `urllib`, responde
em 0,3 s. Não acrescente `User-Agent` em `scripts/juros_eua.py`.

**As séries:**

- `DGS10` — *Market Yield on U.S. Treasury Securities at 10-Year Constant
  Maturity*, **diária, desde 02/01/1962**: a taxa que o Tesouro americano
  publica na curva de *par yields*, interpolada para o prazo cheio de 10 anos.
  Fim de semana e feriado não existem no arquivo, e pregão sem cotação vem como
  `.` (o script descarta). O maior buraco da série é de 5 dias, e o site só
  corta a linha acima de 6 (`buracoMax`), então ela atravessa feriado sem
  furo.
- `GS10` — a mesma taxa na **média do mês, desde abril de 1953**. São nove anos
  a mais de história e é o mais longo que o FRED tem para o prazo de 10 anos;
  entra como o segundo recorte do cartão. (Existe uma série do NBER com yields
  de títulos longos do Tesouro de 1919 a 1944, mas ali "longo" não é 10 anos:
  é outro instrumento, não dá para emendar na mesma linha.)

O gráfico do ano corrente é a série diária filtrada pelo ano em `ANO_RECENTE`
(hoje 2026) — virado o ano, é só mudar essa constante. O do mês em detalhe sai
de `MES_DETALHE` (hoje `2026-09`).

### O intradiário

O FRED não tem dado intradiário: o `DGS10` é **uma cotação por dia**, a das
15h30 de Nova York. Para o gráfico do mês, a fonte é o endpoint de gráfico do
**investing.com** (id 23705), que responde sem chave desde que a requisição
mande o header `Domain-Id: www`. Duas coisas importam:

- **a janela é curta.** O endpoint devolve no máximo 744 pontos: ~1 mês de
  cotação horária (`PT1H`) ou ~13 dias de 15 em 15 minutos (`PT15M`). Por isso
  existe o acervo `dados/intradiario-10a.json`, que **só cresce**: cada rodada
  junta o que baixou ao que já estava guardado, e o gráfico é montado do
  acervo. **O que não for guardado hoje não volta mais** — se o site ficar um
  mês sem rodar, aquele mês fica sem intradiário;
- **não é o dado oficial.** É a cotação de mercado do papel, não o cálculo do
  Tesouro. O script compara as duas todo dia e imprime o resultado: na primeira
  carga, 20 dias conferidos, diferença média de **0,007 p.p.** e máxima de
  0,018 p.p. A linha atravessa a madrugada porque o Treasury é negociado na
  Ásia e na Europa; o corte no fim de semana é o mercado fechado.

A hora gravada é a de **Nova York** (é nela que saem o dado e a decisão do
Fed). A chave é o horário escrito por extenso (`2026-09-16T14:00`) e o
navegador a lê como se fosse UTC: o que importa é o espaçamento, e assim o
rótulo sai direto da chave, sem conta de fuso. Na virada do horário de verão
americano a hora repetida vira uma chave só.

Se a fonte intradiária cair, o script segue: mantém o acervo e continua
atualizando o resto.

### Os acontecimentos marcados

Os dois gráficos de 2026 levam uma linha do tempo: linha vertical na data,
rótulo curto no gráfico e a explicação inteira na lista embaixo do cartão, com
a fonte de cada uma. As listas estão em `EVENTOS_ANO` e `EVENTOS_MES`, no
script — **escritas na mão**, com data e número conferidos na fonte citada.
Nada ali é deduzido do próprio gráfico, e a nota do cartão diz o que a marca
significa: coincidência de data, não prova de causa.

No gráfico do mês a hora entra na marca (`2026-09-16T14:00`), então o dado das
8h30 e a decisão do Fed das 14h caem no ponto exato do salto.

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
dados/      juros-eua.json (gerado) + intradiario-10a.json (o acervo que acumula)
scripts/    juros_eua.py (FRED e intradiário, automático)
.github/workflows/atualizar.yml
```

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

### Por que não há gráfico do preço em torno da eleição

Porque não há o que mostrar. O retorno acumulado em qualquer janela ao redor da
votação cai entre os percentis 46 e 58 de todas as janelas do mesmo tamanho —
indistinguível de um trecho qualquer da série. Desenhar o caminho médio do
índice produziria uma linha serrilhada que o leitor leria como padrão, e os
testes negam que haja um. O gráfico de caminho é o da **volatilidade**, que é
onde a diferença aparece e que é lisa por construção.
