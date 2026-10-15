#!/usr/bin/env python3
"""
Quanto da defasagem da gasolina está represado no IPCA. Modelo contábil.

A pergunta é: se a Petrobras cobrasse a paridade de importação, quanto maior
seria o IPCA? Este script responde por contabilidade, não por econometria.
Nenhum parâmetro é estimado: cada passo é uma soma ou uma divisão que dá para
conferir célula a célula na planilha.

A CORRENTE, EM QUATRO ELOS

  1. **A defasagem, no portão da refinaria.** Preço da Petrobras menos o PPI
     da ANP, em R$ por litro de gasolina A, sem tributos. Vem do defasagem.py,
     semanal, e vira média mensal aqui. Negativo é vender abaixo da paridade.

  2. **Da refinaria para a bomba.** Um litro de gasolina C tem (1 − teor) de
     gasolina A dentro, então um real a mais na refinaria vira (1 − teor)
     reais a mais na bomba. Com o E30, R$ 0,70. É aqui que moram as hipóteses,
     e elas estão listadas abaixo.

  3. **Da bomba para o item Gasolina do IPCA.** O repasse em reais dividido
     pelo preço médio de revenda da ANP dá a variação percentual que faltou no
     item.

  4. **Do item para o índice.** Multiplicado pelo peso do item Gasolina na
     cesta do IPCA (tabela 7060 do SIDRA, subitem 5104001), dá o efeito em
     pontos percentuais.

AS TRÊS HIPÓTESES, QUE SÃO O MODELO INTEIRO

  - **Os tributos não escalam.** PIS, Cofins, Cide e, desde junho de 2023, o
     ICMS são ad rem: um valor fixo por litro. Preço de refinaria maior não
     aumenta imposto. Esta hipótese é um fato legal, não uma suposição.
  - **A margem de distribuição e revenda não escala.** Esta é suposição de
     verdade. Se a margem fosse proporcional ao preço, o repasse seria maior
     que o calculado aqui. A aba "Sensibilidade" mostra os dois casos.
  - **O preço do etanol anidro não muda.** Na prática, gasolina mais cara
     puxa o etanol junto. Isso é efeito de segunda ordem, de comportamento, e
     por isso fica de fora: ele pertence ao modelo estimado, não a este.

O QUE ESTE MODELO NÃO É

  Não é previsão. É o tamanho do represamento hoje, sob a hipótese de que a
  empresa fecharia 100% da defasagem de uma vez, que é forte de propósito:
  serve de teto, não de cenário central.

  Não cobre o diesel. O diesel quase não tem peso direto no IPCA (família não
  compra diesel) e o efeito dele vem por frete e tarifa, que é transmissão
  indireta e exige elasticidade estimada. Além disso não temos a tabela de
  preços da Petrobras para o diesel, só para a gasolina.

NÍVEL E VARIAÇÃO, QUE SÃO COISAS DIFERENTES

  A defasagem segura o **nível** do índice. Uma defasagem constante não muda a
  inflação em 12 meses: ela já está nos dois pontos da comparação. O que mexe
  no acumulado é a **mudança** da defasagem. Por isso a planilha traz as duas
  colunas, e a diferença entre elas costuma surpreender quem olha só uma.
"""
import datetime
import json
import os
import sys
import urllib.request

import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defasagem as df
import oferta_gasolina as og
import precos_combustiveis as pc
import precos_revenda as pr

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
SAIDA = os.path.join(RAIZ, "ipca-defasagem.xlsx")

NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

# Subitens da classificação 315 da tabela 7060 do SIDRA. A 7060 começa em
# janeiro de 2020, com os pesos da POF 2017-2018; é por isso que o modelo
# começa aí e não em setembro de 2019, quando a série de defasagem abre.
ITENS = {"geral": "7169", "gasolina": "7657", "etanol": "7658"}
INICIO = "2020-01"


def sidra(variaveis, classes):
    url = ("https://apisidra.ibge.gov.br/values/t/7060/n1/1/v/%s/p/all/c315/%s"
           "/d/v63%%202,v66%%204" % (variaveis, classes))
    req = urllib.request.Request(url, headers=NAVEGADOR)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def ipca():
    """{'aaaa-mm': {'ipca': %, 'gasolina': %, 'peso_gasolina': %, ...}}."""
    bruto = sidra("63,66", ",".join(ITENS.values()))
    invertido = {v: k for k, v in ITENS.items()}
    fora = {}
    for linha in bruto[1:]:
        valor = linha.get("V")
        if valor in (None, "", "...", "-", ".."):
            continue
        per = linha["D3C"]
        chave = "%s-%s" % (per[:4], per[4:])
        nome = invertido[linha["D4C"]]
        # D2C 63 é variação mensal; 66 é peso mensal na cesta.
        campo = nome if linha["D2C"] == "63" else "peso_" + nome
        fora.setdefault(chave, {})[campo] = float(valor)
    return fora


def defasagem_mensal():
    """({ponto: {mês: (tabela R$/l, efetiva R$/l)}}, último mês completo).

    Semana entra no mês do dia em que termina. Só entram meses com pelo menos
    três semanas, senão a média de um mês recém-começado entra como se fosse o
    mês inteiro."""
    ppi = df.ler_ppi(df.baixar_ppi())
    import glob
    pdfs = sorted(glob.glob(os.path.join(DADOS, "*asolina*.pdf"))
                  + glob.glob(os.path.join(DADOS, "*abela*re*.pdf")),
                  key=os.path.getmtime)
    if not pdfs:
        raise SystemExit("nenhuma tabela da Petrobras em dados/ — veja "
                         "precos_combustiveis.py, que sabe buscá-la")
    linhas = pc.ler_petrobras(pdfs[-1])
    escadas = {p: df.escadas_petrobras(linhas, p) for p in df.PONTOS}
    ultima = max(d for tab, sub in escadas.values() for d, _v in tab + sub)

    acc = {}
    for ponto, fim, tabela, subv, p, _dif, _pc, _pcs, _ex in df.montar(
            ppi, escadas, ultima):
        chave = fim.strftime("%Y-%m")
        acc.setdefault(ponto, {}).setdefault(chave, []).append(
            (tabela - p, (tabela - subv) - p))
    fora = {}
    for ponto, meses in acc.items():
        fora[ponto] = {m: (sum(a for a, _b in v) / len(v),
                           sum(b for _a, b in v) / len(v))
                       for m, v in meses.items() if len(v) >= 3}
    return fora, ultima


def bomba_mensal():
    """{mês: (gasolina R$/l, etanol R$/l)} no Brasil, média das semanas."""
    bruto = pr.ler_agregado()
    acc = {}
    for (semana, ambito, produto), (preco, _coletas) in bruto.items():
        if ambito != "Brasil":
            continue
        acc.setdefault(semana[:7], {}).setdefault(produto, []).append(preco)
    fora = {}
    for mes, prods in acc.items():
        if len(prods.get("gasolina", [])) >= 3:
            fora[mes] = (sum(prods["gasolina"]) / len(prods["gasolina"]),
                         sum(prods.get("etanol", [0])) / max(
                             len(prods.get("etanol", [1])), 1))
    return fora


