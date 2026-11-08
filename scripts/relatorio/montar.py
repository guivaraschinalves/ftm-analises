#!/usr/bin/env python3
"""
Monta o relatório em slides (PDF 16:9) no formato dos relatórios da Liberta
Wealth: logos no alto à esquerda, "Análise:" em tópicos à esquerda e o
gráfico do site à direita.

    python3 scripts/relatorio/montar.py textos/relatorio-2026-11.md saida.pdf

O texto de cada slide mora no .md (formato no topo do arquivo de exemplo):

    ## capa                 subtítulo na linha seguinte
    ## secao                nome da seção na linha seguinte
    ## grafico: Título do gráfico no site | Variante (opcional)
    ## tabela: Título de uma tabela do JSON da análise
    ## copom: Título do slide (lado direito: os pares "saiu:"/"entrou:")
    - **Destaque:** texto do tópico

Os gráficos saem do próprio site (Baixar > SVG, 16:9, tema escuro), por
exportar_svgs.js, com um servidor local temporário. O fundo preto e o logo do
SVG são tirados: o slide tem o fundo e os logos dele. O PDF sai do Chrome
headless (pdf.js).
"""
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
NODE_PATH = os.path.expanduser("~/.npm/_npx/e41f203b7505f1fb/node_modules")
LOGO_WEALTH = os.path.join(os.path.dirname(RAIZ), "lps-ftm", "public", "lp", "ftm", "logo-liberta-wealth.svg")
BEGE = "#cfc7a2"


def ler(caminho):
    meta, slides, atual = {}, [], None
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.rstrip("\n")
        if linha.startswith("# "):
            meta["titulo"] = linha[2:].strip()
        elif linha.startswith("## "):
            tipo, _, resto = linha[3:].partition(":")
            titulo, _, variante = resto.partition("|")
            atual = dict(tipo=tipo.strip(), titulo=titulo.strip(), variante=variante.strip(),
                         topicos=[], linhas=[], pares=[])
            slides.append(atual)
        elif atual is None and re.match(r"^\w+:", linha):
            k, _, v = linha.partition(":")
            meta[k.strip()] = v.strip()
        elif atual is not None and linha.startswith("- "):
            atual["topicos"].append(linha[2:].strip())
        elif atual is not None and re.match(r"^(saiu|entrou|tema):", linha):
            k, _, v = linha.partition(":")
            atual["pares"].append((k, v.strip()))
        elif atual is not None and linha.strip():
            atual["linhas"].append(linha.strip())
    return meta, slides


def negrito(t):
    t = html.escape(t)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)


def porta_livre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def limpar_svg(txt):
    """Tira o retângulo de fundo e o logo do FtM que o site põe no SVG."""
    txt = re.sub(r'(<svg[^>]*>)\s*<rect x="0" y="0" width="\d+" height="\d+" fill="#000000"\s*/?>(</rect>)?',
                 r"\1", txt, count=1)
    # o logo é um <svg> aninhado no canto direito, de onde sai o primeiro <g fill=...>
    txt = re.sub(r'<svg x="1712" y="20"[^>]*>.*?</svg>', "", txt, count=1, flags=re.S)
    return txt


def logos(tamanho=1.0):
    ftm = open(os.path.join(RAIZ, "assets", "logo-ftm.svg"), encoding="utf-8").read()
    ftm = re.sub(r"<\?xml[^>]*>", "", ftm)
    wealth = open(LOGO_WEALTH, encoding="utf-8").read()
    return ('<div class="logos" style="--k:%s"><div class="ftm">%s</div><div class="traco"></div>'
            '<div class="wealth">%s</div></div>' % (tamanho, ftm, wealth))


def tabela_html(g):
    cab = "".join("<th class='%s'>%s</th>" % ("num" if c.get("num") else "", html.escape(c["rot"]))
                  for c in g["colunas"])
    linhas = []
    for l in g["linhas"]:
        cel = []
        for c, col in zip(l, g["colunas"]):
            estilo = ("color:%s;" % c["cor"]) if c.get("cor") else ""
            if c.get("forte"):
                estilo += "font-weight:700;"
            cel.append("<td class='%s' style='%s'>%s</td>" % ("num" if col.get("num") else "", estilo,
                                                              html.escape(c["t"])))
        linhas.append("<tr>%s</tr>" % "".join(cel))
    return ('<div class="painel"><h1>%s</h1><h2>%s</h2><table><thead><tr>%s</tr></thead><tbody>%s</tbody>'
            '</table></div><div class="fonte">Fonte: %s.</div>'
            % (html.escape(g["titulo"]), html.escape(g.get("subtitulo", "")), cab, "".join(linhas),
               html.escape(g["fonte"])))


