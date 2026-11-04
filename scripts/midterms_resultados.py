#!/usr/bin/env python3
"""
A seção "Os resultados" do assunto das midterms (dados/midterms-2026.json).
Não roda sozinho: o scripts/midterms.py chama secoes() e põe o resultado
depois da explicação. Só biblioteca padrão.

DE ONDE VÊM OS NÚMEROS

  A apuração que a CNN publica (a mesma das páginas de resultado dela, da
  Edison Research), um arquivo por tipo de disputa:
      politics.api.cnn.io/results/national-races/2026-HG.json   Câmara
      politics.api.cnn.io/results/national-races/2026-SG.json   Senado
      politics.api.cnn.io/results/national-races/2026-GG.json   governadores
  Em cada disputa: status W = com vencedor projetado, U = sem resultado,
  V = vai a segundo turno (os dois candidatos com runoffCandidate);
  isSwitch = a cadeira trocou de partido. O arquivo da Câmara traz uma 436ª
  disputa, a eleição especial do TX-18 (ecKey 2026-HQ-...), que fica de fora
  da conta das 435.

  Ficam em dados/.cache-midterms/ (fora do git); --atualizar baixa de novo.
  A apuração anda durante dias: rodar de novo atualiza números e texto.

  O que não está no arquivo e vai digitado: as curiosidades (quem foi o
  último senador ou governador de cada partido) e as regras do que falta
  (voto ranqueado no Alasca, Mississippi sem segundo turno em eleição
  federal). Cada curiosidade só entra se o resultado que ela comenta
  estiver confirmado no arquivo.
"""
import datetime as dt
import json

from midterms_motivos import baixar

D, R, I = "#3B7DD8", "#D9453D", "#A979D9"
PARTIDO = {"DEM": "D", "REP": "R"}


def disputas(tipo):
    url = "https://politics.api.cnn.io/results/national-races/2026-%s.json" % tipo
    return json.loads(baixar(url, "cnn-resultados-2026-%s.json" % tipo))


def resumo(r):
    cs = sorted(r["candidates"], key=lambda c: -c["voteNum"])
    w = [c for c in r["candidates"] if c["winner"]]
    return {
        "uf": r["stateAbbreviation"], "nome": r["stateName"], "status": r["status"],
        "vira": r["isSwitch"], "apurado": r["percentReporting"],
        "venc": w[0] if w else None, "lider": cs[0] if cs else None, "seg": cs[1] if len(cs) > 1 else None,
        "segundo_turno": [c for c in r["candidates"] if c.get("runoffCandidate")],
        "distrito": r.get("jurisdictionCode"),
    }


def partido(c):
    return PARTIDO.get(c["majorParty"], "I") if c else None


def nome(c):
    return c["fullName"].replace(" S. ", " ").strip()


def hora_brasilia(dados):
    ts = max(r["extractedAt"] for lista in dados for r in lista)
    t = dt.datetime.fromisoformat(ts[:19]) - dt.timedelta(hours=3)
    return t.strftime("%d/%m/%Y, %Hh%M")


