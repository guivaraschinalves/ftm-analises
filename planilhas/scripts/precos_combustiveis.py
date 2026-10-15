#!/usr/bin/env python3
"""
Monta dados/precos-combustiveis.xlsx — a planilha de trabalho com o preço dos
combustíveis cobrado das distribuidoras, e com a composição do preço na bomba.
Séries de origens diferentes:

  1. **ANP, produtores e importadores** — média ponderada semanal por região,
     de 2002 em diante, sem ICMS. É a série longa, e cobre o mercado inteiro
     (refinaria e importador), não só a Petrobras.
  2. **Petrobras, por UF** — o preço que a própria Petrobras publica, por
     ponto de entrega, de agosto de 2019 em diante. É a série curta, e é a
     única que desce ao estado.
  3. **Composição do preço ao consumidor** — refinaria, biocombustível,
     tributos e margens, da ANP com dados do MME. Semanal para o Brasil e
     mensal por região; quem faz a leitura é scripts/composicao_anp.py, que
     explica no cabeçalho por que são dois recortes e não um.

Uso:
    python3 scripts/precos_combustiveis.py

ESTE SCRIPT NÃO ENTRA NA ACTION e, diferente dos outros, **não é só
biblioteca padrão**: ele precisa de `openpyxl` (escrever .xlsx) e, para a
parte da Petrobras, de `pdfplumber` (ler o PDF). Num venv:

    python3 -m venv ~/.venvs/dados-economicos
    ~/.venvs/dados-economicos/bin/pip install openpyxl xlrd pdfplumber
    ~/.venvs/dados-economicos/bin/python scripts/precos_combustiveis.py

(esse venv já existe nesta máquina, com os três instalados.)

A saída é uma planilha de trabalho, não fonte de dado do site. Se um dia
virar gráfico, a conta vira um script de JSON como os outros.

AS FONTES

  - ANP, "Preços de produtores e importadores de derivados de petróleo e
    biodiesel": dois .xls na pasta dados/, baixados de
    gov.br/anp → Preços e Defesa da Concorrência → Preços. Um cobre 2002–2012
    e o outro 2013 em diante; emendam sem buraco. Semanal, por região
    (Norte, Nordeste, Centro-Oeste, Sul, Sudeste) e Brasil. **Sem ICMS.**
  - Petrobras, "Preços de Gasolina A sem tributos, à vista, por vigência":
    um PDF que ele sobe para dados/. Linhas são ponto de entrega (cidade/UF)
    × modalidade de venda; colunas são as datas de vigência. **R$/m³**, que
    aqui vira R$/litro para bater com a ANP.

O QUE OS NÚMEROS NÃO SÃO

  - A série da ANP não é "o preço da Petrobras": é a média ponderada de todos
    os produtores e importadores. Nos derivados em que a Petrobras é quase
    tudo, a diferença é pequena; não é zero.
  - O diesel **S-10 não existe antes de 2013** — não é lacuna de dado, o
    combustível não existia. Para série longa de diesel, a emenda é "Óleo
    Diesel" (2002–2012) com S-500 (2013 em diante), que é o que a linha
    "Diesel (geral → S-500)" faz.
  - Os preços de 1994 a 2001 **não entram**. Até janeiro de 2002 o preço era
    fixado pelo governo por portaria, não decidido pela empresa: é outro
    regime, e emendar na mesma linha misturaria duas coisas diferentes sem
    avisar.

MODALIDADE DE VENDA (parte da Petrobras). O mesmo produto, na mesma cidade,
tem preço diferente conforme como é entregue: EXA (ex-ponto A, no duto dentro
da refinaria), LPA, LCT, LPC, ETM, LTM, ETT, ETD, LPD. **A média por estado
usa uma modalidade só**, a EXA, e não a média de todas: a composição de
modalidades muda ao longo do tempo (ponto de entrega que some, modalidade que
entra), e média sobre composição que muda gera degrau que não é preço. A
planilha traz as outras modalidades numa aba à parte, para conferência.

O DESCONTO DA MP 1.358. Entre 29/5/2026 e 9/9/2026 houve subvenção de
R$ 0,44/litro na gasolina A, e a tabela da Petrobras traz, nessas vigências,
duas colunas: com e sem o desconto. A série principal usa o preço **sem**
desconto (é o preço da empresa); o com desconto vai numa coluna ao lado, que
é o que a distribuidora de fato pagou.
"""
import csv
import datetime
import glob
import json
import os
import sys

import composicao_anp
import precos_revenda

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DADOS = os.path.join(RAIZ, "dados")
SAIDA = os.path.join(RAIZ, "precos-combustiveis.xlsx")

ANP_ANTIGO = "precos-ponderados-semanais-2002-2012.xls"
ANP_NOVO = "precos-medios-ponderados-semanais-2013.xls"
ANP_URL = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
           "precos/ppidp/%s")

REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sul", "Sudeste", "Brasil"]