def copom_html(s):
    itens, tema = [], None
    for k, v in s["pares"]:
        if k == "tema":
            itens.append("<div class='tema'>%s</div>" % html.escape(v))
        else:
            itens.append("<div class='%s'><span>%s</span> %s</div>"
                         % (k, "Saiu" if k == "saiu" else "Entrou", html.escape(v)))
    return ('<div class="painel"><h1>%s</h1><h2>Trechos que saíram e entraram em relação ao comunicado de '
            '16/09/2026</h2><div class="pares">%s</div></div><div class="fonte">Fonte: Banco Central do '
            'Brasil e FtM/Liberta Wealth.</div>' % (html.escape(s["titulo"]), "".join(itens)))


CSS = """
@page { size: 2400px 1350px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; background: #000; font-family: Calibri, Carlito, 'Segoe UI', Arial, sans-serif; color: #fff; }
.slide { width: 2400px; height: 1350px; position: relative; overflow: hidden; page-break-after: always;
         background: #000 url(fundo.jpg) center / cover no-repeat; }
.slide::before { content: ""; position: absolute; inset: 0; background: rgba(0,0,0,.35); }
.slide > * { position: absolute; }
.logos { left: 30px; top: 26px; width: calc(150px * var(--k)); }
.logos .ftm { color: #fff; } .logos svg { width: 100%; height: auto; display: block; }
.logos .traco { height: 4px; background: BEGE; margin: calc(8px * var(--k)) calc(-28px * var(--k)) calc(12px * var(--k)); }
.analise { left: 90px; top: 300px; width: 690px; }
.analise h3 { font-size: 46px; font-weight: 400; color: BEGE; margin: 0 0 40px; }
.analise ul { margin: 0; padding-left: 44px; }
.analise li { font-size: 34px; line-height: 1.32; margin: 0 0 34px; padding-left: 6px; }
.grafico { left: 790px; top: 215px; width: 1600px; height: 900px; }
.grafico img { width: 100%; height: 100%; display: block; }
.linha-a { left: 806px; top: 305px; width: 2px; height: 55px; background: BEGE; }
.linha-b { left: 1450px; top: 1163px; width: 912px; height: 2px; background: BEGE; }
.linha-c { left: 2360px; top: 1115px; width: 2px; height: 50px; background: BEGE; }
.painel { left: 830px; top: 170px; width: 1520px; }
.painel h1 { font-size: 64px; margin: 0 0 10px; }
.painel h2 { font-size: 34px; font-style: italic; font-weight: 400; margin: 0 0 40px; color: rgba(255,255,255,.85); }
table { width: 100%; border-collapse: collapse; font-size: 30px; }
th { text-align: left; color: BEGE; font-weight: 700; border-bottom: 2px solid BEGE; padding: 10px 14px; }
td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.15); }
th.num, td.num { text-align: right; }
.pares { display: grid; gap: 16px; }
.pares .tema { font-size: 30px; font-weight: 700; color: BEGE; margin-top: 14px; }
.pares .saiu, .pares .entrou { font-size: 29px; line-height: 1.3; padding: 8px 16px; border-radius: 6px; }
.pares .saiu { background: rgba(192,80,77,.22); text-decoration: line-through; text-decoration-color: rgba(255,120,110,.8); }
.pares .entrou { background: rgba(155,187,89,.22); }
.pares span { font-weight: 700; text-decoration: none; display: inline-block; min-width: 110px; }
.pares .saiu span { color: #ff8a80; } .pares .entrou span { color: #c5e1a5; }
.fonte { right: 40px; bottom: 18px; font-size: 22px; color: rgba(255,255,255,.9); }
.capa .logos, .secao .logos { left: 160px; top: 150px; }
.capa h1 { left: 160px; top: 540px; font-size: 128px; margin: 0; white-space: nowrap; line-height: 1; }
.capa h2 { left: 160px; top: 740px; font-size: 58px; font-weight: 400; font-style: italic; margin: 0; color: rgba(255,255,255,.9); }
.capa .data { left: 160px; top: 850px; font-size: 44px; color: BEGE; }
.capa .traco-capa { left: 160px; top: 700px; width: 520px; height: 4px; background: BEGE; }
.secao h1 { left: 160px; top: 600px; font-size: 140px; margin: 0; }
.secao .traco-capa { left: 160px; top: 800px; width: 520px; height: 4px; background: BEGE; }
""".replace("BEGE", BEGE)


