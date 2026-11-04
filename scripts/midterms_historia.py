#!/usr/bin/env python3
"""
A seção "As midterms de outros presidentes" do assunto das midterms
(dados/midterms-2026.json), entre os resultados e os motivos da virada. Não
roda sozinho: o scripts/midterms.py chama secoes(). Só biblioteca padrão.

DE ONDE VÊM OS NÚMEROS

  The American Presidency Project (UCSB):
    seats-congress-gainedlost-the-presidents-party-mid-term-elections
        uma linha por midterm desde 1934: aprovação do Gallup em seis datas
        de agosto a outubro, cadeiras que o partido do presidente defendia
        (na Câmara, todas as que tinha; no Senado, as que estavam em disputa)
        e quantas ganhou ou perdeu. A linha de 2026 ainda vem sem resultado.
    presidential-vetoes
        vetos por Congresso, com a fatia de cadeiras do partido do presidente
        em cada Casa. "Congresso contra" = o partido do presidente com menos
        da metade de ao menos uma Casa (no Senado, 50% conta como maioria,
        pelo voto de desempate do vice).

  2026, da apuração da CNN (o mesmo arquivo de midterms_resultados.py):
    confirmado        cadeiras que já trocaram de partido, num sentido e no outro
    se quem lidera    além das confirmadas, as sem resultado vão para quem está
    vencer            à frente; o segundo turno da Luisiana 5 conta para o
                      partido que tinha a cadeira (republicano)
  As perdas de 2026 contam a partir das cadeiras da tabela da UCSB na Câmara
  (220, as eleitas em 2024) e das 22 em disputa no Senado (a UCSB diz 20; não
  conta as duas eleições especiais, de Ohio e da Flórida).

  Aprovação: para cada midterm, a última leitura do Gallup antes da eleição na
  tabela (fim de outubro quando há). Para 2026, que não tem Gallup, a média de
  outubro calculada em midterms_motivos.py.
"""
import html
import re

from midterms_motivos import baixar, aprovacao
from midterms_resultados import disputas, resumo, partido

D, R = "#3B7DD8", "#D9453D"


