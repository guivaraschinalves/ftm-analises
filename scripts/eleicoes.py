#!/usr/bin/env python3
"""
Monta dados/eleicoes.json — o assunto "A bolsa nas eleições presidenciais" do
site, a partir das séries diárias do Ibovespa no Ipeadata.

Uso:
    python3 scripts/eleicoes.py

Só usa a biblioteca padrão. Os dados vêm da API OData aberta do Ipea, sem
chave:

    GM366_IBVSP366   Ibovespa, fechamento diário (desde 27/04/1993)
    GM366_IBVSPV366  Ibovespa, volatilidade (desde 26/05/1993)

A série de volatilidade do Ipea **não é usada nas contas**. Ela é desvio-padrão
móvel de ~21 pregões (confere com o nosso cálculo: correlação 1,000, razão
1,025), o que significa que olha um mês para trás — no dia seguinte à eleição
ela ainda é quase toda feita de dias anteriores à eleição. Para medir "antes" e
"depois" com janelas que eu controlo, a volatilidade aqui é recalculada dos
fechamentos. A do Ipea serve de conferência, e o script a compara a cada rodada.

O QUE SE MEDE

  reação    último fechamento ANTES do voto → primeiro fechamento DEPOIS.
            Como a eleição é no domingo, isso costuma ser sexta → segunda.
            Em 1994 a eleição foi numa segunda-feira (a única fora do padrão) e
            a bolsa não abriu no dia: ali é sexta → terça.

  dp do ano desvio-padrão dos retornos diários daquele ano civil. É a régua que
            torna 1994 comparável a 2022: um movimento de 3% valia pouco num
            ano em que a bolsa andava 4% por dia, e vale muito num de 1,3%.

  razão de  desvio-padrão dos 21 pregões depois ÷ o dos 21 antes.
  volatil.  ATENÇÃO: para o 2º turno essa janela de 21 pregões **inclui o 1º
            turno**, que fica a 13-18 pregões de distância. Por isso o script
            calcula também a versão limpa, que usa só os pregões entre os dois
            turnos. A diferença não é detalhe: na janela suja a volatilidade
            parecia cair depois do 2º turno em 5 de 6 eleições; na limpa, 3 de
            6 — ou seja, o efeito era da medida, não do mundo.

AS ELEIÇÕES. Oito presidenciais diretas desde o Real, 14 turnos ao todo: 1994 e
1998 foram decididas no 1º turno e não têm segundo.
"""
import datetime
import json
import math
import os
import statistics as st
import sys
import urllib.request

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SAIDA = os.path.join(RAIZ, "dados", "eleicoes.json")

API = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='%s')"
SERIE_FECHAMENTO = "GM366_IBVSP366"
SERIE_VOLATILIDADE = "GM366_IBVSPV366"

FONTE = "Ipeadata (B3/BM&FBovespa) e TSE"

# Cores do tema do Office, as mesmas dos outros sites.
AZUL, VERMELHO, VERDE, ROXO, LARANJA = "#4F81BD", "#C0504D", "#9BBB59", "#8064A2", "#F79646"
BRANCO, CINZA = "#FFFFFF", "#95A5A6"

# (ano, 1º turno, 2º turno ou None, vencedor ou None se ainda não se sabe)
#
# "2º turno = None" quer dizer que o 1º turno DECIDIU a eleição (1994 e 1998).
# Não confundir com um 2º turno marcado que ainda não aconteceu: 2026 tem data
# ali, e é isso que faz o script classificar o 1º turno de 2026 como votação que
# não resolveu — embora nenhuma medida do dia 25/10 exista ainda.
ELEICOES = [
    (1994, "1994-10-03", None, "FHC"),
    (1998, "1998-10-04", None, "FHC"),
    (2002, "2002-10-06", "2002-10-27", "Lula"),
    (2006, "2006-10-01", "2006-10-29", "Lula"),
    (2010, "2010-10-03", "2010-10-31", "Dilma"),
    (2014, "2014-10-05", "2014-10-26", "Dilma"),
    (2018, "2018-10-07", "2018-10-28", "Bolsonaro"),
    (2022, "2022-10-02", "2022-10-30", "Lula"),
    (2026, "2026-10-04", "2026-10-25", None),
]

JANELA = 21          # pregões de cada lado, nas razões de volatilidade
CAMINHO = 60         # pregões de cada lado, no gráfico de caminho


def baixar(codigo):
    """Série diária do Ipea → {"AAAA-MM-DD": valor}. Sem chave, sem cabeçalho."""
    with urllib.request.urlopen(API % codigo, timeout=240) as r:
        bruto = json.load(r)["value"]
    return {x["VALDATA"][:10]: x["VALVALOR"] for x in bruto if x.get("VALVALOR") is not None}


# --------------------------------------------------------------------------
# a base
# --------------------------------------------------------------------------

