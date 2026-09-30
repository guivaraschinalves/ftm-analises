#!/usr/bin/env python3
"""
Monta dados/juros-eua.json — o assunto "Taxa de 10 anos dos EUA" — com as
séries do FRED (Federal Reserve Bank of St. Louis).

Uso:
    python3 scripts/juros_eua.py

Só usa a biblioteca padrão. Roda na Action .github/workflows/atualizar.yml.

FONTE. O FRED tem duas portas:

  - a API JSON (api.stlouisfed.org) **exige chave** — sem api_key ela responde
    400 "Variable api_key is not set";
  - o CSV público do gráfico (fredgraph.csv?id=SERIE) **não exige nada**,
    devolve a série inteira em texto e é o mesmo dado da API.

Aqui usamos o CSV. Se um dia quisermos vintages (o que o mercado via em cada
data, no ALFRED) ou metadados da série, é trocar `baixar_serie` por uma chamada
à API com chave num segredo do repositório — nada mais no arquivo muda.

ARMADILHA, a mesma que o observatorio-politica-monetaria documentou: o FRED
**trava** (timeout, não 403) quando a requisição se identifica como navegador.
Sem headers, com o User-Agent do urllib, ele responde em 0,3 s. Então não
acrescente `User-Agent` aqui.

AS SÉRIES:

  - DGS10 — "Market Yield on U.S. Treasury Securities at 10-Year Constant
    Maturity", diária, desde 02/01/1962. É a taxa que o Treasury publica na
    curva de par yields, interpolada para o prazo cheio de 10 anos. Dia de
    feriado e fim de semana não existe no arquivo, e pregão sem negócio vem
    como ".".
  - GS10 — a mesma taxa na **média do mês**, desde abril de 1953. São nove anos
    a mais de história, e é o mais longo que o FRED tem para o prazo de 10
    anos. (Há uma série do NBER com yields de títulos longos do Tesouro de 1919
    a 1944, mas ali "longo" não é 10 anos: é outro instrumento, não dá para
    emendar na mesma linha.)

O INTRADIÁRIO. O FRED não tem dado intradiário — o DGS10 é uma cotação por dia,
a das 15h30 de Nova York. Para o gráfico do mês, hora a hora, a fonte é o
endpoint de gráfico do investing.com (id 23705, "United States 10-Year"), que
responde sem chave desde que a requisição mande o header `Domain-Id: www`.

Duas consequências que o código trata:

  - **a janela é curta**: o endpoint devolve no máximo 744 pontos, ou seja ~1
    mês de dado horário e ~13 dias de 15 em 15 minutos. Por isso o script
    mantém um **acervo** em dados/intradiario-10a.json que só cresce: cada
    rodada junta o que baixou ao que já estava lá. O que não for guardado hoje
    não volta mais;
  - **não é o dado oficial**: é a cotação de mercado do papel, não o cálculo do
    Tesouro às 15h30. O script compara as duas todo dia e imprime a diferença —
    na primeira carga, 19 dias conferidos, diferença média de 0,007 p.p. e
    máxima de 0,018 p.p.

Se a fonte intradiária cair, o script segue: mantém o acervo que já tem e
continua atualizando o resto.

A hora gravada é a de **Nova York** (o pregão e os indicadores saem nela). Na
virada do horário de verão a hora repetida vira uma chave só.
"""
import csv
import datetime
import io
import json
import os
import time
import urllib.error
import urllib.request
import zoneinfo

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "juros-eua.json")
ACERVO_INTRA = os.path.join(RAIZ, "dados", "intradiario-10a.json")

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s"

# investing.com: 23705 é o "United States 10-Year". O header Domain-Id é o que
# faz o endpoint responder; o User-Agent de navegador aqui é necessário (ao
# contrário do FRED, que trava com ele).
INTRA_URL = ("https://api.investing.com/api/financialdata/23705/historical/chart/"
             "?period=P1M&interval=%s&pointscount=160")