def modelo(defas, bomba, idx, ponto, margem_escala=False):
    """A corrente inteira, mês a mês.

    `margem_escala` troca a hipótese 2: com True, a margem de distribuição e
    revenda sobe na mesma proporção do preço do produtor, o que amplia o
    repasse. É a alternativa da aba Sensibilidade."""
    meses = sorted(m for m in defas.get(ponto, {})
                   if m in bomba and m in idx and m >= INICIO)
    fora, p_cf_ant, p_obs_ant, nivel = [], None, None, {}
    for m in meses:
        _tabela, efetiva = defas[ponto][m]
        teor = og.teor_do_mes(m)
        preco, _etanol = bomba[m]
        dados = idx[m]
        peso = dados.get("peso_gasolina")
        if peso is None or teor is None:
            continue

        # A defasagem é negativa quando a Petrobras vende abaixo da paridade;
        # fechá-la sobe o preço, daí o sinal trocado.
        repasse = -efetiva * (1 - teor)
        if margem_escala:
            # Se a margem for fração fixa do preço de bomba e não valor fixo
            # por litro, ela cresce junto: o repasse vira Δ/(1 − margem).
            repasse = repasse / (1 - MARGEM)
        p_cf = preco + repasse
        gap = repasse / preco * 100            # % que falta no preço de bomba
        nivel_m = peso * gap / 100             # p.p. no nível do índice

        var_obs = var_cf = None
        if p_obs_ant and p_cf_ant:
            var_obs = (preco / p_obs_ant - 1) * 100
            var_cf = (p_cf / p_cf_ant - 1) * 100
        nivel[m] = nivel_m
        fora.append({
            "mes": m, "defasagem_tabela": _tabela, "defasagem_efetiva": efetiva,
            "teor": teor, "repasse": repasse, "preco": preco, "p_cf": p_cf,
            "gap": gap, "peso": peso, "nivel": nivel_m,
            "var_anp": var_obs, "var_cf": var_cf,
            "var_sidra": dados.get("gasolina"), "ipca": dados.get("geral"),
        })
        p_cf_ant, p_obs_ant = p_cf, preco

    # IPCA contrafactual: o observado mais o que o item teria feito a mais.
    for i, linha in enumerate(fora):
        if linha["var_cf"] is None or linha["ipca"] is None:
            linha["ipca_cf"] = None
        else:
            linha["ipca_cf"] = linha["ipca"] + linha["peso"] * (
                linha["var_cf"] - linha["var_anp"]) / 100
        # Efeito no acumulado em 12 meses: a mudança do nível represado.
        anterior = fora[i - 12]["nivel"] if i >= 12 else None
        linha["efeito12"] = (linha["nivel"] - anterior) if anterior is not None else None
    return fora


# Fração do preço de bomba que é margem de distribuição e revenda, usada só na
# variante da Sensibilidade. Vem da composição da ANP, onde fica estável perto
# de 23%; fixá-la evita que a aba dependa de mais um download.
MARGEM = 0.23


# ─── Segunda estimativa: a Bahia como grupo de controle ──────────────────────
#
# A ideia é do artigo da FGV, não minha, mas a execução é: ele não documenta o
# cálculo, então isto é uma reconstrução da ideia, não uma réplica do método.
#
# Na Bahia quem domina é a Acelen, que segue o PPI. Então o preço de bomba
# baiano é uma leitura de mercado do que o preço seria sem defasagem, e o
# excesso do spread BA − Brasil mede o represamento sem precisar de nenhuma
# hipótese sobre mistura, tributo ou margem. É uma segunda medida do mesmo
# fenômeno, por um caminho que não compartilha nenhuma suposição com o
# contábil — e é por isso que vale a pena ter as duas.
#
# O spread tem uma parte estrutural, que é frete e margem e existe sempre, e
# uma parte que responde à defasagem. A regressão separa as duas: o intercepto
# é a estrutural, a inclinação é a resposta.
#
# A janela da estimação começa em junho de 2023, quando o ICMS virou
# monofásico e passou a ser o MESMO valor por litro em todo estado. Antes
# disso o spread carregava diferença de alíquota, e isso aparece no ajuste: o
# R² sai de 0,13 no regime antigo para 0,71 no novo, com a mesma inclinação.
ICMS_MONOFASICO = "2023-06"
CONTROLE = "BA"


def regressao(pares):
    """(inclinação, intercepto, R², n) de y contra x."""
    x = [a for a, _ in pares]
    y = [b for _, b in pares]
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    a0 = my - b * mx
    sst = sum((c - my) ** 2 for c in y)
    sse = sum((c - (a0 + b * a)) ** 2 for a, c in zip(x, y))
    return b, a0, (1 - sse / sst) if sst else float("nan"), n


def bahia(linhas, precos):
    """A segunda estimativa, e os parâmetros que a geraram.

    Devolve ([linha…], (inclinação, estrutural, R², n))."""
    pares = [(l["defasagem_efetiva"],
              precos[l["mes"]][CONTROLE] - precos[l["mes"]]["Brasil"])
             for l in linhas
             if l["mes"] in precos and l["mes"] >= ICMS_MONOFASICO]
    par = regressao(pares)
    inclinacao, estrutural, _r2, _n = par

    fora = []
    ant = None                      # (mês esperado, preço contrafactual)
    for l in linhas:
        if l["mes"] not in precos:
            continue
        p = precos[l["mes"]]
        spread = p[CONTROLE] - p["Brasil"]
        # A parte do spread que a defasagem explica. Com defasagem negativa e
        # inclinação negativa, o excesso é positivo: é o que falta no Brasil.
        excesso = inclinacao * l["defasagem_efetiva"]
        gap = excesso / l["preco"] * 100
        p_cf = l["preco"] + excesso
        # Daqui para a frente é o mesmo caminho do contábil: o preço
        # contrafactual vira variação mensal, e a diferença contra a variação
        # da ANP entra no índice pelo peso do item. Só com mês anterior
        # adjacente, senão a variação cobriria um buraco da série.
        var_cf = ipca_cf = None
        if ant and ant[0] == l["mes"] and l["var_anp"] is not None:
            var_cf = (p_cf / ant[1] - 1) * 100
            if l["ipca"] is not None:
                ipca_cf = l["ipca"] + l["peso"] * (var_cf - l["var_anp"]) / 100
        fora.append({
            "mes": l["mes"], "defasagem_efetiva": l["defasagem_efetiva"],
            "ba": p[CONTROLE], "brasil": p["Brasil"], "spread": spread,
            "estrutural": estrutural, "excesso": excesso, "gap": gap,
            "peso": l["peso"], "nivel": l["peso"] * gap / 100,
            "nivel_contabil": l["nivel"], "p_cf": p_cf, "var_cf": var_cf,
            "ipca": l["ipca"], "ipca_cf": ipca_cf,
        })
        ant = (mes_seguinte(l["mes"]), p_cf)
    return fora, par