# rótulo na planilha → nomes do produto nos dois arquivos da ANP, na ordem
PRODUTOS = [
    ("Gasolina A", ["Gasolina A (R$/litro)", "Gasolina A Comum (R$/litro)"]),
    ("Diesel S-10", ["Óleo Diesel S-10 (R$/litro)"]),
    ("Diesel (geral → S-500)", ["Óleo Diesel (R$/litro)", "Óleo Diesel S-500 (R$/litro)"]),
]

# a modalidade de venda que serve de referência na média por estado
MODALIDADE_BASE = "EXA"


# --------------------------------------------------------------------- ANP

def baixar(url, destino):
    import urllib.request
    if os.path.exists(destino):
        return destino
    print("  baixando %s…" % os.path.basename(destino))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ftm-dados)"})
    with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as f:
        f.write(r.read())
    return destino


def ler_anp():
    """[(produto, data de início da semana, região, R$/litro)], das duas planilhas."""
    import xlrd
    bruto = {}
    for nome in (ANP_ANTIGO, ANP_NOVO):
        caminho = baixar(ANP_URL % nome, os.path.join(DADOS, nome))
        wb = xlrd.open_workbook(caminho)
        s = wb.sheet_by_index(0)
        dm = wb.datemode
        # linha 7 é o cabeçalho de região, 8 o subcabeçalho; o dado começa na 9
        for r in range(9, s.nrows):
            prod = str(s.cell_value(r, 0)).strip()
            if not prod:
                continue
            try:
                ini = datetime.date(*xlrd.xldate_as_tuple(s.cell_value(r, 1), dm)[:3])
            except Exception:         # linha de rodapé, nota de pé de página
                continue
            for k, col in enumerate(range(3, 9)):
                v = s.cell_value(r, col)
                if isinstance(v, float) and v > 0:    # "***" é mês sem dado
                    bruto.setdefault(prod, {}).setdefault(ini, {})[REGIOES[k]] = v
    linhas = []
    for rotulo, partes in PRODUTOS:
        junto = {}
        for p in partes:
            if p not in bruto:
                print("  AVISO: a ANP não trouxe %r — o layout mudou?" % p, file=sys.stderr)
            junto.update(bruto.get(p, {}))
        if not junto:
            raise SystemExit("nenhum dado para %s" % rotulo)
        dias = sorted(junto)
        buracos = [(dias[i], dias[i + 1]) for i in range(len(dias) - 1)
                   if (dias[i + 1] - dias[i]).days > 14]
        print("  %-24s %4d semanas, de %s a %s%s"
              % (rotulo, len(dias), dias[0], dias[-1],
                 "" if not buracos else "  BURACO: %s" % (buracos[:3],)))
        for d in dias:
            for reg in REGIOES:
                if reg in junto[d]:
                    linhas.append((rotulo, d, reg, round(junto[d][reg], 5)))
    return linhas


# ------------------------------------------------------- Petrobras e Acelen
#
# As duas publicam a mesma coisa, por obrigacao da Resolucao ANP 795/2019:
# o preco por ponto de entrega e modalidade de venda, em R$/m3, sem tributos.
# A Petrobras publica num PDF; a Acelen, numa tabela consultavel por produto e
# mes. O que sai daqui tem o mesmo formato nas duas:
#
#     (empresa, produto, vigencia, UF, modalidade, local, R$/litro, desconto)
#
# `desconto` e "" no preco cheio da empresa e traz o rotulo da medida
# provisoria na variante subsidiada ("MP 1.358", "MP 1.363 e MP 1.391"...).
import re                                              # noqa: E402
import time                                            # noqa: E402

UF = re.compile(r"\(([A-Z]{2})\)\s*$")
DATA = re.compile(r"(\d{2})[./](\d{2})[./](\d{4})")

ACELEN_URL = ("https://www.acelen.com.br/precos-as-distribuidoras/"
              "?produto=%d&ano=%d&mes=%d")
# o codigo de cada produto no formulario deles
ACELEN_PRODUTOS = {"Gasolina A": 5, "Diesel S-10": 7, "Diesel S-500": 6}
# a Acelen assumiu a refinaria de Mataripe em 1/12/2021, e a serie comeca ali
ACELEN_INICIO = (2021, 11)
CACHE = os.path.join(DADOS, ".cache-acelen")

# Desempate quando um ponto de entrega tem mais de uma modalidade com o mesmo
# numero de observacoes. A ordem vai do mais "cru" (no duto, dentro da
# refinaria) ao mais entregue, que e a ordem em que o frete entra no preco.
PRIORIDADE = ["EXA", "LPA", "LCT", "LPC", "ETT", "ETD", "LPD", "ETM", "LTM"]


