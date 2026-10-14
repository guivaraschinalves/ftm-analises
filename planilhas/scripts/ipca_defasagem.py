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
    for l in linhas:
        if l["mes"] not in precos:
            continue
        p = precos[l["mes"]]
        spread = p[CONTROLE] - p["Brasil"]
        # A parte do spread que a defasagem explica. Com defasagem negativa e
        # inclinação negativa, o excesso é positivo: é o que falta no Brasil.
        excesso = inclinacao * l["defasagem_efetiva"]
        gap = excesso / l["preco"] * 100
        fora.append({
            "mes": l["mes"], "defasagem_efetiva": l["defasagem_efetiva"],
            "ba": p[CONTROLE], "brasil": p["Brasil"], "spread": spread,
            "estrutural": estrutural, "excesso": excesso, "gap": gap,
            "peso": l["peso"], "nivel": l["peso"] * gap / 100,
            "nivel_contabil": l["nivel"],
        })
    return fora, par


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


def acumulado(valores):
    f = 1.0
    for v in valores:
        f *= 1 + v / 100
    return (f - 1) * 100


def escrever(linhas, sensivel, pontos, bah, par, ultima, hoje):
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
        ("Por ponto | O nível represado em cada ponto de entrega", False),
        ("Contrafactual Bahia | A segunda estimativa, por grupo de controle", False),
        ("Sensibilidade | O mesmo cálculo com a margem escalando junto", False),
        ("", False),
        ("DUAS ESTIMATIVAS, E ELAS NÃO BATEM", True),
        ("A contábil supõe que R$ 1,00 na refinaria vira R$ 0,70 na bomba, "
         "porque 70% do litro é gasolina A.", False),
        ("A da Bahia MEDE quanto aparece, usando a Acelen (que segue o PPI) "
         "como controle, e acha R$ 0,26.", False),
        ("A contábil é teto e a da Bahia é piso. O teto supõe repasse integral "
         "e imediato; o piso subestima", False),
        ("porque a Acelen não atende a Bahia inteira, não segue o PPI "
         "perfeitamente e também recebeu as", False),
        ("subvenções de 2026, que encolhem o próprio spread que serve de "
         "medida. A verdade mora no meio,", False),
        ("e a largura entre as duas é a sua incerteza honesta.", False),
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
    cab2 = ["mês"] + sorted(pontos)
    ws.append(cab2)
    meses = sorted({m for p in pontos.values() for m in p})
    for m in meses:
        ws.append([m] + [pontos[p].get(m) for p in sorted(pontos)])
    formatar(ws, cab2)

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
    for i, nome in enumerate(cab4, start=1):
        c = ws.cell(inicio, i)
        c.font = Font(bold=True)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.column_dimensions[get_column_letter(i)].width = max(10, min(22, len(nome) + 2))
    ws.freeze_panes = "A%d" % (inicio + 1)
    for linha in ws.iter_rows(min_row=inicio + 1):
        for c in linha:
            if isinstance(c.value, float):
                c.number_format = "0.000"

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

    escrever(linhas, sensivel, pontos, bah, par, ultima, hoje)

    u = linhas[-1]
    print("\n%s: defasagem efetiva de R$ %.3f/l em %s, repasse de R$ %.3f na "
          "bomba" % (u["mes"], u["defasagem_efetiva"], df.PRINCIPAL, u["repasse"]))
    print("  falta %.1f%% no preço da gasolina; peso do item %.3f%%"
          % (u["gap"], u["peso"]))
    print("  NÍVEL REPRESADO (contábil): %.2f p.p. do IPCA" % u["nivel"])
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
    doze = [l for l in linhas[-12:] if l["ipca"] is not None]
    if len(doze) == 12:
        print("  IPCA 12m observado %.2f%%, contrafactual %.2f%%"
              % (acumulado([l["ipca"] for l in doze]),
                 acumulado([l["ipca_cf"] for l in doze])))
    print("\nescrito: %s" % SAIDA)


if __name__ == "__main__":
    main()