class Base:
    def __init__(self, fechamento):
        self.fech = fechamento
        self.pregoes = sorted(fechamento)
        self.idx = {d: i for i, d in enumerate(self.pregoes)}
        self.logr = {}
        for i in range(1, len(self.pregoes)):
            a, b = self.pregoes[i-1], self.pregoes[i]
            self.logr[b] = math.log(self.fech[b] / self.fech[a]) * 100
        self.dp_ano = {}
        porano = {}
        for d, r in self.logr.items():
            porano.setdefault(d[:4], []).append(r)
        for ano, rs in porano.items():
            if len(rs) > 2:
                self.dp_ano[ano] = st.stdev(rs)
        # a mesma régua, para o horizonte de 60 pregões: o desvio-padrão dos
        # retornos de 60 pregões daquele ano. Um retorno diário e um de três
        # meses não cabem no mesmo eixo em %, mas cabem medidos cada um na sua
        # própria régua — é o que torna os dois comparáveis no gráfico.
        self.dp_ano60 = {}
        por60 = {}
        for i in range(len(self.pregoes) - CAMINHO):
            a, b = self.pregoes[i], self.pregoes[i + CAMINHO]
            por60.setdefault(a[:4], []).append((self.fech[b] / self.fech[a] - 1) * 100)
        for ano, rs in por60.items():
            if len(rs) > 2:
                self.dp_ano60[ano] = st.stdev(rs)

    def antes(self, data):
        """Último pregão em `data` ou antes dela."""
        import bisect
        i = bisect.bisect_right(self.pregoes, data) - 1
        return self.pregoes[i] if i >= 0 else None

    def depois(self, data):
        """Primeiro pregão depois de `data`."""
        import bisect
        i = bisect.bisect_right(self.pregoes, data)
        return self.pregoes[i] if i < len(self.pregoes) else None

    def desloca(self, pregao, n):
        j = self.idx[pregao] + n
        return self.pregoes[j] if 0 <= j < len(self.pregoes) else None

    def ret(self, a, b):
        return None if a is None or b is None else (self.fech[b] / self.fech[a] - 1) * 100

    def vol(self, ini, fim):
        """Desvio-padrão dos retornos diários entre dois pregões, inclusive."""
        rs = [self.logr[self.pregoes[i]] for i in range(self.idx[ini], self.idx[fim] + 1)
              if self.pregoes[i] in self.logr]
        return st.stdev(rs) if len(rs) > 2 else None


def eventos(base):
    """Um registro por turno, com tudo o que os gráficos usam."""
    fora = []
    por_ano_1t = {}
    for ano, t1, t2, vencedor in ELEICOES:
        for turno, data in (("1T", t1), ("2T", t2)):
            if not data:
                continue
            d0, d1 = base.antes(data), base.depois(data)
            if d1 is None:
                continue          # votação ainda não ocorreu (ou não houve pregão depois)
            dp = base.dp_ano[d0[:4]]
            e = dict(ano=ano, turno=turno, data=data, d0=d0, d1=d1, vencedor=vencedor,
                     rot="%d %s" % (ano, turno), dp_ano=dp)
            e["reacao"] = base.ret(d0, d1)
            e["reacao_dp"] = e["reacao"] / dp
            # a eleição resolveu quem é o presidente?
            e["resolve"] = (turno == "2T") or (t2 is None)
            # volatilidade, janela de 21 pregões de cada lado
            # Janela que ainda não fechou vira None, e o gráfico simplesmente
            # não desenha aquele ponto. É o caso do 1º turno de 2026, com dois
            # pregões de vida: a reação dele existe, a volatilidade dos 21
            # pregões seguintes não — e inventar uma com os dias que há seria
            # comparar um mês com dois dias.
            fim_vol = base.desloca(d1, JANELA - 1)
            e["vol_antes"] = base.vol(base.desloca(d0, -(JANELA - 1)), d0)
            e["vol_depois"] = base.vol(d1, fim_vol) if fim_vol else None
            e["razao"] = e["vol_depois"] / e["vol_antes"] if e["vol_depois"] else None
            e["completo"] = fim_vol is not None
            # retorno nos 60 pregões seguintes, já sem a reação
            fim = base.desloca(d1, CAMINHO - 1)
            e["pos60"] = base.ret(d1, fim) if fim else None
            dp60 = base.dp_ano60.get(d0[:4])
            e["pos60_dp"] = e["pos60"] / dp60 if (dp60 and e["pos60"] is not None) else None
            e["completo60"] = e["pos60"] is not None
            if turno == "1T":
                por_ano_1t[ano] = e
            else:
                # janela limpa: só os pregões ENTRE os turnos, sem o 1º turno
                t1e = por_ano_1t[ano]
                ini = base.desloca(t1e["d1"], 1)
                n = base.idx[d0] - base.idx[ini] + 1
                e["razao_limpa"] = (base.vol(d1, base.desloca(d1, n - 1))
                                    / base.vol(ini, d0))
                e["entre_turnos"] = base.ret(t1e["d1"], d0)
                e["pregoes_entre"] = n
            fora.append(e)
    for e in fora:
        e.setdefault("razao_limpa", e["razao"])      # no 1º turno não há o que limpar
    return fora


