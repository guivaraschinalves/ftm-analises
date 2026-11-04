#!/usr/bin/env python3
"""
A seção "Os motivos da virada" do assunto das midterms (dados/midterms-2026.json).
Não roda sozinho: o scripts/midterms.py chama secoes() e põe o resultado no
fim do artigo. Só biblioteca padrão; o que é baixado fica em
dados/.cache-midterms/ (fora do git) e é baixado de novo com --atualizar.

DE ONDE VÊM OS NÚMEROS

  Confiança   University of Michigan, Surveys of Consumers, leituras mensais
              ("Historical" em data.sca.isr.umich.edu/tables.php):
                tabela 2  índice por terços de renda familiar, desde out/1979
                tabela 5b índice por partido do entrevistado; mensal sem
                          buraco só desde fev/2017 (antes, meses soltos)
              ATENÇÃO: nas planilhas "Historical" o primeiro número fica na
              coluna 2; nas de média móvel, na 3. E o link de cada planilha
              leva um hash que muda todo mês: é preciso ler a página de
              tabelas para achá-lo.
  Voto        boca de urna da Edison Research para a CNN, voto para a Câmara
              (o JSON que a página da CNN lê: politics.api.cnn.io/results/
              exit-poll/<ano>-HG-US.json). 2022 e 2024 são os finais; 2026
              está no estágio 7, ainda reponderado pelo resultado apurado.
  Aprovação   The American Presidency Project (UCSB), uma tabela por
              presidente. Até dez/2025 é tudo Gallup. O Gallup parou de medir
              aprovação presidencial em 2026; a partir daí a UCSB lista outras
              pesquisas com todos os adultos (AP-NORC, CNN/SSRS, Ipsos,
              Marist...), e a conta aqui faz a média delas no mês.
              O mês de mandato conta do mês da posse (janeiro = mês 1), pela
              data de fim de campo da pesquisa.
"""
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xls import abas  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CACHE = RAIZ / "dados" / ".cache-midterms"
UA = {"User-Agent": "ftm-analises/1.0"}
ATUALIZAR = "--atualizar" in sys.argv

D, R, I = "#3B7DD8", "#D9453D", "#A979D9"
MESES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
         "October", "November", "December"]
MES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def baixar(url, nome):
    arq = CACHE / nome
    if ATUALIZAR or not arq.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers=UA)
        arq.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return arq.read_bytes()


# ---------- Michigan ----------
def michigan(tabela):
    pagina = baixar("https://data.sca.isr.umich.edu/tables.php", "umich-tabelas.html").decode("utf-8", "replace")
    m = re.search(r'get-table\.php\?c=RB&(?:amp;)?y=\d+&(?:amp;)?m=\d+&(?:amp;)?n=%s&(?:amp;)?f=xls&(?:amp;)?k=[0-9a-f]+'
                  % tabela, pagina)
    if not m:
        raise SystemExit("não achei a tabela %s de Michigan em tables.php" % tabela)
    url = "https://data.sca.isr.umich.edu/" + html.unescape(m.group(0))
    c = list(abas(baixar(url, "umich-%s.xls" % tabela)).values())[0]
    out = []
    for lin in range(max(k[0] for k in c) + 1):
        mes, ano = c.get((lin, 0)), c.get((lin, 1))
        if isinstance(mes, str) and mes.strip() in MESES and isinstance(ano, float):
            chave = "%d-%02d" % (int(ano), MESES.index(mes.strip()) + 1)
            out.append((chave, c.get((lin, 2)), c.get((lin, 3)), c.get((lin, 4))))
    return out


def rotulo_mes(chave):
    a, m = chave.split("-")
    return "%s/%s" % (MES_PT[int(m) - 1], a)


def grafico_partido():
    lin = [x for x in michigan("5b") if x[0] >= "2017-02"]
    nomes = (("Democratas", D), ("Independentes", I), ("Republicanos", R))
    return lin, {
        "id": "midterms-confianca-partido",
        "titulo": "Confiança do consumidor por partido",
        "subtitulo": "Índice de sentimento do consumidor da Universidade de Michigan, mensal, por partido do entrevistado",
        "fonte": "University of Michigan, Surveys of Consumers (tabela 5b)",
        "unidade": "pts", "eixo": {"zero": False},
        "eventos": [{"em": "2020-11", "rot": "eleição de Biden"}, {"em": "2024-11", "rot": "eleição de Trump"}],
        "series": [{"nome": n, "cor": cor, "rotulo": True,
                    "dados": [[x[0], x[k + 1]] for x in lin if x[k + 1] is not None]}
                   for k, (n, cor) in enumerate(nomes)],
    }