def numero(cru):
    """'R$ 3.849,0000' ou '1.686,70' -> 3849.0 / 1686.7, em R$/m3."""
    cru = cru.replace("R$", "").strip()
    if not cru or cru in ("-", "--"):
        return None
    try:
        return float(cru.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def rotulo_desconto(cabecalho):
    """'Com descontosMP 1.363 e MP 1.391 24/09/2026' -> 'MP 1.363 e MP 1.391'."""
    if "descont" not in cabecalho.lower():
        return ""
    sem_data = DATA.sub("", cabecalho).strip()
    sem_data = re.sub(r"(?i)^com\s*descontos?", "", sem_data).strip(" .-")
    return re.sub(r"\s+", " ", sem_data) or "com desconto"


def colunas_de_data(cabecalho):
    """[(índice, data, rótulo do desconto)] a partir da linha de cabeçalho."""
    fora = []
    for i, c in enumerate(cabecalho[2:], start=2):
        c = (c or "").strip()
        m = DATA.search(c)
        if m:
            d, mes, a = m.groups()
            fora.append((i, datetime.date(int(a), int(mes), int(d)), rotulo_desconto(c)))
    return fora


# ------------------------------------------------------------- Petrobras (PDF)

# O PDF do diesel traz S500 e S10 no mesmo arquivo, uma faixa de páginas para
# cada, e o produto está no título da página. Os nomes aqui são os mesmos que
# a Acelen usa, para as duas empresas casarem na mesma tabela.
PRODUTO_NA_PAGINA = (("Diesel S500", "Diesel S-500"),
                     ("Diesel S10", "Diesel S-10"),
                     ("Gasolina A", "Gasolina A"))


def ler_petrobras(caminho, produto="Gasolina A"):
    """O PDF de tabelas da Petrobras. Uma tabela por página: as duas primeiras
    colunas são ponto de entrega e modalidade, as demais são vigências. As
    páginas de gasolina Premium e a da legenda ficam de fora.

    `produto` é só o palpite de partida: quando o título da página diz qual é,
    ele vence, que é o que permite ler o PDF de diesel, onde convivem S500 e
    S10."""
    import pdfplumber
    fora = []
    with pdfplumber.open(caminho) as pdf:
        for n, pagina in enumerate(pdf.pages, 1):
            topo = (pagina.extract_text() or "")[:200]
            if "Premium" in topo or "Modalidade de Venda" in topo:
                continue
            da_pagina = next((nome for marca, nome in PRODUTO_NA_PAGINA
                              if marca in topo), produto)
            tabela = pagina.extract_table()
            if not tabela or len(tabela) < 3:
                print("  página %d: sem tabela legível" % n, file=sys.stderr)
                continue
            colunas = colunas_de_data([(c or "").strip() for c in tabela[0]])
            for linha in tabela[1:]:
                local = (linha[0] or "").strip().replace("\n", " ")
                mod = (linha[1] or "").strip()
                uf = UF.search(local)
                if not uf or not mod:
                    continue
                for i, data, desc in colunas:
                    v = numero((linha[i] or "")) if i < len(linha) else None
                    if v:
                        fora.append(("Petrobras", da_pagina, data,
                                     uf.group(1), mod, local,
                                     round(v / 1000.0, 5), desc))
    return fora


# A biblioteca de documentos do site de preços é um Liferay, e responde à API
# pública dele. É de lá que vem o PDF quando não há nenhum em dados/:
#
#   .../api/jsonws/dlapp/get-file-entries/repository-id/1295200/folder-id/0
#
# ATENÇÃO: as tabelas correntes ficam nas SUBPASTAS (Diesel, Gasolina, GLP,
# Outros Produtos), não na raiz. Enquanto a busca não descia um nível, ela só
# via o que estava solto na raiz — gasolina até 1/9/2026 e, de diesel, só
# "Outros Diesel" de agosto de 2022 — e dava a impressão de que a biblioteca
# estava atrasada. Estava a busca.
PETRO_BIBLIOTECA = ("https://precos.petrobras.com.br/api/jsonws/dlapp/"
                    "get-file-entries/repository-id/1295200/folder-id/%d")
PETRO_SUBPASTAS = ("https://precos.petrobras.com.br/api/jsonws/dlapp/"
                   "get-folders/repository-id/1295200/parent-folder-id/%d")
# A raiz e a pasta "tabelas de preços". As tabelas correntes NÃO ficam aqui:
# ficam nas subpastas Diesel, Gasolina, GLP e Outros Produtos, e por isso a
# busca desce um nível. Enquanto ela não descia, o script só enxergava o que
# estava solto na raiz, que para o diesel era agosto de 2022.
PETRO_PASTAS = (0, 1296634)
PETRO_ARQUIVO = ("https://precos.petrobras.com.br/c/document_library/get_file"
                 "?uuid=%s&groupId=1295200")
NAVEGADOR = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                           " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"}


# Os dois PDF que interessam, por padrão de nome do arquivo na biblioteca.
PETRO_PRODUTOS = ("Gasolina", "Diesel S500")


