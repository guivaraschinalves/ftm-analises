#!/usr/bin/env python3
"""
Migração na Europa: fluxos, estoque de nascidos no exterior, origens e idade,
para a UE-27, Alemanha, França, Itália e Espanha. Gera dados/migracao-europa.json.
Só biblioteca padrão. Rodado à mão. O texto vem de textos/migracao-europa.md.

Pedido dele em 18/11/2026, a partir do md "ftm-analises-migracao-europa-graficos"
(OpenBot). Os números saem da API do Eurostat, não do md; batem com ele.

DE ONDE VEM CADA COISA (API de disseminação do Eurostat, JSON-stat)

  - demo_pjan: população em 1º de janeiro (2024 para as taxas de fluxo de 2024).
  - migr_imm8 e migr_emi2: imigração e emigração de 2024, totais (idade
    completa). Incluem o retorno de nativos e, na UE-27, a mudança entre países
    da UE.
  - migr_pop3ctb: população em 1º/jan/2025 por país de nascimento (total,
    nascidos no exterior, na UE e fora dela) e por faixa de 5 anos.
  - migr_imm3ctb: imigração de 2024 por país de nascimento e faixa de 5 anos
    (para a idade, a "alcançada no ano", REACH: a única que a França publica).
    A França não abre os países de fora da UE; a UE-27 não abre país nenhum.
    A idade dos novos imigrantes da UE-27 não sai pronta: é a soma dos países
    que publicam a abertura por idade.
  - Idade média: ponto médio de cada faixa (2,5; 7,5; ...; 82,5) e 88,5 para
    85+, como no md.
"""
import datetime
import json
import os
import sys
import time
import urllib.request

RAIZ = os.path.join(os.path.dirname(__file__), "..")
SAIDA = os.path.join(RAIZ, "dados", "migracao-europa.json")
API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
UA = {"User-Agent": "ftm-analises"}

AZUL, VERMELHO, VERDE = "#4F81BD", "#C0504D", "#9BBB59"
AZUL_CLARO, LARANJA, BRANCO = "#8EB4E3", "#F79646", "#FFFFFF"

TERR = [("EU27_2020", "UE-27"), ("DE", "Alemanha"), ("FR", "França"), ("IT", "Itália"), ("ES", "Espanha")]
UE = ["BE", "BG", "CZ", "DK", "DE", "EE", "IE", "EL", "ES", "FR", "HR", "IT", "CY", "LV", "LT", "LU", "HU", "MT",
      "NL", "AT", "PL", "PT", "RO", "SI", "SK", "FI", "SE"]
FAIXAS = ["Y_LT5", "Y5-9", "Y10-14", "Y15-19", "Y20-24", "Y25-29", "Y30-34", "Y35-39", "Y40-44", "Y45-49",
          "Y50-54", "Y55-59", "Y60-64", "Y65-69", "Y70-74", "Y75-79", "Y80-84", "Y_GE85"]
ROT_FAIXAS = ["0–4", "5–9", "10–14", "15–19", "20–24", "25–29", "30–34", "35–39", "40–44", "45–49",
              "50–54", "55–59", "60–64", "65–69", "70–74", "75–79", "80–84", "85+"]
MEIOS = [2.5 + 5 * i for i in range(17)] + [88.5]
AGREGADOS = {"TOTAL", "FOR", "NAT", "EU27_2020_FOR", "NEU27_2020_FOR", "UNK", "STLS", "EU28_FOR", "NEU28_FOR",
             "EU27_2007_FOR", "NEU27_2007_FOR", "EU25_FOR", "NEU25_FOR", "EU15_FOR", "NEU15_FOR", "EFTA_FOR",
             "EU27_2020_NAT", "EFTA", "CC5_13_FOR", "NEU27_2020_NAT"}
# nomes em português dos países que podem aparecer no topo
NOMES = {"UA": "Ucrânia", "SY": "Síria", "TR": "Turquia", "RO": "Romênia", "IN": "Índia", "BD": "Bangladesh",
         "AL": "Albânia", "MA": "Marrocos", "PK": "Paquistão", "EG": "Egito", "CO": "Colômbia", "VE": "Venezuela",
         "PE": "Peru", "AR": "Argentina", "IT": "Itália", "DE": "Alemanha", "BE": "Bélgica", "ES": "Espanha",
         "PT": "Portugal", "PL": "Polônia", "BG": "Bulgária", "AF": "Afeganistão", "CN": "China", "BR": "Brasil",
         "TN": "Tunísia", "DZ": "Argélia", "NG": "Nigéria", "GE": "Geórgia", "RU": "Rússia", "US": "EUA",
         "UK": "Reino Unido", "FR": "França", "NL": "Países Baixos", "AT": "Áustria", "HR": "Croácia",
         "HU": "Hungria", "GR": "Grécia", "EL": "Grécia", "IQ": "Iraque", "IR": "Irã", "PH": "Filipinas",
         "LK": "Sri Lanka", "SN": "Senegal", "HN": "Honduras", "CU": "Cuba", "UY": "Uruguai", "CL": "Chile",
         "EC": "Equador", "BO": "Bolívia", "DO": "República Dominicana", "NP": "Nepal", "MD": "Moldávia",
         "RS": "Sérvia", "XK": "Kosovo", "MK": "Macedônia do Norte", "BA": "Bósnia", "KO": "Kosovo",
         "IE": "Irlanda", "CZ": "Tchéquia", "SK": "Eslováquia", "LT": "Lituânia", "LV": "Letônia",
         "SE": "Suécia", "DK": "Dinamarca", "FI": "Finlândia", "LU": "Luxemburgo", "NO": "Noruega",
         "CH": "Suíça", "SI": "Eslovênia", "CY": "Chipre", "MT": "Malta", "EE": "Estônia"}