def tabela(pagina, nome):
    t = baixar("https://www.presidency.ucsb.edu/statistics/data/" + pagina, nome).decode("utf-8", "replace")
    tb = re.findall(r"<table.*?</table>", t, re.S)[0]
    return [[html.unescape(re.sub("<[^>]+>", "", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", lin, re.S)]
            for lin in re.findall(r"<tr[^>]*>(.*?)</tr>", tb, re.S)]


def num(s):
    s = s.replace("−", "-").replace("+", "").strip()
    return int(s) if re.match(r"^-?\d+$", s) else None


def midterms():
    out = []
    for c in tabela("seats-congress-gainedlost-the-presidents-party-mid-term-elections", "ucsb-midterms.html")[2:]:
        if not re.match(r"^\d{4}$", c[0]):
            continue
        aprov = [num(x) for x in c[4:10]]
        aprov = [a for a in aprov if a is not None]
        out.append({"ano": int(c[0]), "pres": c[2], "partido": c[3], "aprov": aprov[-1] if aprov else None,
                    "def_cam": num(c[10]), "def_sen": num(c[11]), "cam": num(c[12]), "sen": num(c[13])})
    return out


NOMES = {"Franklin D. Roosevelt": "Roosevelt", "Harry S. Truman": "Truman", "Dwight D. Eisenhower": "Eisenhower",
         "John F. Kennedy": "Kennedy", "Lyndon B. Johnson": "Johnson", "Richard Nixon": "Nixon",
         "Gerald R. Ford (Nixon)": "Ford", "Jimmy Carter": "Carter", "Ronald Reagan": "Reagan",
         "George Bush": "Bush pai", "William J. Clinton": "Clinton", "George W. Bush": "Bush filho",
         "Barack Obama": "Obama", "Donald J. Trump-I": "Trump", "Joseph R. Biden, Jr.": "Biden",
         "Donald J. Trump-II": "Trump"}


def apuracao_2026(senado_r):
    """Mudança do partido republicano em 2026: (confirmada, se quem lidera vencer), Câmara e Senado."""
    cam = [resumo(r) for r in disputas("HG") if r["ecKey"].startswith("2026-HG-")]
    conf = sum((1 if partido(s["venc"]) == "R" else -1) for s in cam if s["status"] == "W" and s["vira"])
    r_total = sum(1 for s in cam if s["status"] == "W" and partido(s["venc"]) == "R")
    r_total += sum(1 for s in cam if s["status"] == "U" and partido(s["lider"]) == "R")
    r_total += sum(1 for s in cam if s["status"] == "V")       # segundo turno: fica com quem tinha (R)
    sen = [resumo(r) for r in disputas("SG")]
    sconf = sum((1 if partido(s["venc"]) == "R" else -1) for s in sen if s["status"] == "W" and s["vira"])
    spend = sum(-1 for s in sen if s["status"] != "W" and s["uf"] in senado_r and partido(s["lider"]) != "R")
    spend += sum(1 for s in sen if s["status"] != "W" and s["uf"] not in senado_r and partido(s["lider"]) == "R")
    return conf, r_total - 220, sconf, sconf + spend


PARTIDO_V = {"Franklin D. Roosevelt": "D", "Harry S. Truman": "D", "Dwight D. Eisenhower": "R",
             "John F. Kennedy": "D", "Lyndon B. Johnson": "D", "Richard Nixon": "R", "Gerald R. Ford": "R",
             "Jimmy Carter": "D", "Ronald Reagan": "R", "George Bush": "R", "William J. Clinton": "D",
             "George W. Bush": "R", "Barack Obama": "D", "Donald J. Trump - I": "R", "Joseph R. Biden, Jr.": "D",
             "Donald J. Trump - II": "R"}
NOMES_V = {"Franklin D. Roosevelt": "Roosevelt", "Harry S. Truman": "Truman", "Dwight D. Eisenhower": "Eisenhower",
           "John F. Kennedy": "Kennedy", "Lyndon B. Johnson": "Johnson", "Richard Nixon": "Nixon",
           "Gerald R. Ford": "Ford", "Jimmy Carter": "Carter", "Ronald Reagan": "Reagan", "George Bush": "Bush pai",
           "William J. Clinton": "Clinton", "George W. Bush": "Bush filho", "Barack Obama": "Obama",
           "Donald J. Trump - I": "Trump", "Joseph R. Biden, Jr.": "Biden", "Donald J. Trump - II": "Trump"}


def mmq(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    return my - b * mx, b


def r2(xs, ys):
    """R² da reta de mínimos quadrados e o R² ajustado (um regressor: n - 2 graus de liberdade)."""
    a, b = mmq(xs, ys)
    my, n = sum(ys) / len(ys), len(ys)
    resid = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    total = sum((y - my) ** 2 for y in ys)
    r = 1 - resid / total
    return r, 1 - (1 - r) * (n - 1) / (n - 2), n


def nf(v, casas=1):
    return ("%.*f" % (casas, v)).replace(".", ",")


def sinal(v):
    return ("+%d" % v) if v > 0 else str(v)


def secoes(senado_r):
    ms = midterms()
    conf, cen, sconf, scen = apuracao_2026(senado_r)
    ap26 = aprovacao("donald-j-trump-2nd-term", 2025)
    k26 = max(ap26)
    m26 = [m for m in ms if m["ano"] == 2026][0]
    m26.update({"aprov": round(ap26[k26], 1), "cam": conf, "cam_cen": cen, "sen": sconf, "sen_cen": scen, "def_sen": 22})
    hist = [m for m in ms if m["ano"] < 2026]
    print("história: 2026 Câmara %d (confirmada) / %d (se quem lidera vencer); Senado %d / %d; aprovação %.1f"
          % (conf, cen, sconf, scen, m26["aprov"]))

    anos = [str(m["ano"]) for m in ms]
    idx = {m["ano"]: str(k) for k, m in enumerate(ms)}

    def barras(campo, base=None):
        def v(m, chave):
            x = m[chave]
            return round(x / m[base] * 100, 1) if base else x
        sd = [[idx[m["ano"]], v(m, campo)] for m in hist if m["partido"] == "D"]
        sr = [[idx[m["ano"]], v(m, campo)] for m in hist if m["partido"] == "R"]
        sr.append([idx[2026], v(m26, campo)])
        falta = v(m26, campo + "_cen") - v(m26, campo)
        series = [{"nome": "Presidente democrata", "cor": D, "tipo": "barra", "dados": sd},
                  {"nome": "Presidente republicano", "cor": R, "tipo": "barra", "dados": sr}]
        if falta:
            series.append({"nome": "2026, se quem lidera vencer", "cor": R, "tipo": "barra", "opacidade": 0.35,
                           "dados": [[idx[2026], round(falta, 1)]]})
        return series

    g_barras = {
        "id": "midterms-historia-cadeiras",
        "titulo": "Cadeiras do partido do presidente nas midterms",
        "subtitulo": "Ganho ou perda do partido do presidente em cada eleição de meio de mandato; 2026 parcial",
        "fonte": "The American Presidency Project (UCSB); 2026: Edison Research para a CNN",
        "categorias": anos,
        "variantes": [
            {"rot": "Câmara, em cadeiras", "unidade": "margem", "series": barras("cam")},
            {"rot": "Câmara, em % das cadeiras que tinha", "unidade": "pct1", "series": barras("cam", "def_cam")},
            {"rot": "Senado, em cadeiras", "unidade": "margem", "series": barras("sen")},
            {"rot": "Senado, em % das cadeiras em disputa", "unidade": "pct1", "series": barras("sen", "def_sen")},
        ],
    }

    # ---- dispersão
    def dispersao(campo, rot_y):
        base = [m for m in hist if m["aprov"] is not None and m["ano"] >= 1946]
        a, b = mmq([m["aprov"] for m in base], [m[campo] for m in base])
        rq, rqa, n = r2([m["aprov"] for m in base], [m[campo] for m in base])
        pts = [{"x": m["aprov"], "y": m[campo], "rot": str(m["ano"]), "cor": D if m["partido"] == "D" else R,
                "dica": "%d, %s: aprovação de %d%%, %s cadeiras" % (m["ano"], NOMES[m["pres"]], m["aprov"], sinal(m[campo]))}
               for m in base]
        prev = a + b * m26["aprov"]
        pts.append({"x": m26["aprov"], "y": m26[campo], "ate": m26[campo + "_cen"], "rot": "2026, Trump",
                    "cor": R, "destaque": True,
                    "nota": "a reta previa %s; até agora %s" % (sinal(round(prev)), sinal(m26[campo])),
                    "dica": "2026, Trump: aprovação de %s%%; %s cadeiras confirmadas, %s se quem lidera vencer"
                            % (nf(m26["aprov"]), sinal(m26[campo]), sinal(m26[campo + "_cen"]))})
        xs = [p["x"] for p in pts]
        return a, b, prev, (rq, rqa, n), {
            "unidade": "n", "pontos": pts,
            "eixoX": {"rot": "Aprovação do presidente antes da eleição (%)", "unidade": "n"},
            "eixoY": {"rot": rot_y, "unidade": "margem"},
            "reta": {"a": a, "b": b, "de": min(xs), "ate": max(xs)},
            "legenda": [{"rot": "Presidente democrata", "cor": D}, {"rot": "Presidente republicano", "cor": R},
                        {"rot": "Tendência de 1946 a 2022 (R² %s; ajustado %s)" % (nf(rq, 2), nf(rqa, 2)),
                         "cor": "linha:#FFFFFF"}],
        }

    sa, sb, sprev, sr2, d_sen = dispersao("sen", "Cadeiras no Senado")
    ca, cb, cprev, cr2, d_cam = dispersao("cam", "Cadeiras na Câmara")
    g_disp = {
        "id": "midterms-historia-aprovacao", "tipo": "dispersao",
        "titulo": "Aprovação do presidente e cadeiras do partido dele nas midterms",
        "subtitulo": "Uma midterm por ponto, de 1946 a 2026; reta de tendência de 1946 a 2022",
        "fonte": "The American Presidency Project (UCSB), com Gallup; 2026: Edison Research para a CNN e média de outubro das pesquisas",
        "legenda": [{"rot": "Presidente democrata", "cor": D}, {"rot": "Presidente republicano", "cor": R},
                    {"rot": "Tendência de 1946 a 2022", "cor": "linha:#FFFFFF"}],
        "variantes": [dict(rot="Senado", **d_sen), dict(rot="Câmara", **d_cam)],
    }

    # ---- tabela das maiores perdas
    linhas = sorted(hist, key=lambda m: m["cam"])[:10]
    pos_cen = 1 + sum(1 for m in hist if m["cam"] < m26["cam_cen"])
    pos_pct = 1 + sum(1 for m in hist if m["cam"] / m["def_cam"] < m26["cam_cen"] / m26["def_cam"])

    def linha(m, cen=False):
        cam = m["cam_cen"] if cen else m["cam"]
        sen = m["sen_cen"] if cen else m["sen"]
        return [{"t": "%d%s" % (m["ano"], " (parcial)" if cen else ""), "forte": True}, NOMES[m["pres"]],
                {"t": ("%s%%" % nf(m["aprov"], 0)) if m["aprov"] is not None else "n/d"},
                {"t": sinal(cam), "cor": D if cam > 0 else R},
                {"t": nf(cam / m["def_cam"] * 100) + "%", "cor": D if cam > 0 else R},
                {"t": sinal(sen) if sen else "0", "cor": D if sen > 0 else (R if sen < 0 else None)}]
    lin = [linha(m) for m in linhas]
    lin.insert(min(pos_cen - 1, len(lin)), linha(m26, True))
    g_tab = {
        "id": "midterms-historia-tabela", "tipo": "tabela",
        "titulo": "As maiores perdas do partido do presidente na Câmara",
        "subtitulo": "As dez maiores desde 1934 e 2026 se quem lidera vencer",
        "fonte": "The American Presidency Project (UCSB); 2026: Edison Research para a CNN",
        "colunas": [{"rot": "Midterm"}, {"rot": "Presidente"}, {"rot": "Aprovação", "num": True},
                    {"rot": "Câmara", "num": True}, {"rot": "Câmara (% das cadeiras)", "num": True},
                    {"rot": "Senado", "num": True}],
        "linhas": lin,
    }

    # ---- vetos
    vet, pres = [], None
    for c in tabela("presidential-vetoes", "ucsb-vetos.html")[2:]:
        if c[0]:
            pres = c[0]
        m = re.match(r"^(\d+)", c[1] or "")
        if not m or int(m.group(1)) < 79:
            continue
        n = int(m.group(1))
        cam_pct, sen_pct = float(c[2].rstrip("%")), float(c[3].rstrip("%"))
        contra = cam_pct < 50 or sen_pct < 50
        vet.append({"cong": n, "ano": 1789 + 2 * (n - 1), "pres": pres, "total": int(c[4]), "contra": contra,
                    "cam_pct": cam_pct})
    todos = vet
    vet = [v for v in todos if v["cong"] >= 97]
    cats = ["%d" % v["ano"] for v in vet]
    g_vet = {
        "id": "midterms-historia-vetos",
        "titulo": "Vetos presidenciais por Congresso",
        "subtitulo": "Vetos de cada Congresso de dois anos, pelo ano em que ele começa; 2025 até agora",
        "fonte": "The American Presidency Project (UCSB)",
        "unidade": "n", "categorias": cats,
        "series": [
            {"nome": "Partido do presidente com maioria nas duas Casas", "cor": "#8A9096", "tipo": "barra",
             "dados": [[str(k), v["total"]] for k, v in enumerate(vet) if not v["contra"]]},
            {"nome": "Partido do presidente em minoria em ao menos uma Casa", "cor": "#E8A33D", "tipo": "barra",
             "dados": [[str(k), v["total"]] for k, v in enumerate(vet) if v["contra"]]},
        ],
    }
    fechados = [v for v in vet if v["cong"] < 119]
    med_a = sum(v["total"] for v in fechados if not v["contra"]) / sum(1 for v in fechados if not v["contra"])
    med_c = sum(v["total"] for v in fechados if v["contra"]) / sum(1 for v in fechados if v["contra"])

    # vetos contra a bancada do presidente na Câmara, com a reta
    def disp_vetos(desde):
        base = [v for v in todos if v["ano"] >= desde and v["cong"] < 119]
        a, b = mmq([v["cam_pct"] for v in base], [v["total"] for v in base])
        pts = [{"x": v["cam_pct"], "y": v["total"], "rot": "%s %d" % (NOMES_V.get(v["pres"], v["pres"]), v["ano"]),
                "cor": D if PARTIDO_V[v["pres"]] == "D" else R,
                "dica": "%dº Congresso (%d-%d), %s: %s%% da Câmara, %d vetos"
                        % (v["cong"], v["ano"], v["ano"] + 1, NOMES_V.get(v["pres"], v["pres"]),
                           nf(v["cam_pct"]), v["total"])} for v in base]
        atual = [v for v in todos if v["cong"] == 119][0]
        pts.append({"x": atual["cam_pct"], "y": atual["total"], "rot": "Trump 2025 (até agora)", "cor": R,
                    "destaque": True, "dica": "119º Congresso (2025-2026), Trump: %s%% da Câmara, %d vetos até agora"
                    % (nf(atual["cam_pct"]), atual["total"])})
        xs = [q["x"] for q in pts]
        rq, rqa, n = r2([v["cam_pct"] for v in base], [v["total"] for v in base])
        return a, b, (rq, rqa, n), {
            "pontos": pts, "unidade": "n",
            "eixoX": {"rot": "Cadeiras do partido do presidente na Câmara (%)", "unidade": "pct1"},
            "eixoY": {"rot": "Vetos no Congresso", "unidade": "n", "min": 0},
            "reta": {"a": a, "b": b, "de": min(xs), "ate": max(xs)},
            "legenda": [{"rot": "Presidente democrata", "cor": D}, {"rot": "Presidente republicano", "cor": R},
                        {"rot": "Tendência (R² %s; ajustado %s)" % (nf(rq, 2), nf(rqa, 2)), "cor": "linha:#FFFFFF"}]}
    va45, vb45, vr45, dv45 = disp_vetos(1945)
    va81, vb81, vr81, dv81 = disp_vetos(1981)
    g_vdisp = {
        "id": "midterms-historia-vetos-camara", "tipo": "dispersao",
        "titulo": "Cadeiras do partido do presidente na Câmara e vetos",
        "subtitulo": "Um Congresso de dois anos por ponto; reta de tendência sem o Congresso atual",
        "fonte": "The American Presidency Project (UCSB)",
        "legenda": [{"rot": "Presidente democrata", "cor": D}, {"rot": "Presidente republicano", "cor": R},
                    {"rot": "Tendência", "cor": "linha:#FFFFFF"}],
        "variantes": [dict(rot="desde 1981", **dv81), dict(rot="desde 1945", **dv45)],
    }

    # ---- texto
    menor = min((m for m in hist if m["aprov"] is not None), key=lambda m: m["aprov"])
    assert menor["aprov"] < m26["aprov"] and sum(1 for m in hist if m["aprov"] is not None and m["aprov"] < m26["aprov"]) == 1, \
        "revisar a frase da aprovação: mais de um presidente abaixo de Trump"
    perderam = [m for m in hist if m["cam"] < 0]
    ganharam = [str(m["ano"]) for m in hist if m["cam"] > 0]
    texto_barras = (
        "**O partido do presidente quase sempre perde na midterm.** Das %d eleições de meio de mandato desde "
        "1934, ele perdeu cadeiras na Câmara em %d; só ganhou em %s. Em 2026, os republicanos já perderam %d "
        "cadeiras na Câmara e, se quem lidera vencer nas que faltam, a perda chega a %d. Seria a %dª maior desde "
        "1934 em número de cadeiras%s; em proporção da bancada, seria a %dª: %s%% das %d cadeiras que o partido "
        "tinha."
    ) % (len(hist), len(perderam), lista_pt(ganharam), -conf, -cen, pos_cen,
         empate([m for m in hist if m["cam"] == cen]), pos_pct,
         nf(-cen / m26["def_cam"] * 100), m26["def_cam"])
    pos_sen = 1 + sum(1 for m in hist if m["sen"] < scen)
    texto_sen = (
        "No Senado, os republicanos perderam %d das 22 cadeiras que defendiam%s. Em número, a perda maior desde "
        "1934 foi a de 1958, de 13 cadeiras; a de 2026, com %d, fica em %dº lugar%s."
    ) % (-sconf, (" (%d se o Mississippi também virar)" % -scen) if scen != sconf else "", -scen, pos_sen,
         empate([m for m in hist if m["sen"] == scen]))
    texto_disp = (
        "**Quanto mais impopular o presidente, maior a perda, mas a relação é frouxa.** Na reta de 1946 a 2022, "
        "cada 10 pontos a menos de aprovação custam em média %s cadeiras no Senado e %s na Câmara. Com %s%% "
        "de aprovação, abaixo de todos os presidentes da tabela menos %s em %d (%d%%), a reta previa para Trump "
        "%s cadeiras no Senado e %s na Câmara; até agora são %s e %s.\n\n"
        "A aprovação explica pouco da perda: o R² da reta é de %s no Senado (%s ajustado) e de %s na Câmara (%s "
        "ajustado), com %d midterms. Ou seja, cerca de %s%% e %s%% da variação nas cadeiras acompanham a "
        "aprovação. O resto depende de outras coisas, como o mapa de cada eleição e quantas cadeiras o partido "
        "defendia, que a reta não mede."
    ) % (nf(sb * 10), nf(cb * 10), nf(m26["aprov"]), NOMES[menor["pres"]], menor["ano"], menor["aprov"],
         sinal(round(sprev)), sinal(round(cprev)),
         sinal(sconf), sinal(conf),
         nf(sr2[0], 2), nf(sr2[1], 2), nf(cr2[0], 2), nf(cr2[1], 2), sr2[2],
         nf(sr2[0] * 100, 0), nf(cr2[0] * 100, 0))
    texto_vet = (
        "**O que muda a partir de 2027 é o veto.** Desde 1981, quando o partido do presidente tinha a maioria "
        "nas duas Casas, cada Congresso de dois anos teve em média %s vetos; quando estava em minoria em ao "
        "menos uma delas, %s. Trump vetou %d projetos neste Congresso. Com a Câmara e o Senado nas mãos dos "
        "democratas, é a oposição que decide o que vai a voto, e o veto vira a principal defesa do presidente: "
        "para derrubá-lo são precisos dois terços das duas Casas."
    ) % (nf(med_a), nf(med_c), vet[-1]["total"])

    texto_vdisp = (
        "A relação aparece também contra o tamanho da bancada. Desde 1981, cada 10 pontos a menos de cadeiras do "
        "partido do presidente na Câmara vêm, na média, com %s vetos a mais por Congresso, e a bancada explica "
        "%s%% da variação dos vetos (R² de %s; %s ajustado, com %d Congressos). Contando desde 1945, a reta é "
        "mais plana (%s por 10 pontos) e explica quase nada (R² de %s; %s ajustado): nos anos 1940 e 1950, "
        "Truman e Eisenhower vetaram dezenas de projetos privados, de interesse de uma pessoa só, mesmo com o "
        "Congresso a favor."
    ) % (nf(-vb81 * 10), nf(vr81[0] * 100, 0), nf(vr81[0], 2), nf(vr81[1], 2), vr81[2],
         nf(-vb45 * 10), nf(vr45[0], 2), nf(vr45[1], 2))

    return [
        {"titulo": "As midterms de outros presidentes", "texto": texto_barras + "\n\n" + texto_sen, "graficos": [g_barras]},
        {"titulo": "", "texto": texto_disp, "graficos": [g_disp]},
        {"titulo": "", "texto": "", "graficos": [g_tab]},
        {"titulo": "", "texto": texto_vet, "graficos": [g_vet]},
        {"titulo": "", "texto": texto_vdisp, "graficos": [g_vdisp]},
    ]


def empate(iguais):
    if not iguais:
        return ""
    anos = [str(m["ano"]) for m in sorted(iguais, key=lambda m: m["ano"])]
    return ", empatada com a de %s" % lista_pt(anos) if len(anos) == 1 else ", empatada com as de %s" % lista_pt(anos)


def lista_pt(xs):
    return (", ".join(xs[:-1]) + " e " + xs[-1]) if len(xs) > 1 else xs[0]