def caminho_vol(base, evs):
    """Volatilidade móvel de 21 pregões ao longo de −60/+60, dividida pelo
    desvio-padrão do próprio ano — 1,00 é "o normal daquele ano".

    Por que volatilidade e não preço: o caminho do índice em torno da eleição é
    indistinguível de qualquer outro trecho da série (os percentis das janelas
    ficam entre 46 e 58), então desenhá-lo insinuaria um padrão que os testes
    negam. Já a agitação separa os dois grupos com clareza, e é lisa por
    construção — cada ponto é a média de 21 pregões."""
    grupos = {"resolve": [], "adia": []}
    for e in evs:
        if not e.get("completo60"):
            continue              # 2026 ainda não tem os 60 pregões seguintes
        serie = {}
        for k in range(-CAMINHO, CAMINHO + 1):
            p = base.desloca(e["d0"], k) if k <= 0 else base.desloca(e["d1"], k - 1)
            if not p:
                continue
            ini_ = base.desloca(p, -(JANELA - 1))
            v = base.vol(ini_, p) if ini_ else None
            if v:
                serie[k] = v / base.dp_ano[e["d0"][:4]]
        grupos["resolve" if e["resolve"] else "adia"].append(serie)
    fora = {}
    for nome, lista in grupos.items():
        fora[nome] = {}
        for k in range(-CAMINHO, CAMINHO + 1):
            vs = [s[k] for s in lista if k in s]
            if len(vs) == len(lista):
                fora[nome][k] = st.median(vs)
    return fora


# --------------------------------------------------------------------------
# estatística
# --------------------------------------------------------------------------

def sinal(vals):
    """Teste de sinal: a chance de ver um desequilíbrio destes, ou maior, se
    positivo e negativo fossem igualmente prováveis (cara ou coroa)."""
    n = len(vals)
    k = sum(1 for v in vals if v > 0)
    p = sum(math.comb(n, i) for i in range(n + 1) if abs(i - n / 2) >= abs(k - n / 2)) / 2 ** n
    return k, n, min(1.0, p)


def permutacao(a, b, reps=50000, semente=11):
    """Embaralha os dois grupos entre si muitas vezes e conta com que
    frequência o acaso separa as médias tanto quanto o observado."""
    import random
    rnd = random.Random(semente)
    obs = abs(st.mean(a) - st.mean(b))
    tudo = a + b
    cnt = 0
    for _ in range(reps):
        p = rnd.sample(tudo, len(tudo))
        if abs(st.mean(p[:len(a)]) - st.mean(p[len(a):])) >= obs:
            cnt += 1
    return obs, cnt / reps


# --------------------------------------------------------------------------
# os gráficos
# --------------------------------------------------------------------------

def serie(nome, cor, pares, casas=2, **extra):
    return dict(nome=nome, cor=cor,
                dados=[[str(k), round(v, casas)] for k, v in pares if v is not None], **extra)


def g_reacao(evs):
    rots = [e["rot"] for e in evs]
    def barras(chave, casas):
        return [serie("1º turno", AZUL, [(i, e[chave]) for i, e in enumerate(evs) if e["turno"] == "1T"], casas, tipo="barra"),
                serie("2º turno", LARANJA, [(i, e[chave]) for i, e in enumerate(evs) if e["turno"] == "2T"], casas, tipo="barra")]
    return dict(
        id="eleicoes-reacao",
        titulo="A reação da bolsa ao resultado",
        subtitulo="Variação do Ibovespa do último pregão antes do voto para o primeiro depois",
        categorias=rots,
        unidade="%",
        fonte=FONTE,
        variantes=[dict(rot="em %", series=barras("reacao", 2), unidade="%"),
                   dict(rot="em desvios-padrão do ano", series=barras("reacao_dp", 2), unidade="dp")],
        nota="A eleição é no domingo, então esta é quase sempre a variação de sexta para segunda — "
             "o fim de semana concentra a reação, porque o resultado sai com a bolsa fechada. A "
             "exceção é 1994, única eleição numa segunda-feira, e com a bolsa fechada no dia: ali "
             "a conta vai de sexta a terça. O recorte “em desvios-padrão do ano” divide cada "
             "reação pelo desvio-padrão dos retornos diários daquele ano civil. **Desvio-padrão** é "
             "a medida de quanto um número costuma se afastar da média: aqui, de quanto a bolsa "
             "costuma andar num dia qualquer daquele ano. Serve para comparar épocas — 3% em 1994, "
             "quando a bolsa andava 3,9% por dia, é um dia morno; 3% em 2010, quando andava 1,3%, "
             "é um dia agitado. Sem essa correção os anos 1990 dominariam o gráfico por serem "
             "simplesmente mais voláteis.\n\n"
             "**O 1º turno de 2026 é o maior movimento da série**: +7,70%, ou +6,06 desvios-padrão "
             "do ano — quase o dobro do recorde anterior (+3,28 dp em 2018). Ele é o único evento "
             "que aparece neste gráfico e não nos outros: a reação precisa de um pregão depois da "
             "votação, e os demais precisam de 21 ou 60. O 2º turno de 2026, marcado para 25 de "
             "outubro, ainda não aconteceu.")


