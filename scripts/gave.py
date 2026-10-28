#!/usr/bin/env python3
"""
Monta dados/gave.json, o assunto "Os quatro quadrantes de Charles Gave".

Uso:
    python3 scripts/gave.py

Só usa a biblioteca padrão (e o leitor de .xls em scripts/xls.py).

O MÉTODO é o do livro "The General Theory of Portfolio Construction" (Charles
Gave, Gavekal, out/2024), capítulos 3, 4 e 6. São razões entre preços de
mercado, cada uma comparada com a própria média móvel de 7 anos (84 meses):

  - eficiência energética: S&P 500 / petróleo WTI. Acima da média, +1 (lado
    direito dos quadrantes, a economia cresce); abaixo, -1;
  - moeda como reserva de valor: retorno total de um título de 10 anos do
    Tesouro / ouro. Acima da média, +1 (moeda boa, metade de baixo); abaixo,
    -1 (moeda ruim, metade de cima);
  - a soma dá o quadrante: +2 expansão deflacionária, -2 contração
    inflacionária, 0 as outras duas;
  - S&P 500 / ouro: o mercado de alta ou de baixa "de verdade";
  - ouro / WTI: no capítulo 6, a queda dessa razão (o petróleo subindo mais
    que o ouro) antecede a maior parte das recessões desde 1950.

AS FONTES

  - S&P 500 e juro longo: planilha do Shiller (Yale), mensal desde 1871. O
    preço é a média do mês dos fechamentos. O arquivo de Yale parou em
    ago/2023; dali em diante, a média do mês do SP500 diário do FRED (é o
    mesmo índice). O juro de 10 anos é o GS10 do FRED desde abr/1953; antes,
    o juro longo do Shiller, que é o de títulos longos do governo, não
    exatamente de 10 anos.
  - WTI: WTISPLC do FRED, média do mês, desde 1946.
  - Ouro: datasets/gold-prices (GitHub/datahub), que é o Pink Sheet do Banco
    Mundial desde 1960 (média do mês) e a média anual de Timothy Green antes
    disso, repetida nos 12 meses. Até 1971 o ouro tinha preço fixo, então
    tanto faz.
  - Recessões: USREC (NBER, via FRED).

O RETORNO TOTAL DO TÍTULO de 10 anos de duração constante é calculado a partir
do juro: todo mês compra-se um título ao par com cupom igual ao juro do mês,
e no mês seguinte ele é vendido (com 10 anos menos um mês para vencer) ao juro
novo, mais o cupom de um mês. Cupom semestral.

O mês corrente fica de fora: a média dele ainda está pela metade.
"""
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xls  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "gave.json")
CACHE = os.path.join(RAIZ, "dados", ".cache-gave")

SHILLER = "http://www.econ.yale.edu/~shiller/data/ie_data.xls"
OURO = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
LIVRO = "https://web.gavekal.com/media/ebook_files/PDF_The_General_Theory_of_Portfolio_Construction.pdf"

MESES_MEDIA = 84
INI = "1953-01"          # primeiro mês com as duas razões dos quadrantes

BRANCO, AZUL, VERMELHO, VERDE, CIANO, LARANJA, AMARELO = (
    "#FFFFFF", "#4F81BD", "#C0504D", "#9BBB59", "#4BACC6", "#F79646", "#FFFF00")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

QUADRANTES = {  # (energia, moeda) -> nome
    (1, 1): "Expansão deflacionária",
    (1, -1): "Expansão inflacionária",
    (-1, -1): "Contração inflacionária",
    (-1, 1): "Contração deflacionária",
}


def baixar(url, tentativas=4):
    """Sem headers: com User-Agent de navegador o FRED trava."""
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=120) as r:
                return r.read()
        except Exception as e:
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não consegui baixar %s: %s" % (url, ultimo))


