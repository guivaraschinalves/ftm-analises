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


def escadas_petrobras(linhas, ponto):
    """(escada do preço de tabela, escada do preço com subvenção).

    Desde 29/5/2026 a tabela da Petrobras traz as duas colunas, e nas
    vigências de agosto e setembro de 2026 só a com desconto — o preço cheio
    daqueles meses não foi republicado. Como a escada carrega o último valor
    para a frente, o preço de tabela continua sendo o de 29/5, que é o certo:
    o que mudou foi a subvenção, não o preço da empresa."""
    tabela, subvencionado = {}, {}
    for e, _p, d, _uf, mod, loc, v, desc in linhas:
        if e == "Petrobras" and loc == ponto and mod == MODALIDADE:
            (subvencionado if desc else tabela)[d] = v
    return sorted(tabela.items()), sorted(subvencionado.items())


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


def montar(ppi, escadas, ultima_tabela):
    """[(ponto, fim, tabela, subvenção, ppi, dif, %, % com subvenção, extrap.)]."""
    fora = []
    for ini, fim, valores in ppi:
        for ponto, coluna in PONTOS.items():
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


def escrever(linhas, ultima_tabela, revenda, hoje):
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

    escrever(tudo, ultima, revenda, hoje)
    print("gravado %s (%.0f KB)"
          % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