def referencia(evs):
    """Linha reta em 1,00: acima dela a bolsa ficou mais agitada do que estava,
    abaixo, mais calma. Sem ela a barra não tem contra o que ser lida."""
    return serie("Mesma agitação de antes (1,00)", CINZA,
                 [(i, 1.0) for i in range(len(evs))], 2, largura=3, traco="pontilhado")


def g_volatilidade(todos):
    # só quem já tem os 21 pregões depois: 2026 fica de fora, e a nota diz por quê
    evs = [e for e in todos if e.get("completo")]
    rots = [e["rot"] for e in evs]
    def barras(chave):
        return [serie("Eleição que não resolveu (foi para 2º turno)", VERMELHO,
                      [(i, e[chave]) for i, e in enumerate(evs) if not e["resolve"]], 2, tipo="barra"),
                serie("Eleição que definiu o presidente", VERDE,
                      [(i, e[chave]) for i, e in enumerate(evs) if e["resolve"]], 2, tipo="barra")]
    return dict(
        id="eleicoes-volatilidade",
        titulo="A agitação depois do resultado",
        subtitulo="Volatilidade dos %d pregões seguintes dividida pela dos %d anteriores" % (JANELA, JANELA),
        categorias=rots,
        unidade="x",
        fonte=FONTE,
        # a barra parte do zero (é barra), então o "zero: false" não cabe aqui;
        # quem marca a fronteira é a linha de 1,00
        variantes=[dict(rot="janela de 21 pregões", series=barras("razao") + [referencia(evs)]),
                   dict(rot="sem sobreposição", series=barras("razao_limpa") + [referencia(evs)])],
        nota="**Volatilidade** aqui é o desvio-padrão dos retornos diários: o tamanho típico do "
             "sobe-e-desce, não a direção dele. A barra é a volatilidade depois dividida pela de "
             "antes: acima de 1 a bolsa ficou mais agitada do que estava; abaixo de 1, mais calma. "
             "Os dois recortes existem porque a medida tem uma armadilha. No primeiro, a janela de "
             "21 pregões antes do **2º** turno inclui o 1º turno, que fica a 13-18 pregões de "
             "distância — ou seja, compara um “antes” já contaminado pela própria agitação "
             "eleitoral com um “depois” limpo, e por construção faz a volatilidade parecer cair. "
             "O recorte “sem sobreposição” usa, no 2º turno, só os pregões entre as duas votações, "
             "e o mesmo número de pregões depois. A conclusão muda: na janela de 21 a volatilidade "
             "cai em 5 das 6 segundas voltas; sem sobreposição, em 3 de 6.\n\n"
             "O 1º turno de 2026 não aparece aqui: a conta precisa de 21 pregões depois da "
             "votação e existem dois. Ele está no gráfico da reação, que só precisa de um.")


def g_caminho(base, evs, cam):
    rots = []
    for k in range(-CAMINHO, CAMINHO + 1):
        rots.append("%+d" % k if k % 20 == 0 and k != 0 else ("véspera" if k == 0 else ""))
    def pares(nome):
        return [(k + CAMINHO, cam[nome].get(k)) for k in range(-CAMINHO, CAMINHO + 1)]
    return dict(
        id="eleicoes-caminho",
        titulo="A agitação em torno da votação",
        subtitulo="Em cada ponto: quanto a bolsa oscilou no mês anterior a ele, "
                  "comparado ao normal daquele ano. 1,00 é um mês comum",
        categorias=rots,
        unidade="x",
        fonte=FONTE,
        eixo=dict(zero=False),
        # a votação é no domingo e não tem pregão: o marcador fica na véspera,
        # que é o último dado que existe antes dela
        eventos=[dict(em=str(CAMINHO), rot="votação (domingo)")],
        series=[
            serie("Votação que definiu o presidente", VERDE, pares("resolve"), 3, largura=6, rotulo=True),
            serie("Votação que foi para 2º turno", VERMELHO, pares("adia"), 3, largura=6, rotulo=True),
        ],
        nota="**Não há ponto no dia da votação, porque não há pregão no domingo.** O eixo conta "
             "pregões, e o zero é a **véspera** — o último fechamento antes do voto. O primeiro "
             "ponto depois dele, o +1, já é a segunda-feira. O fim de semana é o buraco entre os "
             "dois, e é nele que o resultado sai.\n\n"
             "Como ler um ponto qualquer: ele responde “quanto a bolsa oscilou no mês que "
             "terminou aqui, comparado com o quanto ela costuma oscilar neste ano?”. A conta é o "
             "desvio-padrão dos retornos dos 21 pregões **anteriores** ao ponto, dividido pelo "
             "desvio-padrão do ano inteiro. 1,00 é um mês tão agitado quanto o ano costuma ser; "
             "1,25 é um mês 25% mais agitado que o normal daquele ano. A divisão pelo ano é o que "
             "torna 1994 comparável a 2026 — sem ela os anos 1990 dominariam tudo, por serem "
             "simplesmente mais voláteis.\n\n"
             "A linha **não é a média**: é a **mediana** das eleições de cada grupo, ou seja, o "
             "valor do meio quando se ordenam os casos. Com 6 e 8 eleições, a média seria "
             "arrastada por um ano extremo — 1998 teve a crise russa no meio da eleição. "
             "60 pregões são cerca de três meses. Como a janela de 21 pregões olha para trás, o "
             "efeito de uma data aparece espalhado nos 21 pregões seguintes a ela, e não de um "
             "dia para o outro: é por isso que a linha vermelha sobe devagar depois da véspera, "
             "em vez de dar um salto. "
             "**Não há um gráfico equivalente para o preço do índice** porque não há o que mostrar: "
             "o retorno acumulado em qualquer janela em torno da eleição cai entre os percentis 46 "
             "e 58 da distribuição de todas as janelas do mesmo tamanho desde 1993 — ou seja, é "
             "indistinguível de um trecho qualquer da série.\n\n"
             "O 1º turno de 2026 não entra nestas linhas: elas precisam de 60 pregões de cada "
             "lado da votação, e dele só há dois.")