def grafico_renda():
    lin = michigan("2n")
    # renda é ordem, não identidade: uma cor só, mais escura com mais renda
    nomes = (("Terço de renda mais baixa", "#F7C46C"), ("Terço do meio", "#E8862A"), ("Terço de renda mais alta", "#B5520C"))
    return lin, {
        "id": "midterms-confianca-renda",
        "titulo": "Confiança do consumidor por renda",
        "subtitulo": "Índice de sentimento do consumidor da Universidade de Michigan, mensal, por terço de renda familiar",
        "fonte": "University of Michigan, Surveys of Consumers (tabela 2)",
        "unidade": "pts", "eixo": {"zero": False},
        "periodoPadrao": "10",
        "series": [{"nome": n, "cor": cor, "rotulo": True, "largura": 4,
                    "dados": [[x[0], x[k + 1]] for x in lin if x[k + 1] is not None]}
                   for k, (n, cor) in enumerate(nomes)],
    }


# ---------- boca de urna ----------
FAIXAS = [
    ("Less than $30,000", "Menos de US$ 30 mil"),
    ("$30,000 - $49,999", "US$ 30 mil a 50 mil"),
    ("$50,000 - $99,999", "US$ 50 mil a 100 mil"),
    ("$100,000 - $199,999", "US$ 100 mil a 200 mil"),
    ("$200,000 or more", "US$ 200 mil ou mais"),
]


def boca_de_urna(ano):
    d = json.loads(baixar("https://politics.api.cnn.io/results/exit-poll/%d-HG-US.json" % ano, "cnn-%d-HG-US.json" % ano))
    norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731  ("$30,000-$49,999" e "$30,000 - $49,999")
    for q in d["questions"]:
        resp = {norm(a["answer"]): a for a in q["answers"]}
        if q.get("question") == "Income" and all(norm(f) in resp for f, _ in FAIXAS):
            out = []
            for f, _ in FAIXAS:
                a = resp[norm(f)]
                v = {c.get("lastName"): c["percentage"] for c in a["candidateAnswers"]}
                out.append((a["totalPercentage"], v["Democrats"], v["Republicans"]))
            return d, out
    raise SystemExit("boca de urna de %d sem a pergunta de renda em cinco faixas" % ano)


def resposta(ano, pergunta, opcao):
    """% de todos os eleitores que deram aquela resposta."""
    d = json.loads(baixar("https://politics.api.cnn.io/results/exit-poll/%d-HG-US.json" % ano, "cnn-%d-HG-US.json" % ano))
    for q in d["questions"]:
        if q.get("question", "").strip() == pergunta:
            for a in q["answers"]:
                if a["answer"].strip() == opcao:
                    return a["totalPercentage"]
    raise SystemExit("boca de urna de %d sem %r / %r" % (ano, pergunta, opcao))


def grafico_voto_renda():
    anos = ((2022, "#C7CCD1"), (2024, "#8A9096"), (2026, "#E8A33D"))
    series, tab, estagio = [], {}, None
    for ano, cor in anos:
        d, faixas = boca_de_urna(ano)
        tab[ano] = faixas
        if ano == 2026:
            estagio = (d.get("stage"), d.get("respondents"), d.get("timestamp"))
        series.append({"nome": str(ano), "cor": cor, "tipo": "barra",
                       "dados": [[str(k), f[1] - f[2]] for k, f in enumerate(faixas)]})
    return tab, estagio, {
        "id": "midterms-voto-renda",
        "titulo": "Voto para a Câmara por renda familiar",
        "subtitulo": "Votos democratas menos republicanos, em pontos percentuais, por renda familiar anual; 2026 preliminar",
        "fonte": "Edison Research para a CNN (boca de urna)",
        "unidade": "margem", "agrupadas": True, "valores": True,
        "categorias": [rot for _, rot in FAIXAS],
        "series": series,
    }


# ---------- aprovação ----------
PRESIDENTES = [
    # (página da UCSB, nome, ano da posse)
    ("donald-j-trump-2nd-term", "Trump, 2º mandato", 2025),
    ("donald-j-trump", "Trump, 1º mandato", 2017),
    ("joseph-r-biden", "Biden", 2021),
    ("barack-obama", "Obama", 2009),
    ("george-w-bush", "Bush filho", 2001),
    ("william-j-clinton", "Clinton", 1993),
    ("george-bush", "Bush pai", 1989),
    ("ronald-reagan", "Reagan", 1981),
    ("jimmy-carter", "Carter", 1977),
]
MESES_MANDATO = 24


