#!/usr/bin/env python3
"""
Juros futuros de DI1 para o meio e o fim de 2027 (DI1N27 e DI1F28) contra a
Selic meta, diário desde janeiro de 2026: o que o mercado espera da Selic,
enquanto não chega o print das opções de Copom (pedido dele em 15/11/2026).

Fonte: o arquivo diário "TradeInformationConsolidatedFile" da B3
(arquivos.b3.com.br, aberto, sem login), coluna AdjstdQtTax (taxa de ajuste).
Cada pregão é baixado uma vez só: as duas taxas ficam em dados/.cache-b3/di1.csv
e a rodada seguinte só busca os dias que faltam.
"""
import csv
import datetime
import os
import sys
import time

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import cenario_fomc as cf                                   # noqa: E402

CACHE = os.path.join(RAIZ, "dados", ".cache-b3", "di1.csv")
CONTRATOS = [("DI1N27", "DI1 jul/27", cf.AZUL), ("DI1F28", "DI1 jan/28", cf.VERMELHO)]
INICIO = datetime.date(2026, 1, 2)
B3_PEDIDO = "https://arquivos.b3.com.br/api/download/requestname"
B3_ARQUIVO = "https://arquivos.b3.com.br/api/download/"
CABECALHO = {"User-Agent": "Mozilla/5.0"}


def num(s):
    s = (s or "").strip()
    return float(s.replace(".", "").replace(",", ".")) if s else None


def pregao(dia):
    """{contrato: taxa de ajuste} do dia, ou None se não houve pregão."""
    r = requests.get(B3_PEDIDO, params={"fileName": "TradeInformationConsolidatedFile", "date": dia.isoformat()},
                     headers=CABECALHO, timeout=30)
    if r.status_code != 200 or not r.text.strip():
        return None
    token = r.json().get("token")
    if not token:
        return None
    r2 = requests.get(B3_ARQUIVO, params={"token": token}, headers=CABECALHO, timeout=120)
    if r2.status_code != 200:
        return None
    linhas = r2.content.decode("latin-1").splitlines()
    if len(linhas) < 3:
        return None
    cab = linhas[1].split(";")
    it, ix = cab.index("TckrSymb"), cab.index("AdjstdQtTax")
    out = {}
    for l in linhas[2:]:
        c = l.split(";")
        if len(c) > ix and c[it] in dict((k, 1) for k, _, _ in CONTRATOS):
            out[c[it]] = num(c[ix])
    return out or None


def serie_di1():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    feitos = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                feitos[r["data"]] = r
    hoje = datetime.date.today()
    d, novos = INICIO, 0
    while d < hoje:
        k = d.isoformat()
        if d.weekday() < 5 and k not in feitos:
            p = None
            for tent in range(3):
                try:
                    p = pregao(d)
                    break
                except (requests.RequestException, ValueError):
                    time.sleep(2)
            # sem pregão (feriado) também fica no cache, vazio, para não buscar de novo;
            # o dia de ontem pode ainda não ter arquivo: esse não entra
            if p or (hoje - d).days > 3:
                feitos[k] = dict(data=k, **{c: (p or {}).get(c, "") for c, _, _ in CONTRATOS})
                novos += 1
        d += datetime.timedelta(days=1)
    with open(CACHE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["data"] + [c for c, _, _ in CONTRATOS])
        w.writeheader()
        for k in sorted(feitos):
            w.writerow(feitos[k])
    print("  DI1: %d pregões novos, %d no cache" % (novos, len(feitos)))
    return {c: {k: float(r[c]) for k, r in feitos.items() if r.get(c) not in ("", None)} for c, _, _ in CONTRATOS}


def grafico_di1():
    di = serie_di1()
    u = max(di["DI1F28"])
    selic = {k: v for k, v in selic_meta().items() if k <= u}     # o SGS 432 já traz a meta até a próxima reunião
    ult = "; ".join("%s: %s%%" % (rot, cf.br(di[c][u], 2)) for c, rot, _ in CONTRATOS)
    return dict(id="di1-2027", titulo="Juros futuros para meados e fim de 2027 e a Selic",
                subtitulo="Taxa de ajuste dos contratos de DI1 que vencem em julho de 2027 e em janeiro de 2028 e "
                          "Selic meta, em %% ao ano; em %s, %s" % (cf.rotulo_dia(u), ult),
                unidade="%", diario=True, fonte="B3 e Banco Central (SGS 432)",
                series=[cf.serie("Selic meta", cf.BRANCO, selic, 2, largura=3, rotulo=True)] +
                       [cf.serie(rot, cor, di[c], 2, largura=3, rotulo=True) for c, rot, cor in CONTRATOS])


def selic_meta():
    """Selic meta (SGS 432), um ponto por dia desde o início."""
    url = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json&dataInicial=%s"
           % INICIO.strftime("%d/%m/%Y"))
    js = requests.get(url, timeout=60, headers=CABECALHO).json()
    out = {}
    for r in js:
        d, m, a = r["data"].split("/")
        out["%s-%s-%s" % (a, m, d)] = float(r["valor"])
    return out


if __name__ == "__main__":
    g = grafico_di1()
    for x in g["series"]:
        print(x["nome"], x["dados"][-3:])