def g_reversao(todos):
    evs = [e for e in todos if e.get("completo60")]
    rots = [e["rot"] for e in evs]
    def par(c_reacao, c_pos, casas):
        return [serie("Reação do primeiro pregão", AZUL,
                      [(i, e[c_reacao]) for i, e in enumerate(evs)], casas, tipo="barra"),
                serie("60 pregões seguintes", BRANCO,
                      [(i, e[c_pos]) for i, e in enumerate(evs)], casas, largura=6)]
    return dict(
        id="eleicoes-reversao",
        titulo="A reação e o que veio depois dela",
        subtitulo="Reação do primeiro pregão e retorno dos 60 pregões seguintes",
        categorias=rots,
        unidade="%",
        fonte=FONTE,
        variantes=[dict(rot="cada um na sua régua", series=par("reacao_dp", "pos60_dp", 2), unidade="dp"),
                   dict(rot="em %", series=par("reacao", "pos60", 2), unidade="%")],
        nota="A barra é o primeiro pregão depois do voto; a linha é o que a bolsa fez nos 60 "
             "pregões seguintes, já sem contar esse primeiro dia — as duas medidas não se "
             "sobrepõem. Elas andam em sentidos opostos em 10 dos 14 turnos.\n\n"
             "Os dois recortes medem a mesma coisa de formas diferentes. “Em %” é o número "
             "cru, e nele a linha esmaga as barras: um dia rende poucos por cento e três meses "
             "rendem dezenas, então o desenho esconde justamente o que se quer comparar. “Cada "
             "um na sua régua” divide cada medida pelo **desvio-padrão** do seu próprio horizonte "
             "naquele ano — a reação pelo desvio-padrão dos retornos diários, os 60 pregões pelo "
             "dos retornos de 60 pregões. Desvio-padrão é o tamanho típico do desvio em torno da "
             "média; dividir por ele responde “quão fora do comum foi isto, para aquele ano e "
             "aquele prazo?”, e é o que permite pôr os dois no mesmo eixo.\n\n"
             "A **correlação** entre as duas séries é −0,43. Correlação é um número entre −1 e +1 "
             "que resume se duas medidas sobem juntas (positiva), andam em sentidos contrários "
             "(negativa) ou não têm relação (perto de zero). O sinal negativo sugere que reações "
             "grandes costumam ser devolvidas, mas o valor está longe de −1 e, com 14 casos, pode "
             "ser acaso: embaralhando os pares ao acaso, uma correlação desse tamanho aparece em "
             "13% das vezes. É indício, não conclusão.\n\n"
             "O 1º turno de 2026 não aparece aqui: faltam os 60 pregões seguintes.")