# ─── Pesar os pontos de entrega por volume ───────────────────────────────────
#
# Se a Petrobras fechar a defasagem, cada ponto sobe o tanto da defasagem dele
# e o preço nacional sobe a MÉDIA PONDERADA PELO VOLUME que sai de cada lugar,
# não a média simples. A diferença não é acadêmica: a média simples dá a
# Manaus o mesmo peso de Paulínia, e Manaus não tem produção da Petrobras
# atrás (a REAM é da Atem desde 2022) enquanto Paulínia sozinha é um quarto da
# gasolina A da empresa. Em set/2026 a simples dá 0,59 e a ponderada 0,63.
#
# O peso é a produção de gasolina A da refinaria que está atrás de cada ponto.
# É aproximação, porque a Petrobras também entrega de terminal e não só da
# refinaria do lado, mas erra pouco e erra parelho: o que ela resolve é o peso
# dos dois pontos sem refinaria dela atrás, que é onde mora a distorção.
REFINARIA = {
    "Paulínia (SP)": "REPLAN",
    "Araucária (PR)": "REPAR",
    "Canoas (RS)": "REFAP",
    "São José dos Campos (SP)": "REVAP",
    "Cubatão (SP)": "RPBC",
    "Betim (MG)": "REGAP",
    "Duque de Caxias (RJ)": "REDUC",
}
# Manaus (REAM, da Atem) e Guamaré (3R) ficam fora de propósito: a Petrobras
# entrega ali, mas não refina, então não há volume dela para pesar.
JANELA_VOLUME = 12


def producao_por_ponto():
    """{mês: {ponto: m³}} de gasolina A em janela de 12 meses."""
    ordem, prod = og.por_refinaria()
    col = {nome: i + 1 for i, nome in enumerate(ordem)}
    faltam = sorted(p for p, r in REFINARIA.items() if r not in col)
    if faltam:
        raise SystemExit("refinaria sem coluna na produção da ANP: %s" % faltam)
    meses = [l[0] for l in prod]
    bruto = {l[0]: {p: (l[col[r]] or 0.0) for p, r in REFINARIA.items()}
             for l in prod}
    fora = {}
    for i, m in enumerate(meses):
        if i + 1 >= JANELA_VOLUME:
            janela = meses[i + 1 - JANELA_VOLUME:i + 1]
            fora[m] = {p: sum(bruto[j][p] for j in janela) for p in REFINARIA}
    return fora


def medias_por_ponto(pontos, volumes):
    """{mês: (ponderada por produção, simples)} do nível represado.

    A produção da ANP sai com um ou dois meses de atraso em relação ao resto,
    então os meses do fim usam a última janela de volume que existir. Peso de
    volume anda devagar, e usar a janela anterior erra menos que não ter
    coluna nenhuma nos meses mais recentes, que são os que interessam."""
    if not volumes:
        return {}
    ultimo = max(volumes)
    fora = {}
    for m in sorted({m for p in pontos.values() for m in p}):
        peso = volumes.get(min(m, ultimo))
        itens = [(pontos[p][m], peso.get(p, 0.0)) for p in REFINARIA
                 if pontos.get(p, {}).get(m) is not None]
        itens = [(v, w) for v, w in itens if w > 0]
        todos = [d[m] for d in pontos.values() if d.get(m) is not None]
        if itens and todos:
            soma = sum(w for _v, w in itens)
            fora[m] = (sum(v * w for v, w in itens) / soma,
                       sum(todos) / len(todos))
    return fora


def precos_por_mes():
    """{mês: {'BA': R$/l, 'Brasil': R$/l}} da gasolina, média das semanas."""
    bruto = pr.ler_agregado()
    acc = {}
    for (semana, ambito, produto), (preco, _c) in bruto.items():
        if produto != "gasolina" or ambito not in (CONTROLE, "Brasil"):
            continue
        acc.setdefault(semana[:7], {}).setdefault(ambito, []).append(preco)
    return {m: {a: sum(v) / len(v) for a, v in d.items()}
            for m, d in acc.items()
            if len(d) == 2 and all(len(v) >= 3 for v in d.values())}


# ─── Terceira estimativa: Salvador como contrafactual ────────────────────────
#
# Esta é a conta do artigo da FGV, a dele mesmo, estendida para série mensal.
# O artigo roda uma vez, no bimestre março-abril de 2026, e chega a 0,59 p.p.;
# aqui a mesma conta roda todo mês.
#
# O IPCA mede a gasolina em 16 praças. Em Salvador a Petrobras não tem ponto
# de entrega e quem forma preço é a Acelen, que segue o PPI. Então a variação
# do subitem Gasolina em Salvador é uma leitura de mercado do que a gasolina
# teria feito no país sem defasagem. A diferença entre o que cada praça fez e
# o que Salvador fez, ponderada pelo peso da praça no índice nacional, é o
# represamento.
#
# A diferença para a estimativa da Bahia é a unidade. Aquela compara NÍVEL de
# preço em R$/l, e por isso precisa descontar um spread estrutural. Esta
# compara VARIAÇÃO, e qualquer diferença permanente de nível (frete, margem,
# custo local) some sozinha na taxa. Em troca, esta supõe que a diferença
# estrutural não mudou dentro do mês.
#
# O que o SIDRA não publica é o peso de cada praça no índice nacional: ele dá
# o peso de cada subitem DENTRO de cada praça, e esses sempre somam 100. Mas o
# peso nacional de cada subitem é a média dos pesos locais ponderada pelas
# praças, e a identidade vale para os 210 níveis de agregação de uma vez. São
# 210 equações para 16 incógnitas, e é isso que pesos_regionais() resolve.

PRACAS = {
    "1501": "Belém", "2301": "Fortaleza", "2601": "Recife", "2901": "Salvador",
    "3101": "Belo Horizonte", "3201": "Grande Vitória",
    "3301": "Rio de Janeiro", "3501": "São Paulo", "4101": "Curitiba",
    "4301": "Porto Alegre", "1200401": "Rio Branco", "2111300": "São Luís",
    "2800308": "Aracaju", "5002704": "Campo Grande", "5208707": "Goiânia",
    "5300108": "Brasília",
}
# As dez primeiras são regiões metropolitanas, que no SIDRA são o nível 7; as
# seis últimas são municípios, que são o nível 6. Daí a consulta em dois
# níveis em toda função daqui para baixo.
NIVEIS = ("n7", "n6")
REFERENCIA = "2901"

# A Acelen comprou a RLAM em 30/11/2021. Antes disso a refinaria era da
# Petrobras e Salvador não servia de contrafactual de nada.
INICIO_SALVADOR = "2022-01"

# O bimestre do artigo e a T.2 como ele a publicou, para a aba de réplica
# conferir número a número: praça -> (var. observada %, var. imputada %,
# impacto p.p.). Salvador é a referência e por isso não tem imputação.
BIMESTRE_FGV = ("2026-03", "2026-04")
T2_FGV = {
    "1200401": (4.3, 13.3, 0.005), "2111300": (13.2, 4.4, 0.005),
    "2800308": (10.7, 6.7, 0.005), "5002704": (7.8, 9.6, 0.012),
    "5208707": (2.6, 15.2, 0.040), "5300108": (1.0, 17.0, 0.049),
    "1501": (9.3, 8.1, 0.020), "2301": (7.6, 9.8, 0.019),
    "2601": (10.6, 6.9, 0.020), "2901": (18.2, None, None),
    "3101": (2.9, 14.9, 0.080), "3201": (6.9, 10.5, 0.011),
    "3301": (7.5, 10.0, 0.040), "3501": (6.3, 11.2, 0.157),
    "4101": (5.7, 11.8, 0.070), "4301": (5.3, 12.3, 0.072),
}
TOTAL_FGV = 0.59


