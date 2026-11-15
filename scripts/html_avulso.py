#!/usr/bin/env python3
"""
Uma análise num HTML só, que abre com dois cliques, sem servidor e sem
internet: o index.html com o styles.css, o app.js, o JSON da análise, a ordem
gravada e as imagens dentro dele. É o mesmo app do site (troca de recorte,
tela cheia, anotação, baixar o gráfico), só que de um arquivo.

    python3 scripts/html_avulso.py                      # Missão Global Miami
    python3 scripts/html_avulso.py dados/ueno-bank.json # outra análise

Sai em avulso/<nome>.html (fora do git: é gerado, e pesa alguns MB).

Como funciona:
- tudo o que é assets/... (no HTML, no CSS, no app.js e no JSON) vira data URI;
  além de dispensar a pasta, isso deixa o canvas limpo, e o "baixar PNG"
  funciona mesmo aberto de file://, onde imagem relativa "suja" o canvas;
- o JSON da análise e o da ordem vão em <script type="application/json"> e um
  fetch de fachada os entrega ao app.js quando ele pede dados/... (com ou sem
  ?t=, que num data URI quebraria o base64);
- os botões de reordenar somem (gravar a ordem pede a chave do GitHub, e a
  ordem que vale já vem aplicada da gravada);
- Zoom e Tela cheia saem dos cartões (e da página): no lugar, "Apresentar daqui"
  abre a apresentação no gráfico;
- a Bebas Neue dos títulos da Missão vem embutida, baixada uma vez do Google
  Fonts (sem internet, sem ela, o título cai na letra padrão).
"""
import base64
import json
import mimetypes
import os
import re
import sys

import requests

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "avulso")
FONTE_GOOGLE = "https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap"
# o Google só serve woff2 para navegador que se apresenta como tal
CABECALHO = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0 Safari/537.36"}


def ler(caminho, binario=False):
    with open(os.path.join(RAIZ, caminho), "rb" if binario else "r", **({} if binario else {"encoding": "utf-8"})) as f:
        return f.read()


def data_uri(caminho):
    tipo = mimetypes.guess_type(caminho)[0] or "application/octet-stream"
    return "data:%s;base64,%s" % (tipo, base64.b64encode(ler(caminho, True)).decode("ascii"))


def embutir_assets(texto, usados):
    """Troca cada assets/... que existe no disco pelo data URI (sem o ?v=)."""
    def troca(m):
        caminho = m.group(1)
        if not os.path.isfile(os.path.join(RAIZ, caminho)):
            return m.group(0)
        usados.add(caminho)
        return data_uri(caminho)
    return re.sub(r"(assets/[A-Za-z0-9_./-]+\.(?:jpg|jpeg|png|svg|gif|webp))(?:\?v=\d+)?", troca, texto)


def json_no_html(obj):
    # "</" dentro de <script> fecha a tag; "\/" é escape válido em JSON
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def fonte_bebas():
    """@font-face da Bebas Neue com o woff2 embutido, ou "" se não baixar."""
    try:
        css = requests.get(FONTE_GOOGLE, headers=CABECALHO, timeout=30).text
        # o Google divide por alfabeto; o latin (último bloco) basta para o português
        blocos = re.findall(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*{[^}]*})", css)
        bloco = dict(blocos).get("latin") or (blocos[-1][1] if blocos else css)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", bloco).group(1)
        woff = requests.get(url, headers=CABECALHO, timeout=30).content
        return bloco.replace(url, "data:font/woff2;base64," + base64.b64encode(woff).decode("ascii"))
    except Exception as e:                                   # noqa: BLE001
        print("  sem a Bebas Neue embutida (%s): o título cai na letra padrão" % e)
        return ""


def montar(arquivo):
    usados = set()
    dados = json.loads(ler(arquivo))
    embutidos = {arquivo: dados}
    if dados.get("reordenar") and os.path.isfile(os.path.join(RAIZ, dados["reordenar"])):
        embutidos[dados["reordenar"]] = json.loads(ler(dados["reordenar"]))
    # as imagens dentro dos JSON também viram data URI
    embutidos = {k: json.loads(embutir_assets(json.dumps(v, ensure_ascii=False), usados))
                 for k, v in embutidos.items()}

    html = ler("index.html")
    css = embutir_assets(ler("styles.css"), usados)
    js = embutir_assets(ler("app.js"), usados)
    html = embutir_assets(html, usados)

    titulo = dados.get("assunto", "Análise")
    bebas = fonte_bebas() if dados.get("marca") == "missao" else ""
    if bebas:
        # com a letra embutida, o <link> que o app.js põe para o Google vira folha vazia
        js = js.replace(FONTE_GOOGLE, "data:text/css,")
    # no avulso, Zoom e Tela cheia saem: cada cartão ganha "Apresentar daqui" (data-so-apresentar)
    extra_css = (".ordem-controles, .ordem-barra, #tela-cheia-pagina { display: none !important; }\n" + bebas)
    # a fachada do fetch: o app.js pede dados/x.json?t=..., recebe o embutido
    fachada = """
(function () {
  var E = {};
  [].forEach.call(document.querySelectorAll('script[type="application/json"][data-caminho]'), function (s) {
    E[s.getAttribute("data-caminho")] = s.textContent;
  });
  var original = window.fetch ? window.fetch.bind(window) : null;
  window.fetch = function (u, o) {
    var k = String(u && u.url || u).split("?")[0];
    if (Object.prototype.hasOwnProperty.call(E, k)) {
      return Promise.resolve(new Response(E[k], { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    return original ? original(u, o) : Promise.reject(new Error("sem fetch"));
  };
})();
"""
    scripts_json = "\n".join('<script type="application/json" data-caminho="%s">%s</script>' % (k, json_no_html(v))
                             for k, v in embutidos.items())

    # o CSS e o JS entram com função no re.sub: o conteúdo tem "\" que o re leria como grupo
    html = re.sub(r'<link rel="stylesheet" href="styles\.css[^"]*">',
                  lambda m: "<style>\n%s\n%s</style>" % (css, extra_css), html)
    html = re.sub(r'<script src="app\.js[^"]*"></script>',
                  lambda m: "%s\n<script>%s</script>\n<script>\n%s\n</script>" % (scripts_json, fachada, js), html)
    html = re.sub(r"<body([^>]*)>", lambda m: '<body%s data-fontes="%s" data-so-apresentar>' % (m.group(1), arquivo),
                  html, count=1)
    html = re.sub(r"<title>.*?</title>", lambda m: "<title>%s</title>" % titulo, html, count=1)
    if "<style>" not in html or 'data-caminho="' not in html:
        raise SystemExit("o index.html mudou: não achei a folha de estilo ou o app.js para embutir")

    os.makedirs(SAIDA, exist_ok=True)
    nome = os.path.splitext(os.path.basename(arquivo))[0] + ".html"
    destino = os.path.join(SAIDA, nome)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(html)
    print("  %s: %.1f MB, %d imagens embutidas" % (os.path.relpath(destino, RAIZ), len(html.encode()) / 1e6, len(usados)))
    return destino


if __name__ == "__main__":
    montar(sys.argv[1] if len(sys.argv) > 1 else "dados/missao-global-miami.json")