def ano_a_ano(base):
    """Retorno do ano partido em dois pela eleição, e a mesma partição nos anos
    sem eleição — que é a régua.

    1994 fica de fora: +1.360% do fim de 1993 à véspera da eleição não é o
    mercado, é a inflação do ano em que o Real estreou (em termos reais o índice
    caiu no período). Qualquer média que o inclua vira um número sobre 1994.
    Nos outros gráficos ele continua, porque lá a medida é de um dia e a
    inflação de um fim de semana é irrelevante.

    Nos anos sem eleição o corte é a véspera do 1º domingo de outubro, para a
    janela do calendário ser a mesma."""
    import datetime
    datas = {ano: t1 for ano, t1, _, _ in ELEICOES}

    def ultimo_do_ano(ano):
        ds = [d for d in base.pregoes if d[:4] == str(ano)]
        return ds[-1] if ds else None

    def corte(ano):
        if ano in datas:
            return base.antes(datas[ano])
        d = datetime.date(ano, 10, 1)
        while d.weekday() != 6:
            d += datetime.timedelta(days=1)
        return base.antes(d.isoformat())

    fora = []
    for ano in range(1995, int(base.pregoes[-1][:4]) + 1):
        ant, c, fim = ultimo_do_ano(ano - 1), corte(ano), ultimo_do_ano(ano)
        if not (ant and c and fim) or c <= ant:
            continue
        # o ano ainda corre: "até o fim" só existe quando o ano acabou
        acabou = fim > c and (ano < int(base.pregoes[-1][:4]) or base.pregoes[-1][5:7] == "12")
        fora.append(dict(ano=ano, eleicao=ano in datas, ate=base.ret(ant, c),
                         depois=base.ret(c, fim) if acabou else None,
                         todo=base.ret(ant, fim) if acabou else None))
    return fora


def mediana_sem_eleicao(anos, chave):
    v = [a[chave] for a in anos if not a["eleicao"] and a[chave] is not None]
    return st.median(v)


def g_ano(anos):
    """Os dois pedaços do ano eleitoral, cada um contra a mediana dos anos sem
    eleição — que é a única forma de saber se o número é grande ou não."""
    el = [a for a in anos if a["eleicao"]]
    rots = [str(a["ano"]) for a in el]
    def barras(chave):
        base_ = mediana_sem_eleicao(anos, chave)
        return [serie("Ano de eleição", AZUL,
                      [(i, a[chave]) for i, a in enumerate(el)], 2, tipo="barra"),
                serie("Mediana dos anos sem eleição (%+.1f%%)" % base_, CINZA,
                      [(i, base_) for i in range(len(el))], 2, largura=3, traco="pontilhado")]
    return dict(
        id="eleicoes-ano",
        titulo="O ano eleitoral, partido em dois pela votação",
        subtitulo="Retorno do Ibovespa em cada metade, contra o mesmo trecho dos anos sem eleição",
        categorias=rots,
        unidade="%",
        fonte=FONTE,
        variantes=[
            dict(rot="do início do ano à véspera", series=barras("ate")),
            dict(rot="da véspera ao fim do ano", series=barras("depois")),
        ],
        nota="O ano é cortado na **véspera do 1º turno** — o último pregão antes da primeira "
             "votação. A primeira metade vai do último pregão do ano anterior até esse corte; a "
             "segunda, do corte até o último pregão do ano, e portanto inclui a reação, o período "
             "entre turnos e o 2º turno.\n\n"
             "A linha pontilhada é a **mediana dos anos sem eleição**, medidos na mesma janela do "
             "calendário: do fim do ano anterior à véspera do 1º domingo de outubro, e daí ao fim "
             "do ano. Sem ela não há como saber se +6% num trecho é muito ou pouco — é mediana, e "
             "não média, porque alguns anos (1999, 2003) multiplicariam a média sozinhos.\n\n"
             "**1994 não está aqui.** Do fim de 1993 à véspera da eleição o índice subiu 1.360%, o "
             "que não é o mercado e sim a inflação do ano em que o Real estreou — em termos reais "
             "ele caiu no período. Um número desses não divide eixo com +6%, e qualquer média que "
             "o inclua passa a ser um número sobre 1994. Nos outros gráficos ele continua, porque "
             "lá a medida é de um dia, e a inflação de um fim de semana é irrelevante.\n\n"
             "**2026 só tem a primeira metade**: o ano não acabou."
    )


def pct(v):
    return ("%+.1f%%" % v).replace(".", ",")


