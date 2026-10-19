#!/usr/bin/env python3
"""
Monta dados/defasagem-combustiveis.json — o assunto "A defasagem dos
combustíveis" do site.

Uso:
    ~/.venvs/dados-economicos/bin/python scripts/defasagem_combustiveis.py

Lê as planilhas de planilhas/, que são geradas pelos scripts de lá. Este aqui
não recalcula nada: ele só arruma para o navegador desenhar. A única exceção é
a defasagem do diesel, que ainda não tem planilha própria e sai aqui mesmo,
reusando as funções do planilhas/scripts/defasagem.py.

A ORDEM DO ARGUMENTO, que é a razão de ser do texto

  Primeiro quanto vale fechar a defasagem, depois quão provável é fechar. A
  premissa é que estimativa sem probabilidade não serve de nada: um efeito de
  0,7 ponto no IPCA só importa se houver chance real de ele aparecer.

O QUE AINDA FALTA

  Marcadores ⟨FALTA: …⟩ no texto apontam onde entram dados que ainda não
  chegaram: a série da Abicom e os efeitos indiretos do Relatório de Política
  Monetária do Banco Central. Procure por "FALTA" neste arquivo.
"""
import datetime
import io
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANILHAS = os.path.join(RAIZ, "planilhas")
sys.path.insert(0, os.path.join(PLANILHAS, "scripts"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texto_assunto as ta                                    # noqa: E402
SAIDA = os.path.join(RAIZ, "dados", "defasagem-combustiveis.json")
# A prosa mora aqui, fora do código, para que mudar uma palavra não exija
# mexer em Python. Ver scripts/texto_assunto.py para o formato.
ARQUIVO_TEXTO = "defasagem-combustiveis.md"

# A paleta da casa, a mesma do scripts/eleicoes.py. Os três primeiros passam na
# checagem de daltonismo com folga (ΔE 16,8 no pior par, deuteranopia), que é o
# que importa quando duas linhas dividem o mesmo gráfico.
AZUL, VERMELHO, VERDE, ROXO, LARANJA = (
    "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#F79646")

FONTE_ANP = "ANP e Petrobras. Elaboração: Follow the Money"

# As fontes que aparecem na margem das seções. Link quando existe página
# pública estável; só o rótulo quando é arquivo que se baixa.
F_ANP_PRODUCAO = {
    "rot": "ANP, produção e vendas de derivados",
    "url": "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-estatisticos",
}
F_ANP_DESEMBARACOS = {
    "rot": "ANP, Relatório de Desembaraços (Siscomex)",
    "url": "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-estatisticos",
}
F_SIDRA = {
    "rot": "IBGE, IPCA (SIDRA, tabela 7060)",
    "url": "https://sidra.ibge.gov.br/tabela/7060",
}
F_FGV = {
    "rot": "Francisco Pessoa Faria, “Impacto da defasagem da gasolina no "
           "IPCA e reflexos de sua subvenção nos resultados da Petrobras”, "
           "Blog do IBRE (FGV)",
    "url": "https://blogdoibre.fgv.br/",
}
F_PETROBRAS = {
    "rot": "Petrobras, tabelas de preços",
    "url": "https://precos.petrobras.com.br/",
}


def planilha(nome):
    from openpyxl import load_workbook
    return load_workbook(os.path.join(PLANILHAS, nome), data_only=True)


def linhas_da_aba(ws, cabecalho="mês"):
    """[(dict da linha)] de uma aba cujo cabeçalho pode não ser a linha 1.

    PARA na primeira linha em branco. Várias abas trazem um segundo bloco
    embaixo — a de sensibilidade ao corte, por exemplo, cuja primeira coluna
    também é um mês — e emendar os dois produz lixo silencioso."""
    grade = [list(r) for r in ws.iter_rows(values_only=True)]
    i = next(n for n, r in enumerate(grade)
             if r and str(r[0] or "").strip() == cabecalho)
    cab = [str(c).strip() if c is not None else "" for c in grade[i]]
    fora = []
    for r in grade[i + 1:]:
        if not r or r[0] is None:
            break
        fora.append(dict(zip(cab, r)))
    return fora


def serie(nome, cor, pares, **extra):
    d = {"nome": nome, "cor": cor,
         "dados": [[k, None if v is None else round(v, 4)] for k, v in pares]}
    d.update(extra)
    return d


def cel(texto, cor=None, forte=False):
    d = {"t": texto}
    if cor:
        d["cor"] = cor
    if forte:
        d["forte"] = True
    return d


def pct(v, casas=1, sinal=False):
    if v is None:
        return "—"
    s = ("%+." + str(casas) + "f") if sinal else ("%." + str(casas) + "f")
    return (s % v).replace(".", ",") + "%"


def br(v, casas=0):
    """Número no formato brasileiro: ponto no milhar, vírgula no decimal."""
    if v is None:
        return "—"
    s = format(v, ",." + str(casas) + "f")
    return s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def volume(m3):
    """Volume na unidade que lê melhor: mil m³ abaixo de um milhão, mi acima."""
    return ("%s mi de m³" % br(m3 / 1e6, 2) if m3 >= 1e6
            else "%s mil m³" % br(m3 / 1e3))


def dinheiro(milhoes):
    """R$ em milhões ou bilhões, conforme a ordem de grandeza."""
    return ("R$ %s bi" % br(milhoes / 1e3, 1) if abs(milhoes) >= 1e3
            else "R$ %s mi" % br(milhoes))


def cor_de(v):
    return None if v is None else (VERDE if v > 0 else VERMELHO)


# ─── a defasagem do diesel, que ainda não tem planilha ───────────────────────

def defasagem_diesel():
    """[(semana, defasagem % de tabela)] em Paulínia.

    NÃO ESTÁ EM USO. O gráfico que ela alimentava saiu da introdução, porque
    ali ele disputava espaço com as duas imagens da Abicom e usava outro
    denominador. Fica porque a conta é o que custou a fazer, e ela volta
    quando houver seção para ela.

    A planilha defasagem-gasolina.xlsx só cobre gasolina. A tabela de diesel da
    Petrobras só ficou acessível em 15/10/2026, quando a busca na biblioteca
    pública passou a descer para as subpastas; enquanto não há planilha de
    diesel, a conta sai aqui, com as mesmas funções da de lá."""
    import defasagem as df
    import precos_combustiveis as pc

    caminho = pc.pdf_de("Diesel")
    if not caminho:
        print("  sem tabela de diesel da Petrobras", file=sys.stderr)
        return []
    brutas = pc.ler_petrobras(caminho)
    escadas = {p: df.escadas_de(brutas, "Petrobras", p, produto="Diesel S-10")
               for p in df.PONTOS}
    escadas = {p: e for p, e in escadas.items() if e[0] or e[1]}
    if df.PRINCIPAL not in escadas:
        print("  diesel: %s não está na tabela" % df.PRINCIPAL, file=sys.stderr)
        return []
    ultima = max(d for tab, sub in escadas.values() for d, _v in tab + sub)
    ppi = df.ler_ppi(df.baixar_ppi(), "Diesel R$ semanal")
    return [(l[1].strftime("%Y-%m-%d"), 100 * l[6])
            for l in df.montar(ppi, escadas, ultima, df.PONTOS)
            if l[0] == df.PRINCIPAL]


# ─── o custo de sustentar o teto ────────────────────────────────────────────
#
# Vender abaixo da paridade é um preço-teto de fato, e um teto cobra de duas
# formas que não se parecem: receita não realizada sobre o que a empresa
# produz, e caixa sobre o que ela própria importa. A primeira uma estatal
# absorve por anos; a segunda dói. Qual das duas aparece diz quem está
# bancando o teto — e é isso que a planilha custo-do-teto.xlsx mede.
CHOQUE = "2026-03"


def custo_do_teto(rotulo, desde=CHOQUE):
    """[dict da linha mensal] de um produto, desde o mês do choque."""
    ws = planilha("custo-do-teto.xlsx")["Custo do teto — " + rotulo]
    return [l for l in linhas_da_aba(ws) if str(l["mês"]) >= desde]


def soma_do_teto(rotulo, desde=CHOQUE):
    """(defasagem média R$/l, volume m³, importação própria m³, oportunidade
    R$ mi, caixa bruto R$ mi)."""
    linhas = custo_do_teto(rotulo, desde)
    n = len(linhas)
    return (sum(l["defasagem R$/l"] for l in linhas) / n,
            sum(l["volume Petrobras (m³)"] for l in linhas),
            sum(l["importação própria (m³)"] for l in linhas),
            sum(l["custo de oportunidade (R$ mi)"] for l in linhas),
            sum(l["caixa, bruto (R$ mi)"] for l in linhas))


def importacao_propria(arq, desde="2025-01"):
    """[(mês, mil m³)] que a Petrobras importou em nome próprio."""
    ws = planilha(arq)["Importação por agente"]
    return [(str(l["mês"]), (l["Petrobras"] or 0) / 1000)
            for l in linhas_da_aba(ws) if str(l["mês"]) >= desde]


# ─── seção 1: o que é defasagem ──────────────────────────────────────────────


# ─── a composição do preço na bomba ─────────────────────────────────────────
#
# Quatro faixas, e não cinco: os dois tributos entram somados. Não foi escolha
# de gosto. Cinco cores encostadas umas nas outras não passam na checagem de
# daltonismo — na paleta da casa, verde e laranja ficam com ΔE 3,6 em
# deuteranopia, o que para quem não separa vermelho de verde é a mesma cor. O
# arranjo abaixo passa nos dois temas, e juntar federais com estaduais num
# bloco "Tributos" ainda lê melhor para quem não é do ramo.
COMPOSICAO = [
    ("produto", "#2a78d6"),      # gasolina A ou diesel A: a fatia do produtor
    ("bio", "#1baf7a"),          # etanol anidro ou biodiesel
    ("Tributos", "#6250d6"),
    ("Margem de distribuição e revenda", "#C0504D"),
]
# A ANP publica a composição por REGIÃO, nunca por estado. São três fontes
# diferentes para a mesma conta, e a que vale é a do painel: semanal, por
# região, desde 2021 e atual. As outras duas ou não têm região (a semanal em
# PDF) ou estão paradas em março de 2026 (as planilhas mensais). O acervo do
# painel é extraído à mão pelo planilhas/scripts/composicao_painel.py.
REGIOES = ["BRASIL", "NORTE", "NORDESTE", "SUDESTE", "SUL", "CENTRO-OESTE"]
NOME_REGIAO = {"BRASIL": "Brasil", "NORTE": "Norte", "NORDESTE": "Nordeste",
               "SUDESTE": "Sudeste", "SUL": "Sul", "CENTRO-OESTE": "Centro-Oeste"}
# (produto no acervo, faixa do produtor, faixa do biocombustível, rótulo)
PRODUTOS_COMPOSICAO = [
    ("GASOLINA", "Gasolina A", "Etanol Anidro", "da gasolina"),
    ("DIESEL S10", "Diesel A", "Biodiesel", "do diesel"),
]
TRIBUTOS = ("Tributos Federais", "Tributo Estadual")
MARGEM = "Margem Distribuição + Revenda"
MES_CURTO = ("jan fev mar abr mai jun jul ago set out nov dez").split()


def composicao(produto, meses=12):
    """{local: [(mês, {parcela: R$/l})]} nos últimos `meses` do acervo.

    A fonte é semanal; aqui vira média mensal, que é o que cabe num gráfico
    de doze barras sem virar serrote."""
    import csv
    caminho = os.path.join(PLANILHAS, "dados", "anp-composicao-painel.csv")
    semanas = {}
    with io.open(caminho, encoding="utf-8") as f:
        for l in csv.DictReader(f):
            if l["produto"] != produto:
                continue
            (semanas.setdefault(l["local"], {})
                    .setdefault(l["data"][:7], {})
                    .setdefault(l["parcela"], []).append(float(l["valor"])))
    fora = {}
    for local, porMes in semanas.items():
        ms = sorted(porMes)[-meses:]
        fora[local] = [(m, {k: sum(v) / len(v) for k, v in porMes[m].items()})
                       for m in ms]
    return fora


def grafico_composicao(produto, nome_produto, bio, rotulo):
    dados = composicao(produto)
    rotulos = {"produto": nome_produto, "bio": bio}
    variantes = []
    for reg in REGIOES:
        if not dados.get(reg):
            continue
        meses = [m for m, _ in dados[reg]]
        # Eixo de categorias, e não de tempo: a ANP pula meses, e num eixo
        # mensal cada mês que falta vira um buraco com cara de defeito. Cada
        # variante leva o seu, porque o Brasil vai mais longe que as regiões.
        categorias = [MES_CURTO[int(m[5:]) - 1] + "/" + m[2:4] for m in meses]
        series = []
        for faixa, cor in COMPOSICAO:
            pares = []
            for i, (_mes, itens) in enumerate(dados[reg]):
                if faixa == "Tributos":
                    v = sum(itens.get(k) or 0 for k in TRIBUTOS)
                elif faixa == "produto":
                    v = itens.get(nome_produto)
                elif faixa == "bio":
                    v = itens.get(bio)
                else:
                    v = itens.get(MARGEM)
                pares.append((str(i), v if v else None))
            series.append(serie(rotulos.get(faixa, faixa), cor, pares,
                                tipo="barra"))
        variantes.append({
            "rot": NOME_REGIAO.get(reg, reg),
            "categorias": categorias,
            "series": series,
        })
    return {
        "id": "composicao-" + slug(produto),
        "titulo": "Do que é feito o preço %s na bomba" % rotulo,
        "subtitulo": "Composição do litro, mês a mês, como a ANP publica",
        "unidade": "R$/l",
        "fonte": "ANP. Elaboração: Follow the Money",
        # sem "barra": 1 — a fresta entre as colunas é o que faz a pilha ser
        # lida como doze meses, e não como uma área empilhada
        "variantes": variantes,
        "nota": "**Tributos** soma os federais (PIS, Cofins e Cide) com o "
                "estadual (ICMS). A ANP publica os dois separados; aqui eles "
                "entram juntos porque cinco faixas encostadas não se "
                "distinguem para quem tem daltonismo.\n\n"
                "Fonte: o painel de composição de preços da ANP, que "
                "publica esta conta SEMANAL e por região. Aqui ela vira média "
                "mensal. As planilhas da ANP, que são a outra fonte com corte "
                "regional, estão paradas em março de 2026; o painel continua. "
                "Estado a ANP não publica em lugar nenhum.\n\n"
                "A margem é calculada por **resíduo**, ou seja, é o que sobra "
                "do preço na bomba depois das outras faixas. Erro em qualquer "
                "uma delas aparece ali.",
    }


def slug(t):
    import unicodedata
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def graficos_composicao():
    return [grafico_composicao(*a) for a in PRODUTOS_COMPOSICAO]


# ─── seção 2: probabilidade de fechar, gasolina ──────────────────────────────

def importado_por_ano():
    """(anos, {produto: [% importado]}) desde 2015."""
    fora, anos = {}, []
    for arq, nome in (("oferta-gasolina.xlsx", "Gasolina A"),
                      ("oferta-diesel.xlsx", "Diesel A")):
        ws = planilha(arq)["Balanço anual"]
        serie_ = []
        for l in linhas_da_aba(ws, "ano"):
            try:
                ano = int(l["ano"])
            except (TypeError, ValueError):
                continue
            if ano < 2015 or not l.get("oferta de gasolina A" if "gasolina"
                                       in arq else "oferta de diesel A"):
                continue
            oferta = l["oferta de gasolina A" if "gasolina" in arq
                       else "oferta de diesel A"]
            imp = l["importação (gasolina A)" if "gasolina" in arq
                    else "importação (diesel A)"]
            serie_.append((str(ano), 100.0 * float(imp) / float(oferta)))
        fora[nome] = serie_
        anos = [a for a, _ in serie_] if len(serie_) > len(anos) else anos
    return anos, fora


def perfil_mensal(arq, desde="2021-01"):
    """{coluna: [(mês, %)]} do perfil do fornecimento."""
    ws = planilha(arq)["Perfil mensal"]
    linhas = [l for l in linhas_da_aba(ws) if str(l["mês"]) >= desde]
    return {c: [(str(l["mês"]), l[c]) for l in linhas if l.get(c) is not None]
            for c in ("Petrobras", "Importações", "Tradings")}


def graficos_gasolina_probabilidade():
    anos, imp = importado_por_ano()
    perfil = perfil_mensal("oferta-gasolina.xlsx")
    g, d = soma_do_teto("gasolina"), soma_do_teto("diesel")
    return [
            {
                "id": "importado-por-ano",
                "titulo": "Quanto do combustível vem de fora",
                "subtitulo": "Importação como % da oferta nacional, por ano",
                "unidade": "%",
                "fonte": FONTE_ANP,
                "categorias": anos,
                # Linha, e não barra: no app a barra é sempre EMPILHADA,
                # porque serve a composição. Empilhar gasolina com diesel
                # somaria 14,4% com 22,7% e daria a entender que 37% do
                # combustível do país é importado, o que é falso — são dois
                # denominadores diferentes.
                "series": [
                    serie("Gasolina A", AZUL,
                          [(str(i), v) for i, (_a, v) in enumerate(imp["Gasolina A"])],
                          largura=3),
                    serie("Diesel A", VERMELHO,
                          [(str(i), v) for i, (_a, v) in enumerate(imp["Diesel A"])],
                          largura=3),
                ],
                "nota": "Cada linha é a importação daquele combustível "
                        "dividida pela oferta dele (produção nacional mais "
                        "importação menos exportação). São denominadores "
                        "diferentes: **não se somam**.\n\n"
                        "2026 cobre oito meses, de janeiro a agosto.",
            },
            {
                "id": "perfil-gasolina",
                "titulo": "Quem fornece a gasolina do Brasil",
                "subtitulo": "% do volume, em janela de 12 meses",
                "unidade": "%",
                "fonte": FONTE_ANP,
                "series": [
                    serie("Petrobras", AZUL, perfil["Petrobras"]),
                    serie("Importações", VERMELHO, perfil["Importações"]),
                    serie("Tradings", VERDE, perfil["Tradings"]),
                ],
                "nota": "No formato da tabela T.1 do artigo de Francisco "
                        "Pessoa Faria no Blog do IBRE: a linha da Petrobras "
                        "inclui o que a própria empresa importa.",
            },
            {
                "id": "quem-paga-o-teto",
                "titulo": "O que custa vender abaixo da paridade",
                "subtitulo": "De março a agosto de 2026, os dois produtos "
                             "lado a lado",
                "tipo": "tabela",
                "fonte": FONTE_ANP,
                "colunas": [{"rot": ""}, {"rot": "Gasolina", "num": True},
                            {"rot": "Diesel", "num": True}],
                "linhas": [
                    [cel("Defasagem média"),
                     cel("R$ %s/l" % br(g[0], 2)), cel("R$ %s/l" % br(d[0], 2))],
                    [cel("Volume que a Petrobras forneceu"),
                     cel(volume(g[1])), cel(volume(d[1]))],
                    [cel("Do qual ela mesma importou"),
                     cel(volume(g[2])), cel(volume(d[2]))],
                    [cel("Receita que deixou na mesa", forte=True),
                     cel(dinheiro(g[3]), VERMELHO, True),
                     cel(dinheiro(d[3]), VERMELHO, True)],
                    [cel("Prejuízo de caixa na importação", forte=True),
                     cel(dinheiro(g[4]), VERMELHO, True),
                     cel(dinheiro(d[4]), VERMELHO, True)],
                    [cel("Uma coisa dividida pela outra"),
                     cel("%s×" % br(g[3] / g[4] if g[4] else 0)),
                     cel("%s×" % br(d[3] / d[4] if d[4] else 0))],
                ],
                "nota": "Um teto de preço cobra de duas formas. A **receita "
                        "deixada na mesa** é a defasagem sobre cada litro que "
                        "a Petrobras produz e vende aqui: não entra dinheiro, "
                        "mas também não sai, e uma estatal absorve isso por "
                        "anos. O **prejuízo de caixa** é a defasagem sobre o "
                        "que ela própria importou, comprando perto da "
                        "paridade e vendendo pela tabela — esse sai do "
                        "bolso.\n\n"
                        "Na gasolina a segunda conta é desprezível diante da "
                        "primeira. No diesel, não.\n\n"
                        "A receita deixada na mesa é **teto, não estimativa**: "
                        "supõe que ela venderia o mesmo volume ao preço de "
                        "paridade, e não venderia — a demanda cairia. Serve "
                        "para comparar os dois produtos, não como lucro "
                        "perdido.",
            },
            {
                "id": "importacao-propria",
                "titulo": "Quando a Petrobras importa por conta própria",
                "subtitulo": "Desembaraços em nome dela, em mil m³ por mês",
                "unidade": "mil m³",
                "fonte": FONTE_ANP,
                "series": [
                    serie("Diesel A", LARANJA,
                          importacao_propria("oferta-diesel.xlsx")),
                    serie("Gasolina A", AZUL,
                          importacao_propria("oferta-gasolina.xlsx")),
                ],
                "nota": "É o teste do argumento. Se o teto fosse "
                        "insustentável, veríamos a Petrobras importando no "
                        "vermelho para cobrir o mercado.\n\n"
                        "Na gasolina ela importa quando compensa, e só: "
                        "297 mil m³ em dezembro de 2025, com a tabela dela "
                        "ainda acima da paridade, e **48 metros cúbicos** em "
                        "todo o trecho de março a junho de 2026, quando a "
                        "defasagem estava aberta. Nesses meses quem trouxe "
                        "gasolina foram distribuidores e tradings. No diesel ela zerou em abril, maio e "
                        "junho e voltou com força em julho e agosto, já com a "
                        "subvenção em vigor para dividir a conta.",
            },
    ]


# ─── seção 3: probabilidade de fechar, diesel ────────────────────────────────

def graficos_diesel_probabilidade():
    perfil = perfil_mensal("oferta-diesel.xlsx")
    mensal = planilha("oferta-diesel.xlsx")["Perfil mensal"]
    pm = {str(l["mês"]): l for l in linhas_da_aba(mensal)}

    def linha_mes(m, rot, forte=False):
        l = pm.get(m)
        if not l:
            return None
        return [cel(rot, forte=forte),
                cel(pct(l["Petrobras"]), AZUL),
                cel(pct(l["Importações"]), VERMELHO),
                cel(pct(l["Tradings"]), VERDE)]

    comparacao = [x for x in (linha_mes("2026-04", "Abril de 2026"),
                              linha_mes("2026-08", "Agosto de 2026", True))
                  if x]

    return [
            {
                "id": "perfil-diesel",
                "titulo": "O importador sai e a Petrobras cobre",
                "subtitulo": "Fornecimento de diesel, % do volume, em janela "
                             "de 12 meses",
                "unidade": "%",
                "fonte": FONTE_ANP,
                "series": [
                    serie("Petrobras", AZUL, perfil["Petrobras"]),
                    serie("Importações", VERMELHO, perfil["Importações"]),
                    serie("Tradings", VERDE, perfil["Tradings"]),
                ],
                "nota": "A janela de 12 meses suaviza sazonalidade e por isso "
                        "atrasa a virada. No mês puro o movimento é mais "
                        "brusco: as tradings vão de 14,7% em abril de 2026 a "
                        "3,8% em agosto.",
            },
            {
                "id": "virada-diesel",
                "titulo": "Quatro meses de defasagem aberta",
                "subtitulo": "Fornecimento de diesel no mês, sem janela móvel",
                "tipo": "tabela",
                "fonte": FONTE_ANP,
                "colunas": [{"rot": "Mês"}, {"rot": "Petrobras", "num": True},
                            {"rot": "Importações", "num": True},
                            {"rot": "Tradings", "num": True}],
                "linhas": comparacao,
                "nota": "É a mesma fonte do gráfico acima, no mês puro em vez "
                        "da janela de 12 meses.",
            },
            {
                "id": "custo-fiscal",
                "titulo": "O que a subvenção custa",
                "subtitulo": "Créditos extraordinários abertos em 2026, "
                             "em R$ bilhões",
                "tipo": "tabela",
                "fonte": "Medidas provisórias e portaria do Ministério da "
                         "Fazenda. Elaboração: Follow the Money",
                "colunas": [{"rot": "Medida"}, {"rot": "Valor", "num": True},
                            {"rot": "Destino"}],
                "linhas": [
                    [cel("MP 1.388"), cel("R$ 3,15 bi"),
                     cel("R$ 2,55 bi para diesel rodoviário")],
                    [cel("MP 1.389"), cel("R$ 6,60 bi"),
                     cel("compromissos das MPs 1.358 e 1.363")],
                    [cel("MP 1.395", forte=True), cel("R$ 7,52 bi"),
                     cel("R$ 6,17 bi para diesel rodoviário")],
                    [cel("Portaria de 13/10"), cel("R$ 1,60 bi"),
                     cel("+R$ 1,40/l no diesel importado, 30 dias")],
                ],
                "nota": "Some pouco mais de R$ 17 bilhões, dos quais perto de "
                        "R$ 9 bilhões para diesel rodoviário.\n\n"
                        "Compare com a nossa conta da planilha de subvenção: "
                        "se a subvenção alcançasse **todo** o diesel que a "
                        "Petrobras produz, só ela receberia R$ 14 bilhões em "
                        "três meses. Não cabe. Logo a subvenção não é paga em "
                        "cada litro, e a linha de ganho daquela planilha é "
                        "teto, não pagamento.",
            },
    ]


# ─── seção 4: estimativa, gasolina ───────────────────────────────────────────

def graficos_gasolina_estimativa():
    wb = planilha("ipca-defasagem.xlsx")
    modelo = linhas_da_aba(wb["Modelo mensal"])
    nivel = [(str(l["mês"]), l["nível represado (p.p.)"]) for l in modelo
             if l.get("nível represado (p.p.)") is not None]

    desde = linhas_da_aba(wb["IPCA 12m desde o choque"])
    # Começa em 2024: antes de março de 2026 as duas linhas são a mesma por
    # construção, e arrastar a série inteira esconde a divergência num canto.
    obs = [(str(l["mês"]), l["IPCA 12m observado %"]) for l in desde
           if l.get("IPCA 12m observado %") is not None and str(l["mês"]) >= "2024-01"]
    cf = [(str(l["mês"]), l["contrafactual contábil %"]) for l in desde
          if l.get("contrafactual contábil %") is not None and str(l["mês"]) >= "2024-01"]

    # a réplica da T.2: a aba traz o bloco depois da tabela de pesos
    grade = [list(r) for r in wb["Praças e pesos"].iter_rows(values_only=True)]
    i = next((n for n, r in enumerate(grade)
              if r and str(r[0] or "").strip() == "praça"
              and any("observada" in str(c or "") for c in r)), None)
    t2 = []
    if i is not None:
        for r in grade[i + 1:]:
            if not r or r[0] is None:
                break
            nome, observada, nosso, dele = r[0], r[1], r[5], r[6]
            t2.append([cel(str(nome), forte=(nome == "São Paulo")),
                       cel(pct(observada, 1) if observada is not None else "—"),
                       cel("%.3f" % nosso if nosso is not None else "—"),
                       cel("%.3f" % dele if dele is not None else "—")])

    ace = linhas_da_aba(planilha("defasagem-gasolina.xlsx")["Acelen vs Petrobras"],
                        "semana (fim)")
    ace_pet = [(l["semana (fim)"].strftime("%Y-%m-%d"),
                100 * l["defasagem Petrobras %"]) for l in ace
               if l.get("defasagem Petrobras %") is not None]
    ace_ace = [(l["semana (fim)"].strftime("%Y-%m-%d"),
                100 * l["defasagem Acelen %"]) for l in ace
               if l.get("defasagem Acelen %") is not None]

    return [
            {
                "id": "nivel-represado",
                "titulo": "Quanto do IPCA está represado",
                "subtitulo": "Pontos percentuais do nível do índice, pela "
                             "conta contábil",
                "unidade": "p.p.",
                "fonte": "ANP, Petrobras e IBGE. Elaboração: Follow the Money",
                "series": [serie("Nível represado", AZUL, nivel)],
                "nota": "Positivo quer dizer que a Petrobras está abaixo da "
                        "paridade e o índice está sendo segurado. Negativo, o "
                        "contrário.\n\n"
                        "É **nível**, não taxa: defasagem constante não muda a "
                        "inflação em 12 meses, porque já está nos dois pontos "
                        "da comparação. O que mexe no acumulado é a mudança.",
            },
            {
                "id": "ipca-12m",
                "titulo": "O IPCA em 12 meses, com e sem a defasagem",
                "subtitulo": "Contrafactual contado a partir de março de 2026, "
                             "quando a guerra abriu a defasagem",
                "unidade": "%",
                "fonte": "IBGE, ANP e Petrobras. Elaboração: Follow the Money",
                # O contrafactual vem PRIMEIRO na lista porque o app desenha
                # na ordem e a última fica por cima: assim a linha observada,
                # que é o dado de verdade, fica visível no trecho em que as
                # duas coincidem.
                "series": [
                    serie("Sem a defasagem", VERMELHO, cf),
                    serie("Observado", AZUL, obs),
                ],
                "nota": "As duas linhas são a mesma coisa até fevereiro de "
                        "2026, e isso é por construção: os meses anteriores ao "
                        "corte entram com o IPCA observado nos dois cenários. "
                        "O que interessa é a abertura a partir de março.\n\n"
                        "A data vem da guerra, não do gráfico. O PPI de "
                        "Paulínia atravessa fevereiro parado entre R$ 2,46 e "
                        "R$ 2,60 e faz **+15,7%** na semana encerrada em 6 de "
                        "março, chegando a R$ 4,04 em 27 de março.",
            },
            {
                "id": "replica-t2",
                "titulo": "A conta da FGV, refeita",
                "subtitulo": "Impacto de cada praça no IPCA do Brasil, em "
                             "pontos percentuais, no bimestre março-abril de 2026",
                "tipo": "tabela",
                "fonte": "IBGE. Elaboração: Follow the Money, replicando a "
                         "tabela T.2 de Francisco Pessoa Faria (Blog do IBRE)",
                "colunas": [{"rot": "Praça"},
                            {"rot": "Variação observada", "num": True},
                            {"rot": "Impacto, nossa conta", "num": True},
                            {"rot": "Impacto, publicado", "num": True}],
                "linhas": t2,
                "nota": "As duas últimas colunas são a mesma conta, feita duas "
                        "vezes: a nossa, a partir do SIDRA, e a que o autor "
                        "publicou. Salvador é a referência e por isso não tem "
                        "impacto.",
            },
            {
                "id": "acelen-petrobras",
                "titulo": "Duas empresas, duas políticas de preço",
                "subtitulo": "Defasagem contra o PPI do próprio ponto de "
                             "entrega, em %",
                "unidade": "%",
                "fonte": FONTE_ANP,
                "diario": True,
                "buracoMax": 10,          # semanal em eixo diário, como acima
                "series": [
                    serie("Acelen, em Candeias (BA)", VERDE, ace_ace),
                    serie("Petrobras, em Paulínia (SP)", AZUL, ace_pet),
                ],
                "nota": "Cada uma contra o PPI do lugar dela: Aratu para a "
                        "Acelen, Paulínia para a Petrobras. Preço de tabela, "
                        "sem desconto de subvenção.\n\n"
                        "É o par de gráficos G.3 e G.4 do artigo da FGV, em "
                        "série semanal no lugar de mensal.",
            },
    ]


# ─── seção 5: estimativa, diesel ─────────────────────────────────────────────

# ─── seção 6: o que monitorar ────────────────────────────────────────────────

def ultima_data(secoes):
    """A data mais recente que aparece em qualquer série, em ISO."""
    datas = [k for s in secoes for g in s["graficos"]
             for se in g.get("series", []) for k, _v in se["dados"]
             if re.match(r"^\d{4}-\d{2}(-\d{2})?$", str(k))]
    return max(datas) if datas else None


# Cada chave do arquivo de texto aponta para quem monta os gráficos daquela
# seção. Seção sem chave, ou com chave que não está aqui, fica só com texto —
# é assim que a introdução e a conclusão existem sem gráfico nenhum.
GRAFICOS = {
    "composicao": graficos_composicao,
    "gasolina-probabilidade": graficos_gasolina_probabilidade,
    "diesel-probabilidade": graficos_diesel_probabilidade,
    "gasolina-estimativa": graficos_gasolina_estimativa,
}


def montar(doc_texto, fonte_padrao=FONTE_ANP):
    """Junta a prosa do arquivo de texto com os gráficos que o código monta."""
    secoes = []
    for sec in doc_texto["secoes"]:
        montador = GRAFICOS.get(sec["chave"])
        secoes.append({
            "titulo": sec["titulo"],
            "texto": sec["texto"],
            "fontes": sec["fontes"],
            "figuras": sec["figuras"],
            "graficos": montador() if montador else [],
        })
    return secoes


def main():
    hoje = datetime.date.today()
    print("Lendo o texto…")
    dt = ta.ler(ARQUIVO_TEXTO)
    print("  %s: %d seções" % (dt["assunto"], len(dt["secoes"])))
    print("Lendo as planilhas…")
    secoes = montar(dt)
    doc = {
        "atualizado": hoje.isoformat(),
        # A referência é a data do dado mais fresco, não a de hoje, e vai em
        # ISO porque é o que o rotuloRef() do app.js sabe ler ("15/10/2026"
        # vira "undefined de nan" no rodapé).
        "referencia": ultima_data(secoes) or hoje.isoformat(),
        "fonte": FONTE_ANP,
        "assunto": dt["assunto"],
        # Este assunto é uma análise, não um painel: o leitor precisa ser
        # levado na ordem, e obrigá-lo a abrir capítulo é atrito. Ver
        # montarArtigo() no app.js.
        "formato": "artigo",
        "secoes": secoes,
    }
    faltas = sum(s["texto"].count("⟨") for s in secoes)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("  %d gráficos, %d figuras, %d marcadores de pendência"
          % (sum(len(s["graficos"]) for s in secoes),
             sum(len(s["figuras"]) for s in secoes), faltas))
    print("escrito: %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