INTRA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
    "Domain-Id": "www",
}
# hora cobre o mês inteiro; 15 minutos detalha os últimos dias. As duas entram
# no mesmo acervo, e o mais fino ganha quando as duas têm o mesmo horário.
INTRA_INTERVALOS = ("PT1H", "PT15M")
NOVA_YORK = zoneinfo.ZoneInfo("America/New_York")

# O mês que ganha o gráfico hora a hora.
MES_DETALHE = "2026-09"

BRANCO, AZUL, VERMELHO, CIANO, LARANJA = "#FFFFFF", "#4F81BD", "#C0504D", "#4BACC6", "#F79646"

ANO_RECENTE = 2026


def baixar(url, tentativas=4, headers=None):
    """Sem headers, o padrão: com User-Agent de navegador o FRED trava."""
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:                      # a rede do Actions falha de vez em quando
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não consegui baixar %s: %s" % (url, ultimo))


def baixar_serie(serie_id):
    """[(data ISO, valor em % a.a.)], sem os dias que o FRED marca com '.'."""
    texto = baixar(FRED_CSV % serie_id).decode("utf-8-sig")
    linhas = list(csv.reader(io.StringIO(texto)))
    cabecalho = linhas[0]
    if len(cabecalho) < 2 or serie_id not in cabecalho[1]:
        raise RuntimeError("cabeçalho inesperado em %s: %r" % (serie_id, cabecalho))
    pontos = []
    for data, valor in (l[:2] for l in linhas[1:] if len(l) >= 2):
        valor = valor.strip()
        if valor in (".", ""):                      # feriado, ou dia sem cotação
            continue
        datetime.date.fromisoformat(data)           # confere o formato antes de gravar
        pontos.append((data, round(float(valor), 2)))
    if len(pontos) < 100:
        raise RuntimeError("%s veio com %d pontos — o arquivo mudou de formato?" % (serie_id, len(pontos)))
    return pontos


# ---------------------------------------------------------------- intradiário

def baixar_intradiario():
    """{"2026-09-16T14:00": 5.01, ...} na hora de Nova York. Devolve {} se a
    fonte não responder — quem chama decide o que fazer com isso."""
    pontos = {}
    for intervalo in INTRA_INTERVALOS:
        try:
            bruto = json.loads(baixar(INTRA_URL % intervalo, tentativas=2, headers=INTRA_HEADERS))
        except Exception as e:
            print("  [!] intradiário %s não veio: %s" % (intervalo, e))
            continue
        linhas = bruto.get("data", [])
        for linha in linhas:
            ms, fecha = linha[0], linha[4]
            t = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).astimezone(NOVA_YORK)
            pontos[t.strftime("%Y-%m-%dT%H:%M")] = round(float(fecha), 3)
        # sem esta linha, "0 novos" no acervo seria ambíguo: fonte fora do ar ou
        # só nada de novo desde a última rodada?
        print("  intradiário %s: %d cotações baixadas" % (intervalo, len(linhas)))
    return pontos