def fred(sid):
    """{"AAAA-MM-DD": valor}."""
    txt = baixar("https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid).decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(txt)))
    if sid not in linhas[0][1]:
        raise RuntimeError("cabeçalho inesperado em %s: %r" % (sid, linhas[0]))
    return {l[0]: float(l[1]) for l in linhas[1:] if len(l) >= 2 and l[1].strip() not in ("", ".")}


def mensal(d):
    """Diário para mensal pela média do mês; mensal ("AAAA-MM-01") só troca a chave."""
    soma, n = {}, {}
    for k, v in d.items():
        soma[k[:7]] = soma.get(k[:7], 0) + v
        n[k[:7]] = n.get(k[:7], 0) + 1
    return {m: soma[m] / n[m] for m in soma}


def mes_mais(m, k):
    a, mm = int(m[:4]), int(m[5:7]) - 1 + k
    return "%04d-%02d" % (a + mm // 12, mm % 12 + 1)


def rot_mes(m):
    return "%s/%s" % (MESES[int(m[5:7]) - 1], m[:4])


def br(v, casas=1, sinal=False):
    v = round(v, casas) + 0.0
    t = ("%+.*f" if sinal else "%.*f") % (casas, v)
    return t.replace(".", ",")


# ---------------------------------------------------------------- dados

def shiller():
    """(S&P 500, juro longo em %), mensais, do arquivo de Yale."""
    os.makedirs(CACHE, exist_ok=True)
    caminho = os.path.join(CACHE, "ie_data.xls")
    try:
        conteudo = baixar(SHILLER)
        with open(caminho, "wb") as f:
            f.write(conteudo)
    except RuntimeError:
        if not os.path.exists(caminho):
            raise
        print("  [!] Yale não respondeu; uso a cópia guardada")
        conteudo = open(caminho, "rb").read()
    c = xls.abas(conteudo)["Data"]
    preco, juro = {}, {}
    for r in range(8, max(r for r, _ in c) + 1):
        d = c.get((r, 0))
        if not isinstance(d, float):
            continue
        ano = int(d)
        m = "%04d-%02d" % (ano, round((d - ano) * 100))
        if isinstance(c.get((r, 1)), float):
            preco[m] = c[(r, 1)]
        if isinstance(c.get((r, 6)), float):
            juro[m] = c[(r, 6)]
    return preco, juro


def ouro():
    txt = baixar(OURO).decode("utf-8-sig")
    return {l["Date"][:7]: float(l["Price"]) for l in csv.DictReader(io.StringIO(txt)) if l["Price"].strip()}


def retorno_total(juro):
    """Índice de retorno total do título de 10 anos (1 no primeiro mês)."""
    def preco(cupom, y, anos):
        n, c, r = round(anos * 2, 6), cupom / 2, y / 2
        if r == 0:
            return c * n + 1
        return c / r * (1 - (1 + r) ** -n) + (1 + r) ** -n
    meses = sorted(juro)
    idx = {meses[0]: 1.0}
    for a, b in zip(meses, meses[1:]):
        y0, y1 = juro[a] / 100, juro[b] / 100
        idx[b] = idx[a] * (preco(y0, y1, 10 - 1 / 12) + y0 / 12)
    return idx


def media_movel(s, n=MESES_MEDIA):
    ks = sorted(s)
    out = {}
    for i in range(n - 1, len(ks)):
        if ks[i] != mes_mais(ks[i - n + 1], n - 1):   # buraco na série: não faz média
            continue
        out[ks[i]] = sum(s[k] for k in ks[i - n + 1:i + 1]) / n
    return out


def razao(a, b):
    return {m: a[m] / b[m] for m in a if m in b and b[m]}


def recessoes():
    r = mensal(fred("USREC"))
    ks = sorted(r)
    faixas, ini = [], None
    for k in ks:
        if r[k] == 1 and ini is None:
            ini = k
        if r[k] == 0 and ini is not None:
            faixas.append(dict(de=ini, ate=mes_mais(k, -1)))
            ini = None
    if ini is not None:
        faixas.append(dict(de=ini, ate=ks[-1]))
    return faixas


def faixas_de(meses):
    """Meses (ordenados) que valem True viram faixas contínuas [{de, ate}]."""
    out = []
    for m in meses:
        if out and out[-1]["ate"] == mes_mais(m, -1):
            out[-1]["ate"] = m
        else:
            out.append(dict(de=m, ate=m))
    return out


def placar(q):
    return "%+d" % sum(q) if sum(q) else "0"


def serie(nome, cor, dados, casas=3, **extra):
    return dict(nome=nome, cor=cor, dados=[[k, round(v, casas)] for k, v in sorted(dados.items())], **extra)


# ---------------------------------------------------------------- gráficos

def grafico_razao(id_, titulo, sub_razao, nome, r, mm, fonte, casas=3, unidade="pts", ini=None, sombra_acima=True):
    """Duas leituras do mesmo sinal: a razão com a média de 7 anos, e a
    distância entre as duas em %."""
    ini = ini or min(mm)
    r = {m: v for m, v in r.items() if m >= ini}
    mm = {m: v for m, v in mm.items() if m >= ini}
    dist = {m: 100 * (r[m] / mm[m] - 1) for m in mm if m in r}
    acima = faixas_de([m for m in sorted(dist) if dist[m] > 0]) if sombra_acima else []
    sub_faixa = "; faixas cinza = acima da média" if sombra_acima else ""
    return dict(id=id_, titulo=titulo, subtitulo=sub_razao + sub_faixa, fonte=fonte, sombras=acima, variantes=[
        dict(rot="razão e média de 7 anos", unidade=unidade, eixo={"zero": False}, series=[
            serie(nome, BRANCO, r, casas, rotulo=True),
            serie("Média de 7 anos", LARANJA, mm, casas)]),
        dict(rot="distância da média (%)", unidade="pct1", series=[
            serie("Distância da média de 7 anos", BRANCO, dist, 1, rotulo=True, legenda=False)])])


def montar():
    hoje = datetime.date.today()
    corte = "%04d-%02d" % (hoje.year, hoje.month)      # o mês corrente fica de fora

    sp, juro = shiller()
    fim_shiller = mes_mais(max(sp), -1)                  # o último mês de Yale é o fechamento do dia 1º
    sp = {m: v for m, v in sp.items() if m <= fim_shiller}
    sp_fred = mensal(fred("SP500"))
    comum = [m for m in sp_fred if m in sp and m >= mes_mais(fim_shiller, -23)]
    dif = max(abs(sp_fred[m] / sp[m] - 1) for m in comum) * 100
    print("  S&P 500: Shiller até %s; FRED depois (diferença máx. de %.2f%% em %d meses comuns)"
          % (fim_shiller, dif, len(comum)))
    for m, v in sp_fred.items():
        if m > fim_shiller:
            sp[m] = v
    gs10 = mensal(fred("GS10"))
    juro = {m: v for m, v in juro.items() if m < min(gs10)}
    juro.update(gs10)
    wti = mensal(fred("WTISPLC"))
    au = ouro()
    sp, juro, wti, au = ({m: v for m, v in s.items() if m < corte} for s in (sp, juro, wti, au))
    tr = retorno_total(juro)
    # o índice de retorno total começa em 1871 e cresce muito: 100 em jan/1971,
    # o ano em que o ouro deixou de ter preço fixo
    base = tr["1971-01"] / au["1971-01"]
    print("  últimos meses: S&P %s, WTI %s, ouro %s, juro %s" % (max(sp), max(wti), max(au), max(juro)))

    r_en, r_mo, r_sg, r_ow = razao(sp, wti), razao(tr, au), razao(sp, au), razao(au, wti)
    r_mo = {m: 100 * v / base for m, v in r_mo.items()}
    mm_en, mm_mo, mm_sg = media_movel(r_en), media_movel(r_mo), media_movel(r_sg)

    # os quadrantes, mês a mês
    quad = {}
    for m in sorted(mm_en):
        if m in mm_mo and m >= INI:
            e = 1 if r_en[m] > mm_en[m] else -1
            b = 1 if r_mo[m] > mm_mo[m] else -1
            quad[m] = (e, b)
    ult = max(quad)
    print("  quadrante em %s: %s" % (ult, QUADRANTES[quad[ult]]))

    fonte = "Shiller (Yale), FRED, Banco Mundial, Charles Gave e FtM"

    # ---------- onde estamos
    def linha(nome, r, mm, pos, neg):
        d = 100 * (r[ult] / mm[ult] - 1)
        desde = ult
        while mes_mais(desde, -1) in mm and (r[mes_mais(desde, -1)] > mm[mes_mais(desde, -1)]) == (d > 0):
            desde = mes_mais(desde, -1)
        return [{"t": nome, "forte": True}, {"t": br(d, 1, True) + "%", "cor": VERDE if d > 0 else VERMELHO},
                {"t": pos if d > 0 else neg}, {"t": rot_mes(desde)}]
    tabela = dict(id="gave-onde-estamos", tipo="tabela", titulo="Onde estamos nos quadrantes",
                  subtitulo="cada razão contra a própria média de 7 anos, em %s" % rot_mes(ult), fonte=fonte,
                  colunas=[{"rot": "Razão"}, {"rot": "Distância da média", "num": True}, {"rot": "Leitura"},
                           {"rot": "Desde"}],
                  linhas=[linha("S&P 500 / petróleo", r_en, mm_en, "+1: energia eficiente", "-1: energia ineficiente"),
                          linha("Título de 10 anos / ouro", r_mo, mm_mo, "+1: moeda boa", "-1: moeda ruim"),
                          linha("S&P 500 / ouro", r_sg, mm_sg, "mercado de alta", "mercado de baixa"),
                          [{"t": "Quadrante", "forte": True}, {"t": ""},
                           {"t": placar(quad[ult]) + ": " + QUADRANTES[quad[ult]].lower(), "forte": True},
                           {"t": ""}]])
    # "desde" do quadrante: o início do período atual
    k = ult
    while mes_mais(k, -1) in quad and quad[mes_mais(k, -1)] == quad[ult]:
        k = mes_mais(k, -1)
    tabela["linhas"][-1][3] = {"t": rot_mes(k)}

    # ---------- S&P 500 em ouro com as faixas de cada quadrante
    sg = {m: v for m, v in r_sg.items() if m >= INI}
    mm_sg_ = {m: v for m, v in mm_sg.items() if m >= INI}

    def var_quadrante(q):
        return dict(rot=QUADRANTES[q].lower(),
                    sombras=faixas_de([m for m in sorted(quad) if quad[m] == q]))
    g_sg = dict(id="gave-sp-ouro", titulo="S&P 500 em ouro e os quadrantes de Gave",
                subtitulo="onças de ouro por unidade do índice; faixas cinza = meses no quadrante escolhido",
                unidade="pts", eixo={"zero": False}, fonte=fonte,
                series=[serie("S&P 500 / ouro", BRANCO, sg, 3, rotulo=True),
                        serie("Média de 7 anos", LARANJA, mm_sg_, 3)],
                variantes=[var_quadrante(q) for q in ((1, 1), (1, -1), (-1, -1), (-1, 1))])

    # ---------- a história dos períodos
    periodos, ks = [], sorted(quad)
    ini = ks[0]
    for a, b in zip(ks, ks[1:] + [None]):
        if b is None or quad[b] != quad[a]:
            periodos.append((ini, a, quad[a]))
            ini = b
    linhas, por_quad = [], {}
    for de, ate, q in periodos:
        n = (int(ate[:4]) - int(de[:4])) * 12 + int(ate[5:7]) - int(de[5:7]) + 1
        ant = mes_mais(de, -1)
        ganho = 100 * (r_sg[ate] / r_sg[ant] - 1) if ant in r_sg else None
        por_quad.setdefault(q, []).append((n, ganho))
        if n < 6:
            continue
        linhas.append([{"t": QUADRANTES[q], "forte": sum(q) != 0}, {"t": rot_mes(de)},
                       {"t": rot_mes(ate) if ate != ult else "hoje"}, {"t": str(n), "num": True},
                       {"t": br(ganho, 0, True) + "%", "cor": VERDE if ganho > 0 else VERMELHO}
                       if ganho is not None else {"t": ""}])
    print("  %d períodos, %d com 6 meses ou mais" % (len(periodos), len(linhas)))
    tab_per = dict(id="gave-periodos", tipo="tabela", titulo="Os quadrantes desde 1953, período a período",
                   subtitulo="períodos de 6 meses ou mais; S&P 500 em ouro = variação da razão no período",
                   fonte=fonte, colunas=[{"rot": "Quadrante"}, {"rot": "De"}, {"rot": "Até"},
                                         {"rot": "Meses", "num": True}, {"rot": "S&P 500 em ouro", "num": True}],
                   linhas=linhas[::-1])

    # resumo por quadrante: S&P 500 em ouro ao ano, em todos os meses
    resumo = []
    for q in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        meses_q = [m for m in ks if quad[m] == q and mes_mais(m, -1) in r_sg]
        log = sum(__import__("math").log(r_sg[m] / r_sg[mes_mais(m, -1)]) for m in meses_q)
        anual = 100 * (__import__("math").exp(log * 12 / len(meses_q)) - 1)
        resumo.append([{"t": QUADRANTES[q], "forte": True}, {"t": placar(q)},
                       {"t": str(len(meses_q)), "num": True},
                       {"t": br(100 * len(meses_q) / len(ks), 0) + "%", "num": True},
                       {"t": br(anual, 1, True) + "%", "cor": VERDE if anual > 0 else VERMELHO}])
        print("  %-26s %4d meses, S&P em ouro %+.1f%% a.a." % (QUADRANTES[q], len(meses_q), anual))
    tab_res = dict(id="gave-resumo", tipo="tabela", titulo="O que o S&P 500 fez em cada quadrante",
                   subtitulo="de %s a %s; S&P 500 em ouro, variação média ao ano nos meses do quadrante"
                             % (rot_mes(ks[0]), rot_mes(ult)),
                   fonte=fonte, colunas=[{"rot": "Quadrante"}, {"rot": "Placar"}, {"rot": "Meses", "num": True},
                                         {"rot": "Do tempo", "num": True},
                                         {"rot": "S&P 500 em ouro ao ano", "num": True}],
                   linhas=resumo)

    # ---------- as duas razões dos eixos
    g_en = grafico_razao("gave-sp-petroleo", "S&P 500 contra o petróleo (eficiência energética)",
                         "pontos do índice por barril de WTI", "S&P 500 / WTI", r_en, mm_en,
                         "Shiller (Yale), FRED e FtM", casas=2, ini=INI)
    g_mo = grafico_razao("gave-titulo-ouro", "Título de 10 anos contra o ouro (a moeda como reserva de valor)",
                         "retorno total do título de 10 anos do Tesouro / preço do ouro, jan/1971 = 100",
                         "Título de 10 anos / ouro", r_mo, mm_mo, "Shiller (Yale), FRED, Banco Mundial e FtM",
                         casas=1, ini=INI)

    # ---------- ouro contra petróleo e recessões
    ow = {m: v for m, v in r_ow.items() if m >= "1947-01"}
    g_ow = dict(id="gave-ouro-petroleo", titulo="Ouro contra petróleo e as recessões",
                subtitulo="barris de WTI por onça de ouro; faixas cinza = recessões (NBER)", unidade="pts",
                sombras=recessoes(), fonte="FRED, Banco Mundial, NBER e FtM",
                series=[serie("Ouro / WTI", AMARELO, ow, 1, rotulo=True, legenda=False)])

    fontes_livro = [dict(id="livro", rot="Charles Gave, The General Theory of Portfolio Construction (2024)",
                         url=LIVRO)]
    secoes = [
        dict(titulo="Os quatro quadrantes", fontes=fontes_livro, figuras=[], texto=(
            "Gave divide a economia em quatro estados a partir de duas perguntas, respondidas por preços de "
            "mercado e não por estatística oficial. A energia está sendo transformada em valor? Para isso, "
            "ele usa o S&P 500 contra o petróleo. A moeda guarda valor? Para isso, usa o título de 10 anos "
            "do Tesouro contra o ouro. Cada razão vale +1 quando está acima da própria média de 7 anos e -1 "
            "quando está abaixo.\n\n"
            "A soma dá o quadrante. Em +2, a expansão deflacionária, aconteceram todos os mercados de alta de "
            "verdade, medidos pelo S&P 500 em ouro. Em -2, a contração inflacionária, aconteceram as grandes "
            "quedas. Nos dois quadrantes de placar zero, diz ele, nada muito dramático costuma acontecer."),
            graficos=[tabela, g_sg, tab_res, tab_per]),
        dict(titulo="S&P 500 contra o petróleo", fontes=[], figuras=[], texto=(
            "O petróleo é o custo da energia, e a bolsa, o valor do que se produz com ela. Enquanto a bolsa "
            "sobe mais que o petróleo, a energia está sendo bem transformada e a economia tende a crescer: é "
            "o lado direito dos quadrantes."),
            graficos=[g_en]),
        dict(titulo="Título de 10 anos contra o ouro", fontes=[], figuras=[], texto=(
            "A pergunta aqui é se o título do Tesouro protege quem o tem. Quando o retorno total dele supera "
            "o ouro, a moeda está guardando valor: é a metade de baixo dos quadrantes. Quando o ouro ganha, "
            "a moeda está sendo desvalorizada."),
            graficos=[g_mo]),
        dict(titulo="Ouro contra petróleo", fontes=[], figuras=[], texto=(
            "No capítulo 6, Gave nota que a maior parte das recessões americanas desde 1950 começou depois "
            "de uma queda desta razão, isto é, com o petróleo subindo mais que o ouro."),
            graficos=[g_ow]),
    ]
    return dict(atualizado=hoje.isoformat(), referencia=ult, formato="artigo",
                assunto="Os quatro quadrantes de Charles Gave",
                fonte="Shiller (Yale), FRED, Banco Mundial (via datahub) e FtM",
                apresentacao=("Os indicadores de Charles Gave, da Gavekal, no livro The General Theory of Portfolio "
                              "Construction (2024), refeitos com dados públicos. Em %s, a economia americana "
                              "está na %s." % (rot_mes(ult), QUADRANTES[quad[ult]].lower())),
                secoes=secoes)


def main():
    doc = montar()
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
