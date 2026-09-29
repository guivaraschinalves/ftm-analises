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
"""
import csv
import datetime
import io
import json
import os
import time
import urllib.error
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "juros-eua.json")

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s"

BRANCO, AZUL, VERMELHO, CIANO, LARANJA = "#FFFFFF", "#4F81BD", "#C0504D", "#4BACC6", "#F79646"

ANO_RECENTE = 2026


def baixar(url, tentativas=4):
    """Sem headers de propósito: com User-Agent de navegador o FRED trava."""
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
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


def main():
    diaria = baixar_serie("DGS10")
    mensal = baixar_serie("GS10")
    recente = do_ano(diaria, ANO_RECENTE)
    if not recente:
        raise RuntimeError("nenhum pregão de %d na série diária" % ANO_RECENTE)

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
                    "nota": (
                        "De %s (%s) a %s (%s): %d pregões, com mínima de %s em %s e máxima de %s em "
                        "%s." % (data_br(ini_rec[0]), fmt(ini_rec[1]), data_br(fim_rec[0]), fmt(fim_rec[1]),
                                 len(recente), fmt(piso_rec[1]), data_br(piso_rec[0]),
                                 fmt(teto_rec[1]), data_br(teto_rec[0]))
                    ),
                }],
            },
        ],
    }

    with io.open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("gravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))
    print("  diária: %d pontos, %s → %s" % (len(diaria), diaria[0][0], diaria[-1][0]))
    print("  mensal: %d pontos, %s → %s" % (len(mensal), mensal[0][0][:7], mensal[-1][0][:7]))
    print("  %d: %d pregões, %s → %s" % (ANO_RECENTE, len(recente), recente[0][0], recente[-1][0]))


if __name__ == "__main__":
    main()