def g_ano_tabela(anos):
    el = [a for a in anos if a["eleicao"]]
    # as medianas entram na tabela E na nota: calculadas aqui, uma vez, para o
    # texto não poder discordar do número logo acima dele
    med_el_ate = st.median([a["ate"] for a in el])
    med_el_dep = st.median([a["depois"] for a in el if a["depois"] is not None])
    med_el_todo = st.median([a["todo"] for a in el if a["todo"] is not None])
    linhas = []
    for a in el:
        linhas.append([dict(t=str(a["ano"]), forte=True), num(a["ate"]), num(a["depois"]), num(a["todo"])])
    linhas.append([dict(t="Mediana, anos de eleição", forte=True),
                   num(med_el_ate), num(med_el_dep), num(med_el_todo)])
    linhas.append([dict(t="Mediana, anos SEM eleição", forte=True),
                   num(mediana_sem_eleicao(anos, "ate")),
                   num(mediana_sem_eleicao(anos, "depois")),
                   num(mediana_sem_eleicao(anos, "todo"))])
    return dict(
        id="eleicoes-ano-tabela",
        titulo="O ano eleitoral em números",
        subtitulo="E a mesma partição do calendário nos anos em que não houve eleição",
        tipo="tabela",
        fonte=FONTE,
        colunas=[dict(rot="Ano"), dict(rot="Até a véspera", num=True),
                 dict(rot="Da véspera ao fim do ano", num=True), dict(rot="Ano todo", num=True)],
        linhas=linhas,
        nota=("As duas últimas linhas são o que dá sentido às de cima. Nas duas metades os "
              "números são quase os mesmos: %s contra %s até a votação, %s contra %s depois "
              "dela. O ano eleitoral não se distingue dos outros nem antes nem depois do voto, "
              "o que combina com o resto desta análise.\n\n"
              "**A coluna do ano todo parece contar outra história — e não conta.** A mediana "
              "dos anos de eleição é %s contra %s dos demais, uma distância de %.0f pontos "
              "percentuais que salta aos olhos. Ela não resiste ao teste: embaralhando os anos "
              "ao acaso entre os dois grupos, uma diferença dessas ou maior aparece em **43%%** "
              "das vezes. Com sete anos completos de eleição, dois deles de crise (1998, da "
              "Rússia, e 2002), é o que se espera do acaso. Some-se que a mediana não é "
              "aditiva: a do ano inteiro não é a soma das medianas das duas metades.\n\n"
              "1994 está fora pelo motivo explicado no gráfico acima (inflação, não mercado), e "
              "2026 não tem as duas últimas colunas porque o ano não acabou. Cada mediana usa "
              "só as células que existem, e por isso a de \u201caté a véspera\u201d tem um ano a mais "
              "que as outras duas."
              % (pct(med_el_ate), pct(mediana_sem_eleicao(anos, "ate")),
                 pct(med_el_dep), pct(mediana_sem_eleicao(anos, "depois")),
                 pct(med_el_todo), pct(mediana_sem_eleicao(anos, "todo")),
                 abs(med_el_todo - mediana_sem_eleicao(anos, "todo"))))
    )


def num(v, fmt="%+.2f%%", cor_por_sinal=True):
    """Célula numérica. Verde no positivo, vermelho no negativo — a mesma
    convenção dos outros sites."""
    if v is None:
        return dict(t=None)
    t = (fmt % v).replace(".", ",")
    if not cor_por_sinal:
        return dict(t=t)
    return dict(t=t, cor=VERDE if v > 0 else (VERMELHO if v < 0 else None))


def g_tabela(evs):
    """Os 15 turnos, com tudo o que os gráficos mostram separado — e com as
    colunas que não cabem em gráfico nenhum (a data, o dia da semana, se a
    votação resolveu a eleição)."""
    linhas = []
    for e in evs:
        d, m, a = e["data"][8:], e["data"][5:7], e["data"][:4]
        linhas.append([
            dict(t=e["rot"], forte=True),
            "%s/%s/%s" % (d, m, a),
            "sim" if e["resolve"] else "não",
            num(e["reacao"]),
            num(e["reacao_dp"], "%+.2f"),
            num(e["razao_limpa"], "%.2f", cor_por_sinal=False) if e["razao_limpa"] else dict(t=None),
            num(e["pos60"]),
        ])
    return dict(
        id="eleicoes-tabela",
        titulo="Os 15 turnos, um a um",
        subtitulo="Tudo o que os gráficos mostram separado, lado a lado",
        tipo="tabela",
        fonte=FONTE,
        colunas=[
            dict(rot="Turno"),
            dict(rot="Votação"),
            dict(rot="Definiu o presidente?"),
            dict(rot="Reação", num=True),
            dict(rot="Reação (dp do ano)", num=True),
            dict(rot="Volatilidade depois ÷ antes", num=True),
            dict(rot="60 pregões seguintes", num=True),
        ],
        linhas=linhas,
        nota="**Reação** é a variação do último fechamento antes do voto para o primeiro depois "
             "— como a votação é no domingo, quase sempre de sexta para segunda. **dp do ano** é "
             "essa mesma reação dividida pelo desvio-padrão dos retornos diários daquele ano "
             "civil, que é o que torna 1994 comparável a 2026: um movimento de 3% valia pouco num "
             "ano em que a bolsa andava 3,9% por dia e vale muito num de 1,3%. **Volatilidade "
             "depois ÷ antes** compara o sobe-e-desce dos 21 pregões seguintes com o dos "
             "anteriores, sem deixar a janela do 2º turno invadir o 1º; acima de 1 a bolsa ficou "
             "mais agitada. **60 pregões seguintes** é o retorno dos três meses posteriores, já "
             "sem contar o dia da reação.\n\n"
             "Os traços na última linha não são dado faltando: o 1º turno de 2026 tem dois "
             "pregões de vida, e as duas últimas colunas precisam de 21 e de 60."
    )


# --------------------------------------------------------------------------