def acervo_intradiario():
    """Junta o que baixou hoje ao que já estava guardado e regrava o acervo.

    A janela da fonte é curta (~1 mês); o acervo é o que dá história ao gráfico.
    """
    guardado = {}
    if os.path.exists(ACERVO_INTRA):
        with io.open(ACERVO_INTRA, encoding="utf-8") as f:
            guardado = json.load(f).get("pontos", {})
    novos = baixar_intradiario()
    juntos = dict(guardado)
    juntos.update(novos)
    if not juntos:
        return {}
    doc = {
        "fonte": "investing.com (id 23705), hora de Nova York",
        "atualizado": datetime.date.today().isoformat(),
        "pontos": {k: juntos[k] for k in sorted(juntos)},
    }
    with io.open(ACERVO_INTRA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("  acervo intradiário: %d pontos (%d novos), %s → %s" % (
        len(juntos), len(set(novos) - set(guardado)), min(juntos), max(juntos)))
    return doc["pontos"]


def conferir_intradiario(intra, diaria):
    """O intradiário não é o dado oficial: imprime, todo dia, o quanto ele se
    afasta do DGS10 no fim da tarde de Nova York."""
    por_dia = {}
    for k, v in intra.items():
        dia, hora = k.split("T")
        if hora.startswith(("15:", "16:")):
            por_dia.setdefault(dia, []).append((hora, v))
    oficial = dict(diaria)
    difs = [abs(sorted(v)[0][1] - oficial[d]) for d, v in por_dia.items() if d in oficial]
    if difs:
        print("  confere com o DGS10: %d dias, diferença média %.3f p.p., máxima %.3f p.p." % (
            len(difs), sum(difs) / len(difs), max(difs)))


def por_mes(pontos):
    """Série mensal do FRED (data no dia 1) com a chave que o site espera: AAAA-MM."""
    return [[d[:7], v] for d, v in pontos]


def do_ano(pontos, ano):
    alvo = "%d-" % ano
    return [[d, v] for d, v in pontos if d.startswith(alvo)]


def pares(pontos):
    return [[d, v] for d, v in pontos]


def fmt(v):
    return ("%.2f" % v).replace(".", ",") + "%"


def data_br(iso):
    p = iso.split("-")
    return "%s/%s/%s" % (p[2], p[1], p[0])


MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def nome_do_mes(aaaa_mm):
    ano, mes = aaaa_mm.split("-")
    return "%s de %s" % (MESES[int(mes) - 1], ano)


def vira_fino(pontos):
    """Primeira cotação fora da hora cheia: dali em diante o passo é de 15 min."""
    for k, _ in pontos:
        if not k.endswith(":00"):
            return k
    return pontos[-1][0]


def hora_br(chave):
    """"2026-09-16T14:00" -> "16/09, 14h00"."""
    dia, hora = chave.split("T")
    p = dia.split("-")
    return "%s/%s, %sh%s" % (p[2], p[1], hora[:2], hora[3:])


# --------------------------------------------------------- a linha do tempo
# Cada item: quando marcar (em), o rótulo curto que vai no gráfico (rot), como
# a data aparece na lista embaixo do cartão (quando) e a explicação (texto).
# Data e número de cada um conferidos na fonte citada; nenhum foi deduzido do
# próprio gráfico. O que o gráfico mostra é coincidência de data — a taxa de 10
# anos é preço de mercado, e um dia junta muita coisa.
EVENTOS_ANO = [
    {"em": "2026-02-05", "rot": "Emprego fraco",
     "quando": "5 de fevereiro",
     "texto": "Pedidos de seguro-desemprego a 231 mil (contra 212 mil esperados) e o maior "
              "corte de vagas para um janeiro desde 2009, no relatório da Challenger, derrubam "
              "a taxa de 10 anos a 4,21%. Fevereiro fecha 32 pb abaixo — a maior queda mensal "
              "do ano. (CNBC, 5/2/2026)"},
    {"em": "2026-02-28", "rot": "Guerra EUA–Irã",
     "quando": "28 de fevereiro",
     "texto": "EUA e Israel lançam quase 900 ataques ao Irã em 12 horas e começa a guerra. "
              "Na véspera, 27/2, a taxa de 10 anos tinha marcado a mínima do ano: 3,97%. "
              "(Wikipédia — 2026 Iran war; Britannica)"},
    {"em": "2026-03-02", "rot": "Ormuz fechado",
     "quando": "2 de março",
     "texto": "O Estreito de Ormuz, por onde passa mais de 20% do petróleo do mundo, fica "
              "fechado na prática. O Brent chega perto de US$ 118 no fim de março e a AIE "
              "libera 400 milhões de barris em 21/3, a maior liberação coordenada da "
              "história. A taxa de 10 anos sobe 25 pb no mês. (CEPR; AIE)"},
    {"em": "2026-03-18", "rot": "Fed revisa a inflação",
     "quando": "18 de março",
     "texto": "O Fed mantém o juro por 11 votos a 1 e sobe a projeção de inflação de 2026 "
              "para 2,7%, por causa da energia. O gráfico de pontos passa a indicar um corte "
              "só no ano. (CNBC, 18/3/2026)"},
    {"em": "2026-05-22", "rot": "Warsh assume o Fed",
     "quando": "22 de maio",
     "texto": "Kevin Warsh toma posse na presidência do Fed, no lugar de Jerome Powell, cujo "
              "mandato terminou em 12/5. Uma semana antes, em 15/5, CPI e PPI acima do "
              "esperado já tinham feito a taxa de 10 anos subir 12 pb num pregão só. "
              "(Federal Reserve; CNBC, 15/5/2026)"},
    {"em": "2026-06-24", "rot": "Petróleo recua",
     "quando": "24 de junho",
     "texto": "O petróleo volta ao nível anterior à guerra e a taxa de 10 anos cai a 4,41%. "
              "(CNN, 24/6/2026)"},
    {"em": "2026-07-14", "rot": "CPI de junho desacelera",
     "quando": "14 de julho",
     "texto": "O CPI de junho cai 0,4% no mês e desacelera para 3,5% em 12 meses, contra 3,8% "
              "esperados. É o único respiro do segundo semestre: o petróleo volta a passar de "
              "US$ 100 no fim de julho e o mês fecha 27 pb acima. (CNBC, 14/7/2026)"},
    {"em": "2026-09-16", "rot": "Fed sobe o juro",
     "quando": "16 de setembro",
     "texto": "O Fed sobe o juro em 0,25 ponto, para 3,75%–4%, na primeira alta desde 2023, "
              "por 12 votos a 0. Dos 18 participantes, 16 passam a ver mais uma alta ainda "
              "este ano. (CNBC e Fox Business, 16/9/2026)"},
    {"em": "2026-09-23", "rot": "PMI forte e leilão fraco",
     "quando": "23 de setembro",
     "texto": "O PMI composto de setembro vem a 58,4, o maior em mais de cinco anos, e o "
              "leilão de 5 anos sai com a segunda maior cauda da história. A taxa de 10 anos "
              "sobe 15 pb no dia e a de 5 anos passa de 5% pela primeira vez desde 2007. "
              "(Bloomberg e Investing.com, 23/9/2026)"},
]

# No gráfico do mês a hora importa: o dado sai às 8h30, a decisão do Fed às 14h,
# o leilão às 13h — e o salto aparece no lugar certo.
EVENTOS_MES = [
    {"em": "2026-09-04T08:30", "rot": "Payroll forte",
     "quando": "4 de setembro, 8h30",
     "texto": "O relatório de emprego de agosto vem forte e leva a taxa de 2 anos ao maior "
              "nível desde janeiro de 2025. (CNBC, 4/9/2026)"},
    {"em": "2026-09-10T09:00", "rot": "Petróleo acima de US$ 100",
     "quando": "10 de setembro",
     "texto": "A alta do petróleo leva a taxa de 10 anos a 4,95%, a maior desde outubro de "
              "2023, por cima de um PPI em linha e de um leilão forte de 30 anos. "
              "(CNBC, 10/9/2026)"},
    {"em": "2026-09-11T08:30", "rot": "CPI de agosto",
     "quando": "11 de setembro, 8h30",
     "texto": "O CPI de agosto confirma a inflação resistente e a taxa fica colada nas "
              "máximas de vários anos. (BLS; CNBC, 11/9/2026)"},
    {"em": "2026-09-16T14:00", "rot": "Fed sobe o juro",
     "quando": "16 de setembro, 14h",
     "texto": "Primeira alta desde 2023: 0,25 ponto, para 3,75%–4%, por 12 a 0, com o gráfico "
              "de pontos indicando mais uma este ano. (CNBC, 16/9/2026)"},
    {"em": "2026-09-23T09:45", "rot": "PMI em máxima de 5 anos",
     "quando": "23 de setembro, 9h45",
     "texto": "O PMI composto vem a 58,4, contra 56,0 do mês anterior, com os custos de "
              "insumo subindo no ritmo mais forte em quatro anos. (S&P Global; Wolf Street)"},
    {"em": "2026-09-23T13:00", "rot": "Leilão de 5 anos",
     "quando": "23 de setembro, 13h",
     "texto": "US$ 70 bilhões em papéis de 5 anos saem a 5,033%, com cauda de 3,1 pb — a "
              "segunda maior da história — e a demanda mais fraca desde 2018. Os dealers "
              "ficam com 15,8% da oferta. (Bloomberg; TFTC)"},
    {"em": "2026-09-24T15:00", "rot": "Máxima em 19 anos",
     "quando": "24 de setembro",
     "texto": "A taxa de 30 anos vai ao maior nível desde 2004 e a de 10 anos fecha a 5,18%, "
              "a maior em 19 anos. (Bloomberg, 24/9/2026)"},
    {"em": "2026-09-28T15:00", "rot": "Aposta em nova alta",
     "quando": "28 de setembro",
     "texto": "A taxa de 10 anos passa de 5,2% e os futuros passam a dar cerca de 70% de "
              "chance de nova alta de juro na reunião de 28 de outubro. (CME FedWatch; CNBC)"},
]


def main():
    diaria = baixar_serie("DGS10")
    mensal = baixar_serie("GS10")
    recente = do_ano(diaria, ANO_RECENTE)
    if not recente:
        raise RuntimeError("nenhum pregão de %d na série diária" % ANO_RECENTE)
    intra = acervo_intradiario()
    conferir_intradiario(intra, diaria)
    do_mes = sorted((k, v) for k, v in intra.items() if k.startswith(MES_DETALHE))

    minimo = min(diaria, key=lambda p: p[1])
    maximo = max(diaria, key=lambda p: p[1])
    ini_rec, fim_rec = recente[0], recente[-1]
    piso_rec = min(recente, key=lambda p: p[1])
    teto_rec = max(recente, key=lambda p: p[1])

    doc = {
        "assunto": "Taxa de 10 anos dos EUA",
        "fonte": "FRED (Federal Reserve Bank of St. Louis) e FtM",
        "referencia": diaria[-1][0],
        "atualizado": datetime.date.today().isoformat(),
        "apresentacao": (
            "A taxa do Treasury de 10 anos é o juro longo que serve de régua para o "
            "preço de quase todo ativo — do financiamento imobiliário americano ao "
            "prêmio que um país emergente paga para se endividar. O FRED guarda a "
            "série desde 1953, e o extremo de tudo que ele tem está no dado diário: "
            "%s em %s, no aperto de Volcker, contra %s em %s, no primeiro ano da "
            "pandemia. (De 1953 a 1962, o que existe é a média do mês, e ela nunca "
            "saiu da faixa de 2,3%% a 4,7%%.)" % (
                fmt(maximo[1]), data_br(maximo[0]), fmt(minimo[1]), data_br(minimo[0]))
        ),
        "secoes": [
            {
                "titulo": "História",
                "graficos": [{
                    "id": "eua-10a",
                    "titulo": "Taxa de 10 anos dos EUA",
                    "subtitulo": "Treasury de 10 anos, em % ao ano",
                    "unidade": "%",
                    "variantes": [
                        {
                            "rot": "pregão a pregão, desde 1962",
                            "diario": True,
                            "series": [{"nome": "10 anos", "cor": BRANCO, "dados": pares(diaria),
                                        "rotulo": True, "legenda": False}],
                        },
                        {
                            "rot": "média do mês, desde 1953",
                            "series": [{"nome": "10 anos", "cor": BRANCO, "dados": por_mes(mensal),
                                        "rotulo": True, "legenda": False}],
                        },
                    ],
                    "nota": (
                        "Série DGS10 do FRED (taxa de mercado a 10 anos de maturidade constante, "
                        "publicada pelo Tesouro americano): %d pregões, de %s a %s. A média do mês "
                        "é a série GS10, que começa em abril de 1953 — nove anos antes da diária, e "
                        "é o mais longo que o FRED tem para esse prazo." % (
                            len(diaria), data_br(diaria[0][0]), data_br(diaria[-1][0]))
                    ),
                }],
            },
            {
                "titulo": "%d" % ANO_RECENTE,
                "graficos": [{
                    "id": "eua-10a-ano",
                    "titulo": "Taxa de 10 anos dos EUA em %d" % ANO_RECENTE,
                    "subtitulo": "Treasury de 10 anos, em %% ao ano — cada pregão de %d" % ANO_RECENTE,
                    "unidade": "%",
                    "diario": True,
                    "series": [{"nome": "10 anos", "cor": BRANCO, "dados": pares(recente),
                                "rotulo": True, "legenda": False}],
                    "eventos": EVENTOS_ANO,
                    "nota": (
                        "De %s (%s) a %s (%s): %d pregões, com mínima de %s em %s e máxima de %s em "
                        "%s. As marcas são acontecimentos que podem ter mexido na taxa — coincidência "
                        "de data, não prova de causa." % (
                            data_br(ini_rec[0]), fmt(ini_rec[1]), data_br(fim_rec[0]), fmt(fim_rec[1]),
                            len(recente), fmt(piso_rec[1]), data_br(piso_rec[0]),
                            fmt(teto_rec[1]), data_br(teto_rec[0]))
                    ),
                }],
            },
        ],
    }

    # o mês em detalhe só entra se houver acervo intradiário dele
    if len(do_mes) > 20:
        ini_mes, fim_mes = do_mes[0], do_mes[-1]
        piso_mes = min(do_mes, key=lambda p: p[1])
        teto_mes = max(do_mes, key=lambda p: p[1])
        doc["secoes"].append({
            "titulo": "O mês em detalhe",
            "graficos": [{
                "id": "eua-10a-mes",
                "titulo": "Taxa de 10 anos dos EUA em %s" % nome_do_mes(MES_DETALHE),
                "subtitulo": "Treasury de 10 anos, em % ao ano — de hora em hora, no horário de Nova York",
                "unidade": "%",
                "intradiario": True,
                "fonte": "Investing.com e FtM",
                "series": [{"nome": "10 anos", "cor": BRANCO, "dados": [[k, v] for k, v in do_mes],
                            "rotulo": True, "legenda": False}],
                "eventos": EVENTOS_MES,
                "nota": (
                    "%d cotações, de %s a %s, com mínima de %s (%s) e máxima de %s (%s). São de "
                    "hora em hora até %s e de 15 em 15 minutos daí em diante — a fonte só "
                    "entrega os últimos dias no passo fino, e o site guarda o que baixa. O dado "
                    "é a cotação de mercado do papel, não o cálculo do Tesouro das 15h30 que "
                    "alimenta os outros dois gráficos: no fim da tarde as duas medidas ficam a "
                    "0,01 p.p. uma da outra. Fora do pregão de Nova York a linha segue, porque o "
                    "Treasury é negociado na Ásia e na Europa; o corte no fim de semana é o "
                    "mercado fechado." % (
                        len(do_mes), hora_br(ini_mes[0]), hora_br(fim_mes[0]),
                        fmt(piso_mes[1]), hora_br(piso_mes[0]),
                        fmt(teto_mes[1]), hora_br(teto_mes[0]), hora_br(vira_fino(do_mes)))
                ),
            }],
        })

    with io.open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    print("  diária: %d pontos, %s → %s" % (len(diaria), diaria[0][0], diaria[-1][0]))
    print("  mensal: %d pontos, %s → %s" % (len(mensal), mensal[0][0][:7], mensal[-1][0][:7]))
    print("  %d: %d pregões, %s → %s" % (ANO_RECENTE, len(recente), recente[0][0], recente[-1][0]))
    if do_mes:
        print("  %s: %d cotações intradiárias, %s → %s" % (
            MES_DETALHE, len(do_mes), do_mes[0][0], do_mes[-1][0]))


if __name__ == "__main__":
    main()