def secoes(NOME):
    """NOME: {UF: nome do estado em português}, o mesmo do midterms.py."""
    camara, senado, gov = disputas("HG"), disputas("SG"), disputas("GG")
    quando = hora_brasilia([camara, senado, gov])
    cam = [resumo(r) for r in camara if r["ecKey"].startswith("2026-HG-")]
    sen = {s["uf"]: s for s in map(resumo, senado)}
    gv = {s["uf"]: s for s in map(resumo, gov)}
    assert len(cam) == 435 and len(sen) == 35 and len(gv) == 36, (len(cam), len(sen), len(gv))

    # ---------- Câmara ----------
    eleitos = {"D": 0, "R": 0, "I": 0}
    lidera = {"D": 0, "R": 0, "I": 0}
    viradas = {"D": 0, "R": 0, "I": 0}
    seg_turno = []
    for s in cam:
        if s["status"] == "W":
            eleitos[partido(s["venc"])] += 1
            if s["vira"]:
                viradas[partido(s["venc"])] += 1
        elif s["status"] == "V":
            seg_turno.append(s)
        else:
            lidera[partido(s["lider"])] += 1
    pend_cam = sum(lidera.values()) + len(seg_turno)
    pend_ca = sum(1 for s in cam if s["uf"] == "CA" and s["status"] != "W")
    print("resultados (%s): Câmara D %d, R %d, sem resultado %d" % (quando, eleitos["D"], eleitos["R"], pend_cam))

    hemi_camara = {
        "id": "midterms-resultado-camara", "tipo": "hemiciclo",
        "titulo": "Câmara dos Representantes: resultado da eleição",
        "subtitulo": "Cadeiras com vencedor projetado e, nas outras, quem lidera a apuração; %s" % quando,
        "fonte": "Edison Research para a CNN",
        "centro": [str(eleitos["D"]), "democratas eleitos"], "maioria": 218,
        "grupos": [g for g in [
            {"nome": "Democratas eleitos", "n": eleitos["D"], "cor": D},
            {"nome": "Sem resultado, democrata à frente", "n": lidera["D"], "cor": D, "apagado": True},
            {"nome": "Segundo turno", "n": len(seg_turno), "cor": "vazio"},
            {"nome": "Sem resultado, outro à frente", "n": lidera["I"], "cor": I, "apagado": True},
            {"nome": "Sem resultado, republicano à frente", "n": lidera["R"], "cor": R, "apagado": True},
            {"nome": "Republicanos eleitos", "n": eleitos["R"], "cor": R},
        ] if g["n"]],
    }

    # ---------- Senado ----------
    fora = {"D": 32, "I": 2, "R": 31}          # cadeiras que não estavam em disputa
    sen_el = {"D": 0, "R": 0, "I": 0}
    sen_vira = []
    sen_pend = []
    for s in sen.values():
        if s["status"] == "W":
            sen_el[partido(s["venc"])] += 1
            if s["vira"]:
                sen_vira.append(s)
        else:
            sen_pend.append(s)
    total_d = fora["D"] + fora["I"] + sen_el["D"] + sen_el["I"]
    total_r = fora["R"] + sen_el["R"]
    hemi_senado = {
        "id": "midterms-resultado-senado", "tipo": "hemiciclo",
        "titulo": "Senado: resultado da eleição",
        "subtitulo": "Composição a partir de 2027 com as cadeiras já definidas; %s" % quando,
        "fonte": "Edison Research para a CNN",
        "centro": ["%d x %d" % (total_d, total_r), "democratas x republicanos"], "maioria": 51,
        "grupos": [g for g in [
            {"nome": "Democratas fora da eleição", "n": fora["D"], "cor": D, "apagado": True},
            {"nome": "Independentes que votam com os democratas", "n": fora["I"], "cor": I, "apagado": True},
            {"nome": "Democratas eleitos", "n": sen_el["D"], "cor": D},
            {"nome": "Sem resultado", "n": len(sen_pend), "cor": "vazio"},
            {"nome": "Republicanos eleitos", "n": sen_el["R"], "cor": R},
            {"nome": "Republicanos fora da eleição", "n": fora["R"], "cor": R, "apagado": True},
        ] if g["n"]],
    }

    def mapa(disp, ident, titulo, cargo, todos):
        est = []
        for uf in todos:
            s = disp.get(uf)
            if not s:
                est.append({"uf": uf, "rot": uf if uf != "DC" else None,
                            "dica": "%s: sem eleição para %s em 2026" % (todos[uf], cargo)})
                continue
            if s["status"] == "W":
                p = partido(s["venc"])
                est.append({"uf": uf, "rot": uf, "cor": {"D": D, "R": R}.get(p, I), "destaque": s["vira"],
                            "dica": "%s: %s (%s) eleito com %s%%%s" % (
                                todos[uf], nome(s["venc"]), p, s["venc"]["votePercentStr"].replace(".", ","),
                                "; trocou de partido" if s["vira"] else "")})
            else:
                est.append({"uf": uf, "rot": uf, "cor": "pendente",
                            "dica": "%s: sem resultado; %s (%s) %s%% x %s (%s) %s%%, %d%% apurado" % (
                                todos[uf], nome(s["lider"]), partido(s["lider"]), s["lider"]["votePercentStr"].replace(".", ","),
                                nome(s["seg"]), partido(s["seg"]), s["seg"]["votePercentStr"].replace(".", ","), s["apurado"])})
        n = lambda f: sum(1 for e in est if f(e))  # noqa: E731
        return {
            "id": ident, "tipo": "estados", "titulo": titulo,
            "subtitulo": "Partido do vencedor projetado; contorno destacado: trocou de partido; %s" % quando,
            "fonte": "Edison Research para a CNN; mapa: Census Bureau",
            "estados": est, "foraDoMapa": ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD"],
            "legenda": [
                {"rot": "Democrata (%d)" % n(lambda e: e.get("cor") == D), "cor": D},
                {"rot": "Republicano (%d)" % n(lambda e: e.get("cor") == R), "cor": R},
                {"rot": "Trocou de partido (%d)" % n(lambda e: e.get("destaque")), "cor": "borda"},
                {"rot": "Sem resultado (%d)" % n(lambda e: e.get("cor") == "pendente"), "cor": "pendente"},
                {"rot": "Sem eleição", "cor": "nenhuma"},
            ],
        }

    mapa_sen = mapa(sen, "midterms-resultado-mapa-senado", "Senado: resultado por estado", "o Senado", NOME)
    mapa_gov = mapa(gv, "midterms-resultado-mapa-governadores", "Governadores: resultado por estado",
                    "governador", NOME)

    # ---------- texto ----------
    lista = lambda xs: (", ".join(xs[:-1]) + " e " + xs[-1]) if len(xs) > 1 else (xs[0] if xs else "")  # noqa: E731
    pt = lambda uf: NOME[uf]  # noqa: E731
    gov_vira = sorted((s for s in gv.values() if s["status"] == "W" and s["vira"]), key=lambda s: pt(s["uf"]))
    gov_pend = sorted((s for s in gv.values() if s["status"] != "W"), key=lambda s: pt(s["uf"]))
    gov_d = 6 + sum(1 for s in gv.values() if s["status"] == "W" and partido(s["venc"]) == "D")
    gov_r = 8 + sum(1 for s in gv.values() if s["status"] == "W" and partido(s["venc"]) == "R")
    vira_d = [s for s in sen_vira if partido(s["venc"]) == "D"]

    texto_intro = (
        "Os números abaixo são da apuração de %s (horário de Brasília). Os resultados ainda mudam: há "
        "cadeiras sem vencedor, e a contagem do voto pelo correio leva dias em vários estados."
    ) % quando
    abre_cam = ("**Os democratas passaram das 218 cadeiras e retomaram a Câmara.** " if eleitos["D"] >= 218
                else "**A Câmara ainda não tem maioria definida.** ")
    texto_camara = abre_cam + (
        "Já são %d democratas eleitos, "
        "contra %d republicanos, e %d cadeiras ainda sem resultado. Os democratas tomaram %d cadeiras que "
        "eram republicanas; os republicanos, %s."
    ) % (eleitos["D"], eleitos["R"], pend_cam, viradas["D"],
         "nenhuma que fosse democrata" if not viradas["R"] else "%d que eram democratas" % viradas["R"])
    texto_senado = ("**No Senado, os democratas viraram %d cadeiras%s.** Tomaram dos republicanos "
                    % (len(vira_d), " e ficaram com a maioria" if total_d >= 51 else "")) + (
        "%s. Com as cadeiras já definidas, o Senado de 2027 terá %d democratas (contando os dois independentes "
        "que votam com eles) e %d republicanos, e %s ainda sem resultado."
    ) % (lista([pt(s["uf"]) for s in sorted(vira_d, key=lambda s: pt(s["uf"]))]),
         total_d, total_r, "%d cadeira" % len(sen_pend) if len(sen_pend) == 1 else "%d cadeiras" % len(sen_pend))
    texto_gov = (
        "**Nos governos estaduais, os democratas tomaram %s.** Somados os 14 estados que não votaram, os "
        "democratas passam a governar ao menos %d estados, e os republicanos, %d; %s sem resultado."
    ) % (lista([pt(s["uf"]) for s in gov_vira]), gov_d, gov_r,
         lista([pt(s["uf"]) for s in gov_pend]) + (" seguem" if len(gov_pend) > 1 else " segue"))

    # curiosidades: cada uma só entra se o resultado dela estiver confirmado
    def venceu(disp, uf, p):
        s = disp.get(uf)
        return s and s["status"] == "W" and partido(s["venc"]) == p

    cur = []
    if venceu(sen, "KS", "D"):
        cur.append("**Kansas** elegeu %s, o primeiro senador democrata do estado desde George McGill, "
                   "derrotado em 1938. Desde janeiro de 1939 as duas cadeiras do Kansas eram republicanas, "
                   "a sequência mais longa de um partido só entre os 50 estados." % nome(sen["KS"]["venc"]))
    if venceu(sen, "TX", "D"):
        cur.append("**Texas** elegeu %s, o primeiro senador democrata do estado desde 1993. O último tinha "
                   "sido Bob Krueger, nomeado para a vaga de Lloyd Bentsen e derrotado na eleição especial "
                   "daquele mesmo ano; o último democrata eleito para o Senado pelo Texas foi o próprio "
                   "Bentsen, em 1988." % nome(sen["TX"]["venc"]))
    if venceu(gv, "TX", "D"):
        cur.append("O **Texas** também elegeu %s governadora, a primeira democrata no cargo desde Ann "
                   "Richards, que governou de 1991 a 1995." % nome(gv["TX"]["venc"]))
    if venceu(sen, "ME", "D") and sen["ME"]["vira"]:
        cur.append("**Susan Collins**, do Maine, senadora desde 1997 e a única republicana da Nova Inglaterra "
                   "no Senado, perdeu para %s." % nome(sen["ME"]["venc"]))
    if venceu(sen, "SC", "D") and sen["SC"]["vira"]:
        cur.append("**Lindsey Graham**, senador pela Carolina do Sul desde 2003, perdeu para %s. O estado não "
                   "tinha senador democrata desde que Fritz Hollings se aposentou, em 2005." % nome(sen["SC"]["venc"]))
    if venceu(sen, "OH", "D") and sen["OH"]["vira"]:
        cur.append("Em **Ohio**, Sherrod Brown voltou ao Senado dois anos depois de perder a própria cadeira, "
                   "em 2024, agora na vaga que foi de JD Vance.")

    falta = []
    if pend_cam:
        falta.append("**Câmara:** %d cadeiras sem resultado, %d delas na Califórnia, que aceita o voto pelo "
                     "correio postado até o dia da eleição e costuma levar semanas para terminar a contagem."
                     % (pend_cam, pend_ca))
    for s in seg_turno:
        a, b = s["segundo_turno"][:2]
        falta.append("**Luisiana, distrito %d:** vai a segundo turno entre %s (%s) e %s (%s)."
                     % (s["distrito"], nome(a), partido(a), nome(b), partido(b)))
    for s in sorted(sen_pend, key=lambda s: pt(s["uf"])):
        dif = abs(s["lider"]["voteNum"] - s["seg"]["voteNum"])
        base = "**Senado, %s:** %s (%s) tem %s%% e %s (%s), %s%%, com %d%% apurado (diferença de %s votos)." % (
            pt(s["uf"]), nome(s["lider"]), partido(s["lider"]), s["lider"]["votePercentStr"].replace(".", ","),
            nome(s["seg"]), partido(s["seg"]), s["seg"]["votePercentStr"].replace(".", ","), s["apurado"],
            "{:,}".format(dif).replace(",", "."))
        if s["uf"] == "AK":
            base += (" O Alasca aceita voto pelo correio que chegue até 10 dias depois da eleição (15, do exterior) "
                     "e, se ninguém passar de 50%, apura o voto ranqueado em 18 de novembro.")
        if s["uf"] == "MS":
            base += " Em eleição federal o Mississippi não tem segundo turno: leva quem tiver mais votos."
        falta.append(base)
    for s in gov_pend:
        base = "**Governador, %s:** %s (%s) tem %s%% e %s (%s), %s%%, com %d%% apurado." % (
            pt(s["uf"]), nome(s["lider"]), partido(s["lider"]), s["lider"]["votePercentStr"].replace(".", ","),
            nome(s["seg"]), partido(s["seg"]), s["seg"]["votePercentStr"].replace(".", ","), s["apurado"])
        if s["uf"] == "AK":
            base += " Também depende do voto ranqueado."
        falta.append(base)
    falta.append("**Depois da apuração:** cada estado certifica o próprio resultado nas próximas semanas, e "
                 "disputas apertadas podem ter recontagem. O novo Congresso toma posse em 3 de janeiro de 2027.")

    return [
        {"titulo": "Os resultados", "texto": texto_intro + "\n\n" + texto_camara, "graficos": [hemi_camara]},
        {"titulo": "", "texto": texto_senado, "graficos": [hemi_senado, mapa_sen]},
        {"titulo": "", "texto": texto_gov, "graficos": [mapa_gov]},
        {"titulo": "Curiosidades", "texto": "\n".join("- " + c for c in cur), "graficos": []},
        {"titulo": "O que falta", "texto": "\n".join("- " + f for f in falta), "graficos": []},
    ]