def baixar(url, headers=None, tentativas=4):
    """Baixa uma URL usando apenas biblioteca padrão, com retentativas."""
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:                               # noqa: BLE001
            ultimo = e
            time.sleep(2 * (i + 1))
    raise RuntimeError("não deu para baixar %s: %s" % (url, ultimo))


def eurostat(codigo, chaves, **filtros):
    """{tupla com os códigos das dimensões em `chaves`, nessa ordem: valor}, mais os rótulos."""
    pares = []
    for k, v in filtros.items():
        for x in (v if isinstance(v, list) else [v]):
            pares.append("%s=%s" % (k, x))
    r = json.loads(baixar(API + codigo + "?format=JSON&lang=EN&" + "&".join(pares), headers=UA))
    ids, tam = r["id"], r["size"]
    cats = [sorted(r["dimension"][d]["category"]["index"].items(), key=lambda kv: kv[1]) for d in ids]
    varia = [ids.index(c) for c in chaves]
    out = {}
    for pos, v in r["value"].items():
        pos, coord = int(pos), []
        for i in reversed(range(len(ids))):
            coord.append(pos % tam[i])
            pos //= tam[i]
        coord.reverse()
        chave = tuple(cats[i][coord[i]][0] for i in varia)
        out[chave if len(chave) > 1 else chave[0]] = v
    rotulos = {d: r["dimension"][d]["category"].get("label", {}) for d in ids}
    return out, rotulos


def br(v, casas=1):
    s = "{:,.{c}f}".format(v, c=casas)
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def conferir(condicao, msg):
    if not condicao:
        raise RuntimeError("conferência falhou: " + msg)