def baixar(url):
    req = urllib.request.Request(url, headers=NAVEGADOR)
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)[1:]


def minimos_quadrados(A, b):
    """x que minimiza |Ax − b|, pelas equações normais.

    São 16 incógnitas e o sistema é bem condicionado (cada praça tem perfil de
    consumo diferente), então Gauss-Jordan com pivotamento resolve sem
    precisar de biblioteca externa."""
    n = len(A[0])
    M = [[sum(l[i] * l[j] for l in A) for j in range(n)]
         + [sum(l[i] * y for l, y in zip(A, b))] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[piv][col]) < 1e-12:
            raise SystemExit("o sistema dos pesos regionais ficou singular")
        M[col], M[piv] = M[piv], M[col]
        for r in range(n):
            if r != col:
                f = M[r][col] / M[col][col]
                for c in range(col, n + 1):
                    M[r][c] -= f * M[col][c]
    return [M[i][n] / M[i][i] for i in range(n)]


def pesos_regionais(mes):
    """({praça: peso no IPCA nacional %}, soma, pior resíduo).

    Recuperado, não publicado: ver o comentário do bloco acima. A soma e o
    resíduo voltam junto porque são a verificação — se a identidade não
    fechar, o peso está errado e o resto da estimativa também."""
    per = mes.replace("-", "")

    def mapa(nivel):
        fora = {}
        for l in baixar("https://apisidra.ibge.gov.br/values/t/7060/%s/all"
                        "/v/66/p/%s/c315/all" % (nivel, per)):
            if l["V"] not in (None, "", "...", "-", ".."):
                fora.setdefault(l["D1C"], {})[l["D4C"]] = float(l["V"])
        return fora

    nacional = mapa("n1")["1"]
    praca = {}
    for nivel in NIVEIS:
        praca.update(mapa(nivel))
    faltam = sorted(set(PRACAS) - set(praca))
    if faltam:
        raise SystemExit("praças sem peso no SIDRA em %s: %s" % (mes, faltam))

    codigos = sorted(PRACAS)
    cats = sorted(set(nacional).intersection(*[set(praca[c]) for c in codigos]))
    A = [[praca[c][k] for c in codigos] for k in cats]
    b = [nacional[k] for k in cats]
    x = minimos_quadrados(A, b)
    soma = sum(x) * 100
    pior = max(abs(sum(a * v for a, v in zip(linha, x)) - y)
               for linha, y in zip(A, b))
    if abs(soma - 100) > 0.05 or pior > 0.05:
        raise SystemExit("pesos regionais não fecham: soma %.4f, resíduo %.4f"
                         % (soma, pior))
    return {c: v * 100 for c, v in zip(codigos, x)}, soma, pior


def ipca_por_praca():
    """{praça: {mês: (variação %, peso do item na praça %)}} da gasolina."""
    fora = {}
    for nivel in NIVEIS:
        for l in baixar("https://apisidra.ibge.gov.br/values/t/7060/%s/all"
                        "/v/63,66/p/all/c315/%s/d/v63%%202,v66%%204"
                        % (nivel, ITENS["gasolina"])):
            if l["V"] in (None, "", "...", "-", ".."):
                continue
            per = l["D3C"]
            mes = "%s-%s" % (per[:4], per[4:])
            atual = fora.setdefault(l["D1C"], {}).setdefault(mes, [None, None])
            atual[0 if l["D2C"] == "63" else 1] = float(l["V"])
    return {c: {m: tuple(v) for m, v in meses.items() if None not in v}
            for c, meses in fora.items()}


def imputacao(alvo, observada):
    """A variação que, somada à observada, leva a praça ao mesmo acumulado da
    referência. É a 'Var % adicional imputada' da T.2, e ela é multiplicativa,
    não uma subtração."""
    return ((1 + alvo / 100) / (1 + observada / 100) - 1) * 100


def salvador(idx, reg, pesos, inicio=INICIO_SALVADOR):
    """[{mês, …}] com o impacto mensal, no formato do artigo."""
    meses = sorted(m for m in reg.get(REFERENCIA, {})
                   if m >= inicio and m in idx
                   and all(m in reg.get(c, {}) for c in PRACAS))
    fora = []
    for m in meses:
        alvo = reg[REFERENCIA][m][0]
        detalhe, impacto = {}, 0.0
        for c in PRACAS:
            var, peso_local = reg[c][m]
            contrib = pesos[c] / 100 * peso_local / 100
            gap = 0.0 if c == REFERENCIA else imputacao(alvo, var)
            # contrib é fração da cesta e gap vem em %, então o produto já
            # está em pontos percentuais do índice.
            parcela = contrib * gap
            detalhe[c] = (var, peso_local, gap, parcela)
            impacto += parcela
        obs = idx[m].get("geral")
        fora.append({"mes": m, "var_salvador": alvo, "impacto": impacto,
                     "ipca": obs, "detalhe": detalhe,
                     "ipca_cf": None if obs is None else obs + impacto})
    return fora


def replica_t2(reg, pesos):
    """[(praça, observada, imputada, impacto, as três da FGV)] no bimestre do
    artigo. É o teste de que o método aqui é o dele, e não uma variação."""
    a, b = BIMESTRE_FGV
    bim = {c: ((1 + reg[c][a][0] / 100) * (1 + reg[c][b][0] / 100) - 1) * 100
           for c in PRACAS if a in reg.get(c, {}) and b in reg.get(c, {})}
    if REFERENCIA not in bim:
        return [], (None, None)
    alvo = bim[REFERENCIA]
    fora, total = [], 0.0
    for c in sorted(PRACAS, key=lambda c: PRACAS[c]):
        if c not in bim:
            continue
        gap = None if c == REFERENCIA else imputacao(alvo, bim[c])
        peso_local = reg[c][b][1]
        imp = None if gap is None else pesos[c] / 100 * peso_local / 100 * gap
        total += imp or 0.0
        fora.append((PRACAS[c], bim[c], gap, imp) + T2_FGV.get(c, (None,) * 3))
    return fora, (total, TOTAL_FGV)

def acumulado(valores):
    f = 1.0
    for v in valores:
        f *= 1 + v / 100
    return (f - 1) * 100


def mes_seguinte(m):
    ano, mes = int(m[:4]), int(m[5:])
    return "%04d-%02d" % (ano + (mes == 12), mes % 12 + 1)


def acumulado12(serie):
    """{mês: acumulado em 12 meses} a partir de {mês: variação mensal %}.

    Só acumula janela de doze meses seguidos e completa: buraco no meio
    devolveria um 'acumulado em 12 meses' que não é de doze meses."""
    meses = sorted(serie)
    fora = {}
    for i in range(11, len(meses)):
        janela = meses[i - 11:i + 1]
        if any(mes_seguinte(a) != b for a, b in zip(janela, janela[1:])):
            continue
        if any(serie[m] is None for m in janela):
            continue
        fora[janela[-1]] = acumulado([serie[m] for m in janela])
    return fora