def main():
    print("Baixando as séries do Ipeadata…")
    fech = baixar(SERIE_FECHAMENTO)
    vol_ipea = baixar(SERIE_VOLATILIDADE)
    base = Base(fech)
    print("  fechamento: %d pregões, %s a %s" % (len(base.pregoes), base.pregoes[0], base.pregoes[-1]))

    # conferência: a série de volatilidade do Ipea é desvio-padrão móvel de 21
    # pregões? Se um dia deixar de ser, é melhor saber antes de publicar.
    pares = []
    for i in range(JANELA, len(base.pregoes)):
        d = base.pregoes[i]
        if d not in vol_ipea:
            continue
        nosso = base.vol(base.pregoes[i - JANELA + 1], d)
        if nosso:
            pares.append((vol_ipea[d], nosso))
    mx, my = st.mean([a for a, _ in pares]), st.mean([b for _, b in pares])
    cov = sum((a - mx) * (b - my) for a, b in pares) / len(pares)
    corr = cov / (st.pstdev([a for a, _ in pares]) * st.pstdev([b for _, b in pares]))
    print("  volatilidade do Ipea vs a nossa de %d pregões: correlação %.3f, razão %.3f"
          % (JANELA, corr, mx / my))
    if corr < 0.95:
        raise SystemExit("a série de volatilidade do Ipea deixou de ser o desvio-padrão de 21 "
                         "pregões (correlação %.3f) — conferir antes de publicar" % corr)

    evs = eventos(base)
    cam = caminho_vol(base, evs)
    anos = ano_a_ano(base)

    print("\n%-9s %-11s %-11s %8s %7s %7s %7s" % ("turno", "eleição", "1º pregão", "reação", "em dp", "razão", "+60"))
    for e in evs:
        n = lambda v, f: (f % v) if v is not None else "      —"
        print("%-9s %-11s %-11s %+7.2f%% %+7.2f %s %s"
              % (e["rot"], e["data"], e["d1"], e["reacao"], e["reacao_dp"],
                 n(e["razao_limpa"], "%7.2f"), n(e["pos60"], "%+7.2f%%")))

    # os números que as notas citam
    k, nn, p = sinal([e["reacao"] for e in evs])
    print("\nreação (%d turnos): %d/%d positivos, teste de sinal p=%.2f, média %+.2f%%"
          % (len(evs), k, nn, p, st.mean([e["reacao"] for e in evs])))
    adia = [e["razao_limpa"] for e in evs if not e["resolve"] and e["razao_limpa"]]
    resolve = [e["razao_limpa"] for e in evs if e["resolve"] and e["razao_limpa"]]
    dif, pp = permutacao(adia, resolve)
    print("volatilidade: não resolve %.2f (n=%d) vs resolve %.2f (n=%d), diferença %+.2f, permutação p=%.3f"
          % (st.mean(adia), len(adia), st.mean(resolve), len(resolve), dif, pp))
    acima = sum(1 for x in adia if x > 1)
    print("              %d de %d que não resolveram ficaram mais agitadas" % (acima, len(adia)))

    doc = dict(
        atualizado=datetime.date.today().isoformat(),
        referencia=base.pregoes[-1],
        fonte=FONTE,
        assunto="A bolsa nas eleições presidenciais",
        apresentacao=(
            "Nove eleições presidenciais desde o Real — 15 turnos já realizados, com o 2º turno "
            "de 2026 ainda pela frente —, medidos contra os 8.315 pregões do Ibovespa que o "
            "Ipeadata guarda desde 1993. A pergunta é simples e "
            "a resposta, em boa parte, é negativa: a bolsa não sobe nem cai de forma previsível "
            "com eleição, não há rali entre os turnos e nenhuma janela em torno da votação se "
            "destaca da distribuição normal de retornos. O que aparece é outra coisa — a "
            "agitação sobe quando o 1º turno **não** resolve a disputa, e não quando há eleição. "
            "O 1º turno de 2026 produziu a maior reação da série inteira, +7,70%, e aparece só "
            "no primeiro gráfico: os demais precisam de 21 ou 60 pregões depois da votação, e "
            "dele há dois. "
            "Com 6 a 8 casos por grupo, tudo aqui é descritivo: os testes são de sinal e de "
            "permutação, que não dependem do formato da distribuição, e nenhuma conclusão "
            "deveria ser levada para além do que esse punhado de casos sustenta."),
        secoes=[
            dict(titulo="Os números, turno a turno",
                 graficos=[g_tabela(evs)]),
            dict(titulo="O dia seguinte",
                 graficos=[g_reacao(evs), g_reversao(evs)]),
            dict(titulo="Antes e depois",
                 graficos=[g_caminho(base, evs, cam), g_volatilidade(evs)]),
            dict(titulo="O ano inteiro",
                 graficos=[g_ano(anos), g_ano_tabela(anos)]),
        ],
    )
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print("\ngravado %s (%.0f KB)" % (SAIDA, os.path.getsize(SAIDA) / 1024))


if __name__ == "__main__":
    main()