def baixar_petrobras(padrao="Gasolina"):
    """Pega da biblioteca pública o PDF mais recente cujo nome case com
    `padrao`, grava em dados/ e devolve o caminho. None se não houver."""
    import urllib.request

    def json_de(url):
        req = urllib.request.Request(url, headers=NAVEGADOR)
        with urllib.request.urlopen(req, timeout=60) as r:
            saida = json.loads(r.read())
        return saida if isinstance(saida, list) else []

    pastas = list(PETRO_PASTAS)
    for pasta in PETRO_PASTAS:
        pastas += [int(f["folderId"]) for f in json_de(PETRO_SUBPASTAS % pasta)
                   if f.get("folderId")]
    melhor = None
    for pasta in dict.fromkeys(pastas):
        lista = json_de(PETRO_BIBLIOTECA % pasta)
        for f in lista:
            nome = f.get("fileName", "")
            if (f.get("extension", "").lower() == "pdf"
                    and re.search(padrao, nome, re.I)
                    and "Tabelas de Pre" in nome and " EN" not in nome):
                if melhor is None or f["modifiedDate"] > melhor["modifiedDate"]:
                    melhor = f
    if not melhor:
        return None
    destino = os.path.join(DADOS, melhor["fileName"].replace("ç", "c").replace("ã", "a"))
    if not os.path.exists(destino):
        print("  baixando %s…" % melhor["fileName"])
        req = urllib.request.Request(PETRO_ARQUIVO % melhor["uuid"], headers=NAVEGADOR)
        with urllib.request.urlopen(req, timeout=180) as r, open(destino, "wb") as f:
            f.write(r.read())
    return destino


# ---------------------------------------------------------------- Acelen (web)