def aprovacao(pagina, posse):
    t = baixar("https://www.presidency.ucsb.edu/statistics/data/%s-public-approval" % pagina,
               "ucsb-%s.html" % pagina).decode("utf-8", "replace")
    por_mes = {}
    for lin in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        c = [html.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", lin, re.S)]
        if len(c) < 3 or not re.match(r"\d{1,2}/\d{1,2}/\d{4}$", c[1]) or not c[2].isdigit():
            continue
        m, _, a = (int(x) for x in c[1].split("/"))
        k = (a - posse) * 12 + m       # janeiro do ano da posse = mês 1
        if 1 <= k <= MESES_MANDATO:
            por_mes.setdefault(k, []).append(int(c[2]))
    return {k: sum(v) / len(v) for k, v in por_mes.items()}


def grafico_aprovacao():
    ap = {nome: aprovacao(pg, posse) for pg, nome, posse in PRESIDENTES}
    antigos = [nome for _, nome, posse in PRESIDENTES if posse <= 2009]
    faixa = []
    for k in range(1, MESES_MANDATO + 1):
        vals = [ap[n][k] for n in antigos if k in ap[n]]
        if len(vals) >= 3:
            faixa.append([str(k - 1), round(min(vals), 1), round(max(vals), 1)])
    linha = lambda n: [[str(k - 1), round(v, 1)] for k, v in sorted(ap[n].items())]  # noqa: E731
    cats = [("mês %d" % k) if k in (1, 6, 12, 18, 24) else "" for k in range(1, MESES_MANDATO + 1)]
    return ap, {
        "id": "midterms-aprovacao",
        "titulo": "Aprovação do presidente nos dois primeiros anos de mandato",
        "subtitulo": "% de adultos que aprovam o presidente, média do mês; o mês 1 é o da posse",
        "fonte": "The American Presidency Project (UCSB), com Gallup até dez/2025 e outras pesquisas depois",
        "unidade": "pct1", "eixo": {"zero": False}, "buracoMax": 2,  # Gallup pulou nov/2022 com Biden
        "categorias": cats,
        "eventos": [{"em": "22", "rot": "eleição de meio de mandato"}],
        "series": [
            {"nome": "De Carter (1976) a Obama: menor e maior no mesmo mês", "cor": "#95A5A6", "tipo": "faixa",
             "opacidade": 0.28, "dados": faixa},
            {"nome": "Biden", "cor": D, "largura": 4, "dados": linha("Biden")},
            {"nome": "Trump, 1º mandato", "cor": "#F2A08F", "largura": 4, "traco": "pontilhado",
             "dados": linha("Trump, 1º mandato")},
            {"nome": "Trump, 2º mandato", "cor": R, "rotulo": True, "dados": linha("Trump, 2º mandato")},
        ],
    }


# ---------- texto ----------
def secoes():
    partido, g_partido = grafico_partido()
    renda, g_renda = grafico_renda()
    voto, estagio, g_voto = grafico_voto_renda()
    ap, g_ap = grafico_aprovacao()

    ult = partido[-1]
    p = {x[0]: x for x in partido}
    rmin = {k: min(renda, key=lambda x: x[k]) for k in (1, 2, 3)}
    nf = lambda v: ("%.1f" % v).replace(".", ",")  # noqa: E731
    marg = lambda ano, i: voto[ano][i][1] - voto[ano][i][2]  # noqa: E731
    sinal = lambda v: ("+%d" % v) if v > 0 else str(v)  # noqa: E731
    t2 = ap["Trump, 2º mandato"]
    k_ult = max(t2)

    print("motivos: Michigan até %s; boca de urna 2026 no estágio %s, %s entrevistas, %s"
          % (ult[0], *estagio))
    print("  aprovação de Trump no mês %d: %.1f%%" % (k_ult, t2[k_ult]))

    texto_partido = (
        "**A confiança do consumidor americano virou uma pergunta sobre o partido do presidente.** Na pesquisa "
        "da Universidade de Michigan, o sentimento de democratas e republicanos troca de lugar a cada eleição "
        "presidencial: em outubro de 2024, os democratas estavam em %s e os republicanos em %s; dois meses "
        "depois da vitória de Trump, a ordem tinha se invertido. O que decide, então, é quem fica no meio. "
        "Os independentes chegaram em %s a %s pontos, o menor nível da série mensal, que começa em 2017. Em "
        "%s estavam em %s, mais perto dos democratas (%s) que dos republicanos (%s)."
    ) % (nf(p["2024-10"][1]), nf(p["2024-10"][3]),
         rotulo_mes(min(partido, key=lambda x: x[2])[0]), nf(min(x[2] for x in partido)),
         rotulo_mes(ult[0]), nf(ult[2]), nf(ult[1]), nf(ult[3]))

    assert rmin[1][0] == rmin[2][0], "revisar a frase de renda: mínimos do terço baixo e do meio em meses diferentes"
    texto_renda = (
        "**A queda pesou mais para quem ganha menos.** Michigan divide os entrevistados em três terços pela renda "
        "familiar, e em %s o terço de renda mais baixa e o do meio marcaram os menores níveis desde o início "
        "da série, em 1979: %s e %s pontos. O terço de renda mais alta caiu menos e ficou acima do próprio "
        "mínimo, de %s. Em %s, os três estavam em %s, %s e %s."
    ) % (rotulo_mes(rmin[1][0]), nf(rmin[1][1]), nf(rmin[2][2]),
         rotulo_mes(rmin[3][0]), rotulo_mes(renda[-1][0]),
         nf(renda[-1][1]), nf(renda[-1][2]), nf(renda[-1][3]))

    mudanca = [marg(2026, i) - marg(2024, i) for i in range(5)]
    texto_voto = (
        "**Na urna, a virada apareceu em todas as faixas de renda.** Pela boca de urna, os democratas venceram "
        "em todas as cinco faixas, de quem ganha menos de US$ 30 mil por ano (%s pontos) a quem ganha mais "
        "de US$ 200 mil (%s). Em 2024, os republicanos tinham vencido a Câmara entre US$ 30 mil e 100 mil. "
        "Na comparação com 2024, a margem democrata cresceu %d pontos abaixo de US$ 30 mil, %d de US$ 30 mil "
        "a 50 mil e %d de US$ 50 mil a 100 mil, contra %d de US$ 100 mil a 200 mil e %d acima de US$ 200 mil.\n\n"
        "Os números de 2026 ainda são preliminares: a boca de urna é reponderada pelo resultado apurado nos "
        "dias seguintes à eleição. E as faixas são em dólares de cada ano, sem correção pela inflação."
    ) % (sinal(marg(2026, 0)), sinal(marg(2026, 4)), *(round(v) for v in mudanca))
    assert min(mudanca[:3]) > max(mudanca[3:]), "revisar a frase da mudança por renda: o contraste mudou"

    comp = sorted(((n, v[k_ult]) for n, v in ap.items() if k_ult in v and n != "Trump, 2º mandato"),
                  key=lambda x: x[1])
    assert t2[k_ult] < comp[0][1], "Trump não é o mais baixo no mês %d: revisar o texto" % k_ult
    desap = resposta(2026, "Opinion of Trump as president", "Disapprove")
    piorou = resposta(2026, "Effect of Trump's policies on economy", "Worsened conditions")
    tarifa = resposta(2026, "Effect of Trump's tariffs on national economy", "Have hurt")
    texto_ap = (
        "**Trump chegou à eleição como o presidente mais impopular nesse ponto do mandato.** Em %s de "
        "mandato, a aprovação média foi de %s%%; o mais baixo entre os antecessores no mesmo mês foi %s, "
        "com %s%%. Na boca de urna, %d%% dos eleitores disseram desaprovar o presidente, %d%% disseram "
        "que a política econômica dele piorou a economia e %d%%, que as tarifas prejudicaram a economia do país.\n\n"
        "Até dezembro de 2025 a série é a do Gallup, a mesma de todos os presidentes do gráfico. O Gallup "
        "deixou de medir aprovação presidencial em 2026; dali em diante a linha de Trump é a média das "
        "pesquisas com todos os adultos reunidas pela UCSB, que mede um pouco diferente."
    ) % ("outubro do segundo ano" if k_ult == 22 else "%d meses" % k_ult,
         nf(t2[k_ult]), comp[0][0], nf(comp[0][1]), desap, piorou, tarifa)

    return [
        {"titulo": "Os motivos da virada",
         "texto": "Os democratas tiraram dos republicanos a Câmara e o Senado. Quatro séries ajudam a entender "
                  "o tamanho da mudança: a confiança do consumidor por partido e por renda, o voto por renda e a "
                  "aprovação do presidente.\n\n" + texto_partido,
         "graficos": [g_partido]},
        {"titulo": "", "texto": texto_renda, "graficos": [g_renda]},
        {"titulo": "", "texto": texto_voto, "graficos": [g_voto]},
        {"titulo": "", "texto": texto_ap, "graficos": [g_ap]},
    ]
