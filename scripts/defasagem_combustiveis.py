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
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANILHAS = os.path.join(RAIZ, "planilhas")
sys.path.insert(0, os.path.join(PLANILHAS, "scripts"))
SAIDA = os.path.join(RAIZ, "dados", "defasagem-combustiveis.json")

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


def cor_de(v):
    return None if v is None else (VERDE if v > 0 else VERMELHO)


# ─── a defasagem do diesel, que ainda não tem planilha ───────────────────────

def defasagem_diesel():
    """[(semana, defasagem % de tabela)] em Paulínia, para o gráfico 1.

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


# ─── seção 1: o que é defasagem ──────────────────────────────────────────────

def secao_introducao():
    wb = planilha("defasagem-gasolina.xlsx")
    gas = [(l["semana (fim)"].strftime("%Y-%m-%d"), 100 * l["defasagem %"])
           for l in linhas_da_aba(wb["Defasagem Paulínia"], "semana (fim)")
           if l.get("defasagem %") is not None]
    die = defasagem_diesel()

    # O texto é dele, com as correções conferidas contra a tabela da
    # Petrobras: o denominador da Abicom, a subvenção dentro do -103% e a
    # fatia da REPLAN na produção nacional. Curto de propósito — parede de
    # texto afasta quem chegou pelo vídeo. O que é detalhe de método desceu
    # para a nota do gráfico, e o que é referência saiu para a margem.
    texto = (
        "Há tempos mostro no canal a defasagem de preços da Petrobras "
        "reportada pela Abicom. Muitos de vocês pediram uma análise do "
        "impacto no IPCA caso a empresa feche essa diferença.\n\n"
        "Os dados de 14 de outubro mostram o diesel em Paulínia a R$ 3,33 o "
        "litro contra um PPI de R$ 6,77, defasagem de **103% do preço "
        "cobrado**. Na gasolina, R$ 3,06 contra R$ 3,80, ou 24%. Paulínia é a "
        "maior refinaria do país: um quarto do diesel e um quinto da gasolina "
        "A que o Brasil produz.\n\n"
        "**PPI** é o custo estimado de importar o produto, com cotação "
        "internacional, câmbio, logística e, dependendo da metodologia, um "
        "prêmio de risco. Os preços são os cobrados das distribuidoras, antes "
        "de tributos, etanol anidro e margens.\n\n"
        "Dois alertas de leitura. A Abicom divide a defasagem pelo preço da "
        "Petrobras, não pelo PPI: contra o PPI o diesel é −51%, não −103%. E "
        "os R$ 3,33 já são o preço **com** a subvenção de R$ 2,12 por litro "
        "bancada pelo Tesouro. A tabela cheia é R$ 5,45; sem o subsídio a "
        "defasagem do diesel seria 24%, igual à da gasolina.\n\n"
        "Ou seja, boa parte do buraco não é política de preço da Petrobras, é "
        "subsídio. O que sobra vem da estratégia comercial que a empresa "
        "adotou em maio de 2023, quando abandonou a paridade estrita com o "
        "PPI.\n\n"
        "Antes de estimar o impacto, é preciso saber se ele tem chance de "
        "acontecer: **estimativa sem probabilidade não serve de nada**. Nas "
        "próximas seções, a estrutura do mercado, as diferenças entre "
        "regiões, a situação da Petrobras e o custo fiscal."
    )

    fontes = [
        {"rot": "Abicom, PPI de 14/10/2026",
         "url": "https://abicom.com.br/ppi/ppi-14-10-2026/"},
        {"rot": "Petrobras, tabelas de preços",
         "url": "https://precos.petrobras.com.br/"},
        {"rot": "ANP, preços de paridade de importação",
         "url": "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-de-paridade-de-importacao"},
        {"rot": "⟨FALTA: a fonte da mudança de política de 2023⟩"},
    ]

    g = {
        "id": "defasagem-semanal",
        "titulo": "A defasagem contra o preço de importação",
        "subtitulo": "Preço da Petrobras menos o PPI da ANP, em % do PPI, "
                     "em Paulínia. Negativo é vender abaixo da paridade",
        "unidade": "%",
        "fonte": FONTE_ANP,
        "diario": True,
        # A série é SEMANAL num eixo diário: dois pontos vizinhos ficam 7 dias
        # um do outro, e o padrão do app corta a linha em buraco maior que 6.
        # Sem isto o gráfico sai em cacos.
        "buracoMax": 10,
        "series": [serie("Gasolina A", AZUL, gas)],
        "nota": "Preço de tabela, sem a subvenção descontada. A modalidade é "
                "EXA, no duto dentro da refinaria, que é onde o PPI dos pontos "
                "interiores também chega.\n\n"
                "CUIDADO COM 2026. A defasagem parece encolher quando a "
                "subvenção entra — na gasolina em maio, no diesel em setembro "
                "—, mas o que subiu foi a tabela, não o preço que a "
                "distribuidora paga. A subvenção é paga ao produtor com a "
                "condição de ser descontada do preço: a empresa sobe a tabela "
                "e o comprador paga o mesmo. Medida pelo que a distribuidora "
                "desembolsa, a defasagem ficou **maior**, não menor.\n\n"
                "POR QUE NÃO BATE COM A ABICOM. Duas razões, e as duas são "
                "de método, não de dado. O denominador: aqui a defasagem é "
                "dividida pelo PPI, e a Abicom divide pelo preço da "
                "Petrobras, o que dá um número maior (−51% contra −103% no "
                "diesel em 14/10). E o PPI: cada casa calcula o seu, com "
                "porto, frete, custo de internação e dia de cotação "
                "diferentes. O daqui é o da ANP, estimado pela S&P Global, "
                "que é público e auditável.",
    }
    if die:
        g["series"].append(serie("Diesel S-10", VERMELHO, die))
    return {"titulo": "O que é defasagem, e por que ela importa",
            "texto": texto, "fontes": fontes, "graficos": [g]}


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


def secao_gasolina_probabilidade():
    anos, imp = importado_por_ano()
    perfil = perfil_mensal("oferta-gasolina.xlsx")
    texto = (
        "Na gasolina a probabilidade de a defasagem fechar é baixa, e o "
        "motivo é estrutural: o Brasil depende pouco de importação. Em 2026, "
        "até agosto, **14,4% da gasolina A** veio de fora. No diesel foram "
        "22,7%, e em 2025, 26,8%.\n\n"
        "Isso muda quem manda no preço. Com pouca importação, o importador que "
        "desiste de trazer gasolina não cria buraco de abastecimento: a "
        "Petrobras absorve, e ela tem de onde. A participação dela oscila "
        "entre 70% e 80% do fornecimento e sobe justamente quando o "
        "importador sai.\n\n"
        "⟨FALTA: quanto do petróleo que extrai a Petrobras exporta. É a outra "
        "perna do argumento: com o petróleo caro, o lucro da exportação de cru "
        "financia o prejuízo do refino vendido abaixo da paridade. Esse dado "
        "não está nas nossas planilhas, que cobrem derivados e não petróleo "
        "bruto — precisa vir da ANP ou do release trimestral da empresa.⟩"
    )
    return {
        "titulo": "Probabilidade de fechar: gasolina",
        "texto": texto,
        "fontes": [F_ANP_PRODUCAO, F_ANP_DESEMBARACOS, F_FGV,
                   {"rot": "⟨FALTA: exportação de petróleo da Petrobras⟩"}],
        "graficos": [
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
        ],
    }


# ─── seção 3: probabilidade de fechar, diesel ────────────────────────────────

def secao_diesel_probabilidade():
    perfil = perfil_mensal("oferta-diesel.xlsx")
    mensal = planilha("oferta-diesel.xlsx")["Perfil mensal"]
    pm = {str(l["mês"]): l for l in linhas_da_aba(mensal)}

    texto = (
        "No diesel a história é outra, e é aqui que mora o problema. O país "
        "importa perto de um quarto do que consome, e isso dá ao importador um "
        "poder que ele não tem na gasolina: **se o preço interno não compensa, "
        "ele simplesmente para de trazer**.\n\n"
        "O mecanismo não é teoria. Entre abril e agosto de 2026, com a "
        "defasagem aberta, a participação das importações no fornecimento de "
        "diesel caiu de 18,7% para 6,8%, e a das tradings de 14,7% para 3,8%. "
        "No mesmo intervalo a Petrobras subiu de 68,4% para 83,2%. Quem saiu "
        "foi substituído por ela, vendendo abaixo da paridade.\n\n"
        "É isso que o governo responde quando edita uma subvenção. Vale aqui a "
        "régua do Druckenmiller: julgue uma intervenção pelo que ela está "
        "respondendo. A subvenção não responde à inflação, responde ao risco "
        "de a Petrobras ter de cobrir sozinha o que o importador deixou de "
        "trazer.\n\n"
        "A métrica oficial de desabastecimento é **oferta confirmada contra "
        "demanda projetada do mês**, em mil m³. Para outubro de 2026 o MME "
        "declarou demanda de 3.950 e oferta confirmada de 4.184, com 1.126 "
        "vindo de importação. Repare no que essa métrica não mede: estoque. "
        "Não existe painel público de dias de cobertura, e é justamente o "
        "estoque que a Abicom aponta como frágil — segundo ela, as "
        "importações de setembro cobriram o consumo do mês mas não "
        "recompuseram o que havia sido queimado.\n\n"
        "⟨VERIFICAR antes de publicar: a ameaça americana de cortar exportação "
        "de diesel e os 92% de origem EUA citados na sala de monitoramento de "
        "agosto; a declaração sobre tradings que não aderem à subvenção por "
        "causa da burocracia e do ressarcimento em 30 dias; a formulação exata "
        "da frase do Druckenmiller. Nenhuma das três tem fonte confirmada "
        "ainda.⟩"
    )

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

    return {
        "titulo": "Probabilidade de fechar: diesel",
        "texto": texto,
        "fontes": [F_ANP_PRODUCAO, F_ANP_DESEMBARACOS,
                   {"rot": "MME, abastecimento de diesel em outubro",
                    "url": "https://agenciagov.ebc.com.br/noticias/202610/"
                           "governo-federal-prorroga-desoneracao-da-gasolina-e-do-etanol"},
                   {"rot": "MPs 1.388, 1.389, 1.391 e 1.395, e portaria do "
                           "Ministério da Fazenda de 13/10/2026"}],
        "graficos": [
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
        ],
    }


# ─── seção 4: estimativa, gasolina ───────────────────────────────────────────

def secao_gasolina_estimativa():
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

    texto = (
        "Duas contas, por caminhos que não dividem nenhuma suposição.\n\n"
        "A **contábil** é aritmética pura. A Petrobras vende R$ 1,17 abaixo da "
        "paridade; como 68% do litro de gasolina C é gasolina A, isso são "
        "R$ 0,80 por litro, ou 12% do preço na bomba; a gasolina pesa 5,13% no "
        "IPCA. Resultado: **0,63 ponto do índice está represado**, e contando "
        "a partir de março de 2026, quando a guerra abriu a defasagem, "
        "**0,70 ponto do IPCA acumulado em 12 meses**.\n\n"
        "A segunda é da FGV, de Francisco Pessoa Faria, e não usa preço de "
        "combustível nenhum: usa o IPCA de Salvador. Na Bahia a Petrobras não "
        "tem ponto de entrega — quem forma preço é a Acelen, refinaria privada "
        "que segue o mercado. Então a variação do IPCA Gasolina em Salvador é "
        "uma leitura do que o país teria feito sem defasagem. No bimestre do "
        "choque a gasolina subiu **18,2% em Salvador e 6,3% em São Paulo**. "
        "Ponderado pelo peso de cada praça, dá **0,59 ponto**.\n\n"
        "Reproduzimos a tabela dele praça a praça, e bate na casa decimal. É a "
        "terceira tabela abaixo.\n\n"
        "A Acelen justifica o papel de régua: desde março de 2026 ela vende, "
        "em média, 5,1% **acima** da paridade, enquanto a Petrobras vende "
        "22,5% abaixo. Com uma ressalva que vale escrever: a subvenção chegou "
        "à Acelen em 13 de agosto de 2026, dois meses e meio depois da "
        "Petrobras. Dali em diante o preço baiano também passou a ser "
        "segurado, e Salvador parou de servir de controle — é por isso que "
        "esta estimativa só vale até o começo de agosto.\n\n"
        "⟨FALTA: os efeitos indiretos do Relatório de Política Monetária do "
        "Banco Central. As duas contas acima medem só o efeito direto, o "
        "preço na bomba. O repasse para transporte, alimentação e o resto da "
        "cesta é o que falta somar.⟩"
    )
    return {
        "titulo": "Quanto vale fechar: gasolina",
        "texto": texto,
        "fontes": [F_SIDRA, F_FGV, F_PETROBRAS,
                   {"rot": "ANP, Levantamento de Preços (revenda)",
                    "url": "https://www.gov.br/anp/pt-br/centrais-de-conteudo/"
                           "dados-abertos/serie-historica-de-precos-de-combustiveis"},
                   {"rot": "⟨FALTA: efeitos indiretos, Relatório de Política "
                           "Monetária do Banco Central⟩"}],
        "graficos": [
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
        ],
    }


# ─── seção 5: estimativa, diesel ─────────────────────────────────────────────

def secao_diesel_estimativa():
    texto = (
        "No diesel a conta direta é pequena, e por um motivo simples: "
        "**família não compra diesel**. O item existe no IPCA — subitem "
        "5104003, Óleo diesel — mas pesa **0,2562%** contra 5,1285% da "
        "gasolina. Vinte vezes menos.\n\n"
        "Então, mesmo com uma defasagem muito maior que a da gasolina, o "
        "efeito direto do diesel no índice é de segunda ordem. O que importa "
        "é o indireto: diesel caro vira frete caro, e frete caro vira "
        "alimento, transporte e quase tudo o mais.\n\n"
        "Sobre o método: a lógica de Salvador vale aqui também. A Petrobras "
        "não tem ponto de entrega na Bahia em nenhum dos dois produtos — são "
        "17 unidades da federação na gasolina e 16 no diesel, e nenhuma delas "
        "é a Bahia. E o IPCA publica o item de óleo diesel nas 16 praças. "
        "Fica de fora só o contrafactual da Bahia por nível de preço, que "
        "exigiria preço de bomba de diesel por estado, e o agregado da ANP que "
        "montamos cobre apenas gasolina e etanol.\n\n"
        "⟨FALTA: esta seção ainda não tem número. Faltam duas coisas, nesta "
        "ordem de importância. Primeiro os efeitos indiretos do Relatório de "
        "Política Monetária do Banco Central, que são o número central da "
        "seção. Segundo as nossas duas contas para o diesel — a contábil com "
        "peso 0,2562% e a de Salvador com o item 5104003 —, que são trabalho "
        "de planilha ainda por fazer.⟩"
    )
    return {"titulo": "Quanto vale fechar: diesel", "texto": texto,
            "fontes": [F_SIDRA, F_PETROBRAS,
                       {"rot": "⟨FALTA: efeitos indiretos, Relatório de "
                               "Política Monetária do Banco Central⟩"}],
            "graficos": []}


# ─── seção 6: o que monitorar ────────────────────────────────────────────────

def secao_conclusao():
    texto = (
        "A defasagem da gasolina vale entre 0,59 e 0,70 ponto do IPCA "
        "acumulado em 12 meses, por duas contas independentes. Mas ela "
        "provavelmente não vai fechar: o país importa pouca gasolina, e quando "
        "o importador sai a Petrobras cobre sem esforço.\n\n"
        "No diesel é o contrário. O efeito direto é pequeno, o indireto não é, "
        "e a probabilidade de a defasagem fechar é alta — porque um quarto do "
        "consumo depende de quem só traz o produto se o preço compensar. É por "
        "isso que as subvenções do ano todo foram para o diesel, e é por isso "
        "que a última foi só para importador.\n\n"
        "**O que monitorar, em ordem de antecedência:**\n\n"
        "1. **Contratação de importação do mês seguinte.** É o indicador mais "
        "à frente de todos. O abastecimento de um mês pode estar garantido e o "
        "do seguinte depender de contrato que ainda não foi fechado.\n\n"
        "2. **Recomposição de estoque, não só cobertura do consumo.** Cobrir o "
        "mês queimando estoque fecha a conta de hoje e deixa amanhã mais "
        "frágil. É o ponto que a métrica oficial não mede.\n\n"
        "3. **Participação das tradings no fornecimento mensal.** É o termômetro "
        "mais direto de se o preço interno está atrativo. Quando cai forte, a "
        "subvenção vem em seguida.\n\n"
        "4. **Prorrogação, ou não, da portaria de 30 dias.** Desde a MP 1.391 "
        "o valor por litro é definido por ato do Ministro da Fazenda, em "
        "janelas renováveis. Cada renovação é uma decisão nova.\n\n"
        "5. **A defasagem semanal contra o PPI**, nos dois combustíveis. É o "
        "primeiro gráfico deste texto, e é o que se move antes de tudo."
    )
    return {"titulo": "O que monitorar", "texto": texto, "graficos": []}


def ultima_data(secoes):
    """A data mais recente que aparece em qualquer série, em ISO."""
    import re
    datas = [k for s in secoes for g in s["graficos"]
             for se in g.get("series", []) for k, _v in se["dados"]
             if re.match(r"^\d{4}-\d{2}(-\d{2})?$", str(k))]
    return max(datas) if datas else None


def main():
    hoje = datetime.date.today()
    print("Lendo as planilhas…")
    secoes = [secao_introducao(), secao_gasolina_probabilidade(),
              secao_diesel_probabilidade(), secao_gasolina_estimativa(),
              secao_diesel_estimativa(), secao_conclusao()]
    doc = {
        "atualizado": hoje.isoformat(),
        # A referência é a data do dado mais fresco, não a de hoje, e vai em
        # ISO porque é o que o rotuloRef() do app.js sabe ler ("15/10/2026"
        # vira "undefined de nan" no rodapé).
        "referencia": ultima_data(secoes) or hoje.isoformat(),
        "fonte": FONTE_ANP,
        "assunto": "A defasagem dos combustíveis",
        # Este assunto é uma análise, não um painel: o leitor precisa ser
        # levado na ordem, e obrigá-lo a abrir capítulo é atrito. Ver
        # montarArtigo() no app.js.
        "formato": "artigo",
        "apresentacao":
            "A Petrobras vende gasolina e diesel abaixo do preço de "
            "importação. Quanto isso segura do IPCA, e qual a chance de a "
            "conta chegar. São duas perguntas, e a segunda vem primeiro na "
            "ordem de importância: **estimativa sem probabilidade não serve "
            "de nada**.\n\n"
            "O que se mede aqui: a defasagem semana a semana contra o PPI da "
            "ANP, quem fornece o combustível do país, duas estimativas "
            "independentes do represamento no IPCA — uma nossa e uma refeita "
            "a partir do artigo da FGV — e o que a subvenção custa.",
        "secoes": secoes,
    }
    faltas = sum(s["texto"].count("⟨") for s in secoes)
    vazias = [s["titulo"] for s in secoes if not s["graficos"]]
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("  %d seções, %d gráficos, %d marcadores de pendência"
          % (len(secoes), sum(len(s["graficos"]) for s in secoes), faltas))
    if vazias:
        print("  ainda sem gráfico: %s" % "; ".join(vazias))
    print("escrito: %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