def main():
    geos = [g for g, _ in TERR]
    pop24, _ = eurostat("demo_pjan", ["geo"], geo=geos, time="2024", age="TOTAL", sex="T")
    imi, _ = eurostat("migr_imm8", ["geo"], geo=geos, time="2024", age="TOTAL", sex="T", agedef="COMPLET")
    emi, _ = eurostat("migr_emi2", ["geo"], geo=geos, time="2024", age="TOTAL", sex="T", agedef="COMPLET")
    # estoque em 1º/jan/2025 por bloco de nascimento e idade (inclui o total da população)
    est, _ = eurostat("migr_pop3ctb", ["geo", "c_birth", "age"], geo=geos, time="2025", sex="T", age=["TOTAL"] + FAIXAS,
                      c_birth=["TOTAL", "FOR", "EU27_2020_FOR", "NEU27_2020_FOR"])
    # fluxo de 2024 por país de nascimento (todos) no total de idades; e por idade para os nascidos fora
    flu, rot = eurostat("migr_imm3ctb", ["geo", "c_birth"], geo=geos, time="2024", sex="T", age="TOTAL", agedef="COMPLET")
    # idade "alcançada no ano" (REACH): é a que a França publica, e a do md
    flu_idade, _ = eurostat("migr_imm3ctb", ["geo", "age"], geo=geos + [g for g in UE if g not in geos], time="2024",
                            sex="T", agedef="REACH", c_birth="FOR", age=FAIXAS)
    nomes_pais = rot.get("c_birth", {})

    for g in geos:
        conferir(pop24.get(g, 0) > 0 and imi.get(g, 0) > 0 and emi.get(g, 0) > 0,
                 "%s sem população ou fluxos em 2024" % g)
        conferir(est[(g, "EU27_2020_FOR", "TOTAL")] + est[(g, "NEU27_2020_FOR", "TOTAL")] == est[(g, "FOR", "TOTAL")],
                 "%s estoque UE + fora UE != FOR" % g)
        conferir(sum(est[(g, "TOTAL", f)] for f in FAIXAS) == est[(g, "TOTAL", "TOTAL")],
                 "%s soma das faixas etárias != TOTAL" % g)
        conferir(sum(est[(g, "FOR", f)] for f in FAIXAS) == est[(g, "FOR", "TOTAL")],
                 "%s soma das faixas etárias (FOR) != FOR TOTAL" % g)
        conferir(flu.get((g, "EU27_2020_FOR"), 0) + flu.get((g, "NEU27_2020_FOR"), 0) == flu[(g, "FOR")],
                 "%s fluxo UE + fora UE != FOR" % g)

    # 1. fluxos em % da população de 2024
    cats = [n for _, n in TERR]
    im = {g: 100 * imi[g] / pop24[g] for g in geos}
    em = {g: 100 * emi[g] / pop24[g] for g in geos}
    for g, n in TERR:
        print("  %s: imigração %.2f%%, emigração %.2f%%, saldo %+.2f p.p." % (n, im[g], em[g], im[g] - em[g]))
    g_fluxos = dict(id="migracao-fluxos", titulo="Imigração e emigração em % da população, 2024",
                    subtitulo="Entradas e saídas no ano, sobre a população em 1º de janeiro de 2024; saldo = "
                              "imigração menos emigração, em pontos percentuais",
                    unidade="%", categorias=cats, agrupadas=True, barra=0.8,
                    fonte="Eurostat (migr_imm8, migr_emi2 e demo_pjan) e FtM",
                    series=[dict(nome="Imigração", cor=AZUL, tipo="barra", valores=True,
                                 dados=[[str(i), round(im[g], 2)] for i, g in enumerate(geos)]),
                            dict(nome="Emigração", cor=VERMELHO, tipo="barra", valores=True,
                                 dados=[[str(i), round(em[g], 2)] for i, g in enumerate(geos)]),
                            dict(nome="Saldo", cor=VERDE, tipo="barra", valores=True,
                                 dados=[[str(i), round(im[g] - em[g], 2)] for i, g in enumerate(geos)])])

    # 2. estoque de nascidos no exterior em % da população de 2025
    pct = {b: {g: 100 * est[(g, b, "TOTAL")] / est[(g, "TOTAL", "TOTAL")] for g in geos}
           for b in ("FOR", "EU27_2020_FOR", "NEU27_2020_FOR")}
    tot = "; ".join("%s %s%%" % (n, br(pct["FOR"][g])) for g, n in TERR)
    g_estoque = dict(id="migracao-estoque", titulo="Nascidos no exterior em % da população, 1º de janeiro de 2025",
                     subtitulo="Residentes nascidos em outro país, por bloco de nascimento; total: %s" % tot,
                     unidade="%", categorias=cats, barra=0.6,
                     fonte="Eurostat (migr_pop3ctb) e FtM",
                     series=[dict(nome="Nascidos em outro país da UE", cor=AZUL_CLARO, tipo="barra",
                                  dados=[[str(i), round(pct["EU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)]),
                             dict(nome="Nascidos fora da UE", cor=AZUL, tipo="barra",
                                  dados=[[str(i), round(pct["NEU27_2020_FOR"][g], 2)] for i, g in enumerate(geos)])])

    # 3. de onde vêm os novos imigrantes nascidos no exterior (2024)
    variantes, fora = [], {}
    for g, n in TERR:
        total = flu[(g, "FOR")]
        fora[n] = 100 * flu.get((g, "NEU27_2020_FOR"), 0) / total
        if g == "EU27_2020":    # a UE-27 não abre país nenhum: só UE contra fora da UE
            variantes.append(dict(rot=n + " (só UE x fora da UE)", itens=[
                ["Nascidos fora da UE", round(fora[n], 1), AZUL],
                ["Nascidos em outro país da UE", round(100 - fora[n], 1), AZUL_CLARO]]))
            continue
        # só países (código de duas letras); os agregados regionais têm código maior
        paises = {c: v for (gg, c), v in flu.items()
                  if gg == g and len(c) == 2 and c not in AGREGADOS and c != g and v}
        if g == "FR":       # a França não abre os países de fora da UE
            paises = {c: v for c, v in paises.items() if c in UE}
        top = sorted(paises.items(), key=lambda kv: -kv[1])[:5]
        itens = [[NOMES.get(c, nomes_pais.get(c, c)), round(100 * v / total, 1), AZUL if c not in UE else AZUL_CLARO]
                 for c, v in top]
        rot_v = n + (" (só países da UE)" if g == "FR" else "")
        variantes.append(dict(rot=rot_v, itens=itens))
        print("  %s: %s" % (n, ", ".join("%s %.1f%%" % (a, b) for a, b, _ in itens)))
    g_origens = dict(id="migracao-origens", tipo="ranking", unidade="%",
                     titulo="Os cinco principais países de nascimento dos novos imigrantes, 2024",
                     subtitulo="%% dos imigrantes nascidos no exterior que chegaram no ano; azul claro = país da UE; "
                               "nascidos fora da UE: %s" % "; ".join("%s %s%%" % (n, br(v)) for n, v in fora.items()),
                     fonte="Eurostat (migr_imm3ctb) e FtM", itens=variantes[0]["itens"], variantes=variantes)

    # 4. idade: residentes e estoque de 2025, novos imigrantes de 2024
    def dist(contagem):
        s = sum(contagem)
        return [100 * x / s for x in contagem]

    def media(d):
        return sum(m * p for m, p in zip(MEIOS, d)) / 100
    var_idade, medias = [], {}
    for g, n in TERR:
        resid = dist([est[(g, "TOTAL", f)] for f in FAIXAS])
        estoq = dist([est[(g, "FOR", f)] for f in FAIXAS])
        if all((g, f) in flu_idade for f in FAIXAS):
            novos_n, base = [flu_idade[(g, f)] for f in FAIXAS], None
        else:              # a UE-27 não publica: soma dos países que publicam todas as faixas
            com = [p for p in UE if all((p, f) in flu_idade for f in FAIXAS)]
            conferir(len(com) >= 20, "UE-27 com poucos países publicando idade: %d" % len(com))
            novos_n = [sum(flu_idade[(p, f)] for p in com) for f in FAIXAS]
            base = com
        novos = dist(novos_n)
        for nome_dist, d in (("resid", resid), ("estoq", estoq), ("novos", novos)):
            conferir(abs(sum(d) - 100.0) < 1e-6, "%s %s não soma 100%% (%.6f)" % (g, nome_dist, sum(d)))
        medias[g] = (media(resid), media(estoq), media(novos))
        print("  %s: idade média residentes %.1f, estoque %.1f, novos %.1f%s"
              % (n, medias[g][0], medias[g][1], medias[g][2], "" if base is None else
                 " (novos: %d países)" % len(base)))
        var_idade.append(dict(rot=n, series=[
            dict(nome="População residente, 2025", cor=AZUL_CLARO, tipo="barra",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(resid)]),
            dict(nome="Nascidos no exterior, estoque de 2025", cor=LARANJA, largura=6, traco="pontilhado",
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(estoq)]),
            dict(nome="Novos imigrantes nascidos no exterior, 2024", cor=BRANCO, largura=5,
                 dados=[[str(i), round(v, 2)] for i, v in enumerate(novos)])]))
    g_idade = dict(id="migracao-idade", titulo="Distribuição por idade: residentes, imigrantes e novos imigrantes",
                   subtitulo="% de cada grupo em cada faixa de 5 anos; a UE-27 dos novos imigrantes soma os países "
                             "que publicam a idade",
                   unidade="%", categorias=ROT_FAIXAS, barra=0.8, eixo=dict(min=0, max=20),
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM", variantes=var_idade)
    g_media = dict(id="migracao-idade-media", titulo="Idade média: residentes, imigrantes e novos imigrantes",
                   subtitulo="Anos, pelo ponto médio das faixas de 5 anos; residentes e estoque em 1º/jan/2025, "
                             "novos imigrantes em 2024",
                   unidade="anos", categorias=cats, agrupadas=True, barra=0.8,
                   fonte="Eurostat (migr_pop3ctb e migr_imm3ctb) e FtM",
                   series=[dict(nome="População residente", cor=AZUL_CLARO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][0], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Nascidos no exterior (estoque)", cor=LARANJA, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][1], 1)] for i, g in enumerate(geos)]),
                           dict(nome="Novos imigrantes", cor=BRANCO, tipo="barra", valores=True,
                                dados=[[str(i), round(medias[g][2], 1)] for i, g in enumerate(geos)])])

    hoje = datetime.date.today().isoformat()
    doc = dict(assunto="Migração na Europa", grupo="Análises Variadas", fonte="Eurostat e FtM",
               referencia="2025-01", atualizado=hoje, formato="artigo",
               secoes=[dict(titulo="Quem chega e quem sai", texto="", fontes=[], figuras=[], graficos=[g_fluxos]),
                       dict(titulo="Quantos nasceram fora", texto="", fontes=[], figuras=[], graficos=[g_estoque]),
                       dict(titulo="De onde vêm", texto="", fontes=[], figuras=[], graficos=[g_origens]),
                       dict(titulo="A idade de quem chega", texto="", fontes=[], figuras=[],
                            graficos=[g_idade, g_media])])
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        f.write("\n")
    print("gravado", SAIDA)
    sys.path.insert(0, os.path.dirname(__file__))
    import aplicar_texto
    if aplicar_texto.aplicar("migracao-europa.md", "migracao-europa.json"):
        raise RuntimeError("falha ao aplicar textos/migracao-europa.md")


if __name__ == "__main__":
    main()