def baixar_acelen(codigo, ano, mes):
    """O HTML de um mês, com cache em disco — a página é estável e a consulta
    é uma por mês e produto."""
    import urllib.request
    os.makedirs(CACHE, exist_ok=True)
    alvo = os.path.join(CACHE, "%d-%04d-%02d.html" % (codigo, ano, mes))
    vencido = (ano, mes) >= (datetime.date.today().year, datetime.date.today().month)
    if os.path.exists(alvo) and not vencido:
        return open(alvo, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(
        ACELEN_URL % (codigo, ano, mes),
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                               " (KHTML, like Gecko) Chrome/131.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html_ = r.read().decode("utf-8", "replace")
    open(alvo, "w", encoding="utf-8").write(html_)
    time.sleep(0.6)                                    # educação com o site deles
    return html_


def tabela_do_html(bruto):
    """A primeira <table> da página, como lista de listas de texto."""
    import html as _html
    achado = re.search(r"<table.*?</table>", bruto, re.S | re.I)
    if not achado:
        return []
    fora = []
    for linha in re.findall(r"<tr.*?</tr>", achado.group(0), re.S | re.I):
        celulas = [re.sub(r"\s+", " ",
                          _html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                   for c in re.findall(r"<t[hd].*?</t[hd]>", linha, re.S | re.I)]
        if celulas:
            fora.append(celulas)
    return fora


def pdf_de(padrao="Gasolina"):
    """O PDF mais recente da Petrobras para esse produto, baixando se faltar.

    Existe porque o nome do arquivo de diesel também casa com o padrão antigo
    "*abela*re*" ("Tabelas de Precos"), e quem pegava só o mais recente da
    pasta passou a pegar o diesel sem perceber."""
    import glob
    achados = [c for c in glob.glob(os.path.join(DADOS, "*.pdf"))
               if re.search(padrao, os.path.basename(c), re.I)]
    if achados:
        return sorted(achados, key=os.path.getmtime)[-1]
    return baixar_petrobras(padrao)


def ler_acelen(ate=None):
    """Varre produto × mês desde dez/2021. Devolve o mesmo formato do PDF."""
    hoje = ate or datetime.date.today()
    fora = []
    for nome, codigo in ACELEN_PRODUTOS.items():
        ano, mes = ACELEN_INICIO
        n0 = len(fora)
        while (ano, mes) <= (hoje.year, hoje.month):
            tabela = tabela_do_html(baixar_acelen(codigo, ano, mes))
            if len(tabela) >= 2:
                colunas = colunas_de_data(tabela[0])
                for linha in tabela[1:]:
                    if len(linha) < 3:
                        continue
                    local, mod = linha[0], linha[1]
                    uf = UF.search(local)
                    if not uf or not mod:
                        continue
                    for i, data, desc in colunas:
                        v = numero(linha[i]) if i < len(linha) else None
                        if v:
                            fora.append(("Acelen", nome, data, uf.group(1),
                                         mod, local, round(v / 1000.0, 5), desc))
            mes += 1
            if mes == 13:
                ano, mes = ano + 1, 1
        print("  %-14s %5d linhas" % (nome, len(fora) - n0))
    return fora


# --------------------------------------------- a média por estado, e a regra

def modalidade_de_cada_ponto(linhas):
    """{(empresa, produto, local): modalidade} — uma por ponto de entrega.

    A regra: a modalidade com mais observações naquele ponto, desempatada pela
    lista PRIORIDADE. Fixar uma por ponto é o que impede a média de pular
    quando a composição muda sem o preço ter mudado — e não dá para fixar a
    mesma para todo mundo, porque a Acelen praticamente só tem EXA em
    Candeias: os outros pontos dela são entrega marítima (ETM, LTM)."""
    contagem = {}
    for empresa, produto, _d, _uf, mod, local, _v, desc in linhas:
        if desc:
            continue
        contagem.setdefault((empresa, produto, local), {}).setdefault(mod, 0)
        contagem[(empresa, produto, local)][mod] += 1
    escolha = {}
    for chave, mods in contagem.items():
        escolha[chave] = max(mods, key=lambda m: (mods[m], -(PRIORIDADE.index(m)
                             if m in PRIORIDADE else len(PRIORIDADE))))
    return escolha


def media_por_uf(linhas):
    """{(empresa, produto, data, UF): (cheio, nº de pontos, com desconto, MP)}.

    Sai o preço de tabela e, quando existe, o com a subvenção aplicada —
    separados, porque são coisas diferentes: o primeiro é o preço da empresa,
    o segundo é o que a distribuidora pagou. Em 2026 a diferença chega a
    R$ 2,12/litro no diesel (MP 1.391), o que não é detalhe."""
    escolha = modalidade_de_cada_ponto(linhas)
    cheio, com_desc, mps = {}, {}, {}
    for empresa, produto, data, uf, mod, local, v, desc in linhas:
        if escolha.get((empresa, produto, local)) != mod:
            continue
        alvo = com_desc if desc else cheio
        alvo.setdefault((empresa, produto, data, uf), []).append(v)
        if desc:
            mps[(empresa, produto, data, uf)] = desc
    fora = {}
    for k in set(cheio) | set(com_desc):
        # durante a subvenção a Petrobras chegou a publicar SÓ a coluna com
        # desconto (é o caso de 1/8 e 1/9/2026 na tabela de setembro). A linha
        # sai mesmo assim, com o preço de tabela em branco — sumir seria pior.
        v, d = cheio.get(k), com_desc.get(k)
        fora[k] = (round(sum(v) / len(v), 5) if v else None, len(v or d),
                   round(sum(d) / len(d), 5) if d else None, mps.get(k, ""))
    return fora


# ----------------------------------------------------------------- planilha

def aba(wb, titulo, cabecalho, linhas, larguras=None, formato=None):
    from openpyxl.styles import Font, Alignment
    ws = wb.create_sheet(titulo)
    ws.append(cabecalho)
    for c in ws[1]:
        c.font = Font(bold=True)
        c.alignment = Alignment(vertical="center")
    for l in linhas:
        ws.append(list(l))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, larg in enumerate(larguras or [], start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = larg
    for col, fmt in (formato or {}).items():
        for linha in ws.iter_rows(min_row=2, min_col=col, max_col=col):
            linha[0].number_format = fmt
    return ws


def escrever(anp, refinarias, composicao, revenda, hoje):
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)

    leia = wb.create_sheet("LEIA-ME")
    for linha in [
        ["Preço dos combustíveis cobrado das distribuidoras"],
        ["Gerado em", hoje.strftime("%d/%m/%Y")],
        [],
        ["Aba", "O que é", "Fonte", "Unidade", "Período"],
        ["ANP semanal", "Média ponderada dos produtores e importadores, por região",
         "ANP, Preços de produtores e importadores", "R$/litro, sem ICMS",
         "2002 em diante, semanal"],
        ["ANP Brasil (largo)", "A mesma série, um produto por coluna",
         "idem", "R$/litro, sem ICMS", "idem"],
        ["Refinarias por UF", "Média dos pontos de entrega de cada estado",
         "Petrobras e Acelen, tabelas da Resolução ANP 795/2019",
         "R$/litro, sem tributos", "Petrobras ago/2019, Acelen dez/2021"],
        ["Refinarias detalhe", "O dado cru: ponto de entrega × modalidade × vigência",
         "idem", "R$/litro, sem tributos", "idem"],
        ["Composição semanal", "Quanto do preço na bomba é refinaria, biocombustível, "
                               "imposto e margem — só Brasil",
         "ANP, Síntese Semanal (dados do MME)", "R$/litro (GLP: R$/13kg)",
         "2023 em diante, semanal"],
        ["Composição regiões", "A mesma conta com corte regional, uma semana por mês",
         "ANP, Composição e estruturas de formação dos preços (dados do MME)",
         "R$/litro (GLP: R$/13kg)", "2018 em diante, mensal"],
        ["Composição (largo)", "As duas acima, um item por coluna",
         "idem", "idem", "idem"],
        ["Etanol vs gasolina", "Preço de BOMBA dos dois e a regra dos 70%, por UF, "
                               "região e Brasil",
         "ANP, Levantamento de Preços (pesquisa semanal em postos)",
         "R$/litro ao consumidor", "2004 em diante, semanal"],
        [],
        ["ATENÇÃO — as duas séries NÃO estão na mesma base tributária:"],
        ["ANP", "o próprio arquivo diz só '(Não inclui ICMS)': PIS/Cofins e CIDE "
                "estão DENTRO do preço."],
        ["Petrobras e Acelen", "as tabelas dizem 'sem tributos'."],
        ["", "Não dá para pôr as três no mesmo eixo sem descontar PIS/Cofins+CIDE "
             "da série da ANP primeiro."],
        [],
        ["Três coisas que o número não é:"],
        ["1", "A série da ANP não é o preço da Petrobras: é a média de todos os "
              "produtores e importadores."],
        ["2", "O diesel S-10 não existe antes de 2013 — o combustível não existia. "
              "A linha 'Diesel (geral → S-500)' é a emenda para série longa."],
        ["3", "1994 a 2001 não entra: até janeiro de 2002 o preço era fixado pelo "
              "governo por portaria, não decidido pela empresa."],
        [],
        ["A média por estado fixa UMA modalidade de venda por ponto de entrega: a "
         "mais frequente naquele ponto."],
        ["Misturar modalidades faria a média pular quando a composição muda, sem o "
         "preço ter mudado. E não dá para usar a mesma"],
        ["para todo mundo: a Acelen só tem EXA em Candeias; os outros pontos dela "
         "são entrega marítima (ETM, LTM)."],
        [],
        ["Houve subvenção em 2026 — R$ 0,44/litro na gasolina A (MP 1.358) e outras "
         "no diesel (MP 1.363, MP 1.391)."],
        ["A série usa o preço SEM desconto, que é o preço da empresa; a aba de "
         "detalhe traz as duas versões, com o rótulo da MP."],
        [],
        ["Petrobras e Acelen quase não se sobrepõem. A Acelen É a antiga RLAM: a "
         "Petrobras publicou Candeias (BA)"],
        ["até 1/9/2021 e parou — a Acelen começa em 1/12/2021, quando assumiu "
         "Mataripe. Não há mês com as duas na"],
        ["mesma cidade. E a Acelen tem uma refinaria só: o resto ela entrega por "
         "terminal marítimo (ETM, LTM), então"],
        ["o preço dela já carrega frete onde o da Petrobras, ex-ponto A, não carrega."],
        [],
        ["CÉLULA VAZIA NÃO É PREÇO REPETIDO. Um ponto de entrega some da tabela "
         "quando deixa de ser vendido ali."],
        ["Ao arrastar o último preço para a frente (step), ponha um limite — senão "
         "você compara um preço de 2021 com um de hoje."],
        [],
        ["SOBRE A COMPOSIÇÃO DO PREÇO"],
        ["Semanal só tem Brasil; por região só tem uma semana por mês. Não é "
         "metodologia diferente — a fonte é a mesma (o"],
        ["Relatório do Mercado de Derivados de Petróleo, do MME) —, é o que a ANP "
         "escolheu publicar em cada lugar."],
        ["O componente de refinaria é LIVRE DE TRIBUTOS: os federais e os estaduais "
         "são linhas à parte. A série de produtores"],
        ["das abas 'ANP semanal' e 'ANP Brasil (largo)' INCLUI PIS/Cofins e CIDE, "
         "então as duas não são comparáveis direto."],
        ["Na gasolina o componente não é um litro de gasolina A: é a parcela de "
         "gasolina A (70%) num litro de gasolina C —"],
        ["e o mesmo vale para o etanol anidro (30%) e para a mistura de biodiesel no "
         "diesel, cuja proporção mudou várias vezes."],
        ["A margem é BRUTA e sai por resíduo: é o que sobra do preço ao consumidor "
         "depois dos outros itens, então carrega"],
        ["frete, custo operacional e lucro, de distribuidora e de posto juntos. Em "
         "alguns meses a ANP a divide em duas"],
        ["(distribuição + transporte, e revenda); em outros publica uma só."],
        ["GLP está em R$ por botijão de 13 kg, não por litro."],
        ["O arquivo de setembro de 2020 saiu com a semana de referência de agosto, "
         "repetida; sem data confiável, ficou fora."],
    ]:
        leia.append(linha)
    from openpyxl.styles import Font
    leia["A1"].font = Font(bold=True, size=14)
    leia["A4"].font = leia["B4"].font = leia["C4"].font = Font(bold=True)
    leia["D4"].font = leia["E4"].font = Font(bold=True)
    leia["A10"].font = Font(bold=True)
    for col, larg in zip("ABCDE", (22, 62, 46, 22, 26)):
        leia.column_dimensions[col].width = larg

    aba(wb, "ANP semanal", ["produto", "semana", "região", "R$/litro"],
        [(p, d, r, v) for p, d, r, v in anp],
        larguras=[24, 12, 14, 11], formato={2: "DD/MM/YYYY", 4: "0.00000"})

    # o mesmo, em formato largo: uma linha por semana, um produto por coluna
    produtos = [p for p, _ in PRODUTOS]
    por_semana = {}
    for p, d, r, v in anp:
        if r == "Brasil":
            por_semana.setdefault(d, {})[p] = v
    aba(wb, "ANP Brasil (largo)", ["semana"] + produtos,
        [[d] + [por_semana[d].get(p) for p in produtos] for d in sorted(por_semana)],
        larguras=[12] + [22] * len(produtos),
        formato={**{1: "DD/MM/YYYY"},
                 **{i: "0.00000" for i in range(2, 2 + len(produtos))}})

    if refinarias:
        medias = media_por_uf(refinarias)
        aba(wb, "Refinarias por UF",
            ["empresa", "produto", "vigência", "UF", "R$/litro (tabela)",
             "R$/litro (com subvenção)", "medida provisória", "pontos de entrega"],
            [(e, p, d, uf, v, vd, mp, n)
             for (e, p, d, uf), (v, n, vd, mp) in sorted(medias.items())],
            larguras=[11, 14, 12, 6, 17, 22, 20, 18],
            formato={3: "DD/MM/YYYY", 5: "0.00000", 6: "0.00000"})
        escolha = modalidade_de_cada_ponto(refinarias)
        aba(wb, "Refinarias detalhe",
            ["empresa", "produto", "vigência", "UF", "modalidade", "ponto de entrega",
             "R$/litro", "desconto", "entra na média"],
            [(e, p, d, uf, mod, loc, v, desc or "",
              "sim" if (not desc and escolha.get((e, p, loc)) == mod) else "não")
             for e, p, d, uf, mod, loc, v, desc in sorted(refinarias)],
            larguras=[11, 14, 12, 6, 12, 28, 11, 22, 14],
            formato={3: "DD/MM/YYYY", 7: "0.00000"})

    if composicao:
        sem, reg = composicao
        aba(wb, "Composição semanal",
            ["produto", "semana", "item", "R$", "% do preço", "preço ao consumidor"],
            [(p, dia_iso(f), i, v, v / t if t else None, t)
             for p, f, i, v, t, _e in sorted(sem, key=lambda l: (l[0], l[1],
                                                                 ordem_item(l[2])))],
            larguras=[14, 12, 34, 11, 12, 20],
            formato={2: "DD/MM/YYYY", 4: "0.0000", 5: "0.0%", 6: "0.0000"})
        aba(wb, "Composição regiões",
            ["produto", "semana", "região", "item", "R$", "% do preço", "unidade",
             "mês da publicação"],
            [(p, dia_iso(f), r, i, v, pc, un, m)
             for p, m, _ini, f, r, i, v, pc, un, _a in
             sorted(reg, key=lambda l: (l[0], l[3],
                                        composicao_anp.REGIOES.index(l[4]),
                                        ordem_item(l[5])))],
            larguras=[14, 12, 14, 34, 11, 12, 11, 18],
            formato={2: "DD/MM/YYYY", 5: "0.0000", 6: "0.0%"})
        aba(wb, "Composição (largo)",
            ["recorte", "produto", "semana", "região"] + composicao_anp.ITENS
            + [composicao_anp.TOTAL],
            composicao_larga(sem, reg),
            larguras=[18, 14, 12, 14] + [20] * (len(composicao_anp.ITENS) + 1),
            formato={3: "DD/MM/YYYY",
                     **{i: "0.0000" for i in range(5, 6 + len(composicao_anp.ITENS))}})

    if revenda:
        aba(wb, "Etanol vs gasolina", precos_revenda.CABECALHO, revenda,
            larguras=[12, 12, 12, 14, 10, 14, 16, 17, 18, 10],
            formato={3: "0.000", 4: "0.000", 5: "0.0", 6: "0.0", 7: "0.0"})

    wb.save(SAIDA)
    return wb


def dia_iso(s):
    return datetime.date(*(int(x) for x in s.split("-")))


def ordem_item(item):
    """Os itens saem na ordem em que entram no preço, não em ordem alfabética."""
    todos = composicao_anp.ITENS + [composicao_anp.TOTAL]
    return (todos.index(item) if item in todos else len(todos), item)


def composicao_larga(sem, reg):
    """Uma linha por (recorte, produto, semana, região), um item por coluna."""
    linhas = {}
    for p, f, i, v, t, _e in sem:
        d = linhas.setdefault(("semanal (Brasil)", p, f, "Brasil"), {})
        d[i], d[composicao_anp.TOTAL] = v, t
    for p, _m, _ini, f, r, i, v, _pc, _un, _a in reg:
        linhas.setdefault(("mensal (regiões)", p, f, r), {})[i] = v
    colunas = composicao_anp.ITENS + [composicao_anp.TOTAL]
    ordem = composicao_anp.REGIOES
    return [[recorte, prod, dia_iso(fim), regiao] + [d.get(c) for c in colunas]
            for (recorte, prod, fim, regiao), d in
            sorted(linhas.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2],
                                                   ordem.index(kv[0][3])))]


def main():
    hoje = datetime.date.today()
    print("ANP, produtores e importadores…")
    anp = ler_anp()

    refinarias = []

    print("Acelen, preços às distribuidoras…")
    try:
        refinarias += ler_acelen(hoje)
    except Exception as e:                    # site fora do ar não derruba o resto
        print("  Acelen falhou: %s" % e, file=sys.stderr)

    print("Petrobras, da biblioteca pública…")
    caminhos = []
    for padrao in PETRO_PRODUTOS:
        try:
            achado = baixar_petrobras(padrao)
        except Exception as e:                # biblioteca fora não derruba o resto
            achado = None
            print("  biblioteca falhou (%s): %s" % (padrao, e), file=sys.stderr)
        if achado:
            caminhos.append(achado)
    # Mais um PDF que tenha chegado à mão em dados/. Os padrões se sobrepõem,
    # então a lista passa por dict.fromkeys para não ler o mesmo arquivo duas
    # vezes, e tudo é ordenado por data de modificação: as escadas são
    # dicionários por vigência, o último lido vence, e assim o arquivo mais
    # novo ganha, venha ele da biblioteca ou de fora.
    caminhos += glob.glob(os.path.join(DADOS, "*asolina*.pdf"))
    caminhos += glob.glob(os.path.join(DADOS, "*iesel*.pdf"))
    caminhos += glob.glob(os.path.join(DADOS, "*abela*re*.pdf"))
    caminhos = sorted(dict.fromkeys(os.path.realpath(c) for c in caminhos),
                      key=os.path.getmtime)
    for caminho in caminhos:
        lidas = ler_petrobras(caminho)
        refinarias += lidas
        print("  %-50s %5d linhas"
              % (os.path.basename(caminho)[:50], len(lidas)))
    if not caminhos:
        print("  nada encontrado — só a Acelen entra.", file=sys.stderr)

    if refinarias:
        por_empresa = {}
        for e, prod, d, uf, *_ in refinarias:
            a = por_empresa.setdefault((e, prod), [d, d, set()])
            a[0], a[1] = min(a[0], d), max(a[1], d)
            a[2].add(uf)
        for (e, prod), (d0, d1, ufs) in sorted(por_empresa.items()):
            print("  %-10s %-14s %s a %s, %2d UF" % (e, prod, d0, d1, len(ufs)))
        escolha = modalidade_de_cada_ponto(refinarias)
        mods = {}
        for (e, _p, _loc), m in escolha.items():
            mods.setdefault(e, {}).setdefault(m, 0)
            mods[e][m] += 1
        for e, c in sorted(mods.items()):
            print("  modalidade escolhida em %s: %s" % (e, dict(sorted(c.items()))))

    print("Composição do preço, semanal (Síntese da ANP)…")
    sem = composicao_anp.semanal()
    print("Composição do preço, por região (planilhas da ANP)…")
    reg = composicao_anp.por_regiao()
    for nome, linhas, i_sem in (("semanal", sem, 1), ("regiões", reg, 3)):
        por_prod = {}
        for l in linhas:
            a = por_prod.setdefault(l[0], [l[i_sem], l[i_sem], 0])
            a[0], a[1] = min(a[0], l[i_sem]), max(a[1], l[i_sem])
            a[2] += 1
        for p, (d0, d1, n) in sorted(por_prod.items()):
            print("  %-9s %-14s %5d linhas, de %s a %s" % (nome, p, n, d0, d1))
    for p in composicao_anp.conferir(sem, reg):
        print(p, file=sys.stderr)

    print("ANP, preço de bomba (etanol e gasolina)…")
    try:
        revenda = precos_revenda.serie()
        print("  %d linhas, de %s a %s"
              % (len(revenda), revenda[0][0], revenda[-1][0]))
    except Exception as e:                    # fonte pesada: não derruba o resto
        print("  Levantamento de Preços falhou: %s" % e, file=sys.stderr)
        revenda = []

    escrever(anp, refinarias, (sem, reg), revenda, hoje)
    print("gravado %s (%.0f KB)"
          % (os.path.relpath(SAIDA, RAIZ), os.path.getsize(SAIDA) / 1024))

    with open(os.path.join(DADOS, "anp-precos-produtor.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["produto", "semana", "regiao", "reais_por_litro"])
        w.writerows([(p, d.isoformat(), r, v) for p, d, r, v in anp])
    print("gravado dados/anp-precos-produtor.csv")


def inspecionar(caminho):
    """Mostra o que o pdfplumber vê, para calibrar o leitor."""
    import pdfplumber
    with pdfplumber.open(caminho) as pdf:
        print("%d páginas" % len(pdf.pages))
        for n, pagina in enumerate(pdf.pages[:3], 1):
            t = pagina.extract_table()
            print("\n== página %d: %s" % (n, (pagina.extract_text() or "")[:90].replace("\n", " | ")))
            if not t:
                print("   extract_table() devolveu nada")
                continue
            print("   %d linhas x %d colunas" % (len(t), max(len(l) for l in t)))
            for linha in t[:4]:
                print("   %s" % [str(c)[:16] for c in linha[:8]])


if __name__ == "__main__":
    if "--inspecionar" in sys.argv:
        alvo = [a for a in sys.argv[1:] if a.endswith(".pdf")]
        inspecionar(alvo[0] if alvo else
                    sorted(glob.glob(os.path.join(DADOS, "*.pdf")))[-1])
    else:
        main()
