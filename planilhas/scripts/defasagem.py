#!/usr/bin/env python3
"""
Monta dados/defasagem-gasolina.xlsx — quanto o preço da gasolina A da
Petrobras está acima ou abaixo do preço de paridade de importação.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/defasagem.py

Precisa de openpyxl e pdfplumber, como precos_combustiveis.py, e usa o leitor
de PDF dele. NÃO entra na Action.

AS DUAS PONTAS, E POR QUE ELAS SE COMPARAM

  - **Petrobras**: o preço por ponto de entrega que ela publica por obrigação
    da Resolução ANP 795/2019, modalidade EXA (ex-ponto A, no duto dentro da
    refinaria), em R$/litro e **sem tributos**. Muda por vigência, não por
    semana: é uma escada, não uma linha.
  - **PPI da ANP**: a média semanal do preço de paridade de importação
    estimado pela S&P Global para cada ponto de entrega, em R$/litro e
    **sem tributos**. Nos pontos que não são porto (Paulínia, Betim, Duque de
    Caxias…) o cálculo já inclui o frete rodoviário do porto até lá.

As duas são preço de gasolina A, no mesmo ponto do país, na mesma unidade e
livres de tributo. É por isso que a subtração significa alguma coisa — e é
por isso que comparar o PPI com o preço da bomba não significaria nada.

A DEFASAGEM AQUI É **Petrobras − PPI**: negativo quer dizer vendendo abaixo
da paridade, que é o caso quase sempre discutido. Em % é sobre o PPI.

DA ESCADA PARA A SEMANA. O preço da Petrobras vale de uma vigência até a
seguinte; o PPI é média de uma semana de segunda a sexta. Para cada semana do
PPI entra a **média dos cinco dias úteis** do preço que estava valendo em cada
um — e não o preço do último dia, que jogaria um reajuste de quinta-feira
sobre a semana inteira.

O QUE O NÚMERO NÃO É

  - Não é a defasagem da Abicom nem a de ninguém mais: cada casa usa o seu
    PPI (porto, frete, custo de internação, dia da cotação). Aqui o PPI é o
    da ANP, que é público e auditável.
  - Não vale para o diesel: a tabela da Petrobras que está em dados/ é só de
    gasolina. Com o PDF do diesel ali, o mesmo script monta a dele.
  - A tabela mais recente da Petrobras é de 1/9/2026. Depois dessa data o
    preço segue valendo até ela mudar — e a planilha marca essas semanas como
    extrapoladas, porque uma mudança que não saiu na biblioteca pública não
    aparece aqui.
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import precos_combustiveis as pc                           # noqa: E402
import precos_revenda                                      # noqa: E402

RAIZ = pc.RAIZ
DADOS = pc.DADOS
SAIDA = os.path.join(RAIZ, "defasagem-gasolina.xlsx")

PPI_URL = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
           "precos/arq-ppi/ppi.xlsx")
PPI_ARQUIVO = os.path.join(RAIZ, "ppi-anp.xlsx")
ABA_PPI = "Gasolina R$ semanal"

# A modalidade da Petrobras que fica no portão da refinaria, que é onde o PPI
# dos pontos interiores também chega. Misturar com entrega marítima ou
# rodoviária poria frete de um lado só.
MODALIDADE = "EXA"

# Ponto de entrega da Petrobras → coluna do PPI. Só entram os que são o mesmo
# lugar: Ipojuca e Suape, por exemplo, ficam de fora porque o PPI de Suape é
# no porto e o ponto da Petrobras é a refinaria, com frete no meio.
PONTOS = {
    "Paulínia (SP)": "Paulínia",
    "Betim (MG)": "Betim",
    "Duque de Caxias (RJ)": "Duque de Caxias",
    "Cubatão (SP)": "Cubatão",
    "São José dos Campos (SP)": "São José dos Campos",
    "Araucária (PR)": "Araucária",
    "Canoas (RS)": "Canoas",
    "Guamaré (RN)": "Guamaré",
    "Manaus (AM)": "Manaus",
}
PRINCIPAL = "Paulínia (SP)"


# ─── A outra ponta do balcão: a Acelen ───────────────────────────────────────
#
# A Acelen assumiu a refinaria de Mataripe em 1/12/2021 e publica a tabela
# dela pela mesma Resolução ANP 795/2019 que obriga a Petrobras. Então dá para
# fazer com ela exatamente a conta que se faz com a Petrobras, e é essa
# comparação que sustenta as estimativas 2 e 3 do ipca-defasagem.xlsx: as duas
# supõem que o preço baiano é uma leitura de mercado, e aqui isso vira medida
# em vez de suposição.
#
# Aratu é o porto, em Candeias, e é lá que a ANP estima o PPI da Bahia. Por
# isso o ponto principal é Candeias. São Francisco do Conde é a refinaria em
# si, dois décimos de centavo abaixo de Candeias em toda a série, e entra
# junto. Jequié é interior, uns sete centavos acima, e entra com o aviso de
# que a diferença ali é frete, não política de preço.
ACELEN_PONTOS = {
    "Candeias (BA)": "Aratu",
    "São Francisco do Conde (BA)": "Aratu",
    "Jequié (BA)": "Aratu",
}
ACELEN_PRINCIPAL = "Candeias (BA)"
ACELEN_COM_FRETE = ("Jequié (BA)",)


# As duas cores do gráfico mensal. Passam na checagem de daltonismo com folga
# (ΔE 24,7 no pior caso, protanopia), que é o que garante que as duas linhas
# continuem distinguíveis para quem não separa vermelho de verde — o gráfico
# do artigo usa preto e vermelho, que não passa.
COR_PPI = "2A78D6"
COR_EMPRESA = "EB6834"


def mensal(linhas, ponto, minimo=3):
    """[(mês, PPI, preço de tabela, preço com subvenção ou None)].

    Média das semanas que terminam no mês. Exige três semanas, senão um mês
    recém-começado entraria como se fosse mês inteiro."""
    acc = {}
    for pt, fim, tab, desc, ppi, _d, _r, _r2, _x in linhas:
        if pt != ponto:
            continue
        a = acc.setdefault(fim.strftime("%Y-%m"), [[], [], []])
        a[0].append(ppi)
        a[1].append(tab)
        a[2].append(tab - desc)
    fora = []
    for mes, (ps, ts, ls) in sorted(acc.items()):
        if len(ps) < minimo:
            continue
        liquido = sum(ls) / len(ls)
        tabela = sum(ts) / len(ts)
        fora.append((mes, sum(ps) / len(ps), tabela,
                     liquido if abs(liquido - tabela) > 1e-9 else None))
    return fora


def grafico_mensal(ws, dados, titulo, rotulo_empresa, primeira, ultima):
    """Reconstrói o G.3 do artigo: duas linhas, PPI e preço ao distribuidor."""
    from openpyxl.chart import LineChart, Reference
    from openpyxl.chart.marker import Marker
    from openpyxl.drawing.line import LineProperties

    ch = LineChart()
    ch.title = titulo
    ch.height, ch.width = 9.5, 24
    ch.y_axis.title = "R$/litro"
    ch.y_axis.scaling.min = max(0.0, min(min(d[1], d[2]) for d in dados) - 0.4)
    ch.y_axis.majorGridlines = None          # grade recessiva: nenhuma
    ch.x_axis.tickLblSkip = 3                # senão os rótulos se atropelam
    ch.x_axis.tickMarkSkip = 3

    ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=primeira - 1,
                          max_row=ultima), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=1, min_row=primeira, max_row=ultima))
    for serie, cor in zip(ch.series, (COR_PPI, COR_EMPRESA)):
        serie.graphicalProperties.line = LineProperties(solidFill=cor, w=19050)
        serie.marker = Marker(symbol="none")
        serie.smooth = False
    return ch


def variacoes(serie):
    """[(x, y)] de variações percentuais semana a semana, para a correlação."""
    fora = []
    for (_d0, a0, b0), (_d1, a1, b1) in zip(serie, serie[1:]):
        if a0 and b0:
            fora.append((a1 / a0 - 1, b1 / b0 - 1))
    return fora


def correlacao(pares):
    """Pearson. Mede se as duas pontas se MEXEM juntas, que é outra pergunta
    que o nível da defasagem não responde: dá para estar sempre R$ 0,50 abaixo
    do PPI e ainda assim acompanhar cada subida dele."""
    n = len(pares)
    if n < 3:
        return float("nan")
    mx = sum(a for a, _ in pares) / n
    my = sum(b for _, b in pares) / n
    sxy = sum((a - mx) * (b - my) for a, b in pares)
    sxx = sum((a - mx) ** 2 for a, _ in pares)
    syy = sum((b - my) ** 2 for _, b in pares)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")


def resumo_contra_ppi(linhas, ponto, desde=None):
    """(n, defasagem % média, mediana, |defasagem| média, correlação).

    `desde` existe para comparar na mesma janela: a série da Petrobras começa
    em set/2019 e a da Acelen em dez/2021, e média de períodos diferentes não
    compara nada."""
    sel = sorted((l for l in linhas if l[0] == ponto
                  and (desde is None or l[1] >= desde)), key=lambda l: l[1])
    if not sel:
        return None
    pcts = sorted(100 * l[6] for l in sel)
    n = len(pcts)
    mediana = (pcts[n // 2] if n % 2 else (pcts[n // 2 - 1] + pcts[n // 2]) / 2)
    serie = [(l[1], l[2], l[4]) for l in sel]
    # "A menos de 5% da paridade" é a estatística que mais diz: média esconde
    # compensação entre semana acima e semana abaixo, e esta não esconde.
    perto = 100 * sum(1 for x in pcts if abs(x) < 5) / n
    return (n, sum(pcts) / n, mediana, sum(abs(p) for p in pcts) / n,
            perto, correlacao(variacoes(serie)))


def baixar_ppi():
    if not os.path.exists(PPI_ARQUIVO):
        print("  baixando ppi.xlsx da ANP…")
        pc.baixar(PPI_URL, PPI_ARQUIVO)
    return PPI_ARQUIVO


def ler_ppi(caminho):
    """[(início, fim, {ponto: R$/litro})], uma entrada por semana."""
    import openpyxl
    ws = openpyxl.load_workbook(caminho, data_only=True)[ABA_PPI]
    grade = [list(r) for r in ws.iter_rows(values_only=True)]
    ih = next((i for i, r in enumerate(grade)
               if any(isinstance(c, str) and c.strip() == "Data" for c in r)), None)
    if ih is None:
        raise SystemExit("a aba %r não tem linha de cabeçalho — o layout mudou?" % ABA_PPI)
    jd = next(j for j, c in enumerate(grade[ih]) if isinstance(c, str) and c.strip() == "Data")
    # as colunas de preço são as contíguas depois de "Data"; o bloco seguinte,
    # separado por uma coluna vazia, repete os nomes com a variação semanal
    col = {}
    for j in range(jd + 1, len(grade[ih])):
        c = grade[ih][j]
        if not isinstance(c, str) or not c.strip():
            break
        col[c.strip()] = j
    faltam = sorted(set(PONTOS.values()) - set(col))
    if faltam:
        raise SystemExit("o PPI não trouxe %s — nomes de coluna mudaram?" % ", ".join(faltam))

    fora = []
    for r in grade[ih + 1:]:
        bruto = r[jd]
        if not isinstance(bruto, str):
            continue
        datas = pc.DATA.findall(bruto)
        if len(datas) != 2:
            continue
        ini, fim = (datetime.date(int(a), int(m), int(d)) for d, m, a in datas)
        valores = {p: float(r[j]) for p, j in col.items()
                   if isinstance(r[j], (int, float)) and r[j] > 0}
        if valores:
            fora.append((ini, fim, valores))
    return fora


PRODUTO = "Gasolina A"


def escadas_de(linhas, empresa, ponto, modalidade=MODALIDADE, produto=PRODUTO):
    """(escada do preço de tabela, escada do preço com subvenção).

    Desde 29/5/2026 a tabela da Petrobras traz as duas colunas, e nas
    vigências de agosto e setembro de 2026 só a com desconto — o preço cheio
    daqueles meses não foi republicado. Como a escada carrega o último valor
    para a frente, o preço de tabela continua sendo o de 29/5, que é o certo:
    o que mudou foi a subvenção, não o preço da empresa. A Acelen publica no
    mesmo formato, e também recebe a subvenção da MP 1.358."""
    tabela, subvencionado = {}, {}
    for e, prod, d, _uf, mod, loc, v, desc in linhas:
        # O filtro de produto não é decorativo: o PDF da Petrobras só traz
        # gasolina, mas a tabela da Acelen traz também os dois diesel, no
        # mesmo ponto e na mesma modalidade. Sem ele o diesel sobrescreve a
        # gasolina e a defasagem sai inventada.
        if (e == empresa and prod == produto and loc == ponto
                and mod == modalidade):
            (subvencionado if desc else tabela)[d] = v
    return sorted(tabela.items()), sorted(subvencionado.items())


def escadas_petrobras(linhas, ponto):
    return escadas_de(linhas, "Petrobras", ponto)


def preco_em(escada, dia):
    """O preço que estava valendo naquele dia, ou None antes da primeira tabela."""
    valor = None
    for d, v in escada:
        if d > dia:
            break
        valor = v
    return valor


def media_na_semana(escada, ini, fim):
    """Média do preço vigente nos dias úteis da semana do PPI."""
    dias, d = [], ini
    while d <= fim:
        if d.weekday() < 5:
            dias.append(d)
        d += datetime.timedelta(days=1)
    valores = [preco_em(escada, x) for x in dias]
    valores = [v for v in valores if v is not None]
    return sum(valores) / len(valores) if len(valores) == len(dias) and dias else None


def montar(ppi, escadas, ultima_tabela, pontos=None):
    """[(ponto, fim, tabela, subvenção, ppi, dif, %, % com subvenção, extrap.)]."""
    fora = []
    for ini, fim, valores in ppi:
        for ponto, coluna in (pontos or PONTOS).items():
            tabela, subv = escadas.get(ponto, ([], []))
            p = valores.get(coluna)
            b = media_na_semana(tabela, ini, fim)
            if p is None or b is None:
                continue
            liquido = media_na_semana(subv, ini, fim)
            desconto = (b - liquido) if liquido is not None else 0.0
            fora.append((ponto, fim, b, desconto, p, b - p, b / p - 1,
                         (b - desconto) / p - 1, "sim" if ini > ultima_tabela else ""))
    return fora


def escrever(linhas, ultima_tabela, acelen, resumos, revenda, hoje):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    wb.remove(wb.active)

    leia = wb.create_sheet("LEIA-ME")
    for linha in [
        ["Defasagem da gasolina A da Petrobras em relação ao PPI"],
        ["Gerado em", hoje.strftime("%d/%m/%Y")],
        [],
        ["Aba", "O que é"],
        ["Defasagem " + PRINCIPAL.split(" (")[0],
         "A série principal: a refinaria de Paulínia, semana a semana"],
        ["Defasagem por ponto", "O mesmo nos nove pontos em que as duas pontas existem"],
        ["Defasagem média", "Média simples dos pontos, semana a semana"],
        ["Etanol vs gasolina", "Do outro lado do balcão: a regra dos 70% na bomba, "
                               "Brasil e São Paulo"],
        [],
        ["DEFASAGEM = PREÇO DA PETROBRAS − PPI. Negativo é vender abaixo da paridade."],
        [],
        ["As duas pontas:"],
        ["Petrobras", "Preço por ponto de entrega, modalidade EXA (no duto dentro da "
                      "refinaria), R$/litro, SEM TRIBUTOS."],
        ["", "Publicado por obrigação da Resolução ANP 795/2019. Muda por vigência, "
             "não por semana."],
        ["PPI", "Média semanal do preço de paridade de importação estimado pela S&P "
                "Global, R$/litro, SEM TRIBUTOS."],
        ["", "Nos pontos que não são porto, o cálculo da ANP já inclui o frete "
             "rodoviário do porto até lá."],
        [],
        ["As duas são gasolina A, no mesmo ponto do país, na mesma unidade e livres de "
         "tributo — é por isso que a subtração"],
        ["significa alguma coisa. Comparar o PPI com o preço da bomba não significaria: "
         "lá dentro há etanol anidro, imposto e margem."],
        [],
        ["DUAS COLUNAS DE PREÇO DA PETROBRAS desde 29/5/2026: o preço de tabela e o "
         "preço com a subvenção da MP 1.358,"],
        ["de R$ 0,44/litro. A defasagem principal é sobre o preço de TABELA, que é a "
         "decisão de preço da empresa; a coluna"],
        ["'defasagem % com subvenção' usa o que a distribuidora de fato pagou, que é o "
         "que chega à bomba. Nas vigências de"],
        ["agosto e setembro de 2026 a Petrobras publicou só a coluna com desconto — o "
         "preço de tabela de 29/5 continua valendo,"],
        ["e a conferência bate: a diferença entre as duas colunas é R$ 0,44 em todo "
         "ponto e em toda vigência. O fim da subvenção"],
        ["depende da medida provisória, não da tabela: depois de 1/9/2026 as duas "
         "colunas são as últimas publicadas."],
        [],
        ["Da escada para a semana: o preço da Petrobras vale de uma vigência até a "
         "seguinte, e o PPI é média de segunda a sexta."],
        ["Entra a média dos cinco dias úteis do preço que estava valendo em cada um — "
         "não o preço do último dia, que jogaria"],
        ["um reajuste de quinta-feira sobre a semana inteira."],
        [],
        ["Só entram os pontos que são o MESMO LUGAR nas duas pontas. Ipojuca e Suape, "
         "por exemplo, ficam de fora: o PPI de"],
        ["Suape é no porto e o ponto da Petrobras é a refinaria, com frete no meio."],
        [],
        ["ATENÇÃO — a tabela mais recente da Petrobras é de " + ultima_tabela.strftime("%d/%m/%Y") + "."],
        ["Depois dessa data o preço segue valendo até ela mudar, e as semanas saem "
         "marcadas como extrapoladas: um reajuste"],
        ["que ainda não apareceu na biblioteca pública da Petrobras não está aqui."],
        [],
        ["Esta não é a defasagem da Abicom nem a de ninguém mais: cada casa usa o seu "
         "PPI (porto, frete, custo de internação,"],
        ["dia da cotação). Aqui o PPI é o da ANP, que é público e auditável."],
        [],
        ["Só gasolina. A tabela da Petrobras que está em dados/ é só de gasolina; com o "
         "PDF do diesel, o mesmo script monta a dele."],
        [],
        ["A ACELEN, DO OUTRO LADO"],
        ["A Acelen assumiu Mataripe em 1/12/2021 e publica pela mesma Resolução ANP "
         "795/2019. Então dá para fazer com ela a"],
        ["mesma conta, contra o PPI de Aratu, que é o porto da Bahia. Isso importa "
         "porque as estimativas 2 e 3 do"],
        ["ipca-defasagem.xlsx supõem que o preço baiano é leitura de mercado. Aqui "
         "isso vira medida, não suposição."],
        [],
    ] + resumos + [
        [],
        ["Leia assim: a defasagem média diz o quanto cada empresa fica abaixo da "
         "paridade; a correlação diz se ela se"],
        ["MEXE junto com o PPI. São perguntas diferentes, e dá para acompanhar cada "
         "subida do PPI vivendo sempre abaixo dele."],
        [],
        ["Aratu fica em Candeias, e por isso Candeias é o ponto principal. São "
         "Francisco do Conde é a refinaria em si,"],
        ["colada em Candeias. Jequié é interior: os centavos a mais ali são frete, "
         "não política de preço."],
    ]:
        leia.append(linha)
    leia["A1"].font = Font(bold=True, size=14)
    leia["A4"].font = leia["B4"].font = Font(bold=True)
    for linha in leia.iter_rows(min_col=1, max_col=1):
        t = linha[0].value or ""
        if t.startswith(("DEFASAGEM =", "ATENÇÃO", "DUAS COLUNAS")):
            linha[0].font = Font(bold=True)
    for col, larg in zip("AB", (26, 104)):
        leia.column_dimensions[col].width = larg

    cab = ["semana (fim)", "Petrobras R$/l (tabela)", "subvenção R$/l", "PPI R$/l",
           "defasagem R$/l", "defasagem %", "defasagem % com subvenção",
           "preço extrapolado"]
    fmt = {1: "DD/MM/YYYY", 2: "0.0000", 3: "0.0000", 4: "0.0000", 5: "0.0000",
           6: "0.0%", 7: "0.0%"}
    larg = [14, 22, 15, 12, 16, 13, 26, 18]

    pc.aba(wb, "Defasagem " + PRINCIPAL.split(" (")[0], cab,
           [l[1:] for l in linhas if l[0] == PRINCIPAL], larguras=larg, formato=fmt)

    pc.aba(wb, "Defasagem por ponto", ["ponto de entrega"] + cab, linhas,
           larguras=[26] + larg, formato={k + 1: v for k, v in fmt.items()})

    por_semana = {}
    for _pt, f, b, s_, p, _d, _r, _r2, x in linhas:
        a = por_semana.setdefault(f, [0.0, 0.0, 0.0, 0, ""])
        a[0] += b
        a[1] += s_
        a[2] += p
        a[3] += 1
        a[4] = a[4] or x
    pc.aba(wb, "Defasagem média", ["pontos"] + cab,
           [(n, f, b / n, s_ / n, p / n, (b - p) / n, b / p - 1, (b - s_) / p - 1, x)
            for f, (b, s_, p, n, x) in sorted(por_semana.items())],
           larguras=[9] + larg, formato={k + 1: v for k, v in fmt.items()})

    if acelen:
        # A reconstrução do gráfico G.3 do artigo, estendida: ele vai até
        # abr/2026 e esta vai até onde a ANP e a Acelen publicaram.
        ws = wb.create_sheet("Gráfico Acelen vs PPI")
        for t in [
            "Gasolina A: PPI em Aratu (BA) contra o preço da Acelen aos "
            "distribuidores em Candeias (BA)",
            "",
            "É o gráfico G.3 do artigo da FGV, refeito e estendido. Média "
            "mensal das semanas, R$/litro, sem tributos.",
            "A coluna 'com subvenção' é o que a distribuidora de fato pagou "
            "depois da MP 1.358. Ela só existe de",
            "13/8/2026 em diante: a Petrobras começou a descontar os R$ 0,44 "
            "em 29/5/2026 e a Acelen dois meses e",
            "meio depois. Esse atraso é o que explica a queda do preço de "
            "bomba baiano em agosto, com a tabela da",
            "Acelen praticamente parada, e é também o que derruba a terceira "
            "estimativa do ipca-defasagem.xlsx.",
            "Ela fica fora do gráfico de propósito, para a linha ser "
            "comparável de ponta a ponta; para incluí-la,",
            "é só estendê-la à seleção de dados.",
            "",
        ]:
            ws.append([t])
        ws["A1"].font = Font(bold=True)
        primeira = ws.max_row + 2
        ws.append(["mês", "PPI Aratu", "Acelen Candeias",
                   "Acelen com subvenção", "defasagem %"])
        for c in ws[primeira - 1]:
            c.font = Font(bold=True)
        dados = mensal(acelen, ACELEN_PRINCIPAL)
        for mes, ppi_m, tab, liq in dados:
            ws.append([mes, ppi_m, tab, liq, tab / ppi_m - 1])
        ultima_linha = ws.max_row
        for linha in ws.iter_rows(min_row=primeira, min_col=2, max_col=4):
            for c in linha:
                c.number_format = "0.000"
        for linha in ws.iter_rows(min_row=primeira, min_col=5, max_col=5):
            linha[0].number_format = "0.0%"
        for col, w in zip("ABCDE", (10, 13, 17, 20, 13)):
            ws.column_dimensions[col].width = w
        if dados:
            ws.add_chart(grafico_mensal(
                ws, dados,
                "Gasolina A: PPI Aratu-BA vs. preço aos distribuidores "
                "Acelen na Bahia (R$/litro)",
                "Acelen", primeira, ultima_linha), "G2")

        cab_a = ["semana (fim)", "Acelen R$/l (tabela)", "subvenção R$/l",
                 "PPI Aratu R$/l", "defasagem R$/l", "defasagem %",
                 "defasagem % com subvenção", "preço extrapolado"]
        pc.aba(wb, "Acelen vs PPI", ["ponto de entrega"] + cab_a, acelen,
               larguras=[28] + larg, formato={k + 1: v for k, v in fmt.items()})

        # O lado a lado que responde a pergunta inteira: a mesma semana, o
        # mesmo produto, duas empresas, cada uma contra o PPI do lugar dela.
        pet = {l[1]: l for l in linhas if l[0] == PRINCIPAL}
        ace = {l[1]: l for l in acelen if l[0] == ACELEN_PRINCIPAL}
        juntas = []
        for f in sorted(set(pet) & set(ace)):
            a, b = ace[f], pet[f]
            juntas.append((f, a[4], a[2], a[6], b[4], b[2], b[6], a[6] - b[6]))
        pc.aba(wb, "Acelen vs Petrobras",
               ["semana (fim)", "PPI Aratu R$/l", "Acelen Candeias R$/l",
                "defasagem Acelen %", "PPI Paulínia R$/l",
                "Petrobras Paulínia R$/l", "defasagem Petrobras %",
                "diferença (p.p.)"],
               juntas, larguras=[14, 16, 21, 19, 17, 24, 22, 17],
               formato={1: "DD/MM/YYYY", 2: "0.0000", 3: "0.0000", 4: "0.0%",
                        5: "0.0000", 6: "0.0000", 7: "0.0%", 8: "0.0%"})

    if revenda:
        # A defasagem é o preço na refinaria; esta aba é o que o motorista vê na
        # bomba. Ficam juntas porque uma explica a outra: segurar a gasolina na
        # refinaria também derruba a competitividade do etanol.
        pc.aba(wb, "Etanol vs gasolina", precos_revenda.CABECALHO, revenda,
               larguras=[12, 12, 12, 14, 10, 14, 16, 17, 18, 10],
               formato={3: "0.000", 4: "0.000", 5: "0.0", 6: "0.0", 7: "0.0"})

    wb.save(SAIDA)


def main():
    hoje = datetime.date.today()
    print("PPI da ANP…")
    ppi = ler_ppi(baixar_ppi())
    print("  %d semanas, de %s a %s" % (len(ppi), ppi[0][0], ppi[-1][1]))

    import glob
    pdfs = sorted(glob.glob(os.path.join(DADOS, "*asolina*.pdf"))
                  + glob.glob(os.path.join(DADOS, "*abela*re*.pdf")), key=os.path.getmtime)
    if not pdfs:
        raise SystemExit("nenhuma tabela da Petrobras em dados/ — veja "
                         "precos_combustiveis.py, que sabe buscá-la")
    print("Petrobras, de %s…" % os.path.basename(pdfs[-1]))
    linhas = pc.ler_petrobras(pdfs[-1])
    escadas = {p: escadas_petrobras(linhas, p) for p in PONTOS}
    ultima = max(d for tab, sub in escadas.values() for d, _v in tab + sub)
    for p, (tab, sub) in sorted(escadas.items()):
        print("  %-26s %3d vigências (%d com subvenção), de %s a %s"
              % (p, len(tab) + len(sub), len(sub), tab[0][0], max(tab + sub)[0]))

    # A subvenção da MP 1.358 é de R$ 0,44/litro por lei, igual em todo ponto de
    # entrega. Se a diferença entre as duas colunas não for essa, uma das duas
    # está sendo lida errado.
    descontos = {round(tab_v - sub_v, 4)
                 for tab, sub in escadas.values()
                 for d, sub_v in sub
                 for tab_v in [preco_em(tab, d)] if tab_v is not None}
    print("  desconto implícito nas colunas subvencionadas: %s"
          % sorted(descontos))
    if len(descontos) > 1:
        print("  AVISO: a subvenção deveria ser uma só", file=sys.stderr)

    tudo = montar(ppi, escadas, ultima)
    if not tudo:
        raise SystemExit("nenhuma semana casou — confira os nomes dos pontos")
    principal = [l for l in tudo if l[0] == PRINCIPAL]
    print("casamento: %d semanas × ponto; %s tem %d semanas, de %s a %s"
          % (len(tudo), PRINCIPAL, len(principal), principal[0][1], principal[-1][1]))
    u = principal[-1]
    print("  última semana: %s — Petrobras %.4f (subvenção %.2f), PPI %.4f, "
          "defasagem %+.4f (%+.1f%%; com subvenção %+.1f%%)%s"
          % (u[1], u[2], u[3], u[4], u[5], 100 * u[6], 100 * u[7],
             "  [preço extrapolado]" if u[8] else ""))

    print("Acelen, da tabela publicada no site…")
    acelen, resumos = [], []
    try:
        linhas_a = pc.ler_acelen()
        escadas_a = {pt: escadas_de(linhas_a, "Acelen", pt)
                     for pt in ACELEN_PONTOS}
        ultima_a = max(d for tab, sub in escadas_a.values()
                       for d, _v in tab + sub)
        acelen = montar(ppi, escadas_a, ultima_a, ACELEN_PONTOS)
        # Mesma janela para as duas: a da Acelen, que é a mais curta.
        comum = min(l[1] for l in acelen) if acelen else None
        # A janela do choque do Oriente Médio, que é onde as duas políticas de
        # preço se separam de vez.
        choque = datetime.date(2026, 3, 1)
        for rotulo, dados, ponto, desde in (
                ("Acelen, Candeias (BA), contra o PPI de Aratu", acelen,
                 ACELEN_PRINCIPAL, comum),
                ("Petrobras, %s, na mesma janela" % PRINCIPAL, tudo,
                 PRINCIPAL, comum),
                ("", None, None, None),
                ("Acelen, de março de 2026 em diante", acelen,
                 ACELEN_PRINCIPAL, choque),
                ("Petrobras, de março de 2026 em diante", tudo,
                 PRINCIPAL, choque)):
            if dados is None:
                resumos.append([])
                continue
            r = resumo_contra_ppi(dados, ponto, desde)
            if not r:
                continue
            n, media, mediana, absoluta, perto, corr = r
            resumos.append([rotulo, "%d semanas | defasagem média %+.1f%% | "
                                    "mediana %+.1f%% | em módulo %.1f%% | a "
                                    "menos de 5%% da paridade em %.0f%% das "
                                    "semanas | correlação das variações "
                                    "semanais com o PPI %.2f"
                            % (n, media, mediana, absoluta, perto, corr)])
            print("  %-46s %3d sem | média %+6.1f%% | perto %3.0f%% | corr %+.2f"
                  % (rotulo, n, media, perto, corr))
        print("  última vigência da Acelen: %s" % ultima_a)
    except Exception as e:              # fonte web: não derruba o resto
        print("  tabela da Acelen falhou: %s" % e, file=sys.stderr)

    print("ANP, preço de bomba (etanol e gasolina)…")
    try:
        # Só Brasil e São Paulo: a planilha é da defasagem, e a série completa
        # por UF está em precos-combustiveis.xlsx.
        revenda = [l for l in precos_revenda.serie() if l[1] in ("Brasil", "SP")]
        print("  %d linhas, de %s a %s"
              % (len(revenda), revenda[0][0], revenda[-1][0]))
    except Exception as e:                    # fonte pesada: não derruba o resto
        print("  Levantamento de Preços falhou: %s" % e, file=sys.stderr)
        revenda = []

    escrever(tudo, ultima, acelen, resumos, revenda, hoje)
    print("gravado %s (%.0f KB)"
          % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