def doze_meses(linhas, bah, sal):
    """[{mês, observado, e um contrafactual por estimativa}] em 12 meses."""
    obs = acumulado12({l["mes"]: l["ipca"] for l in linhas})
    contab = acumulado12({l["mes"]: l["ipca_cf"] for l in linhas})
    baia = acumulado12({l["mes"]: l["ipca_cf"] for l in bah})
    salv = acumulado12({l["mes"]: l["ipca_cf"] for l in sal})
    fora = []
    for m in sorted(obs):
        linha = {"mes": m, "obs": obs[m], "contabil": contab.get(m),
                 "bahia": baia.get(m), "salvador": salv.get(m)}
        for k in ("contabil", "bahia", "salvador"):
            linha["efeito_" + k] = (None if linha[k] is None
                                    else linha[k] - linha["obs"])
        fora.append(linha)
    return fora


def escrever(linhas, sensivel, pontos, medias, bah, par, sal, pesos, diag,
             t2, doze, ultima, hoje):
    wb = openpyxl.Workbook()
    neg = Font(bold=True)

    ws = wb.active
    ws.title = "LEIA-ME"
    texto = [
        ("Quanto da defasagem da gasolina está represado no IPCA", True),
        ("Gerado em %s" % hoje.strftime("%d/%m/%Y"), False),
        ("", False),
        ("Modelo CONTÁBIL: nenhum parâmetro estimado. Cada número é soma ou "
         "divisão conferível.", True),
        ("", False),
        ("A CORRENTE", True),
        ("1. Defasagem = preço da Petrobras − PPI da ANP, gasolina A, no duto "
         "da refinaria, sem tributos.", False),
        ("   Negativo é vender abaixo da paridade. Semanal no defasagem.py, "
         "média mensal aqui.", False),
        ("2. Da refinaria para a bomba: um litro de gasolina C tem (1 − teor) "
         "de gasolina A dentro.", False),
        ("   Com o E30, R$ 1,00 a mais na refinaria vira R$ 0,70 a mais na "
         "bomba.", False),
        ("3. Da bomba para o item: o repasse dividido pelo preço médio de "
         "revenda da ANP.", False),
        ("4. Do item para o índice: multiplicado pelo peso do item Gasolina "
         "(SIDRA 7060, subitem 5104001).", False),
        ("", False),
        ("AS TRÊS HIPÓTESES, QUE SÃO O MODELO INTEIRO", True),
        ("Tributos não escalam. PIS, Cofins, Cide e, desde jun/2023, o ICMS "
         "são ad rem, um valor fixo por litro.", False),
        ("   Isso é fato legal, não suposição.", False),
        ("Margem de distribuição e revenda não escala. Esta é suposição de "
         "verdade — veja a aba Sensibilidade.", False),
        ("Preço do etanol anidro não muda. Na prática gasolina cara puxa "
         "etanol; isso é comportamento,", False),
        ("   não contabilidade, e fica para o modelo estimado.", False),
        ("", False),
        ("NÍVEL E VARIAÇÃO SÃO COISAS DIFERENTES", True),
        ("A defasagem segura o NÍVEL do índice. Defasagem constante NÃO muda a "
         "inflação em 12 meses:", False),
        ("ela já está nos dois pontos da comparação. O que mexe no acumulado é "
         "a MUDANÇA da defasagem.", False),
        ("Por isso há duas colunas: 'nível represado' e 'efeito no IPCA 12m'.", False),
        ("", False),
        ("SINAL, que é onde todo mundo se perde", True),
        ("'nível represado' positivo = a Petrobras está ABAIXO da paridade e o "
         "índice está sendo segurado.", False),
        ("Negativo = ela está acima, e o índice está sendo empurrado.", False),
        ("'efeito no IPCA 12m' = nível de hoje menos nível de 12 meses atrás. "
         "Positivo = a inflação acumulada", False),
        ("seria MAIOR sem a defasagem. Negativo = a defasagem encolheu no "
         "período, então o preço correu atrás", False),
        ("e o acumulado observado já está INFLADO por essa recuperação.", False),
        ("", False),
        ("O QUE NÃO É", True),
        ("Não é previsão. Supõe que a empresa fecharia 100% da defasagem de "
         "uma vez, o que é forte de", False),
        ("propósito: serve de teto, não de cenário central.", False),
        ("Não cobre o diesel. Diesel quase não tem peso direto no IPCA e o "
         "efeito dele é indireto, por frete", False),
        ("e tarifa, que exige elasticidade estimada. E não temos tabela de "
         "preços da Petrobras para diesel.", False),
        ("", False),
        ("ABAS", True),
        ("Modelo mensal | A corrente inteira, mês a mês, em Paulínia", False),
        ("Por ponto | O nível represado em cada ponto de entrega, com a "
         "média ponderada por produção", False),
        ("Contrafactual Bahia | Segunda estimativa: preço de bomba baiano "
         "como controle", False),
        ("Contrafactual Salvador | Terceira estimativa: o método da FGV, "
         "estendido para série mensal", False),
        ("Praças e pesos | Os pesos regionais recuperados e a réplica da "
         "tabela T.2 do artigo", False),
        ("IPCA 12 meses | O acumulado observado e como ficaria em cada "
         "estimativa", False),
        ("Sensibilidade | O mesmo cálculo com a margem escalando junto", False),
        ("", False),
        ("TRÊS ESTIMATIVAS, E ELAS NÃO BATEM", True),
        ("1. CONTÁBIL. Supõe que R$ 1,00 na refinaria vira R$ 0,70 na bomba, "
         "porque 70% do litro é gasolina A.", False),
        ("   Nada é estimado. Supõe repasse integral e imediato, e por isso "
         "é TETO.", False),
        ("2. BAHIA. MEDE quanto do repasse aparece, usando o preço de bomba "
         "baiano (Acelen, que segue o PPI)", False),
        ("   como controle. Acha R$ 0,26 por real de defasagem, não R$ 0,70. "
         "É PISO: a Acelen não atende a", False),
        ("   Bahia inteira, não segue o PPI perfeitamente e também recebeu as "
         "subvenções de 2026, que encolhem", False),
        ("   o próprio spread que serve de medida.", False),
        ("3. SALVADOR (FGV). Compara a VARIAÇÃO do IPCA Gasolina de cada praça "
         "com a de Salvador e imputa a", False),
        ("   diferença à defasagem. Não é ideia nossa: é o método de Francisco "
         "Pessoa Faria no Blog do IBRE,", False),
        ("   'Impacto da defasagem da gasolina no IPCA e reflexos de sua "
         "subvenção nos resultados da Petrobras'.", False),
        ("   Ele roda a conta uma vez, no bimestre mar-abr/2026, e acha 0,59 "
         "p.p.; aqui ela roda todo mês. A aba", False),
        ("   'Praças e pesos' reproduz a tabela T.2 dele para mostrar que é a "
         "mesma conta.", False),
        ("", False),
        ("A 2 e a 3 usam a mesma intuição (a Bahia como mercado sem "
         "defasagem) por caminhos diferentes: a 2", False),
        ("compara NÍVEL de preço em R$/l e por isso desconta um spread "
         "estrutural; a 3 compara VARIAÇÃO, onde", False),
        ("diferença permanente de nível some sozinha. A largura entre as três "
         "é a sua incerteza honesta.", False),
        ("", False),
        ("ATENÇÃO — a tabela mais recente da Petrobras é de %s."
         % ultima.strftime("%d/%m/%Y"), True),
        ("Depois dessa data o preço segue valendo até mudar. Reajuste que "
         "ainda não apareceu não está aqui.", False),
        ("", False),
        ("Fontes: PPI e preços de revenda da ANP; tabela de preços da "
         "Petrobras; IPCA da tabela 7060 do", False),
        ("SIDRA (IBGE); teor de anidro pela legislação (CNPE e MAPA).", False),
    ]
    for t, bold in texto:
        ws.append([t])
        if bold:
            ws.cell(ws.max_row, 1).font = neg
    ws.column_dimensions["A"].width = 105

    cab = ["mês", "defasagem R$/l (tabela)", "defasagem R$/l (efetiva)",
           "teor de anidro", "repasse à bomba R$/l", "bomba observada R$/l",
           "bomba contrafactual R$/l", "falta no preço %", "peso do item %",
           "nível represado (p.p.)", "var. mensal ANP %", "var. mensal IPCA %",
           "var. mensal contrafactual %", "IPCA mês %", "IPCA mês contrafactual %",
           "efeito no IPCA 12m (p.p.)"]
    ws = wb.create_sheet("Modelo mensal")
    ws.append(cab)
    for l in linhas:
        ws.append([l["mes"], l["defasagem_tabela"], l["defasagem_efetiva"],
                   l["teor"], l["repasse"], l["preco"], l["p_cf"], l["gap"],
                   l["peso"], l["nivel"], l["var_anp"], l["var_sidra"],
                   l["var_cf"], l["ipca"], l["ipca_cf"], l["efeito12"]])
    formatar(ws, cab)

    ws = wb.create_sheet("Por ponto")
    ws.append(["O nível represado em cada ponto de entrega da Petrobras"])
    ws.cell(ws.max_row, 1).font = neg
    for t in [
        "Mesma conta do Modelo mensal, repetida nos nove pontos em que a "
        "tabela da Petrobras e o PPI da ANP",
        "existem no mesmo lugar. O Modelo mensal é Paulínia, e só.",
        "",
        "QUAL MÉDIA USAR. Se a empresa fechar a defasagem, cada ponto sobe o "
        "tanto do dele e o preço nacional",
        "sobe a média PONDERADA PELO VOLUME, não a simples. A simples dá a "
        "Manaus o mesmo peso de Paulínia, e",
        "os dois não se parecem: a REAM é da Atem desde 2022 e não tem "
        "produção da Petrobras atrás, enquanto",
        "Paulínia sozinha é um quarto da gasolina A da empresa. Por isso a "
        "simples sai sempre mais baixa.",
        "",
        "O peso é a produção de gasolina A, em janela de doze meses, da "
        "refinaria atrás de cada ponto:",
        "   " + ", ".join("%s = %s" % (REFINARIA[p], p.split(" (")[0])
                          for p in sorted(REFINARIA, key=REFINARIA.get)) + ".",
        "Manaus e Guamaré entram nas colunas e na média simples, mas não na "
        "ponderada: a Petrobras entrega",
        "ali e não refina, então não há volume dela para pesar.",
        "",
        "É aproximação, porque a empresa também entrega de terminal e não só "
        "da refinaria do lado. Erra pouco",
        "e erra parelho; o que ela conserta é o peso dos dois pontos sem "
        "refinaria dela atrás, que é onde",
        "a média simples se perde.",
        "",
    ]:
        ws.append([t])
    inicio = ws.max_row + 1
    cab2 = (["mês"] + sorted(pontos)
            + ["média ponderada por produção", "média simples"])
    ws.append(cab2)
    for m in sorted({m for p in pontos.values() for m in p}):
        med = medias.get(m, (None, None))
        ws.append([m] + [pontos[p].get(m) for p in sorted(pontos)]
                  + [med[0], med[1]])
    cabecalho(ws, cab2, inicio)

    ws = wb.create_sheet("Contrafactual Bahia")
    inclinacao, estrutural, r2, n = par
    ws.append(["Segunda estimativa: a Bahia como grupo de controle"])
    ws.cell(ws.max_row, 1).font = neg
    for t in [
        "Na Bahia quem domina é a Acelen, que segue o PPI. O preço de bomba "
        "baiano é, então, uma leitura de",
        "mercado do que o preço seria sem defasagem. O excesso do spread "
        "BA − Brasil mede o represamento SEM",
        "nenhuma hipótese sobre mistura, tributo ou margem: é um caminho que "
        "não divide suposição nenhuma",
        "com o modelo contábil, e por isso serve de segunda opinião.",
        "",
        "Estimado de %s em diante, quando o ICMS virou monofásico e passou a "
        "ser o mesmo valor por litro em" % ICMS_MONOFASICO,
        "todo estado. Antes disso o spread carregava diferença de alíquota: o "
        "R² era 0,13, contra %.2f agora." % r2,
        "",
        "spread BA − Brasil = R$ %.3f estrutural %+.3f × defasagem   "
        "(R² %.2f, n=%d meses)" % (estrutural, inclinacao, r2, n),
        "",
        "Leia a inclinação assim: a cada R$ 1,00 de defasagem na refinaria, "
        "R$ %.3f aparecem como" % abs(inclinacao),
        "diferença de preço entre a Bahia e o Brasil. O contábil supõe R$ 0,70 "
        "(o teor de gasolina A).",
        "A distância entre os dois é o tamanho da sua incerteza, e as razões "
        "estão no LEIA-ME.",
        "",
    ]:
        ws.append([t])
    inicio = ws.max_row + 1
    cab4 = ["mês", "defasagem R$/l", "bomba BA R$/l", "bomba Brasil R$/l",
            "spread observado R$/l", "spread estrutural R$/l",
            "excesso atribuído R$/l", "falta no preço %", "peso do item %",
            "nível represado (Bahia) p.p.", "nível represado (contábil) p.p."]
    ws.append(cab4)
    for l in bah:
        ws.append([l["mes"], l["defasagem_efetiva"], l["ba"], l["brasil"],
                   l["spread"], l["estrutural"], l["excesso"], l["gap"],
                   l["peso"], l["nivel"], l["nivel_contabil"]])
    cabecalho(ws, cab4, inicio)

    ws = wb.create_sheet("Contrafactual Salvador")
    ws.append(["Terceira estimativa: Salvador como contrafactual "
               "(o método da FGV, estendido)"])
    ws.cell(ws.max_row, 1).font = neg
    for t in [
        "O IPCA mede a gasolina em 16 praças. Em Salvador a Petrobras não tem "
        "ponto de entrega e quem forma",
        "preço é a Acelen, que segue o PPI. Então a variação do subitem "
        "Gasolina em Salvador é uma leitura de",
        "mercado do que a gasolina teria feito no país sem defasagem. A "
        "diferença entre o que cada praça fez e",
        "o que Salvador fez, ponderada pelo peso da praça no índice nacional, "
        "é o represamento do mês.",
        "",
        "Não é conta nossa. É a de Francisco Pessoa Faria, no Blog do IBRE da "
        "FGV. Ele roda uma vez, no",
        "bimestre março-abril de 2026, e acha 0,59 p.p.; aqui ela roda todo "
        "mês. A aba 'Praças e pesos' mostra",
        "a réplica da tabela T.2 dele, número a número, que é a prova de que "
        "é o mesmo método.",
        "",
        "Começa em %s porque a Acelen comprou a RLAM em 30/11/2021. Antes "
        "disso a refinaria era da" % INICIO_SALVADOR,
        "Petrobras e Salvador não servia de contrafactual de nada. E a janela "
        "só fica limpa de verdade a partir",
        "de %s, quando o ICMS virou monofásico: antes, mudança de alíquota "
        "num estado entrava na conta" % ICMS_MONOFASICO,
        "como se fosse defasagem.",
        "",
        "ATENÇÃO AO SINAL. Em mês de defasagem crescente Salvador sobe mais "
        "que o resto e o impacto é",
        "positivo. Quando a defasagem encolhe, ou quando algo local mexe no "
        "preço baiano, Salvador sobe menos",
        "e o impacto fica NEGATIVO. Isso não é erro: é o preço de estender "
        "para série mensal uma conta que o",
        "artigo faz num bimestre escolhido justamente por ser o do choque. A "
        "coluna 'praças acima de Salvador'",
        "é o termômetro: quando ela é alta, o contrafactual daquele mês não "
        "está medindo defasagem.",
        "",
        "O QUE ESTA ESTIMATIVA NÃO VÊ",
        "Ela mede só a parte do represamento que NÃO é comum a Salvador. No "
        "bimestre do choque isso era quase",
        "tudo: Salvador repassou na hora e o resto do país não. Depois duas "
        "coisas estreitaram a diferença.",
        "Primeiro, as outras praças correram atrás, e correr atrás some do "
        "acumulado em doze meses. Segundo, e",
        "sobretudo, a subvenção da MP 1.358 chegou à Bahia. A Petrobras passou "
        "a descontar os R$ 0,44 por litro em",
        "29/5/2026; a Acelen, só em 13/8/2026, dois meses e meio depois. Nas "
        "duas semanas seguintes o preço de",
        "bomba baiano caiu R$ 0,25 enquanto o do Brasil ficou parado, e o IPCA "
        "Gasolina de Salvador fez -4,4% em",
        "agosto, o maior recuo das dezesseis praças. A tabela da Acelen mal se "
        "mexeu nesse período: o que mudou",
        "foi o que a distribuidora pagou. Ver a aba 'Acelen vs PPI' do "
        "defasagem-gasolina.xlsx.",
        "",
        "Ou seja, o controle recebeu o mesmo remédio que o resto do país "
        "tomava desde maio, só que de uma vez e",
        "atrasado. A diferença entre as praças sumiu, e com ela o "
        "contrafactual.",
        "",
        "É por isso que o acumulado em 12 meses por este caminho vai a zero em "
        "setembro de 2026 enquanto o",
        "contábil ainda marca 0,8 p.p. Os dois podem estar certos ao mesmo "
        "tempo: o contábil mede o nível da",
        "defasagem no portão da refinaria, este mede o quanto uma praça andou "
        "diferente da outra. Quando as duas",
        "estão seguradas pelo mesmo programa, a diferença some e a defasagem "
        "fica onde estava.",
        "",
    ]:
        ws.append([t])
    inicio = ws.max_row + 1
    cab5 = ["mês", "var. Salvador %", "praças acima de Salvador",
            "impacto do mês (p.p.)", "IPCA mês %", "IPCA mês contrafactual %"]
    ws.append(cab5)
    for l in sal:
        acima = sum(1 for c, (_v, _pl, gap, _p) in l["detalhe"].items()
                    if c != REFERENCIA and gap < 0)
        ws.append([l["mes"], l["var_salvador"], acima, l["impacto"],
                   l["ipca"], l["ipca_cf"]])
    cabecalho(ws, cab5, inicio)

    ws = wb.create_sheet("Praças e pesos")
    soma, pior = diag
    ws.append(["Os pesos regionais, e a réplica da tabela T.2 do artigo"])
    ws.cell(ws.max_row, 1).font = neg
    for t in [
        "O SIDRA publica o peso de cada subitem DENTRO de cada praça, e esses "
        "sempre somam 100. O peso da",
        "praça no índice nacional ele não publica. Mas o peso nacional de cada "
        "subitem é a média dos pesos",
        "locais ponderada pelas praças, e essa identidade vale para os 210 "
        "níveis de agregação de uma vez:",
        "210 equações para 16 incógnitas, resolvidas por mínimos quadrados.",
        "",
        "A verificação: os pesos somam %.4f (tem que dar 100) e o pior "
        "resíduo das 210 equações é %.6f," % (soma, pior),
        "que é o arredondamento do próprio SIDRA. Se isso parasse de fechar, "
        "o script aborta.",
        "",
    ]:
        ws.append([t])
    inicio = ws.max_row + 1
    cab6 = ["praça", "peso no IPCA nacional %",
            "peso da gasolina na praça %", "contribuição da gasolina (p.p.)"]
    ws.append(cab6)
    ultimo = sal[-1] if sal else None
    for c in sorted(PRACAS, key=lambda c: -pesos[c]):
        local = ultimo["detalhe"].get(c) if ultimo else None
        peso_local = local[1] if local else None
        ws.append([PRACAS[c], pesos[c], peso_local,
                   None if peso_local is None else pesos[c] / 100 * peso_local])
    if ultimo:
        ws.append(["(peso da gasolina: %s)" % ultimo["mes"]])
    cabecalho(ws, cab6, inicio)

    if t2[0]:
        base = ws.max_row + 2
        ws.cell(base, 1, "Réplica da T.2: bimestre %s a %s"
                % BIMESTRE_FGV).font = neg
        ws.cell(base + 1, 1, "As colunas 'FGV' são as publicadas no artigo. "
                             "Se batem, o método aqui é o dele.")
        inicio = base + 3
        cab7 = ["praça", "var. observada %", "FGV", "var. imputada %", "FGV",
                "impacto (p.p.)", "FGV"]
        for i, nome in enumerate(cab7, start=1):
            ws.cell(inicio, i, nome)
        for linha in t2[0]:
            ws.append(list(linha[:1]) + [linha[1], linha[4], linha[2],
                                         linha[5], linha[3], linha[6]])
        total, total_fgv = t2[1]
        ws.append(["TOTAL", None, None, None, None, total, total_fgv])
        for i, nome in enumerate(cab7, start=1):
            c = ws.cell(inicio, i)
            c.font = Font(bold=True)
            c.alignment = Alignment(wrap_text=True, vertical="top")
        for linha in ws.iter_rows(min_row=inicio + 1):
            for c in linha:
                if isinstance(c.value, float):
                    c.number_format = "0.000"

    ws = wb.create_sheet("IPCA 12 meses")
    ws.append(["O IPCA acumulado em 12 meses, e como ficaria em cada estimativa"])
    ws.cell(ws.max_row, 1).font = neg
    for t in [
        "Cada contrafactual é o IPCA mensal observado mais o que o item "
        "Gasolina teria feito a mais naquele",
        "mês, acumulado em doze meses. Só entram janelas de doze meses "
        "seguidos e completos.",
        "",
        "O contábil e o da Bahia dependem do preço de bomba da ANP e da "
        "tabela da Petrobras; o de Salvador",
        "depende só do IPCA regional do IBGE. São três fontes e três "
        "hipóteses diferentes para o mesmo número,",
        "e é por isso que a distância entre eles é informação, não ruído.",
        "",
        "LEMBRE DO QUE É CADA UM: contábil é TETO (repasse integral e "
        "imediato), Bahia é PISO (mede o repasse",
        "que de fato apareceu no preço baiano), Salvador fica no meio e o "
        "próprio autor o chama de limite",
        "superior da ordem de magnitude.",
        "",
        "E leia a coluna de Salvador junto com a aba dela. Ela não mede nível "
        "de defasagem, mede diferença de",
        "ritmo entre praças, então ela zera quando todo mundo repassa igual — "
        "inclusive quando todo mundo está",
        "igualmente segurado, que é o caso desde 13/8/2026, quando a subvenção "
        "da MP 1.358 chegou à Acelen.",
        "",
    ]:
        ws.append([t])
    inicio = ws.max_row + 1
    cab8 = ["mês", "IPCA 12m observado %", "contrafactual contábil %",
            "contrafactual Bahia %", "contrafactual Salvador %",
            "efeito contábil (p.p.)", "efeito Bahia (p.p.)",
            "efeito Salvador (p.p.)"]
    ws.append(cab8)
    for l in doze:
        ws.append([l["mes"], l["obs"], l["contabil"], l["bahia"],
                   l["salvador"], l["efeito_contabil"], l["efeito_bahia"],
                   l["efeito_salvador"]])
    cabecalho(ws, cab8, inicio)

    ws = wb.create_sheet("Sensibilidade")
    cab3 = ["mês", "nível represado (p.p.) — margem fixa",
            "nível represado (p.p.) — margem escalando", "diferença (p.p.)"]
    ws.append(cab3)
    base = {l["mes"]: l["nivel"] for l in linhas}
    for l in sensivel:
        b = base.get(l["mes"])
        ws.append([l["mes"], b, l["nivel"],
                   (l["nivel"] - b) if b is not None else None])
    formatar(ws, cab3)

    wb.save(SAIDA)


