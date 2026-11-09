#!/usr/bin/env python3
"""
Exporta uma análise do site para um arquivo de texto (Markdown) que dá para
mandar a outra pessoa ou colar numa IA: o texto de cada seção, os números de
cada gráfico em tabela e as fontes com link, numeradas.

    python3 scripts/exportar_md.py dados/ueno-bank.json saida.md

Séries mensais e diárias saem com um ponto por mês (o último do mês), nos
últimos 10 anos. Se a série cobre mais de três anos, só os meses de fim de
trimestre (março, junho, setembro, dezembro), mais o primeiro e o último
ponto, para a tabela caber; a página tem a série inteira.

Os gráficos que não são série também entram: comunicados (o texto do mais
recente), ranking, hemiciclo, dispersão, tabela e simulador (premissas e o
resultado do padrão).

Só biblioteca padrão.
"""
import json
import re
import sys

MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()
SITE = "https://guivaraschinalves.github.io/ftm-analises/"


def fmt_num(v, casas):
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt(v, unidade):
    if v is None:
        return ""
    if unidade.startswith("pct") or unidade == "%":
        return fmt_num(v, 1 if unidade == "pct1" else 2) + "%"
    if unidade == "gs-tri":
        return "₲ " + fmt_num(v, 2) + " tri"
    if unidade == "usd-bi":
        return "US$ " + fmt_num(v, 1) + " bi"
    if unidade == "usd-tri":
        return "US$ " + fmt_num(v, 2) + " tri"
    if unidade == "brl":
        return "R$ " + fmt_num(v, 4)
    if unidade == "pb":
        return fmt_num(v, 0) + " pb"
    if abs(v) >= 1000 or float(v).is_integer():
        return fmt_num(v, 0)
    # até duas casas, sem zero sobrando no fim ("56,5", não "56,50")
    return fmt_num(v, 2).rstrip("0").rstrip(",")


def rot_chave(k):
    if re.fullmatch(r"\d{4}-\d{2}", k):
        return f"{MESES[int(k[5:7]) - 1]}/{k[:4]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k):
        return f"{k[8:]}/{k[5:7]}/{k[:4]}"
    if re.fullmatch(r"\d{4}-Q\d", k):
        return f"{k[-1]}º tri/{k[:4]}"
    return k


def md_tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(str(c) for c in l) + " |" for l in linhas]
    return "\n".join(out)