def montar(md, saida):
    meta, slides = ler(md)
    with open(os.path.join(RAIZ, "dados", meta["dados"]), encoding="utf-8") as f:
        doc = json.load(f)
    graficos = {g["titulo"]: g for s in doc["secoes"] for g in s.get("graficos", [])}
    trab = tempfile.mkdtemp(prefix="relatorio-")
    try:
        lista = [dict(titulo=s["titulo"], variante=s["variante"] or None, arquivo="g%02d.svg" % i)
                 for i, s in enumerate(slides) if s["tipo"] == "grafico"]
        with open(os.path.join(trab, "lista.json"), "w", encoding="utf-8") as f:
            json.dump(lista, f, ensure_ascii=False)
        porta = porta_livre()
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(porta), "--bind", "127.0.0.1"],
                               cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(1)
            env = dict(os.environ, NODE_PATH=NODE_PATH)
            subprocess.run(["node", os.path.join(AQUI, "exportar_svgs.js"), str(porta), meta["assunto"],
                            os.path.join(trab, "lista.json"), trab], check=True, env=env)
        finally:
            srv.terminate()
        shutil.copy(os.path.join(RAIZ, "assets", "fundo.jpg"), trab)

        paginas = []
        for i, s in enumerate(slides):
            if s["tipo"] == "capa":
                paginas.append('<section class="slide capa">%s<h1>%s</h1><div class="traco-capa"></div><h2>%s</h2>'
                               '<div class="data">%s</div></section>'
                               % (logos(1.6), html.escape(meta["titulo"]), html.escape(" ".join(s["linhas"])),
                                  html.escape(meta.get("data", ""))))
                continue
            if s["tipo"] == "secao":
                paginas.append('<section class="slide secao">%s<h1>%s</h1><div class="traco-capa"></div></section>'
                               % (logos(1.6), html.escape(" ".join(s["linhas"]))))
                continue
            analise = ('<div class="analise"><h3>Análise:</h3><ul>%s</ul></div>'
                       % "".join("<li>%s</li>" % negrito(t) for t in s["topicos"]))
            if s["tipo"] == "grafico":
                arq = os.path.join(trab, "g%02d.svg" % i)
                if not os.path.exists(arq):
                    raise SystemExit("faltou o gráfico: %s" % s["titulo"])
                with open(arq, encoding="utf-8") as f:
                    svg = limpar_svg(f.read())
                with open(arq, "w", encoding="utf-8") as f:
                    f.write(svg)
                direita = ('<div class="grafico"><img src="g%02d.svg"></div><div class="linha-a"></div>'
                           '<div class="linha-b"></div><div class="linha-c"></div>' % i)
            elif s["tipo"] == "tabela":
                direita = tabela_html(graficos[s["titulo"]])
            elif s["tipo"] == "copom":
                direita = copom_html(s)
            else:
                raise SystemExit("tipo de slide desconhecido: %s" % s["tipo"])
            paginas.append('<section class="slide">%s%s%s</section>' % (logos(), analise, direita))

        pagina = os.path.join(trab, "relatorio.html")
        with open(pagina, "w", encoding="utf-8") as f:
            f.write('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>%s</title><style>%s</style>'
                    '</head><body>%s</body></html>' % (html.escape(meta["titulo"]), CSS, "".join(paginas)))
        previas = [os.environ["PREVIAS"]] if os.environ.get("PREVIAS") else []
        subprocess.run(["node", os.path.join(AQUI, "pdf.js"), pagina, os.path.abspath(saida)] + previas, check=True,
                       env=dict(os.environ, NODE_PATH=NODE_PATH))
        print("gravado %s: %d slides" % (saida, len(paginas)))
    finally:
        if os.environ.get("MANTER") != "1":
            shutil.rmtree(trab, ignore_errors=True)
        else:
            print("pasta de trabalho mantida:", trab)


if __name__ == "__main__":
    montar(sys.argv[1], sys.argv[2])