def cabecalho(ws, cab, inicio):
    """Formata uma linha de cabeçalho que não é a primeira da aba."""
    for i, nome in enumerate(cab, start=1):
        c = ws.cell(inicio, i)
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(i)].width = max(
            10, min(24, len(nome) + 2))
    ws.freeze_panes = "A%d" % (inicio + 1)
    for linha in ws.iter_rows(min_row=inicio + 1):
        for c in linha:
            if isinstance(c.value, float):
                c.number_format = "0.000"


def formatar(ws, cab):
    ws.freeze_panes = "A2"
    for i, nome in enumerate(cab, start=1):
        ws.cell(1, i).font = Font(bold=True)
        ws.cell(1, i).alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(i)].width = max(
            10, min(22, len(nome) + 2))
    for linha in ws.iter_rows(min_row=2):
        for c in linha:
            if isinstance(c.value, float):
                c.number_format = "0.000" if abs(c.value) < 10 else "0.00"


def main():
    hoje = datetime.date.today()

    print("Defasagem da gasolina…")
    defas, ultima = defasagem_mensal()
    print("  %d pontos, última tabela da Petrobras em %s"
          % (len(defas), ultima))

    print("Preço de bomba da ANP…")
    if not os.path.exists(pr.AGREGADO):
        pr.agregar()
    bomba = bomba_mensal()
    print("  %d meses, de %s a %s" % (len(bomba), min(bomba), max(bomba)))

    print("IPCA no SIDRA…")
    idx = ipca()
    print("  %d meses, de %s a %s" % (len(idx), min(idx), max(idx)))

    linhas = modelo(defas, bomba, idx, df.PRINCIPAL)
    sensivel = modelo(defas, bomba, idx, df.PRINCIPAL, margem_escala=True)
    bah, par = bahia(linhas, precos_por_mes())
    pontos = {p: {m: v for m, v in
                  ((l["mes"], l["nivel"]) for l in modelo(defas, bomba, idx, p))}
              for p in defas}

    print("IPCA por praça no SIDRA…")
    reg = ipca_por_praca()
    pesos, soma, pior = pesos_regionais(max(idx))
    print("  %d praças; pesos regionais somam %.4f, pior resíduo %.6f"
          % (len(reg), soma, pior))
    sal = salvador(idx, reg, pesos)
    t2 = replica_t2(reg, pesos)
    doze = doze_meses(linhas, bah, sal)

    medias = medias_por_ponto(pontos, producao_por_ponto())

    escrever(linhas, sensivel, pontos, medias, bah, par, sal, pesos,
             (soma, pior), t2, doze, ultima, hoje)

    u = linhas[-1]
    print("\n%s: defasagem efetiva de R$ %.3f/l em %s, repasse de R$ %.3f na "
          "bomba" % (u["mes"], u["defasagem_efetiva"], df.PRINCIPAL, u["repasse"]))
    print("  falta %.1f%% no preço da gasolina; peso do item %.3f%%"
          % (u["gap"], u["peso"]))
    print("  NÍVEL REPRESADO (contábil, Paulínia): %.2f p.p. do IPCA"
          % u["nivel"])
    if u["mes"] in medias:
        pond, simples = medias[u["mes"]]
        print("  nos nove pontos: %.2f ponderada por produção, %.2f simples"
              % (pond, simples))
    inclinacao, estrutural, r2, n = par
    print("\nsegunda estimativa, Bahia como controle:")
    print("  spread BA−Brasil = R$ %.3f estrutural %+.3f × defasagem "
          "(R² %.2f, n=%d)" % (estrutural, inclinacao, r2, n))
    if bah and bah[-1]["mes"] == u["mes"]:
        b = bah[-1]
        print("  %s: excesso de R$ %.3f/l, falta %.1f%% no preço"
              % (b["mes"], b["excesso"], b["gap"]))
        print("  NÍVEL REPRESADO (Bahia): %.2f p.p. — contábil diz %.2f"
              % (b["nivel"], b["nivel_contabil"]))
    if u["efeito12"] is not None:
        print("  efeito no IPCA 12m: %+.2f p.p." % u["efeito12"])

    if sal:
        u3 = sal[-1]
        print("\nterceira estimativa, Salvador como contrafactual (FGV):")
        print("  %s: impacto de %+.2f p.p. no mês, %d praças acima de Salvador"
              % (u3["mes"], u3["impacto"],
                 sum(1 for c, d in u3["detalhe"].items()
                     if c != REFERENCIA and d[2] < 0)))
    if t2[0]:
        total, total_fgv = t2[1]
        print("  réplica da T.2 (%s a %s): %.3f p.p. aqui, %.2f no artigo"
              % (BIMESTRE_FGV[0], BIMESTRE_FGV[1], total, total_fgv))

    if doze:
        d = doze[-1]
        print("\nIPCA 12 meses em %s: observado %.2f%%" % (d["mes"], d["obs"]))
        for chave, nome in (("contabil", "contábil"), ("bahia", "Bahia"),
                            ("salvador", "Salvador")):
            if d[chave] is not None:
                print("  contrafactual %-9s %.2f%%  (%+.2f p.p.)"
                      % (nome, d[chave], d["efeito_" + chave]))
    print("\nescrito: %s" % SAIDA)


if __name__ == "__main__":
    main()
