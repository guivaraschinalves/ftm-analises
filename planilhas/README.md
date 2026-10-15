# Planilhas de combustíveis

Sete planilhas sobre petróleo, derivados e Petrobras. Cada uma tem uma aba
LEIA-ME que explica fonte, método e armadilha; este arquivo só diz qual é
qual e como refazer.

Elas vieram do `ftm-dados` em outubro de 2026. Lá o assunto era outro (IPCA,
fiscal, dívida, Tesouro) e os scripts de combustível não entravam em nenhum
workflow automático, então ficavam de carona. Aqui ficam junto das análises
que as usam.

## As planilhas

| Arquivo | O que tem |
|---|---|
| `oferta-diesel.xlsx` | Quem fornece o diesel do Brasil, mês a mês: produção por refinaria, importação por agente e por empresa, vendas por tipo, e o perfil do fornecimento no formato da tabela T.1 da FGV |
| `oferta-gasolina.xlsx` | A gêmea, para gasolina A, com a ponte gasolina C → gasolina A pelo teor legal de anidro |
| `defasagem-gasolina.xlsx` | Preço da Petrobras contra o PPI da ANP, semanal desde set/2019, nos nove pontos de entrega em que as duas pontas são o mesmo lugar. E a mesma conta para a Acelen na Bahia, contra o PPI de Aratu, que é o que mede (em vez de supor) se o preço baiano segue o mercado. A aba "Gráfico Acelen vs PPI" traz a reconstrução do G.3 do artigo da FGV, mensal, já com o gráfico montado |
| `precos-combustiveis.xlsx` | Preço ao distribuidor, preço por refinaria e por UF, e a composição do preço na bomba decomposta em produto, anidro, tributos e margem |
| `ipca-defasagem.xlsx` | Quanto da defasagem está represado no IPCA, por três caminhos independentes: o contábil (teto), a Bahia como grupo de controle (piso) e o método da FGV estendido para série mensal. Traz também o IPCA em 12 meses sob cada estimativa |
| `ppi-anp.xlsx` | O arquivo bruto da ANP: PPI semanal de gasolina, diesel, QAV e GLP. Insumo, não produto, e por isso não é versionado |
| `PPI_combustiveis_2016-2026.xlsx` | A planilha antiga, de setembro de 2026. Substituída em quase tudo pelas outras, **menos** na aba "Brent e Câmbio", que não existe em lugar nenhum. Não se atualiza sozinha |

## Como refazer

```bash
cd planilhas
python scripts/precos_combustiveis.py   # preços e composição
python scripts/defasagem.py             # precisa do PPI, que ele baixa
python scripts/oferta_diesel.py
python scripts/oferta_gasolina.py
python scripts/ipca_defasagem.py        # depende dos de cima
```

Os scripts acham a própria pasta, então rodam de qualquer diretório. O que
eles baixam vai para `dados/`, e o que é grande demais para versionar está no
`.gitignore` da raiz, com o motivo escrito em cada linha.

A ordem importa só para o `ipca_defasagem.py`, que lê a defasagem, o preço de
bomba e o teor de anidro dos outros. Ele é o único que baixa o IPCA por praça,
e por isso demora mais que os demais.

## O que é nosso e o que é emprestado

A terceira estimativa do `ipca-defasagem.xlsx` é o método de Francisco Pessoa
Faria, no artigo "Impacto da defasagem da gasolina no IPCA e reflexos de sua
subvenção nos resultados da Petrobras", do Blog do IBRE. A aba "Praças e pesos"
reproduz a tabela T.2 dele número a número justamente para que dê para checar
que é a mesma conta, e não uma variação nossa. O que é nosso ali é só a
extensão para série mensal.

A segunda estimativa, a da Bahia por nível de preço, é inspirada no mesmo
artigo mas não é o método dele: ele compara variação, nós comparamos nível, e
por isso precisamos estimar um spread estrutural que na conta dele não existe.

## O que cada script é

| Script | Papel |
|---|---|
| `anp_desembaracos.py` | Módulo comum: lê o Relatório de Desembaraços da ANP, guarda o calendário de quem era dono de cada refinaria em cada mês, e monta o perfil no formato da FGV. Não roda sozinho |
| `composicao_anp.py` | O acervo de composição de preço, extraído dos PDF da Síntese Semanal |
| `precos_revenda.py` | O Levantamento de Preços da ANP, por posto, agregado em média semanal por UF. Não roda sozinho |
| `precos_combustiveis.py`, `defasagem.py`, `oferta_diesel.py`, `oferta_gasolina.py`, `ipca_defasagem.py` | Um por planilha |

## A armadilha que custa mais caro

O `.cache-anp-revenda/` tem 2,6 GB de zips da ANP e não é versionado. O que
interessa dele é um arquivo só, `revenda-semanal.csv`, com a média semanal por
UF de 2004 a hoje. Se o cache sumir, o `precos_revenda.py` remonta tudo, mas
são algumas dezenas de minutos de download.