def tabela_series(grafico, var):
    unidade = var.get("unidade") or grafico.get("unidade", "")
    series = var.get("series") or grafico.get("series") or []
    # muitas linhas (uma por semana do Focus): ficam só as que têm legenda
    if len(series) > 8:
        series = [s for s in series if s.get("legenda") is not False] or series[-3:]
    series = [s for s in series if s.get("dados")]
    if not series:
        return ""
    if grafico.get("categorias"):
        cats = grafico["categorias"]
        dic = [dict(s["dados"]) for s in series]
        linhas = [[c] + [fmt(d.get(str(i)), unidade) for d in dic] for i, c in enumerate(cats)
                  if c and any(str(i) in d for d in dic)]
        return md_tabela(["Categoria"] + [s["nome"] for s in series], linhas)
    # um ponto por mês: o último do mês (as diárias viram mensais)
    dic = []
    for s in series:
        m = {}
        for k, v in sorted(s["dados"]):
            m[k[:7] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", k) else k] = v
        dic.append(m)
    todos = sorted({k for d in dic for k in d})
    # mais de 10 anos: só os últimos 10 (a página tem a série inteira)
    ultimo_ano = int(todos[-1][:4])
    todos = [k for k in todos if int(k[:4]) > ultimo_ano - 10]
    anos = {k[:4] for k in todos}
    if len(anos) > 3:
        todos = [k for k in todos if k in (todos[0], todos[-1]) or k[5:7] in ("03", "06", "09", "12")
                 or k[-2:] in ("Q4",)]
    linhas = [[rot_chave(k)] + [fmt(d.get(k), unidade) for d in dic] for k in todos]
    rot = "Mês" if not str(todos[0]).count("Q") else "Trimestre"
    return md_tabela([rot] + [s["nome"] for s in series], linhas)


def simular(g, e):
    r0, n, ac = g["bases"][e.get("base", 0)]["v"], max(1, round(e["anos"])), g["acoes"]
    ps0, psf = g["preco"] * ac / r0, e["pl"] * e["margem"] / 100
    rec = r0 * (1 + e["cresc"] / 100) ** n
    preco = rec * (ps0 + (psf - ps0)) / ac
    meta = g["preco"] * (1 + e["retorno"] / 100) ** n
    return n, rec, preco, meta, ((max(preco, 0) / g["preco"]) ** (1 / n) - 1) * 100


def bloco_grafico(g):
    t = g.get("tipo")
    if t == "comunicados":
        c = g["comunicados"][-1]
        ant = g["comunicados"][-2]["data"] if len(g["comunicados"]) > 1 else None
        txt = [f"Comunicado de {rot_chave(c['data'])} (a página compara com qualquer outro; o anterior é de "
               f"{rot_chave(ant)}):", ""] if ant else []
        return "\n".join(txt) + "\n" + "\n>\n".join("> " + p for p in c["paragrafos"])
    if t == "ranking":
        u = g.get("unidade", "")
        return md_tabela(["Item", "Valor"], [[i[0], fmt(i[1], u)] for i in g["itens"]])
    if t == "hemiciclo":
        return md_tabela(["Grupo", "Cadeiras"], [[gr["nome"], gr["n"]] for gr in g["grupos"]]) + \
            (f"\n\nMaioria: {g['maioria']}." if g.get("maioria") else "")
    if t == "tabela":
        return md_tabela([c["rot"] for c in g["colunas"]], [[c["t"] for c in l] for l in g["linhas"]])
    if t == "simulador":
        e = g["padrao"]
        n, rec, preco, meta, ret = simular(g, e)
        base = g["bases"][e.get("base", 0)]
        return "\n".join([
            f"Preço de partida: US$ {fmt_num(g['preco'], 0)} por ação; {fmt_num(g['acoes'], 2)} bilhões de ações.",
            f"Premissas do padrão: receita-base {base['rot']} (US$ {fmt_num(base['v'], 1)} bi), crescimento de "
            f"{fmt_num(e['cresc'], 0)}% ao ano, margem líquida final de {fmt_num(e['margem'], 0)}%, P/L de saída de "
            f"{fmt_num(e['pl'], 0)}, retorno exigido de {fmt_num(e['retorno'], 1)}% ao ano, horizonte de {n} anos.",
            f"Resultado do padrão: receita de US$ {fmt_num(rec, 0)} bi no ano {n}; preço projetado de "
            f"US$ {fmt_num(preco, 0)} contra a meta de US$ {fmt_num(meta, 0)}; retorno anual implícito de "
            f"{fmt_num(ret, 1)}%.",
            "Na página, cada premissa pode ser mudada."])
    if t == "dispersao":
        partes = []
        for v in g.get("variantes", [g]):
            if "variantes" in g:
                partes += [f"**{v['rot']}**", ""]
            linhas = [[p.get("rot", ""), fmt_num(p["x"], 1), fmt_num(p["y"], 0)] for p in v["pontos"]]
            partes.append(md_tabela(["Ponto", v.get("eixoX", {}).get("rot", "x"), v.get("eixoY", {}).get("rot", "y")],
                                    linhas))
            if v.get("reta"):
                r = v["reta"]
                partes.append(f"\nReta de tendência: y = {fmt_num(r['a'], 2)} + {fmt_num(r['b'], 3)} × x.")
            partes.append("")
        return "\n".join(partes)
    if t == "figura":
        return f"Imagem de terceiros: {g.get('link') or g.get('imagem')}"
    partes = []
    for v in g.get("variantes", [g]):
        if "variantes" in g:
            partes += [f"**{v['rot']}**", ""]
        partes += [tabela_series(g, v), ""]
    return "\n".join(partes)


def main():
    entrada, saida = sys.argv[1], sys.argv[2]
    d = json.load(open(entrada, encoding="utf-8"))
    refs, numero = [], {}
    fontes_secao = {}

    def citar(m):
        trecho, fid = m.group(1), m.group(2)
        chave = (fid, json.dumps(fontes_secao.get(fid), sort_keys=True))
        if chave not in numero:
            refs.append(fontes_secao.get(fid, {"rot": fid}))
            numero[chave] = len(refs)
        return f"{trecho} [{numero[chave]}]"

    a = d["atualizado"]
    partes = [f"# {d['assunto']}", "",
              f"Follow the Money, Análises. Atualizado em {a[8:10]}/{a[5:7]}/{a[:4]}"
              + (f"; dados até {rot_chave(d['referencia'])}." if d.get("referencia") else "."),
              "",
              "Este arquivo reúne o texto da análise, os números de cada gráfico em tabela e as fontes. "
              "Séries longas aparecem trimestrais, nos últimos 10 anos (mais o primeiro e o último ponto); as curtas, "
              "mês a mês. A página tem as séries inteiras.", ""]
    for s in d["secoes"]:
        fontes_secao = {f["id"]: f for f in s.get("fontes", [])}
        if s.get("parte"):
            partes += [f"# {s['parte']}", ""]
        if s.get("titulo"):
            partes += [f"## {s['titulo']}", ""]
        if s.get("texto"):
            partes += [re.sub(r"\[([^\]]+)\]\(fonte:([^)]+)\)", citar, s["texto"]), ""]
        for g in s.get("graficos", []):
            partes += [f"### Gráfico: {g['titulo']}", ""]
            if g.get("subtitulo"):
                partes += [g["subtitulo"] + ".", ""]
            corpo = bloco_grafico(g)
            if corpo.strip():
                partes += [corpo.rstrip(), ""]
            if g.get("fonte"):
                partes += [f"Fonte: {g['fonte']}.", ""]
    partes += ["## Fontes e notas", ""]
    for i, f in enumerate(refs, 1):
        url = f.get("url", "")
        if url.startswith("#"):
            url = SITE + url
        partes.append(f"{i}. {f['rot']}" + (f": {url}" if url else ""))
    texto = "\n".join(partes) + "\n"
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    open(saida, "w", encoding="utf-8").write(texto)
    print(f"gravado {saida}: {len(d['secoes'])} seções, {len(refs)} fontes, {len(texto) // 1024} KB")


if __name__ == "__main__":
    main()
