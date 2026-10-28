/* FtM Análises — desenha os gráficos de cada assunto no estilo dos slides do FtM.
 *
 * Mesmo motor do ftm-dados: tudo vira SVG com as cores em atributos (nada de
 * CSS dentro do SVG), então o mesmo desenho serve para a tela, para o SVG
 * baixado e para o PNG (que serializa o SVG num canvas por cima da imagem de
 * fundo).
 *
 * Os dados já chegam prontos: as contas ficam nos scripts de cada assunto
 * (scripts/gave.py e afins).
 *
 * O mesmo desenho serve para o cartão da página e para o visor (um gráfico só,
 * grande, com tela cheia e anotação à mão por cima, num <canvas>).
 */
(function () {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";
  var FONT = "Calibri, Carlito, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif";
  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  var MESES_LONGOS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
    "Setembro", "Outubro", "Novembro", "Dezembro"];

  var PALETAS = {
    dark: {
      texto: "#ffffff", eixo: "#ffffff", suave: "rgba(255,255,255,.78)", grade: "rgba(255,255,255,.09)",
      zero: "rgba(255,255,255,.85)", logo: "#a3a3a3", bg: "#000000",
      tipBg: "rgba(0,0,0,.9)", tipBorda: "rgba(255,255,255,.3)", fundo: "assets/fundo.jpg"
    },
    light: {
      texto: "#1b1f23", eixo: "#30363d", suave: "#5b6570", grade: "#e3e6e9",
      zero: "#4a525a", logo: "#595959", bg: "#ffffff",
      tipBg: "rgba(255,255,255,.96)", tipBorda: "#b9c1c9", fundo: null
    }
  };

  var LAYOUTS = {
    wide: {
      W: 1920, H: 1080, x0: 108, y1: 945, rotuloX: 14,
      titulo: { x: 35, y: 66, fs: 40, max: 1600 }, sub: { x: 36, y: 104, fs: 24, max: 1600 },
      logo: { x: 1712, y: 20, w: 180 }, legenda: { y: 181, fs: 24, passo: 40, colunas: 5, larguraCol: 318 },
      tick: 24, xlab: 22, xRot: -45, rotulo: 26, fonte: { x: 1905, y: 1070, fs: 16 },
      tip: 22, linha: 7, eixoDuplo: true
    },
    narrow: vertical(1350, 0, 0)
  };

  // Layout em pé (largura 1080). topo/base = margem livre para a interface do
  // Instagram nos Stories (o gráfico fica dentro da área segura).
  function vertical(H, topo, base) {
    var b = H - base;
    return {
      W: 1080, H: H, x0: 96, y1: b - 160, rotuloX: 12,
      titulo: { x: 30, y: topo + 150, fs: 48, max: 1020 }, sub: { x: 31, y: topo + 196, fs: 28, max: 1020 },
      logo: { x: 860, y: topo + 26, w: 190 }, legenda: { y: 0, fs: 28, passo: 42, colunas: 2, larguraCol: 505 },
      tick: 30, xlab: 27, xRot: -60, rotulo: 30, fonte: { x: 1060, y: b - 14, fs: 22 },
      tip: 30, linha: 7, eixoDuplo: false
    };
  }

  // Tamanhos para baixar. escala = quantas vezes os pixels do layout (o desenho
  // é vetorial, então 2× sai nítido, não esticado).
  var TAMANHOS = [
    { id: "slide", nome: "Apresentação 16:9", layout: LAYOUTS.wide, escala: 2 },
    { id: "ig-4x5", nome: "Instagram feed 4:5", layout: LAYOUTS.narrow, escala: 2 },
    { id: "ig-3x4", nome: "Instagram feed 3:4", layout: vertical(1440, 0, 0), escala: 2 },
    { id: "ig-1x1", nome: "Instagram quadrado 1:1", layout: vertical(1080, 0, 0), escala: 2 },
    { id: "ig-story", nome: "Instagram Stories 9:16", layout: vertical(1920, 250, 340), escala: 2 }
  ];

  var cartoes = [];
  // Um arquivo por assunto. Cada um traz assunto, fonte, data de referência,
  // uma apresentação e as suas seções; um que faltar é só ignorado. A ordem
  // aqui é a ordem da página.
  // A análise vem primeiro: ela é o que se lê de ponta a ponta. Os painéis
  // antigos ficam embaixo, fechados, como acervo.
  // a ordem é a do índice; assuntos do mesmo "grupo" ficam juntos
  var FONTES = ["dados/gave.json", "dados/cenario-2026-10-28-fomc.json",
                "dados/defasagem-combustiveis.json", "dados/eleicoes.json", "dados/petroleo.json"];
  // Uma página pode pedir outros arquivos: <body data-fontes="dados/x.json">.
  if (document.body && document.body.getAttribute("data-fontes")) {
    FONTES = document.body.getAttribute("data-fontes").split(/\s*,\s*/);
  }
  var docs = [], atual = 0;
  var logoSvg = null;   // {viewBox, nos}

  // ---------- utilidades ----------
  function el(nome, attrs, filhos) {
    var n = document.createElementNS(NS, nome);
    for (var k in attrs) if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    (filhos || []).forEach(function (f) { n.appendChild(f); });
    return n;
  }
  function texto(conteudo, attrs) {
    var t = el("text", Object.assign({ "font-family": FONT }, attrs));
    t.textContent = conteudo;
    return t;
  }
  function html(tag, attrs, filhos) {
    var n = document.createElement(tag);
    for (var k in (attrs || {})) {
      if (k === "texto") n.textContent = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (filhos || []).forEach(function (f) { n.appendChild(f); });
    return n;
  }
  // Prosa vinda do arquivo de dados. Aceita duas marcações, e só duas: linha
  // em branco separa parágrafo, **assim** fica em negrito. É o suficiente para
  // definir um termo técnico no meio da explicação sem o texto virar um bloco
  // só — e não é Markdown, para não abrir a porta a HTML vindo do arquivo.
  // Usada na apresentação do assunto, no texto da seção e na nota do gráfico.
  function paragrafos(txt, classe) {
    if (!txt) return [];
    return String(txt).split(/\n\s*\n/).map(function (paragrafo) {
      return LISTA.test(paragrafo) ? lista(paragrafo, classe)
                                   : paragrafo1(paragrafo, classe);
    });
  }

  // Um bloco cujas linhas todas comecam por "- " vira lista. Dois espacos
  // antes do traco aninham um nivel. Serve ao esqueleto de uma secao ainda em
  // rascunho, e ao texto final que precise de uma enumeracao — negrito e
  // citacao continuam valendo dentro de cada item.
  var LISTA = /^\s*-\s+\S/;
  function lista(bloco, classe) {
    var raiz = html("ul", { "class": classe ? classe + " lista" : "lista" });
    var dentro = null;
    bloco.split(/\n/).forEach(function (linha) {
      var m = /^(\s*)-\s+(.*)$/.exec(linha);
      if (!m) return;
      var item = html("li");
      m[2].split(/\*\*/).forEach(function (pedaco, i) {
        if (pedaco) trecho(pedaco, i % 2 === 1, item);
      });
      if (m[1].length >= 2) {
        if (!dentro) {
          dentro = html("ul");
          (raiz.lastChild || raiz).appendChild(dentro);
        }
        dentro.appendChild(item);
      } else {
        dentro = null;
        raiz.appendChild(item);
      }
    });
    return raiz;
  }
  // "[trecho](fonte:id)" marca de onde veio a informação. O trecho fica
  // sublinhado e a fonte vai para a margem na altura dele, ligada por uma
  // linha. A marcação é tratada ANTES do negrito, e o que sobra de cada
  // pedaço continua passando pelo **negrito** normalmente.
  var MARCA_CITA = /\[([^\]]+)\]\(fonte:([\w-]+)\)/g;

  // O negrito é resolvido ANTES da citação, e não ao contrário: o ** alterna
  // um estado que vale para o parágrafo inteiro, então "**[x](fonte:y)**"
  // precisa fechar o negrito no ** de fora. Processar a citação primeiro
  // quebrava o par e pintava o resto do parágrafo de negrito.
  function trecho(texto, forte, destino) {
    var fim = 0, m;
    MARCA_CITA.lastIndex = 0;
    var por = function (t, fonte) {
      if (!t) return;
      var no = forte ? html("b", { texto: t }) : document.createTextNode(t);
      if (!fonte) return destino.appendChild(no);
      var marca = html("span", { "class": "cita", "data-fonte": fonte });
      marca.appendChild(no);
      destino.appendChild(marca);
    };
    while ((m = MARCA_CITA.exec(texto)) !== null) {
      por(texto.slice(fim, m.index), null);
      por(m[1], m[2]);
      fim = m.index + m[0].length;
    }
    por(texto.slice(fim), null);
  }
  function paragrafo1(paragrafo, classe) {
    var p = html("p", { "class": classe });
    paragrafo.split(/\*\*/).forEach(function (pedaco, i) {
      if (pedaco) trecho(pedaco, i % 2 === 1, p);
    });
    return p;
  }

  // Imagem no meio do texto. Um parágrafo que seja só "[figura:nome]" vira a
  // figura de mesmo id declarada na seção — é assim que uma tabela da Abicom
  // entra entre dois parágrafos, e não num amontoado no fim.
  var MARCA_FIGURA = /^\[figura:([\w-]+)\]$/;
  function figura(f) {
    var fig = html("figure", { "class": "figura" });
    fig.appendChild(html("img", {
      src: f.arquivo, alt: f.legenda || "", loading: "lazy"
    }));
    var legenda = html("figcaption", {});
    if (f.legenda) legenda.appendChild(document.createTextNode(f.legenda + " "));
    if (f.fonte) {
      var credito = f.url
        ? html("a", { href: f.url, target: "_blank", rel: "noopener noreferrer", texto: f.fonte })
        : html("span", { texto: f.fonte });
      legenda.appendChild(html("span", { "class": "figura-fonte" }, [credito]));
    }
    fig.appendChild(legenda);
    return fig;
  }

  // Prosa e figuras na ordem em que o texto pede.
  function blocos(txt, classe, figuras) {
    var porId = {};
    (figuras || []).forEach(function (f) { porId[f.id] = f; });
    return String(txt || "").split(/\n\s*\n/).filter(Boolean).map(function (b) {
      var m = b.trim().match(MARCA_FIGURA);
      if (m && porId[m[1]]) return figura(porId[m[1]]);
      return LISTA.test(b) ? lista(b, classe) : paragrafo1(b, classe);
    });
  }

  function tema() { return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark"; }

  var medidor = document.createElement("canvas").getContext("2d");
  function largura(str, fs, estilo) {
    medidor.font = (estilo || "normal") + " " + fs + "px " + FONT;
    return medidor.measureText(str).width;
  }
  function corpoQueCabe(str, fsMax, disponivel, estilo) {
    return Math.min(fsMax, disponivel / largura(str, 100, estilo) * 100);
  }

  var nfCache = {};
  function nf(casas) {
    if (!nfCache[casas]) {
      nfCache[casas] = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
    }
    return nfCache[casas];
  }
  function pct(v, casas) { return nf(casas === undefined ? 2 : casas).format(v) + "%"; }

  // Como cada gráfico escreve os seus números: no eixo (curto) e no valor
  // cheio (rótulo do último ponto e caixa do mouse). "%" é o padrão.
  // casas do eixo conforme o passo da grade: numa janela curta (7,0% a 9,5%) o
  // eixo sem decimal repetiria "7%, 8%, 8%, 9%"
  function casasDoPasso(p) {
    // as casas que o passo pede: 20 → 0, 1,6 → 1, 0,25 → 2
    p = Math.abs(p || 1);
    for (var c = 0; c < 2; c++) {
      if (Math.abs(p * Math.pow(10, c) - Math.round(p * Math.pow(10, c))) < 1e-6) return c;
    }
    return 2;
  }
  var UNIDADES = {
    "%": { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v) + "%"; },
           valor: function (v) { return pct(v, 2); } },
    // variação de uma casa (rankings de alta e queda)
    pct1: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v) + "%"; },
            valor: function (v) { return pct(v, 1); } },
    bi: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
          valor: function (v) { return "R$ " + nf(1).format(v) + " bi"; } },
    anos: { eixo: function (v, passo) { return nf(Math.max(1, casasDoPasso(passo))).format(v); },
            valor: function (v) { return nf(2).format(v) + " anos"; } },
    // desvio-padrão: o tamanho do movimento medido na régua do próprio ano
    dp: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
          valor: function (v) { return nf(2).format(v) + " dp"; } },
    // razão entre duas medidas (volatilidade depois ÷ antes)
    x: { eixo: function (v, passo) { return nf(Math.max(1, casasDoPasso(passo))).format(v); },
         valor: function (v) { return nf(2).format(v) + "\u00d7"; } },
    // reais por litro: preço de combustível, onde o centavo é a unidade que
    // o leitor reconhece
    "R$/l": { eixo: function (v, passo) { return "R$ " + nf(casasDoPasso(passo)).format(v); },
              valor: function (v) { return "R$ " + nf(2).format(v); } },
    // volume de combustível: o eixo fica só com o número, e a unidade vai no
    // subtítulo; no valor cheio ela aparece, porque ali não há contexto
    "mil m³": { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
                    valor: function (v) { return nf(0).format(v) + " mil m³"; } },
    // comércio exterior em bilhões de dólares, e índice (IC-Br, dez/2005 = 100)
    "usd-bi": { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
                valor: function (v) { return "US$ " + nf(1).format(v) + " bi"; } },
    pts: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
           valor: function (v) { return nf(1).format(v); } },
    // petróleo e derivados em mil barris por dia; contribuição em pontos percentuais
    kbd: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
           valor: function (v) { return nf(0).format(v) + " mil b/d"; } },
    // pontos-base (contribuição de um item pequeno, onde 0,03 p.p. não diz nada)
    pb: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
          valor: function (v) { return nf(1).format(v) + " pb"; } },
    // milhares (vagas, pedidos de seguro-desemprego) e horas por semana
    mil: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
           valor: function (v) { return nf(0).format(v) + " mil"; } },
    h: { eixo: function (v, passo) { return nf(Math.max(1, casasDoPasso(passo))).format(v); },
         valor: function (v) { return nf(1).format(v) + " h"; } },
    pp: { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
          valor: function (v) { return nf(2).format(v) + " p.p."; } },
    votos: { eixo: function (v, passo) { return nf(0).format(Math.abs(v)); },
             valor: function (v) { var n = Math.abs(v); return nf(0).format(n) + (n === 1 ? " voto" : " votos"); } },
    "usd-tri": { eixo: function (v, passo) { return "US$ " + nf(casasDoPasso(passo)).format(v); },
                 valor: function (v) { return "US$ " + nf(2).format(v) + " tri"; } },
    "usd-bbl": { eixo: function (v, passo) { return nf(casasDoPasso(passo)).format(v); },
                 valor: function (v) { return "US$ " + nf(2).format(v) + "/barril"; } }
  };
  function unidade(g) { return UNIDADES[g.unidade] || UNIDADES["%"]; }
  // a série pode ter unidade própria (a que vai no eixo da direita, quando o
  // gráfico tem "eixoDireita"): vale para o rótulo do último ponto e a caixa
  function unidadeDe(g, s) { return (s && UNIDADES[s.unidade]) || unidade(g); }

  function idxMes(m) { var p = m.split("-"); return (+p[0]) * 12 + (+p[1] - 1); }
  // eixo diário: o índice é o dia corrido (UTC, para não pegar fuso nem horário de verão)
  function idxDia(iso) { var p = iso.split("-"); return Math.round(Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000); }
  function dataDeIdx(i) { return new Date(i * 86400000); }
  // eixo intradiário: o índice é o bloco de 15 minutos. A chave é a hora de
  // Nova York escrita por extenso ("2026-09-16T14:00") e lida como se fosse
  // UTC — o que importa é o espaçamento, e assim o rótulo sai direto da chave,
  // sem conta de fuso no navegador. (Na virada do horário de verão americano a
  // hora repetida some: o script grava uma chave só.)
  var BLOCO = 900000;
  function idxIntra(k) {
    var p = k.split("T"), d = p[0].split("-"), h = (p[1] || "00:00").split(":");
    return Math.round(Date.UTC(+d[0], +d[1] - 1, +d[2], +h[0], +h[1]) / BLOCO);
  }
  function dataDeIdxIntra(i) { return new Date(i * BLOCO); }
  function hhmm(d) { return d.getUTCHours() + "h" + ("0" + d.getUTCMinutes()).slice(-2); }
  function mesDeIdx(i) { return Math.floor(i / 12) + "-" + ("0" + (i % 12 + 1)).slice(-2); }
  function rotuloMesCurto(i) { return MESES[i % 12] + "/" + String(Math.floor(i / 12)).slice(-2); }
  function rotuloMesLongo(i) { return MESES_LONGOS[i % 12] + " de " + Math.floor(i / 12); }

  // Eixo X: normalmente é o tempo (um passo por mês); com "categorias" no
  // gráfico, é uma lista de rótulos (o acumulado do cronograma de vencimentos).
  function idxDe(g, chave) {
    return g.categorias ? +chave : g.intradiario ? idxIntra(chave) : g.diario ? idxDia(chave) : idxMes(chave);
  }
  function rotuloX(g, i, longo) {
    if (g.categorias) return g.categorias[i] || "";
    if (g.intradiario) {
      var t = dataDeIdxIntra(i), dia = t.getUTCDate(), mes = t.getUTCMonth();
      if (!longo) return dia + "/" + ("0" + (mes + 1)).slice(-2);
      return dia + " de " + MESES_LONGOS[mes].toLowerCase() + ", " + hhmm(t);
    }
    if (g.diario) {
      var d = dataDeIdx(i);
      if (!longo) return MESES[d.getUTCMonth()] + "/" + String(d.getUTCFullYear()).slice(-2);
      return d.getUTCDate() + " de " + MESES_LONGOS[d.getUTCMonth()].toLowerCase() + " de " + d.getUTCFullYear();
    }
    return longo ? rotuloMesLongo(i) : rotuloMesCurto(i);
  }
  // Quantos passos do eixo cabem num ano — o que separa "mês" de "dia" nas
  // contas de período (Tudo / 10 anos / 5 anos…).
  function passosPorAno(g) { return g.intradiario ? 365.25 * 96 : g.diario ? 365.25 : 12; }

  // Um cartão pode ter variantes (agência, moeda, "% ou R$"…): o gráfico que
  // vale é a base com a variante escolhida por cima. O objeto fica guardado
  // para as séries manterem a identidade entre desenho e interação.
  function graficoDe(cartao) {
    var base = cartao.grafico;
    if (!base.variantes) return base;
    var k = cartao.variante || 0;
    if (!cartao.montados) cartao.montados = {};
    if (!cartao.montados[k]) {
      var v = base.variantes[k] || base.variantes[0], fora = {};
      for (var a in base) if (a !== "variantes") fora[a] = base[a];
      for (var b in v) if (b !== "rot") fora[b] = v[b];
      // o recorte escolhido entra no subtítulo: sem isso, a imagem baixada não
      // diz qual deles está na tela
      fora.subtitulo = (base.subtitulo ? base.subtitulo + " · " : "") + v.rot;
      cartao.montados[k] = fora;
    }
    return cartao.montados[k];
  }

  // Branco e amarelo somem no fundo claro: no tema claro viram tinta escura / ocre.
  function corNoTema(cor, pal) {
    if (tema() !== "light") return cor;
    var c = cor.toUpperCase();
    if (c === "#FFFFFF") return pal.texto;
    if (c === "#FFFF00") return "#C9A800";
    return cor;
  }

  // ---------- escala Y ----------
  function passoBonito(faixa, alvo) {
    var bruto = faixa / alvo;
    var mag = Math.pow(10, Math.floor(Math.log10(bruto)));
    var cands = [1, 2, 5, 10];   // sem 2,5: o eixo mostra % sem casas decimais
    for (var i = 0; i < cands.length; i++) if (cands[i] * mag >= bruto) return cands[i] * mag;
    return 10 * mag;
  }
  function escalaY(mn, mx, eixo) {
    eixo = eixo || {};
    var baixo = mn, alto = mx;
    // Série que não chega perto de zero pede "zero: false": aí o piso acompanha
    // os dados, em vez de descer até zero e espremer a linha na metade de cima.
    // (É o caso da razão de volatilidade, que vive em torno de 1.)
    if (eixo.zero !== false && mn >= 0 && mn <= mx * 0.6) baixo = 0;
    if (eixo.min !== undefined) baixo = eixo.min;
    if (eixo.max !== undefined) alto = eixo.max;
    if (alto - baixo <= 0) alto = baixo + 1;
    var passo = passoBonito(alto - baixo, 8);
    var min = eixo.min !== undefined ? eixo.min : Math.floor(baixo / passo + 1e-9) * passo;
    var max = eixo.max !== undefined ? eixo.max : Math.ceil(alto / passo - 1e-9) * passo;
    var ticks = [];
    for (var k = 0; min + k * passo <= max + passo / 2; k++) ticks.push(+(min + k * passo).toFixed(6));
    return { min: min, max: max, passo: passo, ticks: ticks };
  }

  // ---------- legenda ----------
  function itensLegenda(g) {
    return g.series.filter(function (s) { return s.legenda !== false; });
  }
  function montarLegenda(g, L) {
    var itens = itensLegenda(g), lg = L.legenda, fs = lg.fs, sw = 34, gap = 8;
    var larg = itens.map(function (s) { return sw + gap + largura(s.nome, fs); });
    var pos = [];
    var total = larg.reduce(function (a, b) { return a + b; }, 0) + 40 * (itens.length - 1);
    if (itens.length <= lg.colunas && total <= L.W - 80) {
      var x = (L.W - total) / 2;
      itens.forEach(function (s, k) { pos.push({ s: s, x: x, linha: 0 }); x += larg[k] + 40; });
    } else {
      // em grade, como os slides com muitas séries (contribuição por grupo)
      var cols = lg.colunas, cw = lg.larguraCol;
      var fsCab = Math.min.apply(null, itens.map(function (s) { return corpoQueCabe(s.nome, fs, cw - sw - gap - 6); }));
      fs = Math.max(fs * 0.8, fsCab);
      var x0 = (L.W - cols * cw) / 2;
      itens.forEach(function (s, k) { pos.push({ s: s, x: x0 + (k % cols) * cw, linha: Math.floor(k / cols) }); });
    }
    var linhas = pos.length ? pos[pos.length - 1].linha + 1 : 0;
    return { pos: pos, fs: fs, sw: sw, gap: gap, linhas: linhas };
  }

  // ---------- desenho ----------
  // Ranking: barras deitadas, um item abaixo do outro, do maior para o menor.
  // "itens": [[rótulo, valor, cor?]]. Mesmo título, subtítulo, fonte e logo
  // dos outros gráficos, sem eixo de tempo e sem caixa do mouse (o valor já
  // vai escrito na ponta de cada barra).
  // Mapa de bolhas: os estados (IBGE) ao fundo e uma bolha por item, com a
  // área proporcional ao valor. "vista" é o recorte do mapa ([x0, y0, x1, y1],
  // nas coordenadas já projetadas do "mapa"). Bolha com "abre" leva, no
  // clique, à variante de número "abre" (mar ou terra → o detalhe).
  function construirMapa(cartao, L0, nomeTema) {
    var g = graficoDe(cartao), pal = PALETAS[nomeTema], F = unidade(g);
    var L = Object.assign({}, L0);
    var svg = el("svg", {
      xmlns: NS, viewBox: "0 0 " + L.W + " " + L.H, width: L.W, height: L.H,
      role: "img", "aria-label": g.titulo + (g.subtitulo ? " — " + g.subtitulo : "")
    });
    var ax0 = L.titulo.x, ax1 = L.W - L.titulo.x, ay0 = L.sub.y + L.sub.fs * 1.6, ay1 = L.fonte.y - L.fonte.fs * 2;
    var v = g.vista, sx = (ax1 - ax0) / (v[2] - v[0]), sy = (ay1 - ay0) / (v[3] - v[1]), esc = Math.min(sx, sy);
    var tx = ax0 + ((ax1 - ax0) - (v[2] - v[0]) * esc) / 2, ty = ay0 + ((ay1 - ay0) - (v[3] - v[1]) * esc) / 2;
    var X = function (x) { return tx + (x - v[0]) * esc; }, Y = function (y) { return ty + (y - v[1]) * esc; };
    var idClip = "clip-mapa-" + g.id + "-" + nomeTema;
    svg.appendChild(el("defs", {}, [el("clipPath", { id: idClip }, [
      el("rect", { x: ax0, y: ay0, width: ax1 - ax0, height: ay1 - ay0 })])]));
    var fundo = el("g", { "clip-path": "url(#" + idClip + ")" });
    var estados = el("g", { transform: "translate(" + tx + " " + ty + ") scale(" + esc + ") translate(" + (-v[0]) + " " + (-v[1]) + ")" });
    (g.mapa || []).forEach(function (uf) {
      estados.appendChild(el("path", { d: uf[1], fill: pal.suave, "fill-opacity": 0.22, stroke: pal.suave,
                                       "stroke-width": 1.2, "vector-effect": "non-scaling-stroke" }));
    });
    fundo.appendChild(estados);
    svg.appendChild(fundo);

    // bolhas: a área é proporcional ao valor; as que se encostam são
    // afastadas, com um traço até o lugar de verdade
    var bolhas = g.bolhas || [], mx = Math.max.apply(null, [0].concat(bolhas.map(function (b) { return b.pct; }))) || 1;
    var rMax = Math.min(ax1 - ax0, ay1 - ay0) * (g.raio || 0.17);
    var pos = bolhas.map(function (b) {
      var r = Math.max(7, rMax * Math.sqrt(b.pct / mx));
      return { b: b, ax: X(b.x), ay: Y(b.y), x: X(b.x), y: Y(b.y), r: r };
    });
    for (var it = 0; it < 400; it++) {
      for (var i = 0; i < pos.length; i++) {
        for (var j = i + 1; j < pos.length; j++) {
          var p = pos[i], q = pos[j], dx = q.x - p.x, dy = q.y - p.y, dist = Math.sqrt(dx * dx + dy * dy) || 0.01;
          var falta = p.r + q.r + 4 - dist;
          if (falta > 0) {
            var wp = q.r / (p.r + q.r), wq = p.r / (p.r + q.r);
            p.x -= dx / dist * falta * wp; p.y -= dy / dist * falta * wp;
            q.x += dx / dist * falta * wq; q.y += dy / dist * falta * wq;
          }
        }
      }
      pos.forEach(function (o) {
        o.x += (o.ax - o.x) * 0.02; o.y += (o.ay - o.y) * 0.02;
        o.x = Math.min(Math.max(o.x, ax0 + o.r), ax1 - o.r);
        o.y = Math.min(Math.max(o.y, ay0 + o.r), ay1 - o.r);
      });
    }
    var fs = Math.round(L.tick * 1.05), rotulos = [];
    var cxm = pos.reduce(function (a, o) { return a + o.x; }, 0) / (pos.length || 1);
    // rótulo por cima de tudo, com contorno da cor do fundo: legível mesmo
    // quando encosta numa bolha vizinha
    var halo = { stroke: pal.bg, "stroke-width": 6, "stroke-linejoin": "round" };
    pos.forEach(function (o) {
      if (Math.abs(o.x - o.ax) + Math.abs(o.y - o.ay) > 6) {
        svg.appendChild(el("line", { x1: o.ax, y1: o.ay, x2: o.x, y2: o.y, stroke: pal.texto, "stroke-width": 1.2,
                                     opacity: 0.6 }));
        svg.appendChild(el("circle", { cx: o.ax, cy: o.ay, r: 3.5, fill: pal.texto, opacity: 0.8 }));
      }
    });
    pos.forEach(function (o) {
      var b = o.b, grupo = el("g", {});
      var c = el("circle", { cx: o.x, cy: o.y, r: o.r, fill: corNoTema(b.cor || "#4F81BD", pal), "fill-opacity": 0.95,
                             stroke: pal.bg, "stroke-width": 1.5 });
      var dica = el("title", {});
      dica.textContent = b.nome + ": " + F.valor(b.pct) + " da produção do país (" + nf(0).format(b.kbd) + " mil b/d)";
      c.appendChild(dica);
      grupo.appendChild(c);
      // dentro da bolha, numa letra que caiba (até 60% da normal)
      var fsIn = Math.min(fs, fs * o.r * 1.8 / Math.max(largura(b.nome, fs, "bold"), 1), o.r / 1.15);
      var dentro = fsIn >= fs * 0.6;
      if (dentro) {
        grupo.appendChild(texto(b.nome, { x: o.x, y: o.y - fsIn * 0.15, "font-size": fsIn, "font-weight": "bold",
                                          fill: "#000", "text-anchor": "middle", "pointer-events": "none" }));
        grupo.appendChild(texto(F.valor(b.pct), { x: o.x, y: o.y + fsIn * 1.05, "font-size": fsIn, fill: "#000",
                                                   "text-anchor": "middle", "pointer-events": "none" }));
      } else {
        // fora da bolha: à direita, à esquerda, em cima ou embaixo, o lado que
        // bater em menos bolhas (e não sair do quadro)
        var txt = b.nome + " " + F.valor(b.pct), fsr = fs * 0.85, w = largura(txt, fsr), h = fsr * 1.2;
        var lados = [
          { x: o.x + o.r + 8, y: o.y, a: "start", bx: o.x + o.r + 8 },
          { x: o.x - o.r - 8, y: o.y, a: "end", bx: o.x - o.r - 8 - w },
          { x: o.x, y: o.y - o.r - h * 0.7, a: "middle", bx: o.x - w / 2 },
          { x: o.x, y: o.y + o.r + h * 0.7, a: "middle", bx: o.x - w / 2 }
        ];
        var melhor = null;
        lados.forEach(function (l, k) {
          var fora = l.bx < ax0 || l.bx + w > ax1 ? 100 : 0, bate = 0;
          pos.forEach(function (q) {
            if (q === o) return;
            var nx = Math.max(l.bx, Math.min(q.x, l.bx + w)), ny = Math.max(l.y - h / 2, Math.min(q.y, l.y + h / 2));
            if ((nx - q.x) * (nx - q.x) + (ny - q.y) * (ny - q.y) < q.r * q.r) bate++;
          });
          var custo = fora + bate * 10 + k;
          if (!melhor || custo < melhor.custo) melhor = { l: l, custo: custo };
        });
        var at = { x: melhor.l.x, y: melhor.l.y, "font-size": fsr, "dominant-baseline": "central",
                   "text-anchor": melhor.l.a, "pointer-events": "none" };
        rotulos.push(texto(txt, Object.assign({}, at, halo, { fill: pal.bg })));
        rotulos.push(texto(txt, Object.assign({}, at, { fill: pal.texto })));
      }
      if (b.abre !== undefined && cartao.trocarVariante) {
        grupo.setAttribute("style", "cursor:pointer");
        grupo.addEventListener("click", function () { cartao.trocarVariante(b.abre); });
      }
      svg.appendChild(grupo);
    });
    rotulos.forEach(function (t) { svg.appendChild(t); });

    svg.appendChild(texto(g.titulo, {
      x: L.titulo.x, y: L.titulo.y, "font-weight": "bold", fill: pal.texto,
      "font-size": corpoQueCabe(g.titulo, L.titulo.fs, L.titulo.max, "bold")
    }));
    if (g.subtitulo) {
      svg.appendChild(texto(g.subtitulo, {
        x: L.sub.x, y: L.sub.y, "font-style": "italic", fill: pal.texto,
        "font-size": corpoQueCabe(g.subtitulo, L.sub.fs, L.sub.max, "italic")
      }));
    }
    svg.appendChild(texto("Fonte: " + g.fonte + ".", {
      x: L.fonte.x, y: L.fonte.y, "font-size": L.fonte.fs, fill: pal.texto, "text-anchor": "end"
    }));
    if (logoSvg) {
      var lh = L.logo.w * logoSvg.razao;
      var gl = el("svg", { x: L.logo.x, y: L.logo.y, width: L.logo.w, height: lh, viewBox: logoSvg.viewBox });
      var gg = el("g", { fill: pal.logo });
      logoSvg.nos.forEach(function (n) { gg.appendChild(n.cloneNode(true)); });
      gl.appendChild(gg);
      svg.appendChild(gl);
    }
    return { svg: svg, L: L, pal: pal, ranking: true };
  }

  function construirRanking(cartao, L0, nomeTema) {
    var g = graficoDe(cartao), pal = PALETAS[nomeTema], F = unidade(g);
    var L = Object.assign({}, L0);
    var svg = el("svg", {
      xmlns: NS, viewBox: "0 0 " + L.W + " " + L.H, width: L.W, height: L.H,
      role: "img", "aria-label": g.titulo + (g.subtitulo ? " — " + g.subtitulo : "")
    });
    var itens = g.itens || [];
    var fs = Math.round(L.tick * 1.15);
    var y0 = L.sub.y + L.sub.fs * 2.4, y1 = L.y1;
    var passo = (y1 - y0) / Math.max(itens.length, 1), alt = passo * 0.66;
    // "sinal": o valor sai com + quando é alta (ranking de variação)
    var rotulo = function (v) { return (g.sinal && v > 0 ? "+" : "") + F.valor(v); };
    var lw = Math.max.apply(null, [0].concat(itens.map(function (it) { return largura(it[0], fs); })));
    var vw = Math.max.apply(null, [0].concat(itens.map(function (it) { return largura(rotulo(it[1]), fs, "bold"); })));
    var x0 = L.titulo.x + lw + 18, x1 = L.W - L.titulo.x - vw - 16;
    // valores negativos (quedas) saem para a esquerda de uma linha do zero; o
    // número deles fica do lado direito do zero, para não bater nos nomes
    var mx = Math.max.apply(null, [0].concat(itens.map(function (it) { return it[1]; })));
    var mn = Math.min.apply(null, [0].concat(itens.map(function (it) { return it[1]; })));
    if (mx - mn <= 0) mx = mn + 1;
    var xz = x0 + (x1 - x0) * (-mn) / (mx - mn);
    itens.forEach(function (it, k) {
      var yc = y0 + passo * (k + 0.5), w = Math.max(1, (x1 - x0) * Math.abs(it[1]) / (mx - mn));
      svg.appendChild(texto(it[0], { x: x0 - 14, y: yc, "font-size": fs, fill: pal.texto, "text-anchor": "end",
                                     "dominant-baseline": "central", "font-weight": it[3] ? "bold" : null }));
      svg.appendChild(el("rect", { x: it[1] >= 0 ? xz : xz - w, y: yc - alt / 2, width: w, height: alt, rx: 3,
                                   fill: corNoTema(it[2] || "#4F81BD", pal) }));
      svg.appendChild(texto(rotulo(it[1]), { x: (it[1] >= 0 ? xz + w : xz) + 10, y: yc, "font-size": fs,
                                              "font-weight": "bold", fill: pal.texto, "dominant-baseline": "central" }));
    });
    if (mn < 0) {
      svg.appendChild(el("line", { x1: xz, x2: xz, y1: y0, y2: y1, stroke: pal.zero || pal.texto, "stroke-width": 1.5 }));
    }
    svg.appendChild(texto(g.titulo, {
      x: L.titulo.x, y: L.titulo.y, "font-weight": "bold", fill: pal.texto,
      "font-size": corpoQueCabe(g.titulo, L.titulo.fs, L.titulo.max, "bold")
    }));
    if (g.subtitulo) {
      svg.appendChild(texto(g.subtitulo, {
        x: L.sub.x, y: L.sub.y, "font-style": "italic", fill: pal.texto,
        "font-size": corpoQueCabe(g.subtitulo, L.sub.fs, L.sub.max, "italic")
      }));
    }
    svg.appendChild(texto("Fonte: " + g.fonte + ".", {
      x: L.fonte.x, y: L.fonte.y, "font-size": L.fonte.fs, fill: pal.texto, "text-anchor": "end"
    }));
    if (logoSvg) {
      var lh = L.logo.w * logoSvg.razao;
      var gl = el("svg", { x: L.logo.x, y: L.logo.y, width: L.logo.w, height: lh, viewBox: logoSvg.viewBox });
      var gg = el("g", { fill: pal.logo });
      logoSvg.nos.forEach(function (n) { gg.appendChild(n.cloneNode(true)); });
      gl.appendChild(gg);
      svg.appendChild(gl);
    }
    return { svg: svg, L: L, pal: pal, ranking: true };
  }

  function construir(cartao, L0, nomeTema) {
    var g = graficoDe(cartao), pal = PALETAS[nomeTema], F = unidade(g);
    if (g.tipo === "ranking") return construirRanking(cartao, L0, nomeTema);
    if (g.tipo === "mapa") return construirMapa(cartao, L0, nomeTema);
    var L = Object.assign({}, L0);

    // subtítulo que não cabe numa linha quebra em duas (versão estreita)
    var subLinhas = [g.subtitulo || ""];
    if (g.subtitulo && largura(g.subtitulo, L.sub.fs, "italic") > L.sub.max) {
      var partes = g.subtitulo.split("; ");
      subLinhas = partes.length > 1 ? [partes[0] + ";", partes.slice(1).join("; ")] : [g.subtitulo];
    }
    var legenda = montarLegenda(g, L);
    var topoLegenda = L.legenda.y || (L.sub.y + (subLinhas.length - 1) * L.sub.fs * 1.2 + 62);
    var y0 = topoLegenda + (legenda.linhas - 1) * L.legenda.passo + 42;

    // período visível
    // tipo "faixa": cada ponto é [chave, mínimo, máximo] e o desenho é a
    // área entre os dois (a sazonalidade contra os anos anteriores)
    var todas = g.series.map(function (s) {
      return s.dados.map(function (d) { return { i: idxDe(g, d[0]), v: d[1], v2: d[2] }; });
    });
    var ini = Infinity, fim = -Infinity;
    todas.forEach(function (pts) { pts.forEach(function (p) { if (p.i < ini) ini = p.i; if (p.i > fim) fim = p.i; }); });
    var d0 = cartao.inicioIdx === null ? ini : Math.max(ini, cartao.inicioIdx);
    var d1 = cartao.fimIdx === null ? fim + 1 : Math.min(fim + 1, cartao.fimIdx + 1);
    if (d1 - d0 < 2) { d0 = ini; d1 = fim + 1; }     // faixa degenerada volta a ser tudo
    var vis = todas.map(function (pts) { return pts.filter(function (p) { return p.i >= d0 && p.i < d1; }); });

    // extremos: barras entram empilhadas (positivas e negativas em separado)
    var mn = Infinity, mx = -Infinity, pilhaPos = {}, pilhaNeg = {};
    g.series.forEach(function (s, k) {
      vis[k].forEach(function (p) {
        if (s.tipo === "barra") {
          if (p.v >= 0) pilhaPos[p.i] = (pilhaPos[p.i] || 0) + p.v;
          else pilhaNeg[p.i] = (pilhaNeg[p.i] || 0) + p.v;
        } else {
          if (p.v < mn) mn = p.v;
          if (p.v > mx) mx = p.v;
          if (p.v2 !== undefined) { mn = Math.min(mn, p.v2); mx = Math.max(mx, p.v2); }
        }
      });
    });
    Object.keys(pilhaPos).forEach(function (i) { mx = Math.max(mx, pilhaPos[i]); mn = Math.min(mn, 0); });
    // barra sai do zero: o zero entra na escala mesmo com todas negativas
    Object.keys(pilhaNeg).forEach(function (i) { mn = Math.min(mn, pilhaNeg[i]); mx = Math.max(mx, 0); });
    // Acontecimentos: cada um ganha uma linha vertical e um rótulo curto no
    // alto do gráfico. Os rótulos entram em fileiras — a próxima fileira só é
    // usada quando o texto encostaria no anterior — e quem cai perto da borda
    // direita escreve para a esquerda da linha.
    var fsEv = Math.round(L.xlab * 0.95);
    var eventos = (g.eventos || []).map(function (e) {
      return { i: idxDe(g, e.em), rot: e.rot };
    }).filter(function (e) {
      return e.i >= d0 && e.i < d1;
    }).sort(function (a, b) { return a.i - b.i; });
    function disporEventos(fx, xDir) {
      var fimFileira = [];
      return eventos.map(function (e) {
        var xe = fx(e.i + 0.5), w = largura(e.rot, fsEv), paraEsq = xe + w + 10 > xDir;
        var ini = paraEsq ? xe - w - 8 : xe + 6, fila = 0;
        while (fimFileira[fila] !== undefined && ini < fimFileira[fila] + 12) fila++;
        fimFileira[fila] = ini + w;
        return { i: e.i, rot: e.rot, x: xe, paraEsq: paraEsq, fila: fila,
                 y: y0 + fsEv * (1 + fila * 1.25) };
      });
    }

    // Antes de fechar a escala, abre espaço no alto para esses rótulos: sem
    // isso eles caem em cima da linha justamente quando a taxa está no topo.
    // Duas passadas, porque a largura do eixo depende da escala e a posição do
    // rótulo depende da largura — a primeira é só para contar as fileiras.
    if (eventos.length && mx > mn) {
      var esc0 = escalaY(mn, mx, g.eixo);
      var tw0 = Math.max.apply(null, esc0.ticks.map(function (t) { return largura(F.eixo(t, esc0.passo), L.tick); }));
      var xa = 26 + tw0 + 14, xb = L.W - (22 + (L.eixoDuplo ? tw0 + 14 : 0) + 60);
      var filas = disporEventos(function (i) { return xa + (i - d0) / (d1 - d0) * (xb - xa); }, xb)
        .reduce(function (n, e) { return Math.max(n, e.fila + 1); }, 0);
      var folga = (filas * fsEv * 1.25 + fsEv * 0.8) / (L.y1 - y0);
      mx = mn + (mx - mn) / (1 - Math.min(0.45, folga));
    }
    var esc = escalaY(mn, mx, g.eixo);

    var tw = Math.max.apply(null, esc.ticks.map(function (t) { return largura(F.eixo(t, esc.passo), L.tick); }));
    var rotulos = [];
    g.series.forEach(function (s, k) {
      if (!s.rotulo || !vis[k].length) return;
      var u = vis[k][vis[k].length - 1];
      rotulos.push({ s: s, p: u, txt: unidadeDe(g, s).valor(u.v) });
    });
    var rw = Math.max.apply(null, [0].concat(rotulos.map(function (r) { return largura(r.txt, L.rotulo, "bold"); })));
    // "eixoDireita": o eixo da direita repete a escala com outra unidade
    // (ativos em US$ tri à esquerda, juros em % à direita, um para um)
    var F2 = g.eixoDireita ? UNIDADES[g.eixoDireita] : F, duplo = L.eixoDuplo || !!g.eixoDireita;
    var tw2 = Math.max.apply(null, esc.ticks.map(function (t) { return largura(F2.eixo(t, esc.passo), L.tick); }));
    L.x0 = 26 + tw + 14;
    L.x1 = L.W - (22 + Math.max(duplo ? tw2 + 14 : 0, rw + L.rotuloX + 10));
    L.y0 = y0;
    var pw = L.x1 - L.x0, ph = L.y1 - L.y0;
    var X = function (i) { return L.x0 + (i - d0) / (d1 - d0) * pw; };
    var Y = function (v) { return L.y1 - (v - esc.min) / (esc.max - esc.min) * ph; };
    var pxMes = pw / (d1 - d0);

    var svg = el("svg", {
      xmlns: NS, viewBox: "0 0 " + L.W + " " + L.H, width: L.W, height: L.H,
      role: "img", "aria-label": g.titulo + (g.subtitulo ? " — " + g.subtitulo : "")
    });
    var idClip = "clip-" + g.id + "-" + nomeTema;
    svg.appendChild(el("defs", {}, [el("clipPath", { id: idClip }, [
      el("rect", { x: L.x0, y: L.y0 - 2, width: pw, height: ph + 4 })
    ])]));

    // Onde cada rótulo do último ponto vai ficar, afastando os que se
    // encostam. Fica antes do eixo porque o eixo da direita só imprime o
    // número onde não houver rótulo — e o que vale é a posição final dele.
    var rotY = rotulos.map(function (r) { return Math.min(Math.max(Y(r.p.v), L.y0), L.y1); });
    var ordem = rotulos.map(function (r, k) { return { r: r, y: rotY[k] }; }).sort(function (a, b) { return a.y - b.y; });
    var passoRot = L.rotulo * 1.08;
    for (var a = 1; a < ordem.length; a++) {
      if (ordem[a].y - ordem[a - 1].y < passoRot) ordem[a].y = ordem[a - 1].y + passoRot;
    }
    for (var b2 = ordem.length - 1; b2 >= 0; b2--) {
      var teto = b2 === ordem.length - 1 ? L.y1 : ordem[b2 + 1].y - passoRot;
      if (ordem[b2].y > teto) ordem[b2].y = teto;
    }

    // Faixas de fundo ("sombras": [{de, ate}]), como as recessões: um
    // retângulo translúcido do primeiro ao último período de cada uma, atrás
    // da grade e das séries. Quem explica o que a faixa é, é o subtítulo.
    (g.sombras || []).forEach(function (sb) {
      var ia = Math.max(idxDe(g, sb.de), d0), ib = Math.min(idxDe(g, sb.ate) + 1, d1);
      if (ib <= ia) return;
      svg.appendChild(el("rect", { x: X(ia), y: L.y0, width: X(ib) - X(ia), height: ph,
                                   fill: pal.texto, opacity: tema() === "light" ? 0.09 : 0.14 }));
    });

    // grade e eixo Y (dos dois lados, como nos slides)
    esc.ticks.forEach(function (t) {
      var y = Y(t), zero = Math.abs(t) < 1e-9;
      svg.appendChild(el("line", {
        x1: L.x0, x2: L.x1, y1: y, y2: y, stroke: zero && esc.min < 0 ? pal.zero : pal.grade,
        "stroke-width": zero && esc.min < 0 ? 1.5 : 1.2
      }));
      var at = { y: y, "font-size": L.tick, fill: pal.eixo, "dominant-baseline": "central" };
      svg.appendChild(texto(F.eixo(t, esc.passo), Object.assign({ x: L.x0 - 14, "text-anchor": "end" }, at)));
      if (duplo && ordem.every(function (o) { return Math.abs(o.y - y) > L.rotulo * 0.9; })) {
        svg.appendChild(texto(F2.eixo(t, esc.passo), Object.assign({ x: L.x1 + 14, "text-anchor": "start" }, at)));
      }
    });
    // eixo X: linha de base (zero, se estiver no gráfico; senão a base)
    var yBase = esc.min <= 0 && esc.max >= 0 ? Y(0) : L.y1;
    if (!(esc.min < 0)) {
      svg.appendChild(el("line", { x1: L.x0, x2: L.x1, y1: yBase, y2: yBase, stroke: pal.zero, "stroke-width": 1.5 }));
    }

    // rótulos do eixo X
    if (g.categorias) {
      // Rótulo do tamanho que couber ENTRE DOIS RÓTULOS, e não dentro de uma
      // coluna: num eixo de 121 posições que mostra só de vinte em vinte, a
      // largura da coluna é de poucos pixels e a fonte sairia invisível.
      var comRotulo = [];
      for (var cr = d0; cr < d1; cr++) if (rotuloX(g, cr)) comRotulo.push(cr);
      var vao = comRotulo.length > 1 ? X(comRotulo[1] + 0.5) - X(comRotulo[0] + 0.5) : pw;
      var fsCat = Math.min(L.xlab * 1.2, corpoQueCabe(
        g.categorias.reduce(function (a, b) { return a.length > b.length ? a : b; }, ""),
        L.xlab * 1.2, vao * 0.95));
      for (var ci = d0; ci < d1; ci++) {
        // categoria de rótulo vazio não ganha marca nem texto: é assim que um
        // eixo de 121 posições mostra só de dez em dez sem virar borrão
        if (!rotuloX(g, ci)) continue;
        var cxc = X(ci + 0.5);
        svg.appendChild(el("line", { x1: cxc, x2: cxc, y1: L.y1, y2: L.y1 + 7, stroke: pal.zero, "stroke-width": 1.5 }));
        svg.appendChild(texto(rotuloX(g, ci), {
          x: cxc, y: L.y1 + 14, "font-size": fsCat, fill: pal.eixo,
          "text-anchor": "middle", "dominant-baseline": "hanging"
        }));
      }
    } else if (g.intradiario) {
      // janela longa: a virada de cada dia; janela curta: de hora em hora
      var marcasI = [], porDia = d1 - d0 > 96 * 4;
      var passoI = porDia ? 96 : 4;
      for (var ii = Math.ceil(d0 / passoI) * passoI; ii < d1; ii += passoI) marcasI.push(ii);
      var espacoI = marcasI.length > 1 ? pw / (marcasI.length - 1) : pw;
      var puloI = Math.max(1, Math.ceil(L.xlab * 1.4 / espacoI));
      [1, 2, 3, 4, 6, 8, 12, 24].some(function (n) { if (n >= puloI) { puloI = n; return true; } });
      marcasI.forEach(function (im, k4) {
        if (k4 % puloI !== 0) return;
        var cxi = X(im + 0.5), t = dataDeIdxIntra(im);
        svg.appendChild(el("line", { x1: cxi, x2: cxi, y1: L.y1, y2: L.y1 + 7, stroke: pal.zero, "stroke-width": 1.5 }));
        svg.appendChild(texto(porDia ? t.getUTCDate() + "/" + ("0" + (t.getUTCMonth() + 1)).slice(-2) : hhmm(t), {
          x: cxi + 4, y: L.y1 + 16, "font-size": L.xlab, fill: pal.eixo, "text-anchor": "end",
          "dominant-baseline": "hanging", transform: "rotate(" + L.xRot + " " + (cxi + 4) + " " + (L.y1 + 16) + ")"
        }));
      });
    } else if (g.diario) {
      // 1º de janeiro de cada ano (de 1, 2, 5 ou 10 em 10, conforme couber);
      // em janela curta, o primeiro dia de cada mês
      var marcas = [], ini0 = dataDeIdx(d0), fim0 = dataDeIdx(d1);
      var anual = d1 - d0 > 365.25 * 2.5;   // marca de ano ganha rótulo de ano ("1981", não "jan/81")
      if (anual) {
        for (var y = ini0.getUTCFullYear(); y <= fim0.getUTCFullYear(); y++) {
          var iy = Math.round(Date.UTC(y, 0, 1) / 86400000);
          if (iy >= d0 && iy < d1) marcas.push(iy);
        }
      } else {
        var ym = ini0.getUTCFullYear(), mm = ini0.getUTCMonth();
        for (var k2 = 0; k2 < 400; k2++) {
          var im = Math.round(Date.UTC(ym, mm, 1) / 86400000);
          if (im >= d1) break;
          if (im >= d0) marcas.push(im);
          if (++mm > 11) { mm = 0; ym++; }
        }
      }
      // rareia até os rótulos não se encostarem, em degraus redondos
      var espaco = marcas.length > 1 ? pw / (marcas.length - 1) : pw;
      var pulo = Math.max(1, Math.ceil(L.xlab * 1.3 / espaco));
      [1, 2, 3, 5, 6, 10, 12, 20, 24].some(function (n) { if (n >= pulo) { pulo = n; return true; } });
      marcas.forEach(function (im, k3) {
        if (k3 % pulo !== 0) return;
        var cxd = X(im + 0.5);
        svg.appendChild(el("line", { x1: cxd, x2: cxd, y1: L.y1, y2: L.y1 + 7, stroke: pal.zero, "stroke-width": 1.5 }));
        svg.appendChild(texto(anual ? String(dataDeIdx(im).getUTCFullYear()) : rotuloX(g, im), {
          x: cxd + 4, y: L.y1 + 16, "font-size": L.xlab, fill: pal.eixo, "text-anchor": "end",
          "dominant-baseline": "hanging", transform: "rotate(" + L.xRot + " " + (cxd + 4) + " " + (L.y1 + 16) + ")"
        }));
      });
    } else {
      // janeiro de cada ano; trimestral em janela curta
      var passoX = g.passoX || 12;
      if (d1 - d0 <= 72) passoX = Math.min(passoX, 3);
      var degraus = [3, 6, 12, 24, 36, 60];
      while (pxMes * passoX < L.xlab * 1.3) {
        var prox = degraus.filter(function (n) { return n > passoX; })[0];
        if (!prox) break;
        passoX = prox;
      }
      // marca de ano inteiro ganha rótulo de ano ("1981", não "jan/81"), como no eixo diário
      var anualM = passoX % 12 === 0;
      for (var i = d0; i < d1; i++) {
        if (i % passoX !== 0) continue;
        var cx = X(i + 0.5);
        svg.appendChild(el("line", { x1: cx, x2: cx, y1: L.y1, y2: L.y1 + 7, stroke: pal.zero, "stroke-width": 1.5 }));
        svg.appendChild(texto(anualM ? String(Math.floor(i / 12)) : rotuloMesCurto(i), {
          x: cx + 4, y: L.y1 + 16, "font-size": L.xlab, fill: pal.eixo, "text-anchor": "end",
          "dominant-baseline": "hanging", transform: "rotate(" + L.xRot + " " + (cx + 4) + " " + (L.y1 + 16) + ")"
        }));
      }
    }

    // acontecimentos: linha vertical fina na data, rótulo curto no alto. A
    // disposição já foi calculada (as fileiras), então aqui é só desenhar; o
    // texto vai por cima da linha do gráfico, no fim.
    var rotulosEventos = [];
    disporEventos(X, L.x1).forEach(function (e) {
      svg.appendChild(el("line", {
        x1: e.x, x2: e.x, y1: e.y + fsEv * 0.3, y2: L.y1,
        stroke: pal.suave, "stroke-width": 1.2, "stroke-dasharray": "3 7", opacity: 0.75
      }));
      rotulosEventos.push(texto(e.rot, {
        x: e.paraEsq ? e.x - 8 : e.x + 6, y: e.y, "font-size": fsEv, fill: pal.suave,
        "text-anchor": e.paraEsq ? "end" : "start"
      }));
    });

    // barras empilhadas
    var area = el("g", { "clip-path": "url(#" + idClip + ")" });
    svg.appendChild(area);
    // barra=1 (composição): 1px a mais tira a fresta entre uma coluna e outra,
    // e a pilha fica com cara de área empilhada
    var fBarra = g.barra || 0.86;
    var baseP = {}, baseN = {}, bw = Math.max(2, pxMes * fBarra + (fBarra >= 1 ? 1 : 0));
    g.series.forEach(function (s, k) {
      if (s.tipo !== "barra") return;
      var cor = corNoTema(s.cor, pal);
      vis[k].forEach(function (p) {
        if (!p.v) return;
        var b = p.v >= 0 ? baseP : baseN, antes = b[p.i] || 0, depois = antes + p.v;
        b[p.i] = depois;
        var ya = Y(antes), yb = Y(depois);
        area.appendChild(el("rect", {
          x: X(p.i + 0.5) - bw / 2, y: Math.min(ya, yb), width: bw, height: Math.max(0.6, Math.abs(yb - ya)), fill: cor,
          opacity: s.opacidade || null
        }));
      });
    });
    // faixas: o máximo de ida, o mínimo de volta, fechado e translúcido
    g.series.forEach(function (s, k) {
      if (s.tipo !== "faixa" || vis[k].length < 2) return;
      var ida = vis[k].map(function (p) { return X(p.i + 0.5).toFixed(1) + " " + Y(p.v2).toFixed(1); });
      var volta = vis[k].slice().reverse().map(function (p) { return X(p.i + 0.5).toFixed(1) + " " + Y(p.v).toFixed(1); });
      area.appendChild(el("path", {
        d: "M" + ida.join("L") + "L" + volta.join("L") + "Z", fill: corNoTema(s.cor, pal),
        opacity: s.opacidade || 0.3, stroke: "none"
      }));
    });
    // linhas, na ordem da lista (a última fica por cima)
    // no eixo diário, todo fim de semana é um salto de 3 dias: a linha só corta
    // quando o buraco for maior que isso (ali o título não estava em oferta)
    // no intradiário o pregão é quase 24 h: só o fim de semana (mais de 2 h
    // sem cotação) corta a linha
    var buracoMax = g.buracoMax || (g.intradiario ? 8 : g.diario ? 6 : 1);
    g.series.forEach(function (s, k) {
      if (s.tipo === "barra" || s.tipo === "faixa" || !vis[k].length) return;
      var d = "", ant = null;
      vis[k].forEach(function (p) {
        d += (ant === null || p.i - ant > buracoMax ? "M" : "L") + X(p.i + 0.5).toFixed(1) + " " + Y(p.v).toFixed(1);
        ant = p.i;
      });
      var w = s.largura || L.linha;
      area.appendChild(el("path", {
        d: d, fill: "none", stroke: corNoTema(s.cor, pal), "stroke-width": w,
        "stroke-linejoin": "round", "stroke-linecap": s.traco ? "butt" : "round",
        "stroke-dasharray": s.traco === "pontilhado" ? (w * 1.2) + " " + (w * 1.6) : null
      }));
    });

    ordem.forEach(function (o) {
      var cor = corNoTema(o.r.s.cor, pal);
      var px = X(o.r.p.i + 0.5), py = Y(o.r.p.v), lx = L.x1 + L.rotuloX;
      svg.appendChild(el("polyline", {
        points: px + "," + py + " " + (lx - 4) + "," + o.y, fill: "none", stroke: pal.suave, "stroke-width": 1.2
      }));
      svg.appendChild(texto(o.r.txt, {
        x: lx, y: o.y, "font-size": L.rotulo, "font-weight": "bold", fill: cor, "dominant-baseline": "central"
      }));
    });

    // legenda
    legenda.pos.forEach(function (it) {
      var y = topoLegenda + it.linha * L.legenda.passo, s = it.s, cor = corNoTema(s.cor, pal);
      if (s.tipo === "barra" || s.tipo === "faixa") {
        svg.appendChild(el("rect", { x: it.x + 6, y: y - 10, width: 22, height: 20, fill: cor,
                                     opacity: s.tipo === "faixa" ? (s.opacidade || 0.3) * 1.6 : (s.opacidade || null) }));
      } else {
        var w = Math.min(s.largura || L.linha, 8);
        svg.appendChild(el("line", {
          x1: it.x + 4, x2: it.x + legenda.sw - 2, y1: y, y2: y, stroke: cor, "stroke-width": w,
          "stroke-linecap": s.traco ? "butt" : "round",
          "stroke-dasharray": s.traco === "pontilhado" ? (w * 1.2) + " " + (w * 1.6) : null
        }));
      }
      svg.appendChild(texto(s.nome, {
        x: it.x + legenda.sw + legenda.gap, y: y, "font-size": legenda.fs, fill: pal.texto, "dominant-baseline": "central"
      }));
    });

    // título, subtítulo, fonte e logo
    svg.appendChild(texto(g.titulo, {
      x: L.titulo.x, y: L.titulo.y, "font-weight": "bold", fill: pal.texto,
      "font-size": corpoQueCabe(g.titulo, L.titulo.fs, L.titulo.max, "bold")
    }));
    subLinhas.forEach(function (linha, k) {
      if (!linha) return;
      svg.appendChild(texto(linha, {
        x: L.sub.x, y: L.sub.y + k * L.sub.fs * 1.2, "font-style": "italic", fill: pal.texto,
        "font-size": corpoQueCabe(linha, L.sub.fs, L.sub.max, "italic")
      }));
    });
    svg.appendChild(texto("Fonte: " + g.fonte + ".", {
      x: L.fonte.x, y: L.fonte.y, "font-size": L.fonte.fs, fill: pal.texto, "text-anchor": "end"
    }));
    if (logoSvg) {
      var lh = L.logo.w * logoSvg.razao;
      var gl = el("svg", { x: L.logo.x, y: L.logo.y, width: L.logo.w, height: lh, viewBox: logoSvg.viewBox });
      var gg = el("g", { fill: pal.logo });
      logoSvg.nos.forEach(function (n) { gg.appendChild(n.cloneNode(true)); });
      gl.appendChild(gg);
      svg.appendChild(gl);
    }

    rotulosEventos.forEach(function (t) { svg.appendChild(t); });

    return { svg: svg, L: L, pal: pal, X: X, Y: Y, d0: d0, d1: d1, vis: vis, esc: esc };
  }

  // ---------- passar o mouse ----------
  // Mouse fino: a faixa é escolhida arrastando no gráfico. Dedo não arrasta
  // (ali o arrasto é a rolagem da página), e o celular fica com os botões.
  function mouseFino() {
    try { return window.matchMedia("(pointer: fine)").matches; } catch (e) { return true; }
  }

  // Um só ouvinte para o Esc: `ligarHover` roda a cada pintura do cartão.
  var cancelarArrasto = null;
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && cancelarArrasto) cancelarArrasto();
  });

  function aplicarJanela(cartao, ini, fim) {
    cartao.inicioIdx = ini;
    cartao.fimIdx = fim;
    cartao.periodo = ini === null && fim === null ? "tudo" : "faixa";
    if (cartao.atualizarPeriodos) cartao.atualizarPeriodos();
    desenhar(cartao, true);
    if (visor && visor.cartao === cartao && !visor.box.hidden) pintarVisor();
  }

  function ligarHover(cartao, desenho) {
    if (desenho.ranking) return;            // o valor já está escrito na barra
    var svg = desenho.svg, L = desenho.L, pal = desenho.pal, g = graficoDe(cartao), F = unidade(g);
    var camada = el("g", { "pointer-events": "none" });
    var alvo = el("rect", { x: L.x0, y: L.y0, width: L.x1 - L.x0, height: L.y1 - L.y0, fill: "transparent" });
    svg.appendChild(alvo);
    svg.appendChild(camada);
    var porSerie = desenho.vis.map(function (pts) {
      return pts.reduce(function (o, p) { o[p.i] = p.v2 === undefined ? p.v : [p.v, p.v2]; return o; }, {});
    });

    function limpar() { while (camada.firstChild) camada.removeChild(camada.firstChild); }
    // a faixa mostra os dois extremos
    function valorTip(v, s) {
      var Fs = unidadeDe(g, s);
      return Array.isArray(v) ? Fs.valor(v[0]) + " a " + Fs.valor(v[1]) : Fs.valor(v);
    }
    function mover(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      var p = pt.matrixTransform(svg.getScreenCTM().inverse());
      var i = Math.floor(desenho.d0 + (p.x - L.x0) / (L.x1 - L.x0) * (desenho.d1 - desenho.d0));
      if (g.diario || g.intradiario) {
        // fim de semana e feriado não têm pregão: vale a última cotação antes
        var limite = g.intradiario ? 9 : 7;
        for (var volta = 0; volta < limite; volta++) {
          var achou = porSerie.some(function (m) { return m[i - volta] !== undefined; });
          if (achou) { i -= volta; break; }
        }
      }
      // ficar fora da legenda não é ficar fora da caixa: o que sai daqui é a
      // série repetida (mesmo nome), como as duas metades de uma banda
      var linhas = [];
      g.series.forEach(function (s, k) {
        if (porSerie[k][i] === undefined) return;
        if (linhas.some(function (l) { return l.s.nome === s.nome; })) return;
        linhas.push({ s: s, v: porSerie[k][i] });
      });
      limpar();
      if (!linhas.length) return;
      var x = desenho.X(i + 0.5), fs = L.tip, pad = fs * 0.6;
      camada.appendChild(el("line", {
        x1: x, x2: x, y1: L.y0, y2: L.y1, stroke: pal.suave, "stroke-width": 1.5, "stroke-dasharray": "6 6"
      }));
      var titulo = rotuloX(g, i, true);
      var w = Math.max(largura(titulo, fs, "bold"), Math.max.apply(null, linhas.map(function (l) {
        return largura(l.s.nome + "  " + valorTip(l.v, l.s), fs) + fs * 1.1;
      }))) + pad * 2;
      var h = (linhas.length + 1) * fs * 1.3 + pad;
      var bx = x + 22; if (bx + w > L.x1) bx = x - 22 - w;
      var by = Math.max(L.y0 + 8, Math.min(p.y - h / 2, L.y1 - h - 8));
      camada.appendChild(el("rect", { x: bx, y: by, width: w, height: h, rx: 8, fill: pal.tipBg, stroke: pal.tipBorda, "stroke-width": 1.5 }));
      camada.appendChild(texto(titulo, { x: bx + pad, y: by + pad + fs * 0.8, "font-size": fs, "font-weight": "bold", fill: pal.texto }));
      linhas.forEach(function (l, k) {
        var ty = by + pad + fs * 0.8 + (k + 1) * fs * 1.3;
        camada.appendChild(el("rect", { x: bx + pad, y: ty - fs * 0.62, width: fs * 0.7, height: fs * 0.7, rx: 2, fill: corNoTema(l.s.cor, pal) }));
        camada.appendChild(texto(l.s.nome, { x: bx + pad + fs * 1.1, y: ty, "font-size": fs, fill: pal.suave }));
        camada.appendChild(texto(valorTip(l.v, l.s), { x: bx + w - pad, y: ty, "font-size": fs, "font-weight": "bold", fill: pal.texto, "text-anchor": "end" }));
        if (desenho.vis[g.series.indexOf(l.s)] && l.s.tipo !== "barra") {
          camada.appendChild(el("circle", { cx: x, cy: desenho.Y(l.v), r: 6, fill: corNoTema(l.s.cor, pal), stroke: pal.bg, "stroke-width": 2 }));
        }
      });
    }
    // ---- escolher o período arrastando, como no FRED ----
    // A faixa fica numa camada própria, abaixo da do mouse: `limpar()` apaga a
    // caixa de valores a cada movimento, e levaria o retângulo junto.
    var faixa = el("rect", {
      y: L.y0, height: L.y1 - L.y0, width: 0, fill: pal.suave, opacity: 0.2,
      "pointer-events": "none", visibility: "hidden"
    });
    svg.insertBefore(faixa, camada);
    var arrasto = null;

    function xNoSvg(ev) {
      var pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse()).x;
    }
    function idxNoX(x) {
      var t = Math.min(Math.max(x, L.x0), L.x1);
      return Math.floor(desenho.d0 + (t - L.x0) / (L.x1 - L.x0) * (desenho.d1 - desenho.d0));
    }
    function pintarFaixa() {
      var a = Math.min(arrasto.a, arrasto.b), b = Math.max(arrasto.a, arrasto.b);
      faixa.setAttribute("x", Math.max(L.x0, a));
      faixa.setAttribute("width", Math.max(0, Math.min(L.x1, b) - Math.max(L.x0, a)));
      faixa.setAttribute("visibility", "visible");
    }
    function encerrar() {
      arrasto = null;
      cancelarArrasto = null;
      faixa.setAttribute("visibility", "hidden");
    }

    if (!g.categorias && mouseFino()) {
      alvo.addEventListener("pointerdown", function (ev) {
        if (ev.button !== 0 || ev.pointerType === "touch") return;
        arrasto = { a: xNoSvg(ev), b: xNoSvg(ev) };
        cancelarArrasto = encerrar;
        try { alvo.setPointerCapture(ev.pointerId); } catch (e) {}
        ev.preventDefault();
      });
      alvo.addEventListener("pointermove", function (ev) {
        if (!arrasto) return;
        arrasto.b = xNoSvg(ev);
        pintarFaixa();
      });
      alvo.addEventListener("pointerup", function () {
        if (!arrasto) return;
        var a = Math.min(arrasto.a, arrasto.b), b = Math.max(arrasto.a, arrasto.b);
        var i0 = idxNoX(a), i1 = idxNoX(b);
        encerrar();
        // arrasto curto é clique, não seleção
        if (b - a < 8 || i1 - i0 < 1) return;
        aplicarJanela(cartao, i0, i1);
      });
      alvo.addEventListener("pointercancel", encerrar);
      alvo.addEventListener("dblclick", function () { aplicarJanela(cartao, null, null); });
    }

    alvo.addEventListener("pointermove", function (ev) { if (!arrasto) mover(ev); else limpar(); });
    alvo.addEventListener("pointerdown", function (ev) { if (!arrasto) mover(ev); });
    alvo.addEventListener("pointerleave", function () { if (!arrasto) limpar(); });
  }

  // ---------- retrátil (categorias, seções e cartões) ----------
  // Tudo começa fechado, toda vez que o site abre: a página inicial é o índice
  // dos gráficos, e o usuário abre o que quiser ver.
  function seta() {
    return el("svg", { "class": "seta", viewBox: "0 0 16 16", width: "13", height: "13", "aria-hidden": "true" }, [
      el("path", {
        d: "M5 3l5 5-5 5", fill: "none", stroke: "currentColor",
        "stroke-width": "1.8", "stroke-linecap": "round", "stroke-linejoin": "round"
      })
    ]);
  }
  function icone(d, tam) {
    return el("svg", { viewBox: "0 0 24 24", width: tam || 16, height: tam || 16, fill: "none",
      stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round",
      "aria-hidden": "true" }, [el("path", { d: d })]);
  }
  var ICO_ENTRAR = "M3 9V3h6M21 9V3h-6M3 15v6h6M21 15v6h-6";
  var ICO_COMENTARIO = "M4 5h16v11H9l-5 4z";
  var ICO_ZOOM = "M11 4a7 7 0 1 0 0 14a7 7 0 0 0 0-14zM20 20l-4.2-4.2M11 8v6M8 11h6";

  // ---------- tela cheia (API do navegador, com o prefixo do Safari) ----------
  // requestFullscreen devolve Promise nos navegadores atuais e undefined nos
  // antigos — daí o teste antes do .catch. Uma recusa (gesto fora do clique,
  // política de permissão) não deve virar erro no console.
  function elFullscreen() { return document.fullscreenElement || document.webkitFullscreenElement || null; }
  function fullscreenSuportado(n) { return !!(n.requestFullscreen || n.webkitRequestFullscreen); }
  function entrarFullscreen(n) {
    var p = n.requestFullscreen ? n.requestFullscreen()
          : n.webkitRequestFullscreen ? n.webkitRequestFullscreen() : null;
    if (p && p.catch) p.catch(function () {});
  }
  function sairFullscreen() {
    if (!elFullscreen()) return;
    var p = document.exitFullscreen ? document.exitFullscreen()
          : document.webkitExitFullscreen ? document.webkitExitFullscreen() : null;
    if (p && p.catch) p.catch(function () {});
  }
  function telaCheiaDaPagina() {
    var btn = document.getElementById("tela-cheia-pagina");
    if (!btn) return;
    if (!fullscreenSuportado(document.documentElement)) { btn.hidden = true; return; }
    function sincronizar() {
      var ativo = !!elFullscreen() && !(visor && !visor.box.hidden);
      btn.setAttribute("aria-pressed", ativo ? "true" : "false");
      var rot = ativo ? "Sair da tela cheia" : "Ver a página em tela cheia";
      btn.setAttribute("aria-label", rot);
      btn.title = rot;
    }
    btn.addEventListener("click", function () {
      if (elFullscreen()) sairFullscreen(); else entrarFullscreen(document.documentElement);
    });
    ["fullscreenchange", "webkitfullscreenchange"].forEach(function (t) {
      document.addEventListener(t, sincronizar);
    });
    sincronizar();
  }

  // ---------- anotação à mão sobre o gráfico ----------
  // Os traços ficam guardados como listas de pontos nas coordenadas do layout
  // (1920×1080 e afins) e são repintados do zero a cada mudança: por isso o
  // canvas acompanha o SVG em qualquer tamanho de tela, e o mesmo traço pode
  // ser redesenhado em escala 2× no PNG baixado.
  function anotacao(tela) {
    var ctx = tela.getContext("2d"), tracos = [], atual = null;
    function cor() { return tema() === "light" ? "#D92B1F" : "#FF4B3E"; }
    function espessura() { return Math.max(3, tela.width / 320); }
    function tracar(c) {
      c.strokeStyle = cor(); c.lineWidth = espessura(); c.lineCap = "round"; c.lineJoin = "round";
      tracos.forEach(function (t) {
        if (t.length < 2) return;
        c.beginPath(); c.moveTo(t[0].x, t[0].y);
        for (var i = 1; i < t.length; i++) c.lineTo(t[i].x, t[i].y);
        c.stroke();
      });
    }
    function repintar() { ctx.clearRect(0, 0, tela.width, tela.height); tracar(ctx); }
    function ponto(ev) {
      var r = tela.getBoundingClientRect();
      return { x: (ev.clientX - r.left) * (tela.width / r.width), y: (ev.clientY - r.top) * (tela.height / r.height) };
    }
    tela.addEventListener("pointerdown", function (ev) {
      ev.preventDefault();
      try { tela.setPointerCapture(ev.pointerId); } catch (e) {}
      atual = [ponto(ev)]; tracos.push(atual);
    });
    tela.addEventListener("pointermove", function (ev) {
      if (!atual) return;
      atual.push(ponto(ev)); repintar();
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (t) {
      tela.addEventListener(t, function () { atual = null; });
    });
    return {
      tamanho: function (w, h) { tela.width = w; tela.height = h; repintar(); },
      limpar: function () { tracos = []; atual = null; repintar(); },
      desfazer: function () { tracos.pop(); repintar(); },
      desenhando: function () { return !!atual; },
      tem: function () { return tracos.length > 0; },
      // para o PNG baixado: mesmo traço, na escala do arquivo
      pintar: function (c, k) { c.save(); c.scale(k, k); tracar(c); c.restore(); }
    };
  }

  // ---------- visor: um gráfico só, grande, em tela cheia e anotável ----------
  var visor = null;

  function montarVisor() {
    var box = html("div", { "class": "visor", role: "dialog", "aria-modal": "true",
      "aria-label": "Gráfico ampliado", hidden: "" });

    var btnFechar = html("button", { type: "button", "class": "visor-fechar", "aria-label": "Fechar", texto: "✕" });
    btnFechar.addEventListener("click", fecharVisor);

    var palco = html("div", { "class": "visor-palco" });
    var tela = html("canvas", { "class": "visor-tela", "aria-hidden": "true" });
    palco.appendChild(tela);
    var anot = anotacao(tela);

    var barra = html("div", { "class": "visor-barra" });
    var inline = html("div", { "class": "visor-barra-inline" });
    var dica = html("span", { "class": "visor-dica" });

    var btnFs = html("button", { type: "button", "class": "visor-btn", texto: "Tela cheia", "aria-pressed": "false" });
    btnFs.hidden = !fullscreenSuportado(box);
    // a tela cheia é a do visor: se a página inteira estiver em tela cheia,
    // o botão leva o gráfico para a tela cheia, em vez de tirar a página dela
    btnFs.addEventListener("click", function () {
      if (elFullscreen() === box) sairFullscreen(); else entrarFullscreen(box);
    });
    // no Zoom, a saída tem nome: volta à página
    var btnSairZoom = html("button", { type: "button", "class": "visor-btn", texto: "Sair do Zoom" });
    btnSairZoom.addEventListener("click", function () { fecharVisor(); });

    var desenhando = false;
    function alternarDesenho(ligar) {
      desenhando = ligar === undefined ? !desenhando : ligar;
      box.classList.toggle("desenhando", desenhando);
      btnDesenho.setAttribute("aria-pressed", String(desenhando));
      btnDesenho.textContent = desenhando ? "Parar de desenhar" : "Desenhar";
      itemDesenho.textContent = btnDesenho.textContent;
      dica.textContent = desenhando ? "Arraste sobre o gráfico para anotar" : "";
    }
    var btnDesenho = html("button", { type: "button", "class": "visor-btn", "aria-pressed": "false", texto: "Desenhar" });
    btnDesenho.addEventListener("click", function () { alternarDesenho(); });
    var btnDesfazer = html("button", { type: "button", "class": "visor-btn", texto: "Desfazer" });
    btnDesfazer.addEventListener("click", function () { anot.desfazer(); });
    var btnLimpar = html("button", { type: "button", "class": "visor-btn", texto: "Limpar anotações" });
    btnLimpar.addEventListener("click", function () { anot.limpar(); });

    // Recortes do gráfico: ficam fora de "inline", que em tela cheia vira o
    // hambúrguer, para dar para trocar sem sair dela
    var recortes = html("div", { "class": "visor-recortes", role: "group", "aria-label": "Recorte do gráfico" });
    barra.appendChild(recortes);
    inline.appendChild(btnSairZoom);
    inline.appendChild(btnFs);
    inline.appendChild(btnDesenho);
    inline.appendChild(btnDesfazer);
    inline.appendChild(btnLimpar);
    inline.appendChild(dica);

    // Em tela cheia os controles passam a flutuar sobre o próprio gráfico —
    // então viram um hambúrguer só, que abre com um clique, em vez de quatro
    // botões brotando a cada movimento do mouse (é assim no chart book).
    var btnMenu = html("button", { type: "button", "class": "visor-menu-btn",
      "aria-haspopup": "true", "aria-expanded": "false", "aria-label": "Menu" });
    btnMenu.appendChild(el("svg", { viewBox: "0 0 16 16", width: "16", height: "16", "aria-hidden": "true" },
      [4, 8, 12].map(function (y) {
        return el("line", { x1: 2, y1: y, x2: 14, y2: y, stroke: "currentColor", "stroke-width": "1.6", "stroke-linecap": "round" });
      })));
    var menu = html("div", { "class": "visor-menu", role: "menu", hidden: "" });
    var menuAberto = false;
    function abrirMenu() {
      menuAberto = true; menu.hidden = false;
      btnMenu.setAttribute("aria-expanded", "true");
      mostrarChrome(false);   // enquanto o menu está aberto, nada some
    }
    function fecharMenu() {
      menuAberto = false; menu.hidden = true;
      btnMenu.setAttribute("aria-expanded", "false");
    }
    btnMenu.addEventListener("click", function (ev) { ev.stopPropagation(); if (menuAberto) fecharMenu(); else abrirMenu(); });
    document.addEventListener("click", function (ev) {
      if (!menuAberto || ev.target === btnMenu || menu.contains(ev.target)) return;
      fecharMenu();
    });

    function itemMenu(rot, acao) {
      var b = html("button", { type: "button", role: "menuitem", texto: rot });
      b.addEventListener("click", function () { fecharMenu(); acao(); });
      menu.appendChild(b);
      return b;
    }
    itemMenu("Sair da tela cheia", function () { sairFullscreen(); });
    var itemDesenho = itemMenu("Desenhar", function () { alternarDesenho(); });
    itemMenu("Desfazer", function () { anot.desfazer(); });
    itemMenu("Limpar anotações", function () { anot.limpar(); });
    itemMenu("Baixar PNG", function () { baixarDoVisor(); });

    var caixaMenu = html("div", { "class": "visor-menu-caixa" });
    caixaMenu.appendChild(btnMenu);
    caixaMenu.appendChild(menu);
    barra.appendChild(inline);
    barra.appendChild(caixaMenu);

    var btnBaixar = html("button", { type: "button", "class": "visor-baixar", texto: "Baixar PNG" });
    btnBaixar.addEventListener("click", function () { baixarDoVisor(); });

    function baixarDoVisor() {
      if (!visor.cartao) return;
      exportar(visor.cartao, visor.tamanho, "png", anot.tem() ? anot.pintar : null);
    }

    // Controles que somem sozinhos depois de um tempo parado e voltam a
    // qualquer movimento, toque ou foco de teclado — como num player de vídeo.
    // Só vale em tela cheia: fora dela eles ficam na margem escura, longe do
    // gráfico, e não atrapalham ninguém.
    var OCULTAR_APOS = 2600, timerChrome = null;
    function focoDeTeclado() {
      var a = document.activeElement;
      if (!a || a === box || !box.contains(a)) return false;
      try { return a.matches(":focus-visible"); } catch (e) { return false; }
    }
    function mostrarChrome(agendar) {
      box.classList.remove("chrome-oculto");
      if (timerChrome) { clearTimeout(timerChrome); timerChrome = null; }
      if (!agendar || !elFullscreen()) return;
      timerChrome = setTimeout(function () {
        timerChrome = null;
        if (focoDeTeclado() || menuAberto) return;   // não some com o foco ou o menu dentro
        box.classList.add("chrome-oculto");
      }, OCULTAR_APOS);
    }
    box.addEventListener("pointermove", function () { if (!anot.desenhando()) mostrarChrome(true); });
    box.addEventListener("pointerdown", function () { mostrarChrome(true); });
    box.addEventListener("focusin", function () { mostrarChrome(true); });
    box.addEventListener("focusout", function () { mostrarChrome(true); });

    // Em tela cheia os controles passam a flutuar sobre o gráfico. Colados no
    // topo eles cobririam o título — então descem para ~11,5% da altura do
    // palco (entre o subtítulo e a legenda), medida do retângulo real dele:
    // numa tela que não seja 16:9 o gráfico entra centralizado, com faixa
    // preta em volta, e a mesma porcentagem da janela cairia em outro lugar.
    function posicionarChrome() {
      if (!elFullscreen()) {
        barra.style.top = barra.style.left = "";
        btnFechar.style.top = btnFechar.style.right = "";
        return;
      }
      var r = palco.getBoundingClientRect();
      if (!r.height) return;
      var topo = (r.top + r.height * 0.115) + "px";
      barra.style.top = topo;
      barra.style.left = (r.left + 22) + "px";
      btnFechar.style.top = topo;
      btnFechar.style.right = (window.innerWidth - r.right + 22) + "px";
    }
    window.addEventListener("resize", posicionarChrome);

    // "Tela cheia" e "Zoom" são dois modos do visor. Sair da tela cheia (pelo
    // Esc ou pelo botão) volta à página, não ao Zoom: quem quis tela cheia não
    // pediu o zoom. Exceção: quem abriu o Zoom e de lá foi à tela cheia, ao
    // sair dela volta ao Zoom (visor.doZoom), que é de onde veio.
    var emTelaCheia = false;
    function sincronizarFs() {
      var ativo = elFullscreen() === box;
      if (!ativo && emTelaCheia && !box.hidden && !visor.doZoom) { emTelaCheia = false; fecharVisor(); return; }
      emTelaCheia = ativo;
      btnFs.textContent = ativo ? "Sair da tela cheia" : "Tela cheia";
      btnSairZoom.hidden = ativo;
      btnFs.setAttribute("aria-pressed", String(ativo));
      if (!ativo) fecharMenu();   // o hambúrguer nem aparece fora da tela cheia
      mostrarChrome(ativo);
      posicionarChrome();
      // o retângulo do palco só vale depois que o navegador repinta em tela cheia
      requestAnimationFrame(posicionarChrome);
    }
    ["fullscreenchange", "webkitfullscreenchange"].forEach(function (t) {
      document.addEventListener(t, sincronizarFs);
    });

    box.addEventListener("click", function (ev) { if (ev.target === box) fecharVisor(); });
    document.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape" || box.hidden) return;
      // Esc fecha o visor nos dois modos e volta à página (de tela cheia, o
      // navegador costuma sair sozinho e quem fecha é o sincronizarFs)
      fecharVisor();
    });

    // setas para o gráfico anterior e o seguinte, na ordem da página
    function seta(dir) {
      var b = html("button", { type: "button", "class": "visor-seta visor-seta-" + (dir < 0 ? "ant" : "prox"),
        "aria-label": dir < 0 ? "Gráfico anterior" : "Próximo gráfico" });
      b.appendChild(el("svg", { viewBox: "0 0 24 24", width: "22", height: "22", "aria-hidden": "true" }, [
        el("path", { d: dir < 0 ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7", fill: "none", stroke: "currentColor",
          "stroke-width": "2.4", "stroke-linecap": "round", "stroke-linejoin": "round" })
      ]));
      b.addEventListener("click", function (ev) { ev.stopPropagation(); irNoVisor(dir); });
      box.appendChild(b);
      return b;
    }
    var setaAnt = seta(-1), setaProx = seta(1);
    // ← e → do teclado fazem o mesmo (menos desenhando ou com modificador)
    document.addEventListener("keydown", function (ev) {
      if (box.hidden || desenhando || ev.altKey || ev.ctrlKey || ev.metaKey) return;
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      irNoVisor(ev.key === "ArrowLeft" ? -1 : 1);
    });

    box.appendChild(btnFechar);
    box.appendChild(barra);
    box.appendChild(palco);
    box.appendChild(btnBaixar);
    document.body.appendChild(box);

    visor = { box: box, palco: palco, tela: tela, anot: anot, fechar: btnFechar, recortes: recortes,
              setaAnt: setaAnt, setaProx: setaProx,
              mostrarChrome: mostrarChrome, fecharMenu: fecharMenu, desenho: alternarDesenho,
              cartao: null, tamanho: TAMANHOS[0], layout: "wide" };
    alternarDesenho(false);
  }

  function pintarVisor() {
    if (!visor || !visor.cartao) return;
    var L = LAYOUTS[visor.layout];
    var d = construir(visor.cartao, L, tema());
    ligarHover(visor.cartao, d);
    var antigo = visor.palco.querySelector("svg");
    if (antigo) visor.palco.removeChild(antigo);
    visor.palco.insertBefore(d.svg, visor.tela);
    visor.palco.style.setProperty("--ar", L.W / L.H);
  }

  // Os recortes do cartão, também no visor (em tela cheia não há outro jeito
  // de trocar). trocarVariante repinta o cartão e o visor.
  function montarRecortesDoVisor() {
    var box = visor.recortes, c = visor.cartao, vs = c.grafico.variantes;
    box.innerHTML = "";
    box.hidden = !vs;
    if (!vs) return;
    // muitos recortes, ou de nome comprido, quebrariam a barra em duas linhas
    // por cima do título: aí vira uma lista suspensa
    var texto = vs.reduce(function (n, v) { return n + v.rot.length; }, 0);
    if (vs.length > 3 || texto > 70) {
      var sel = html("select", { "class": "visor-btn visor-select", "aria-label": "Recorte do gráfico" });
      vs.forEach(function (v, k) {
        var o = html("option", { value: String(k), texto: v.rot });
        if (k === (c.variante || 0)) o.selected = true;
        sel.appendChild(o);
      });
      sel.addEventListener("click", function (ev) { ev.stopPropagation(); });
      sel.addEventListener("change", function () { c.trocarVariante(+sel.value); });
      box.appendChild(sel);
      return;
    }
    vs.forEach(function (v, k) {
      var b = html("button", { type: "button", "class": "visor-btn", texto: v.rot, "aria-pressed": String(k === (c.variante || 0)) });
      b.addEventListener("click", function (ev) {
        ev.stopPropagation();
        c.trocarVariante(k);
        Array.prototype.forEach.call(box.children, function (x, j) { x.setAttribute("aria-pressed", String(j === k)); });
      });
      box.appendChild(b);
    });
  }

  // Os cartões que abrem no visor, na ordem da página (tabela não abre: não
  // há desenho para ampliar)
  function navegaveis() {
    return cartoes.filter(function (c) { return c.grafico.tipo !== "tabela" && c.grafico.tipo !== "comunicados"; });
  }
  // Passa o visor para o gráfico vizinho (dir = −1 ou 1). Não dá a volta: no
  // primeiro e no último a seta daquele lado some.
  function irNoVisor(dir) {
    if (!visor || !visor.cartao) return;
    var lista = navegaveis(), j = lista.indexOf(visor.cartao) + dir;
    if (j < 0 || j >= lista.length) return;
    visor.cartao = lista[j];
    montarRecortesDoVisor();
    visor.anot.limpar();
    visor.desenho(false);
    pintarVisor();
    atualizarSetas();
    visor.mostrarChrome(true);
  }
  function atualizarSetas() {
    var lista = navegaveis(), i = lista.indexOf(visor.cartao);
    [[visor.setaAnt, lista[i - 1], "Anterior: "], [visor.setaProx, lista[i + 1], "Próximo: "]].forEach(function (x) {
      x[0].hidden = !x[1];
      if (x[1]) x[0].title = x[2] + x[1].grafico.titulo;
    });
  }

  function abrirVisor(cartao, comTelaCheia) {
    if (!visor) montarVisor();
    visor.cartao = cartao;
    visor.abertoEm = cartao;
    visor.doZoom = !comTelaCheia;
    montarRecortesDoVisor();
    atualizarSetas();
    visor.layout = window.innerWidth < 700 ? "narrow" : "wide";
    visor.tamanho = visor.layout === "wide" ? TAMANHOS[0] : TAMANHOS[1];
    pintarVisor();
    visor.anot.tamanho(LAYOUTS[visor.layout].W, LAYOUTS[visor.layout].H);
    visor.anot.limpar();
    visor.desenho(false);
    visor.box.hidden = false;
    document.body.classList.add("visor-aberto");
    visor.mostrarChrome(false);
    visor.fechar.focus();
    // o clique é o gesto que a API exige — pedir a tela cheia aqui funciona;
    // se o navegador recusar, o visor continua aberto com o botão à mão.
    if (comTelaCheia && fullscreenSuportado(visor.box)) entrarFullscreen(visor.box);
  }

  function fecharVisor() {
    if (!visor || visor.box.hidden) return;
    // sem isto, fechar pelo ✕ estando em tela cheia deixaria o navegador em
    // tela cheia exibindo um elemento já escondido (tela preta). Só a tela
    // cheia do visor: a da página inteira, se estiver ligada, continua.
    if (elFullscreen() === visor.box) sairFullscreen();
    visor.mostrarChrome(false);
    visor.fecharMenu();
    visor.box.hidden = true;
    visor.anot.limpar();
    var antigo = visor.palco.querySelector("svg");
    if (antigo) visor.palco.removeChild(antigo);
    document.body.classList.remove("visor-aberto");
    var volta = visor.cartao;
    visor.cartao = null;
    // andou pelas setas: a página vai até o último gráfico visto (abrindo o
    // que estiver fechado no caminho), em vez de voltar ao de partida
    if (volta && volta !== visor.abertoEm) {
      // depois de a tela cheia terminar de sair, senão a rolagem se perde
      setTimeout(function () {
        irPara(volta.grafico.id);
        if (volta.botaoTelaCheia) volta.botaoTelaCheia.focus({ preventScroll: true });
      }, 150);
    } else if (volta && volta.botaoTelaCheia) volta.botaoTelaCheia.focus({ preventScroll: true });
  }

  // ---------- cartão ----------
  function extensao(g) {
    var ini = Infinity, fim = -Infinity;
    g.series.forEach(function (s) {
      if (!s.dados.length) return;
      ini = Math.min(ini, idxDe(g, s.dados[0][0]));
      fim = Math.max(fim, idxDe(g, s.dados[s.dados.length - 1][0]));
    });
    return { ini: ini, fim: fim };
  }
  function periodosDisponiveis(g) {
    // tabela não tem eixo do tempo nem séries: não há janela a oferecer
    if (g.tipo === "tabela" || !g.series) return [];
    if (g.categorias) return [];   // eixo de categorias não tem janela de tempo
    var e = extensao(g), lista = [{ id: "tudo", rot: "Tudo" }];
    if (g.intradiario) {           // no intradiário a janela se conta em dias
      var dias = (e.fim - e.ini + 1) / 96;
      [10, 5, 2, 1].forEach(function (d) {
        if (dias > d * 1.3) lista.push({ id: "d" + d, rot: d === 1 ? "1 dia" : d + " dias" });
      });
      return lista;
    }
    var anos = (e.fim - e.ini + 1) / passosPorAno(g);
    (g.diario ? [20, 10, 5, 2, 1] : [20, 10, 5]).forEach(function (a) {
      if (anos > a * 1.1) lista.push({ id: String(a), rot: a === 1 ? "1 ano" : a + " anos" });
    });
    return lista;
  }
  function inicioDoPeriodo(g, id) {
    if (id === "tudo") return null;
    if (id.charAt(0) === "d") return extensao(g).fim - (+id.slice(1)) * 96 + 1;
    return extensao(g).fim - Math.round((+id) * passosPorAno(g)) + 1;
  }

  function criarCartao(g) {
    var cartao = { grafico: g, variante: 0, periodo: "tudo", inicioIdx: null, fimIdx: null, chave: null };
    var raiz = html("details", { "class": "card", id: g.id });

    var cabecalho = html("summary", { "class": "card-cabecalho" });
    cabecalho.appendChild(seta());
    var titulos = html("div", {}, [html("h3", { "class": "card-titulo", texto: g.titulo })]);
    if (g.subtitulo) titulos.appendChild(html("p", { "class": "card-sub", texto: g.subtitulo }));
    cabecalho.appendChild(titulos);
    raiz.appendChild(cabecalho);

    var ferramentas = html("div", { "class": "card-tools" });
    var esquerda = html("div", { "class": "card-escolhas" });

    // variantes: o mesmo cartão mostrando um recorte por vez (dívida interna ou
    // externa, % ou R$, um título ou um detentor…)
    if (g.variantes) {
      var grupoVar = html("div", { "class": "periodos", role: "group", "aria-label": "Recorte de " + g.titulo });
      // também chamada pelo clique numa bolha do mapa (mar → campos)
      cartao.trocarVariante = function (k) {
        cartao.variante = k;
        Array.prototype.forEach.call(grupoVar.children, function (x, j) {
          x.setAttribute("aria-pressed", String(j === k));
        });
        montarPeriodos();
        desenhar(cartao, true);
        if (visor && visor.cartao === cartao && !visor.box.hidden) pintarVisor();
      };
      g.variantes.forEach(function (v, k) {
        var b = html("button", { type: "button", texto: v.rot, "aria-pressed": String(k === 0) });
        b.addEventListener("click", function () { cartao.trocarVariante(k); });
        grupoVar.appendChild(b);
      });
      esquerda.appendChild(grupoVar);
    }

    // períodos: dependem da variante (a que tem eixo de categorias não tem)
    var grupo = html("div", { "class": "periodos", role: "group", "aria-label": "Período de " + g.titulo });
    function montarPeriodos() {
      var efetivo = graficoDe(cartao);
      var periodos = periodosDisponiveis(efetivo);
      grupo.innerHTML = "";
      // com mouse o controle vale em todo gráfico de tempo (o ranking não tem
      // eixo de tempo); sem mouse, só quando há mais de um recorte
      var deTempo = !!efetivo.series && !efetivo.categorias && efetivo.tipo !== "ranking" &&
                    efetivo.tipo !== "mapa" && efetivo.tipo !== "tabela";
      grupo.hidden = mouseFino() ? !deTempo : periodos.length < 2;
      if (grupo.hidden) {
        cartao.periodo = "tudo";
        cartao.inicioIdx = cartao.fimIdx = null;
        return;
      }
      if (mouseFino()) {
        // a faixa de um recorte não vale para o outro: trocar de variante volta tudo
        if (cartao.periodo !== "faixa") { cartao.inicioIdx = cartao.fimIdx = null; }
        grupo.appendChild(html("span", { "class": "periodos-dica",
          texto: "Arraste no gráfico para escolher o período" }));
        var volta = html("button", { type: "button", texto: "Ver tudo",
          title: "Volta à série inteira (duplo clique no gráfico faz o mesmo)" });
        volta.addEventListener("click", function () { aplicarJanela(cartao, null, null); });
        grupo.appendChild(volta);
        atualizarDica();
        return;
      }
      if (!periodos.some(function (p) { return p.id === cartao.periodo; })) cartao.periodo = "tudo";
      cartao.inicioIdx = inicioDoPeriodo(efetivo, cartao.periodo);
      cartao.fimIdx = null;
      periodos.forEach(function (p) {
        var b = html("button", { type: "button", texto: p.rot, "data-p": p.id, "aria-pressed": String(p.id === cartao.periodo) });
        b.addEventListener("click", function () {
          cartao.periodo = p.id;
          cartao.inicioIdx = inicioDoPeriodo(graficoDe(cartao), p.id);
          cartao.fimIdx = null;
          Array.prototype.forEach.call(grupo.children, function (x) {
            x.setAttribute("aria-pressed", String(x.getAttribute("data-p") === p.id));
          });
          desenhar(cartao, true);
        });
        grupo.appendChild(b);
      });
    }
    // Com a faixa escolhida, a dica dá lugar ao recorte na tela, e o "Ver
    // tudo" só aparece quando tem o que desfazer.
    function atualizarDica() {
      var dica = grupo.querySelector(".periodos-dica");
      var botao = grupo.querySelector("button");
      if (!dica || !botao) return;
      var efetivo = graficoDe(cartao), zoom = cartao.periodo === "faixa";
      function minusculo(t) { return t.charAt(0).toLowerCase() + t.slice(1); }
      dica.textContent = zoom && cartao.inicioIdx !== null
        ? minusculo(rotuloX(efetivo, cartao.inicioIdx, true)) + " a "
          + minusculo(rotuloX(efetivo, cartao.fimIdx, true))
        : "Arraste no gráfico para escolher o período";
      dica.classList.toggle("escolhido", zoom);
      botao.hidden = !zoom;
    }
    cartao.atualizarPeriodos = atualizarDica;
    cartao.periodo = g.periodoPadrao || "tudo";
    montarPeriodos();
    esquerda.appendChild(grupo);
    ferramentas.appendChild(esquerda);

    var acoes = html("div", { "class": "card-acoes" });
    if (g.tipo === "comunicados") {
      // nada a baixar: o texto é o do Fed, e o link de cada um fica no
      // comparador. Zoom e tela cheia levam o comparador (o mesmo, com as
      // escolhas feitas) para uma janela de leitura com letra maior.
      var btnZoomC = html("button", { type: "button", "class": "btn", title: "Ampliar o comparador na janela" });
      btnZoomC.appendChild(icone(ICO_ZOOM));
      btnZoomC.appendChild(html("span", { texto: "Zoom" }));
      btnZoomC.addEventListener("click", function () { abrirLeitor(cartao, false, btnZoomC); });
      var btnFsC = html("button", { type: "button", "class": "btn", title: "Ver o comparador em tela cheia" });
      btnFsC.appendChild(icone(ICO_ENTRAR));
      btnFsC.appendChild(html("span", { texto: "Tela cheia" }));
      btnFsC.addEventListener("click", function () { abrirLeitor(cartao, true, btnFsC); });
      if (!fullscreenSuportado(document.documentElement)) btnFsC.hidden = true;
      acoes.appendChild(btnZoomC);
      acoes.appendChild(btnFsC);
    } else if (g.tipo === "tabela") {
      // nada de tela cheia nem de PNG: não há desenho para ampliar nem para
      // rasterizar. O dado, esse sai em CSV como o de qualquer cartão.
      var btnCsv = html("button", { type: "button", "class": "btn", texto: "Baixar CSV" });
      btnCsv.addEventListener("click", function () { baixarCSV(cartao); });
      acoes.appendChild(btnCsv);
    } else {
      // Zoom: o gráfico ampliado dentro da janela. Tela cheia: ocupa a tela
      // toda, e o Esc volta direto à página.
      var btnZoom = html("button", { type: "button", "class": "btn", title: "Ampliar este gráfico na janela, com anotação à mão" });
      btnZoom.appendChild(icone(ICO_ZOOM));
      btnZoom.appendChild(html("span", { texto: "Zoom" }));
      btnZoom.addEventListener("click", function () { cartao.botaoTelaCheia = btnZoom; abrirVisor(cartao, false); });
      var btnFs = html("button", { type: "button", "class": "btn", title: "Ver só este gráfico, em tela cheia, com anotação à mão" });
      btnFs.appendChild(icone(ICO_ENTRAR));
      btnFs.appendChild(html("span", { texto: "Tela cheia" }));
      btnFs.addEventListener("click", function () { cartao.botaoTelaCheia = btnFs; abrirVisor(cartao, true); });
      cartao.botaoTelaCheia = btnFs;
      // sem a API (o Safari do iPhone, por exemplo), fica só o Zoom
      if (!fullscreenSuportado(document.documentElement)) btnFs.hidden = true;
      acoes.appendChild(btnZoom);
      acoes.appendChild(btnFs);
      acoes.appendChild(menuBaixar(cartao));
    }
    ferramentas.appendChild(acoes);
    raiz.appendChild(ferramentas);

    cartao.frame = html("div", { "class": "frame" });
    if (g._comentarios && g.tipo !== "comunicados") {
      var corpo = html("div", { "class": "card-corpo" });
      corpo.appendChild(cartao.frame);
      corpo.appendChild(montarComentario(cartao));
      raiz.appendChild(corpo);
    } else {
      raiz.appendChild(cartao.frame);
    }
    paragrafos(g.nota, "nota").forEach(function (p) { raiz.appendChild(p); });
    // o gráfico leva o rótulo curto do acontecimento; a explicação inteira fica
    // aqui embaixo, em lista, na ordem em que aconteceu
    var comTexto = (g.eventos || []).filter(function (e) { return e.texto; });
    if (comTexto.length) {
      var lista = html("ul", { "class": "eventos" });
      comTexto.forEach(function (e) {
        var li = html("li", {});
        li.appendChild(html("b", { texto: e.quando || e.rot }));
        li.appendChild(document.createTextNode(" — " + e.texto));
        lista.appendChild(li);
      });
      raiz.appendChild(lista);
    }

    // fechado não tem largura: o desenho espera o cartão abrir
    raiz.addEventListener("toggle", function () {
      if (raiz.open) desenhar(cartao, true);
    });

    cartao.raiz = raiz;
    return cartao;
  }

  // Cartão de tabela: HTML, não SVG. Nem todo achado é uma linha ou uma barra —
  // um resumo de teste estatístico, com p-valor e contagem, se lê melhor numa
  // tabela, e forçá-lo num gráfico só esconderia o número.
  //
  // Formato: `colunas` é a lista de cabeçalhos ({rot, num} — "num" alinha à
  // direita e usa fonte tabular, para as casas decimais ficarem em coluna), e
  // `linhas` é uma lista de listas. Cada célula é texto ou {t, cor, forte}.
  // ---------- comparador de comunicados ----------
  // Dois comunicados lado a lado num texto só: o que saiu do anterior vem
  // riscado, o que entrou no novo vem marcado. A comparação é palavra a
  // palavra (a maior subsequência comum, que é o que um "diff" faz); com
  // comunicados de algumas centenas de palavras a tabela da conta tem uns
  // 300 mil números e sai na hora.
  function palavrasDe(c) {
    var t = [];
    c.paragrafos.forEach(function (p, i) {
      if (i) t.push("\n");
      p.split(/\s+/).forEach(function (w) { if (w) t.push(w); });
    });
    return t;
  }
  function diffPalavras(a, b) {
    var n = a.length, m = b.length, L = [], i, j;
    for (i = 0; i <= n; i++) L.push(new Uint16Array(m + 1));
    for (i = n - 1; i >= 0; i--) {
      for (j = m - 1; j >= 0; j--) {
        L[i][j] = a[i] === b[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
      }
    }
    var ops = [];
    i = 0; j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push(["=", a[i]]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { ops.push(["-", a[i]]); i++; }
      else { ops.push(["+", b[j]]); j++; }
    }
    while (i < n) ops.push(["-", a[i++]]);
    while (j < m) ops.push(["+", b[j++]]);
    return ops;
  }
  function dataBR(iso) { var p = iso.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }

  // ---------- leitor: o comparador ampliado ----------
  // O visor dos gráficos pinta num canvas; o comparador é texto e tem
  // seletores, então o zoom dele é outro: o próprio nó sai do cartão para uma
  // janela por cima da página e volta ao fechar, com as escolhas intactas.
  var leitor = null;
  function abrirLeitor(cartao, comTelaCheia, origem) {
    if (!leitor) {
      var box = html("div", { "class": "leitor", role: "dialog", "aria-modal": "true", hidden: "" });
      var barra = html("div", { "class": "leitor-barra" });
      var titulo = html("h2", { "class": "leitor-titulo" });
      var btnSair = html("button", { type: "button", "class": "btn", texto: "Sair do Zoom" });
      btnSair.addEventListener("click", function () { fecharLeitor(); });
      var btnFs = html("button", { type: "button", "class": "btn", texto: "Tela cheia" });
      btnFs.hidden = !fullscreenSuportado(box);
      btnFs.addEventListener("click", function () {
        if (elFullscreen() === box) sairFullscreen(); else entrarFullscreen(box);
      });
      barra.appendChild(titulo);
      barra.appendChild(btnSair);
      barra.appendChild(btnFs);
      var corpo = html("div", { "class": "leitor-corpo" });
      box.appendChild(barra);
      box.appendChild(corpo);
      document.body.appendChild(box);
      document.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape" && !box.hidden && elFullscreen() !== box) fecharLeitor();
      });
      // saiu da tela cheia (pelo Esc do navegador) tendo entrado direto nela:
      // volta à página, como no visor
      ["fullscreenchange", "webkitfullscreenchange"].forEach(function (t) {
        document.addEventListener(t, function () {
          var ativo = elFullscreen() === box;
          btnFs.textContent = ativo ? "Sair da tela cheia" : "Tela cheia";
          if (!ativo && leitor.soTelaCheia && !box.hidden) fecharLeitor();
          if (ativo) leitor.entrou = true;
        });
      });
      leitor = { box: box, titulo: titulo, corpo: corpo, sair: btnSair };
    }
    var no = cartao.frame.querySelector(".comparador");
    if (!no) return;
    leitor.cartao = cartao;
    leitor.origem = origem;
    leitor.soTelaCheia = comTelaCheia;
    leitor.sair.hidden = comTelaCheia;
    leitor.titulo.textContent = cartao.grafico.titulo;
    leitor.box.setAttribute("aria-label", cartao.grafico.titulo);
    leitor.corpo.appendChild(no);
    leitor.box.hidden = false;
    document.body.classList.add("visor-aberto");
    if (comTelaCheia && fullscreenSuportado(leitor.box)) entrarFullscreen(leitor.box);
    (comTelaCheia ? no.querySelector("select") : leitor.sair).focus();
  }
  function fecharLeitor() {
    if (!leitor || leitor.box.hidden) return;
    if (elFullscreen() === leitor.box) sairFullscreen();
    var no = leitor.corpo.querySelector(".comparador");
    if (no && leitor.cartao) leitor.cartao.frame.appendChild(no);
    leitor.box.hidden = true;
    document.body.classList.remove("visor-aberto");
    if (leitor.origem) leitor.origem.focus({ preventScroll: true });
    leitor.cartao = null;
  }

  // ---------- comentários do autor (análise de cenário) ----------
  // À direita do gráfico, como a margem do Word, e retrátil. Quem tem a chave
  // do GitHub escreve ali mesmo: o texto vai para o arquivo de comentários do
  // assunto (textos/comentarios/…md) pela API do GitHub, e a Action "Publica
  // o texto" o costura no JSON em cerca de um minuto. Até lá, o navegador de
  // quem escreveu mostra a versão nova (guardada em "pendentes").
  var REPO = "guivaraschinalves/ftm-analises", RAMO = "main";
  var CHAVE_GH = "ftm_analises_github", CHAVE_PEND = "ftm_analises_comentarios_pendentes";
  function lerLocal(k, padrao) {
    try { var v = localStorage.getItem(k); return v === null ? padrao : JSON.parse(v); } catch (e) { return padrao; }
  }
  function gravarLocal(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

  function textoDoComentario(g) {
    var pend = lerLocal(CHAVE_PEND, {})[g._comentarios + "|" + g.titulo];
    if (!pend) return g.comentario || "";
    // o JSON já trouxe a versão gravada, ou passou tempo demais: vale o JSON
    if ((g.comentario || "") === pend.texto || Date.now() - pend.em > 15 * 60 * 1000) {
      var todos = lerLocal(CHAVE_PEND, {});
      delete todos[g._comentarios + "|" + g.titulo];
      gravarLocal(CHAVE_PEND, todos);
      return g.comentario || "";
    }
    return pend.texto;
  }

  function b64ParaTexto(b) {
    var bin = atob(b.replace(/\s/g, "")), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder().decode(bytes);
  }
  function textoParaB64(t) {
    var bytes = new TextEncoder().encode(t), bin = "";
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }
  // troca (ou cria, ou apaga, se vazio) o bloco "## título" do arquivo
  function trocarBloco(md, titulo, texto) {
    var linhas = md.replace(/\s+$/, "").split("\n"), ini = -1, fim = linhas.length;
    for (var i = 0; i < linhas.length; i++) {
      if (ini < 0 && linhas[i].trim() === "## " + titulo) { ini = i; continue; }
      if (ini >= 0 && /^##? /.test(linhas[i])) { fim = i; break; }
    }
    var bloco = texto ? ["## " + titulo].concat(texto.split("\n"), [""]) : [];
    if (ini >= 0) linhas.splice.apply(linhas, [ini, fim - ini].concat(bloco));
    else if (texto) linhas = linhas.concat([""], bloco);
    return linhas.join("\n").replace(/\n{3,}/g, "\n\n").replace(/\s*$/, "\n");
  }
  function chaveGitHub(pedirDeNovo) {
    var t = pedirDeNovo ? null : lerLocal(CHAVE_GH, null);
    if (t) return t;
    t = window.prompt("Para gravar, cole a chave do GitHub (token com permissão de escrita no " +
                      "repositório ftm-analises). Ela fica salva só neste navegador.");
    if (t) gravarLocal(CHAVE_GH, t.trim());
    return t ? t.trim() : null;
  }
  function gravarComentario(arquivo, titulo, texto, tentativa) {
    var token = chaveGitHub(tentativa === "nova-chave");
    if (!token) return Promise.reject(new Error("sem chave"));
    var url = "https://api.github.com/repos/" + REPO + "/contents/" + arquivo;
    var cab = { Authorization: "Bearer " + token, Accept: "application/vnd.github+json" };
    return fetch(url + "?ref=" + RAMO + "&t=" + Date.now(), { headers: cab, cache: "no-store" }).then(function (r) {
      if (r.status === 401 || r.status === 403) throw { chave: true };
      if (r.status === 404) return { sha: null, md: "" };
      if (!r.ok) throw new Error("GitHub respondeu " + r.status);
      return r.json().then(function (j) { return { sha: j.sha, md: b64ParaTexto(j.content) }; });
    }).then(function (atual) {
      var novo = trocarBloco(atual.md || "# Comentários\n", titulo, texto);
      var corpo = { message: (texto ? "Comentário: " : "Apaga comentário: ") + titulo,
                    content: textoParaB64(novo), branch: RAMO };
      if (atual.sha) corpo.sha = atual.sha;
      return fetch(url, { method: "PUT", headers: cab, body: JSON.stringify(corpo) });
    }).then(function (r) {
      if (r.status === 401 || r.status === 403) throw { chave: true };
      if ((r.status === 409 || r.status === 422) && !tentativa) return gravarComentario(arquivo, titulo, texto, "de-novo");
      if (!r.ok) throw new Error("GitHub respondeu " + r.status);
    }).catch(function (e) {
      if (e && e.chave && tentativa !== "nova-chave") {
        window.alert("A chave do GitHub não foi aceita. Cole outra.");
        return gravarComentario(arquivo, titulo, texto, "nova-chave");
      }
      throw e;
    });
  }

  function montarComentario(cartao) {
    var g = cartao.grafico;
    var aside = html("aside", { "class": "comentario" });
    var aba = html("button", { type: "button", "class": "comentario-aba" });
    aba.appendChild(icone(ICO_COMENTARIO));
    var rotAba = html("span", {});
    aba.appendChild(rotAba);
    var painel = html("div", { "class": "comentario-painel" });
    var topo = html("div", { "class": "comentario-topo" });
    topo.appendChild(html("span", { "class": "comentario-rot", texto: "Comentário" }));
    var fechar = html("button", { type: "button", "class": "comentario-fechar", title: "Recolher",
                                  "aria-label": "Recolher o comentário", texto: "›" });
    topo.appendChild(fechar);
    var leitura = html("div", { "class": "comentario-leitura" });
    var acoes = html("div", { "class": "comentario-acoes" });
    var btnEditar = html("button", { type: "button", "class": "btn" });
    acoes.appendChild(btnEditar);
    var edicao = html("div", { "class": "comentario-edicao", hidden: "" });
    var caixa = html("textarea", { rows: "8", placeholder: "Escreva o comentário. Linha em branco separa parágrafo; **assim** fica em negrito." });
    var botoes = html("div", { "class": "comentario-acoes" });
    var btnSalvar = html("button", { type: "button", "class": "btn btn-forte", texto: "Salvar" });
    var btnCancelar = html("button", { type: "button", "class": "btn", texto: "Cancelar" });
    var btnApagar = html("button", { type: "button", "class": "btn", texto: "Apagar" });
    botoes.appendChild(btnSalvar); botoes.appendChild(btnCancelar); botoes.appendChild(btnApagar);
    var aviso = html("p", { "class": "comentario-aviso" });
    edicao.appendChild(caixa); edicao.appendChild(botoes);
    painel.appendChild(topo); painel.appendChild(leitura); painel.appendChild(acoes);
    painel.appendChild(edicao); painel.appendChild(aviso);
    aside.appendChild(aba); aside.appendChild(painel);

    var atual = textoDoComentario(g);
    function mostrar() {
      leitura.innerHTML = "";
      paragrafos(atual, "comentario-texto").forEach(function (p) { leitura.appendChild(p); });
      leitura.hidden = !atual;
      btnEditar.textContent = atual ? "Editar" : "Escrever comentário";
      rotAba.textContent = atual ? "Comentário" : "Comentar";
      aba.title = atual ? "Mostrar o comentário" : "Escrever um comentário";
      aside.classList.toggle("vazio", !atual);
    }
    function abrir(sim) {
      aside.classList.toggle("aberto", sim);
      aba.setAttribute("aria-expanded", String(sim));
      desenhar(cartao, true);
    }
    function editar(sim) {
      edicao.hidden = !sim; acoes.hidden = sim; leitura.hidden = sim || !atual;
      if (sim) { caixa.value = atual; caixa.focus(); }
    }
    function salvar(texto) {
      texto = texto.replace(/\r/g, "").replace(/\n{3,}/g, "\n\n").trim();
      btnSalvar.disabled = btnApagar.disabled = true;
      aviso.textContent = "Gravando…";
      gravarComentario(g._comentarios, g.titulo, texto).then(function () {
        atual = texto;
        var todos = lerLocal(CHAVE_PEND, {});
        todos[g._comentarios + "|" + g.titulo] = { texto: texto, em: Date.now() };
        gravarLocal(CHAVE_PEND, todos);
        mostrar(); editar(false);
        aviso.textContent = "Gravado. Aparece para todos em cerca de um minuto.";
        if (!texto) abrir(false);
      }).catch(function (e) {
        aviso.textContent = e && e.message === "sem chave" ? "Sem a chave do GitHub, não dá para gravar."
          : "Não gravou: " + ((e && e.message) || "erro") + ". O texto continua na caixa.";
      }).then(function () { btnSalvar.disabled = btnApagar.disabled = false; });
    }
    aba.addEventListener("click", function () { abrir(true); if (!atual) editar(true); });
    fechar.addEventListener("click", function () { editar(false); aviso.textContent = ""; abrir(false); });
    btnEditar.addEventListener("click", function () { editar(true); });
    btnCancelar.addEventListener("click", function () { editar(false); aviso.textContent = ""; if (!atual) abrir(false); });
    btnSalvar.addEventListener("click", function () { salvar(caixa.value); });
    btnApagar.addEventListener("click", function () {
      if (atual && window.confirm("Apagar este comentário?")) salvar("");
      else if (!atual) { editar(false); abrir(false); }
    });
    mostrar();
    // com comentário e largura sobrando, nasce aberto; sem, só a aba
    var nasceAberto = !!atual && window.innerWidth >= 1100;
    aside.classList.toggle("aberto", nasceAberto);
    aba.setAttribute("aria-expanded", String(nasceAberto));
    return aside;
  }

  function montarComparador(g) {
    var lista = g.comunicados || [];
    var raiz = html("div", { "class": "comparador" });
    var escolhas = html("div", { "class": "comparador-escolhas" });
    function seletor(rotulo, padrao) {
      var sel = html("select", { "aria-label": rotulo });
      lista.slice().reverse().forEach(function (c) {
        var o = html("option", { value: c.data, texto: dataBR(c.data) });
        if (c.data === padrao) o.selected = true;
        sel.appendChild(o);
      });
      var rot = html("label", {});
      rot.appendChild(html("span", { texto: rotulo }));
      rot.appendChild(sel);
      escolhas.appendChild(rot);
      return sel;
    }
    var n = lista.length;
    var selA = seletor("Comunicado anterior", n > 1 ? lista[n - 2].data : (lista[0] || {}).data);
    var selB = seletor("Comunicado novo", n ? lista[n - 1].data : null);
    var resumo = html("span", { "class": "comparador-resumo" });
    escolhas.appendChild(resumo);
    var texto = html("div", { "class": "comparador-texto" });
    var links = html("p", { "class": "comparador-links" });
    raiz.appendChild(escolhas);
    raiz.appendChild(texto);
    raiz.appendChild(links);

    function achar(d) { return lista.filter(function (c) { return c.data === d; })[0]; }
    function comparar() {
      var a = achar(selA.value), b = achar(selB.value);
      texto.innerHTML = "";
      links.innerHTML = "";
      if (!a || !b) return;
      var ops = diffPalavras(palavrasDe(a), palavrasDe(b));
      var p = html("p", {}), tirou = 0, pos = 0, atual = null, tipo = null;
      texto.appendChild(p);
      ops.forEach(function (op) {
        if (op[1] === "\n") {
          // fim de parágrafo do texto novo (ou dos dois); o fim de um
          // parágrafo que só existia no anterior não quebra a linha
          if (op[0] !== "-") { p = html("p", {}); texto.appendChild(p); atual = null; tipo = null; }
          return;
        }
        if (op[0] === "-") tirou++;
        if (op[0] === "+") pos++;
        if (op[0] !== tipo || !atual) {
          atual = op[0] === "=" ? html("span", {}) : html(op[0] === "-" ? "del" : "ins", {});
          p.appendChild(atual);
          tipo = op[0];
          if (atual.previousSibling) p.insertBefore(document.createTextNode(" "), atual);
        } else {
          atual.appendChild(document.createTextNode(" "));
        }
        atual.appendChild(document.createTextNode(op[1]));
      });
      [].slice.call(texto.querySelectorAll("p")).forEach(function (x) { if (!x.textContent) texto.removeChild(x); });
      resumo.textContent = a === b ? "É o mesmo comunicado"
        : tirou + (tirou === 1 ? " palavra saiu" : " palavras saíram") + ", " +
          pos + (pos === 1 ? " entrou" : " entraram");
      [[a, "anterior"], [b, "novo"]].forEach(function (x, k) {
        if (k) links.appendChild(document.createTextNode(" · "));
        links.appendChild(html("a", { href: x[0].url, target: "_blank", rel: "noopener noreferrer",
          texto: "Comunicado de " + dataBR(x[0].data) + " no site do Fed" }));
      });
    }
    selA.addEventListener("change", comparar);
    selB.addEventListener("change", comparar);
    comparar();
    return raiz;
  }

  function montarTabela(g) {
    var tab = html("table", { "class": "tabela" });
    var thead = html("thead", {});
    var tr = html("tr", {});
    (g.colunas || []).forEach(function (c) {
      tr.appendChild(html("th", { "class": c.num ? "num" : "", texto: c.rot }));
    });
    thead.appendChild(tr);
    tab.appendChild(thead);
    var tbody = html("tbody", {});
    (g.linhas || []).forEach(function (linha) {
      var l = html("tr", {});
      linha.forEach(function (cel, k) {
        var col = (g.colunas || [])[k] || {};
        var o = (cel && typeof cel === "object") ? cel : { t: cel };
        var td = html("td", { "class": (col.num ? "num " : "") + (o.forte ? "forte" : ""),
                              texto: o.t === null || o.t === undefined ? "—" : String(o.t) });
        if (o.cor) td.style.color = corNoTema(o.cor, PALETAS[tema()]);
        l.appendChild(td);
      });
      tbody.appendChild(l);
    });
    tab.appendChild(tbody);
    return tab;
  }

  function desenhar(cartao, forcar) {
    // cartão (ou seção) fechado mede zero: redesenha quando voltar a aparecer
    if (!cartao.frame.clientWidth) { cartao.chave = null; return; }
    var nomeLayout = cartao.frame.clientWidth < 700 || window.innerWidth < 700 ? "narrow" : "wide";
    var chave = nomeLayout + "|" + tema() + "|" + cartao.periodo + "|" + cartao.inicioIdx + "|" + cartao.fimIdx + "|" + cartao.variante;
    if (!forcar && cartao.chave === chave) return;
    cartao.chave = chave;
    if (graficoDe(cartao).tipo === "comunicados") {
      // montado uma vez: as escolhas do leitor ficam no próprio DOM
      cartao.frame.style.aspectRatio = "";
      if (!cartao.frame.firstChild) cartao.frame.appendChild(montarComparador(graficoDe(cartao)));
      return;
    }
    if (graficoDe(cartao).tipo === "tabela") {
      // sem proporção fixa: a tabela tem a altura que o conteúdo pedir
      cartao.frame.style.aspectRatio = "";
      cartao.frame.innerHTML = "";
      cartao.frame.appendChild(montarTabela(graficoDe(cartao)));
      return;
    }
    var L = LAYOUTS[nomeLayout];
    var d = construir(cartao, L, tema());
    ligarHover(cartao, d);
    cartao.frame.style.aspectRatio = L.W + " / " + L.H;
    cartao.frame.innerHTML = "";
    cartao.frame.appendChild(d.svg);
  }

  // ---------- baixar ----------
  var FORMATOS = [
    { id: "png", nome: "PNG", nota: "sem perda, o mais nítido" },
    { id: "jpg", nome: "JPG", nota: "arquivo menor, para redes e WhatsApp" },
    { id: "pdf", nome: "PDF", nota: "para imprimir ou anexar" },
    { id: "svg", nome: "SVG", nota: "vetor editável (Illustrator/Figma)" }
  ];
  var tamanhoEscolhido = "slide";
  try { tamanhoEscolhido = localStorage.getItem("ftm_analises_tamanho") || "slide"; } catch (e) {}

  function tamanhoPorId(id) {
    return TAMANHOS.filter(function (t) { return t.id === id; })[0] || TAMANHOS[0];
  }
  function dimensoes(t) { return (t.layout.W * t.escala) + "×" + (t.layout.H * t.escala); }

  function menuBaixar(cartao) {
    var caixa = html("div", { "class": "baixar" });
    var botao = html("button", { type: "button", "class": "btn", "aria-haspopup": "menu", "aria-expanded": "false" });
    botao.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M4 20h16"/></svg><span>Baixar</span>';
    var menu = html("div", { "class": "menu", role: "menu", hidden: "" });

    var rotTam = html("label", { "class": "menu-rotulo", texto: "Tamanho" });
    var sel = html("select", { "class": "menu-tamanho", "aria-label": "Tamanho da imagem" });
    TAMANHOS.forEach(function (t) {
      var o = html("option", { value: t.id, texto: t.nome + " · " + dimensoes(t) });
      if (t.id === tamanhoPorId(tamanhoEscolhido).id) o.selected = true;
      sel.appendChild(o);
    });
    sel.addEventListener("change", function () {
      tamanhoEscolhido = sel.value;
      try { localStorage.setItem("ftm_analises_tamanho", sel.value); } catch (e) {}
      document.querySelectorAll(".menu-tamanho").forEach(function (x) { x.value = sel.value; });
    });
    rotTam.appendChild(sel);
    menu.appendChild(rotTam);

    FORMATOS.forEach(function (f) {
      var b = html("button", { type: "button", role: "menuitem" });
      b.innerHTML = "Imagem (" + f.nome + ")<small>" + f.nota + ", no tema atual</small>";
      b.addEventListener("click", function () { fechar(); exportar(cartao, tamanhoPorId(sel.value), f.id); });
      menu.appendChild(b);
    });
    menu.appendChild(html("hr"));
    var bc = html("button", { type: "button", role: "menuitem" });
    bc.innerHTML = "Dados (CSV)<small>uma coluna por série, para o Excel</small>";
    bc.addEventListener("click", function () { fechar(); baixarCSV(cartao); });
    menu.appendChild(bc);

    function fechar() { menu.hidden = true; botao.setAttribute("aria-expanded", "false"); }
    botao.addEventListener("click", function (e) {
      e.stopPropagation();
      var abrir = menu.hidden;
      document.querySelectorAll(".menu").forEach(function (m) { m.hidden = true; });
      menu.hidden = !abrir;
      botao.setAttribute("aria-expanded", String(abrir));
    });
    document.addEventListener("click", function (e) { if (!caixa.contains(e.target)) fechar(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") fechar(); });
    caixa.appendChild(botao);
    caixa.appendChild(menu);
    return caixa;
  }

  function salvar(blob, nome) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = nome;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  }
  function nomeArquivo(cartao, ext, t) {
    var g = cartao.grafico;
    var recorte = g.variantes ? "-" + slug(g.variantes[cartao.variante || 0].rot) : "";
    return "ftm-" + g.id + recorte + (t && t.id !== "slide" ? "-" + t.id : "") + "." + ext;
  }
  function carregarImagem(src) {
    return new Promise(function (ok, erro) {
      var im = new Image();
      im.onload = function () { ok(im); };
      im.onerror = function () { erro(new Error("não carregou " + src.slice(0, 60))); };
      im.src = src;
    });
  }
  function serializar(svg) { return new XMLSerializer().serializeToString(svg); }

  // pintar: função opcional que desenha as anotações do visor por cima (ctx, escala)
  function exportar(cartao, t, formato, pintar) {
    if (formato === "svg") return baixarSVG(cartao, t);
    var nomeTema = tema(), L = t.layout, d = construir(cartao, L, nomeTema);
    var W = L.W * t.escala, H = L.H * t.escala;
    // o SVG é rasterizado já no tamanho final: texto e linhas saem nítidos
    d.svg.setAttribute("width", W); d.svg.setAttribute("height", H);
    Promise.all([
      carregarImagem("data:image/svg+xml;charset=utf-8," + encodeURIComponent(serializar(d.svg))),
      d.pal.fundo ? carregarImagem(d.pal.fundo) : Promise.resolve(null)
    ]).then(function (r) {
      var c = document.createElement("canvas");
      c.width = W; c.height = H;
      var x = c.getContext("2d");
      x.imageSmoothingEnabled = true; x.imageSmoothingQuality = "high";
      x.fillStyle = d.pal.bg; x.fillRect(0, 0, W, H);
      if (r[1]) {
        // fundo em "cover": preenche o quadro sem distorcer (recorta o excesso)
        var f = r[1], k = Math.max(W / f.naturalWidth, H / f.naturalHeight);
        var fw = f.naturalWidth * k, fh = f.naturalHeight * k;
        x.drawImage(f, (W - fw) / 2, (H - fh) / 2, fw, fh);
      }
      x.drawImage(r[0], 0, 0, W, H);
      if (pintar) pintar(x, t.escala);
      if (formato === "png") {
        c.toBlob(function (b) { salvar(b, nomeArquivo(cartao, "png", t)); }, "image/png");
      } else if (formato === "jpg") {
        c.toBlob(function (b) { salvar(b, nomeArquivo(cartao, "jpg", t)); }, "image/jpeg", 0.95);
      } else {
        c.toBlob(function (b) {
          b.arrayBuffer().then(function (buf) {
            salvar(pdfComJpeg(new Uint8Array(buf), W, H, L.W * 0.75, L.H * 0.75), nomeArquivo(cartao, "pdf", t));
          });
        }, "image/jpeg", 0.97);
      }
    }).catch(function (e) { alert("Não consegui gerar a imagem: " + e.message); });
  }

  // PDF de uma página com a imagem (JPEG) ocupando a página toda.
  // pw/ph em pontos: 1 px do layout = 0,75 pt (96 dpi), então 16:9 vira 1440×810 pt.
  function pdfComJpeg(jpeg, iw, ih, pw, ph) {
    var enc = new TextEncoder(), partes = [], tam = 0, offs = [];
    function add(x) { var b = typeof x === "string" ? enc.encode(x) : x; partes.push(b); tam += b.length; }
    function obj(n, corpo) { offs[n] = tam; add(n + " 0 obj\n" + corpo + "\nendobj\n"); }
    var conteudo = "q " + pw + " 0 0 " + ph + " 0 0 cm /Im0 Do Q";
    add("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
    obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
    obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
    obj(3, "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 " + pw + " " + ph + "] " +
      "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>");
    offs[4] = tam;
    add("4 0 obj\n<< /Type /XObject /Subtype /Image /Width " + iw + " /Height " + ih +
      " /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length " + jpeg.length + " >>\nstream\n");
    add(jpeg);
    add("\nendstream\nendobj\n");
    obj(5, "<< /Length " + conteudo.length + " >>\nstream\n" + conteudo + "\nendstream");
    var xref = tam, linhas = "xref\n0 6\n0000000000 65535 f \n";
    for (var i = 1; i <= 5; i++) linhas += String(offs[i]).padStart(10, "0") + " 00000 n \n";
    add(linhas + "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + xref + "\n%%EOF\n");
    return new Blob(partes, { type: "application/pdf" });
  }

  function baixarSVG(cartao, t) {
    var L = t.layout, d = construir(cartao, L, tema());
    d.svg.insertBefore(el("rect", { x: 0, y: 0, width: L.W, height: L.H, fill: d.pal.bg }), d.svg.firstChild);
    salvar(new Blob([serializar(d.svg)], { type: "image/svg+xml" }), nomeArquivo(cartao, "svg", t));
  }

  function baixarCSV(cartao) {
    // toda série desenhada entra, inclusive a que não aparece na legenda: sem
    // legenda é decisão de leitura do gráfico, não de exportação do dado
    // (linha única num cartão de uma série só). Nome repetido vira "nome (2)".
    var g = graficoDe(cartao);
    if (g.tipo === "mapa") {
      return salvar(new Blob(["\ufeff" + ["item;pct_do_pais;mil_barris_dia"].concat((g.bolhas || []).map(function (b) {
        return b.nome.replace(/;/g, ",") + ";" + String(b.pct).replace(".", ",") + ";" + b.kbd;
      })).join("\r\n")], { type: "text/csv;charset=utf-8" }), nomeArquivo(cartao, "csv"));
    }
    if (g.tipo === "ranking") {
      return salvar(new Blob(["\ufeff" + ["item;valor"].concat((g.itens || []).map(function (it) {
        return it[0].replace(/;/g, ",") + ";" + String(it[1]).replace(".", ",");
      })).join("\r\n")], { type: "text/csv;charset=utf-8" }), nomeArquivo(cartao, "csv"));
    }
    if (g.tipo === "tabela") {
      var cab = (g.colunas || []).map(function (c) { return c.rot.replace(/;/g, ","); });
      var corpo = (g.linhas || []).map(function (l) {
        return l.map(function (cel) {
          var o = (cel && typeof cel === "object") ? cel : { t: cel };
          return String(o.t === null || o.t === undefined ? "" : o.t).replace(/;/g, ",");
        }).join(";");
      });
      return salvar(new Blob(["\ufeff" + [cab.join(";")].concat(corpo).join("\r\n")],
                             { type: "text/csv;charset=utf-8" }), nomeArquivo(cartao, "csv"));
    }
    // a faixa vira duas colunas, mínimo e máximo
    var cols = [];
    g.series.forEach(function (s) {
      if (s.tipo !== "faixa") return cols.push(s);
      cols.push({ nome: s.nome + " (mínimo)", dados: s.dados.map(function (d) { return [d[0], d[1]]; }) });
      cols.push({ nome: s.nome + " (máximo)", dados: s.dados.map(function (d) { return [d[0], d[2]]; }) });
    });
    var meses = {};
    cols.forEach(function (s) { s.dados.forEach(function (d) { meses[d[0]] = true; }); });
    var mapas = cols.map(function (s) { return s.dados.reduce(function (o, d) { o[d[0]] = d[1]; return o; }, {}); });
    var nomes = cols.map(function (s, k) {
      var n = s.nome.replace(/;/g, ",");
      return cols.filter(function (t, j) { return j < k && t.nome === s.nome; }).length ? n + " (2)" : n;
    });
    var linhas = [(g.categorias ? "faixa" : g.intradiario ? "hora" : g.diario ? "data" : "mes") + ";" + nomes.join(";")];
    Object.keys(meses).sort().forEach(function (m) {
      linhas.push((g.categorias ? g.categorias[+m] : m) + ";" + mapas.map(function (mp) {
        return mp[m] === undefined ? "" : String(mp[m]).replace(".", ",");
      }).join(";"));
    });
    salvar(new Blob(["﻿" + linhas.join("\r\n")], { type: "text/csv;charset=utf-8" }), nomeArquivo(cartao, "csv"));
  }

  // ---------- tema ----------
  function alternarTema() {
    var novo = tema() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novo);
    try { localStorage.setItem("ftm_analises_tema", novo); } catch (e) {}
    cartoes.forEach(function (c) { desenhar(c, true); });
    if (visor && !visor.box.hidden) pintarVisor();
  }

  // ---------- carga ----------
  function carregarLogo() {
    return fetch("assets/logo-ftm.svg").then(function (r) { return r.text(); }).then(function (txt) {
      var raiz = new DOMParser().parseFromString(txt, "image/svg+xml").documentElement;
      var vb = raiz.getAttribute("viewBox").split(/\s+/).map(Number);
      var nos = [];
      Array.prototype.forEach.call(raiz.childNodes, function (n) {
        if (n.nodeType !== 1 || n.nodeName === "style") return;
        var c = document.importNode(n, true);
        c.querySelectorAll ? c.querySelectorAll("[class]").forEach(function (x) { x.removeAttribute("class"); }) : null;
        nos.push(c);
      });
      logoSvg = { viewBox: vb.join(" "), razao: vb[3] / vb[2], nos: nos };
      var topo = document.getElementById("logo-topo");
      var s = el("svg", { viewBox: logoSvg.viewBox, "aria-hidden": "true" });
      var gg = el("g", { fill: "currentColor" });
      nos.forEach(function (n) { gg.appendChild(n.cloneNode(true)); });
      s.appendChild(gg);
      topo.appendChild(s);
    }).catch(function () {});
  }

  function rotuloNav(sec, g) {
    // o menu inteiro já está dentro de "IPCA": repetir o prefixo em cada linha
    // só faz o texto quebrar em três linhas na barra lateral
    var t = g.titulo.replace(/^IPCA: /, "");
    // dois gráficos com o mesmo título na mesma seção (contribuição em 12 e em
    // 3 meses) só se distinguem pelo fim do subtítulo ("... em 12 meses")
    var repetido = sec.graficos.filter(function (o) { return o.titulo === g.titulo; }).length > 1;
    if (!repetido || !g.subtitulo) return t;
    return t + " (" + g.subtitulo.split(";")[0].trim().split(" ").slice(-2).join(" ") + ")";
  }

  // O índice é uma lista, não um acordeão: assuntos, e sob o que está na tela
  // as seções dele. Nada retrátil — num relatório, abrir aba para descobrir o
  // que tem dentro é atrito. Clicar em outro assunto TROCA a página: um por
  // vez, porque empilhar três análises numa rolagem só perde o leitor.
  function montarNav(lista, host, atual) {
    host.innerHTML = "";
    lista.forEach(function (dados, i) {
      // "grupo" junta assuntos da mesma família (as análises de cenário, uma
      // por data) sob um cabeçalho no índice
      if (dados.grupo && (i === 0 || lista[i - 1].grupo !== dados.grupo)) {
        host.appendChild(html("p", { "class": "nav-grupo", texto: dados.grupo }));
      }
      var total = dados.secoes.reduce(function (n, sec) { return n + sec.graficos.length; }, 0);
      var linha = html("a", {
        "class": "nav-assunto" + (i === atual ? " atual" : ""),
        href: "#" + idAssunto(dados)
      });
      linha.appendChild(html("span", { texto: dados.assunto }));
      linha.appendChild(html("span", { "class": "nav-conta", texto: total + " gráficos" }));
      linha.addEventListener("click", function (ev) {
        ev.preventDefault();
        if (i === atual) { fecharIndice(); irPara(idAssunto(dados)); }
        else mostrar(i);
      });
      host.appendChild(linha);

      if (i !== atual) return;
      dados.secoes.forEach(function (sec, k) {
        if (!sec.titulo) return;          // seção sem título não vira linha do índice
        var destino = "secao-" + slug(dados.assunto) + "-" + k;
        var a = html("a", { "class": "nav-secao", href: "#" + destino, texto: sec.titulo });
        a.addEventListener("click", function (ev) {
          ev.preventDefault();
          fecharIndice();
          irPara(destino);
        });
        host.appendChild(a);
      });
    });
  }

  // ---------- notas de margem ----------
  //
  // Cada nota vai para a altura do trecho que a cita. Isso não dá para fazer
  // em CSS: depende de onde a palavra caiu depois de quebrar a linha, o que
  // só se sabe com o layout pronto. Daí ser recalculado aqui, e de novo a
  // cada redimensionamento.
  //
  // Abaixo de 1500px as notas voltam ao fluxo (o CSS cuida disso) e esta
  // função não mexe em nada: na coluna estreita não há margem para ocupar.
  var secoesComNotas = [];
  function posicionarNotas(secoes) {
    if (!window.matchMedia || !window.matchMedia("(min-width: 1500px)").matches) {
      (secoes || []).forEach(function (secao) {
        [].forEach.call(secao.querySelectorAll(".nota-margem"), function (n) {
          n.style.top = "";
        });
      });
      return;
    }
    (secoes || []).forEach(function (secao) {
      var base = secao.getBoundingClientRect().top;
      // A ordem na margem é a da CITAÇÃO, não a da declaração no arquivo de
      // texto. Sem isto, declarar as fontes numa ordem e citá-las em outra
      // empurrava cada nota para longe do trecho dela.
      var fila = [].map.call(secao.querySelectorAll(".nota-margem"), function (nota) {
        var id = nota.getAttribute("data-fonte");
        var alvo = id && secao.querySelector('.cita[data-fonte="' + id + '"]');
        return {
          nota: nota,
          // sem citação no texto, a nota vai para o fim da fila
          alvo: alvo ? alvo.getBoundingClientRect().top - base : Infinity
        };
      });
      fila.sort(function (a, b) { return a.alvo - b.alvo; });
      var piso = 0;                       // onde a nota anterior terminou
      fila.forEach(function (item) {
        var topo = Math.max(item.alvo === Infinity ? piso : item.alvo, piso);
        item.nota.style.top = topo + "px";
        piso = topo + item.nota.offsetHeight + 12;
      });
    });
  }

  // Passar o mouse num dos dois acende o outro: é o que confirma ao leitor
  // qual fonte pertence a qual trecho quando há várias por perto.
  function ligarRealce(raiz) {
    raiz.addEventListener("mouseover", function (ev) {
      var alvo = ev.target.closest && ev.target.closest(".cita, .nota-margem");
      if (!alvo) return;
      var id = alvo.getAttribute("data-fonte");
      if (!id) return;
      [].forEach.call(raiz.querySelectorAll('[data-fonte="' + id + '"]'),
        function (n) { n.classList.add("aceso"); });
    });
    raiz.addEventListener("mouseout", function () {
      [].forEach.call(raiz.querySelectorAll(".aceso"),
        function (n) { n.classList.remove("aceso"); });
    });
  }

  function fecharIndice() {
    var d = document.querySelector(".indice");
    if (d) d.open = false;
  }

  // Link do menu para um gráfico dentro de categoria, seção ou cartão fechado:
  // abre tudo que estiver no caminho antes de rolar até lá.
  function irPara(id) {
    var alvo = document.getElementById(id);
    if (!alvo) return;
    for (var n = alvo; n; n = n.parentElement) if (n.tagName === "DETAILS") n.open = true;
    cartoes.forEach(function (c) { desenhar(c, false); });
    alvo.scrollIntoView({ block: "start" });
    try { history.replaceState(null, "", "#" + id); } catch (e) {}
  }

  function idAssunto(dados) { return "assunto-" + slug(dados.assunto); }
  function slug(t) {
    return t.toLowerCase().replace(/%/g, "pct").normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  }

  // "2026-09-25" vira "25/09/2026"; "2026-09", "setembro de 2026" — quem manda
  // é a precisão do dado (o FRED é diário, o IPCA é mensal).
  function rotuloRef(ref) {
    var p = ref.split("-");
    return p.length > 2 ? p[2] + "/" + p[1] + "/" + p[0] : rotuloMesLongo(idxMes(ref)).toLowerCase();
  }
  function montarRodape(lista) {
    var rodape = document.getElementById("rodape");
    rodape.innerHTML = "";
    lista.forEach(function (dados) {
      var at = dados.atualizado.split("-");
      rodape.appendChild(html("p", { style: "margin:0 0 6px",
        texto: dados.assunto + " até " + rotuloRef(dados.referencia) +
               ", atualizado em " + at[2] + "/" + at[1] + "/" + at[0] + ". Fonte: " + dados.fonte + "." }));
    });
  }

  // Dois formatos, e a escolha é do arquivo de dados.
  //
  // O padrão é o índice retrátil: assunto > seções > gráficos, tudo fechado, a
  // tela inicial é o sumário. Serve a um painel, onde o leitor sabe o que
  // procura e não quer ler nada.
  //
  // `"formato": "artigo"` monta a mesma árvore aberta e sem setas, como um
  // texto: título, lede, e cada seção com a sua prosa e os gráficos dela no
  // meio. Serve a uma análise, onde o leitor precisa ser levado na ordem e
  // obrigá-lo a abrir capítulo é atrito. Os cartões continuam retráteis, mas
  // nascem abertos.
  function montarArtigo(dados, host) {
    var art = html("article", { "class": "artigo", id: idAssunto(dados) });
    ligarRealce(art);
    if (dados.grupo) art.appendChild(html("p", { "class": "artigo-grupo", texto: dados.grupo }));
    art.appendChild(html("h2", { "class": "artigo-titulo", texto: dados.assunto }));
    paragrafos(dados.apresentacao, "artigo-lede").forEach(function (p) {
      art.appendChild(p);
    });

    var aDesenhar = [], comNotas = [];
    dados.secoes.forEach(function (sec, k) {
      // Seção sem título é legítima: a primeira costuma continuar o título
      // do assunto, e repetir um cabeçalho ali só empurra o texto para baixo.
      var secao = html("section", {
        "class": "artigo-secao" + (sec.titulo ? "" : " sem-titulo"),
        id: "secao-" + slug(dados.assunto) + "-" + k
      });
      if (sec.titulo) {
        secao.appendChild(html("h3", { "class": "artigo-secao-titulo", texto: sec.titulo }));
      }
      // As fontes da seção vão para a margem esquerda em tela larga e viram
      // uma linha discreta embaixo do título em tela estreita. Ficam fora do
      // texto de propósito: quem lê não tropeça nelas, e quem quer conferir
      // acha sem caçar.
      var notas = (sec.fontes || []).map(function (f) {
        var nota = html("aside", { "class": "nota-margem", "data-fonte": f.id || "" });
        var item = f.url
          ? html("a", { href: f.url, target: "_blank", rel: "noopener noreferrer", texto: f.rot })
          : html("span", { texto: f.rot });
        nota.appendChild(item);
        return nota;
      });
      blocos(sec.texto, "artigo-texto", sec.figuras).forEach(function (p) {
        secao.appendChild(p);
      });
      sec.graficos.forEach(function (g) {
        g.fonte = g.fonte || dados.fonte;
        g._comentarios = dados.comentarios || null;
        var c = criarCartao(g);
        c.raiz.open = true;
        cartoes.push(c);
        aDesenhar.push(c);
        secao.appendChild(c.raiz);
      });
      // as notas entram por último para ficarem por cima na pilha
      notas.forEach(function (n) { secao.appendChild(n); });
      if (notas.length) comNotas.push(secao);
      art.appendChild(secao);
    });

    host.appendChild(art);
    // No quadro seguinte, não agora: desenhar() desiste se o frame ainda tem
    // largura zero (veja o clientWidth lá embaixo), e logo depois do
    // appendChild o navegador pode não ter feito o layout. Com o rAF o
    // desenho acontece depois dele. As notas de margem vêm depois dos
    // gráficos pelo mesmo motivo, e porque o gráfico muda a altura da seção.
    var pintar = function () {
      aDesenhar.forEach(function (c) { desenhar(c, true); });
      posicionarNotas(comNotas);
    };
    if (window.requestAnimationFrame) window.requestAnimationFrame(pintar);
    else setTimeout(pintar, 0);
    secoesComNotas = comNotas;
  }

  // Monta um assunto inteiro na página: assunto > seções > gráficos, tudo
  // fechado — a página inicial é o índice.
  // Com um assunto por página, nada nasce fechado: a antiga tela de sumário
  // existia porque os três dividiam a mesma rolagem, e agora quem faz esse
  // papel é o índice da barra de cima. O <details> fica, porque o leitor pode
  // querer recolher uma seção, mas o padrão é aberto.
  function montarAssunto(dados, host) {
    if (dados.formato === "artigo") return montarArtigo(dados, host);
    var cat = html("details", { "class": "categoria", id: idAssunto(dados), open: "" });
    var rotulo = html("summary", { "class": "categoria-rotulo" });
    rotulo.appendChild(seta());
    rotulo.appendChild(html("span", { texto: dados.assunto }));
    cat.appendChild(rotulo);
    var aDesenhar = [];
    paragrafos(dados.apresentacao, "apresentacao").forEach(function (p) {
      cat.appendChild(p);
    });

    dados.secoes.forEach(function (sec, k) {
      var secao = html("details", {
        "class": "secao", id: "secao-" + slug(dados.assunto) + "-" + k, open: ""
      });
      var rotuloSecao = html("summary", { "class": "secao-rotulo" });
      rotuloSecao.appendChild(seta());
      rotuloSecao.appendChild(html("span", { texto: sec.titulo }));
      secao.appendChild(rotuloSecao);
      // O texto da seção é onde mora a análise: fica entre o título e os
      // gráficos, e some junto com eles quando a seção está fechada.
      paragrafos(sec.texto, "secao-texto").forEach(function (p) {
        secao.appendChild(p);
      });

      var listaGraficos = html("div", { "class": "secao-graficos" });
      var daSecao = [];
      sec.graficos.forEach(function (g) {
        g.fonte = g.fonte || dados.fonte;
        g._comentarios = dados.comentarios || null;
        var c = criarCartao(g);
        c.raiz.open = true;
        cartoes.push(c);
        daSecao.push(c);
        aDesenhar.push(c);
        listaGraficos.appendChild(c.raiz);
      });
      secao.appendChild(listaGraficos);
      secao.addEventListener("toggle", function () {
        if (secao.open) daSecao.forEach(function (c) { desenhar(c, true); });
      });
      cat.appendChild(secao);
    });
    host.appendChild(cat);
    // Como no artigo: no quadro seguinte, quando o layout já aconteceu.
    var pintar = function () { aDesenhar.forEach(function (c) { desenhar(c, true); }); };
    if (window.requestAnimationFrame) window.requestAnimationFrame(pintar);
    else setTimeout(pintar, 0);
  }

  // Um assunto por vez. Trocar desmonta o anterior inteiro, inclusive a lista
  // de cartões — ela é quem o resize e o irPara percorrem, e deixar nela
  // cartão que saiu do DOM faria os dois desenharem no vazio.
  function mostrar(i, ancora) {
    var host = document.getElementById("graficos");
    atual = i;
    cartoes.length = 0;
    host.innerHTML = "";
    montarAssunto(docs[i], host);
    montarNav(docs, document.getElementById("nav"), i);
    montarRodape([docs[i]]);
    fecharIndice();
    if (ancora) irPara(ancora);
    else window.scrollTo({ top: 0, behavior: "auto" });
    try { history.replaceState(null, "", "#" + (ancora || idAssunto(docs[i]))); } catch (e) {}
  }

  // De qual assunto é esta âncora? Serve para um link direto a um gráfico
  // abrir a análise certa, e não a primeira da lista.
  function assuntoDoHash(h) {
    for (var i = 0; i < docs.length; i++) {
      if (idAssunto(docs[i]) === h) return [i, null];
      for (var k = 0; k < docs[i].secoes.length; k++) {
        if ("secao-" + slug(docs[i].assunto) + "-" + k === h) return [i, h];
        var achou = docs[i].secoes[k].graficos.some(function (g) { return g.id === h; });
        if (achou) return [i, h];
      }
    }
    return null;
  }

  function iniciar() {
    var host = document.getElementById("graficos");
    var buscas = FONTES.map(function (url) {
      return fetch(url).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    });
    Promise.all(buscas.concat([carregarLogo()])).then(function (r) {
      docs = r.slice(0, FONTES.length).filter(Boolean);
      if (!docs.length) throw new Error("nenhum arquivo de dados foi carregado");
      var alvo = location.hash.length > 1 ? assuntoDoHash(location.hash.slice(1)) : null;
      mostrar(alvo ? alvo[0] : 0, alvo ? alvo[1] : null);
    }).catch(function (e) {
      host.innerHTML = "";
      host.appendChild(html("p", { "class": "estado erro", texto: "Não foi possível carregar os dados. " + e.message }));
    });

    document.getElementById("tema").addEventListener("click", alternarTema);
    telaCheiaDaPagina();
    var espera;
    window.addEventListener("resize", function () {
      clearTimeout(espera);
      espera = setTimeout(function () {
        cartoes.forEach(function (c) { desenhar(c, false); });
        posicionarNotas(secoesComNotas);
      }, 120);
    });
  }

  iniciar();
})();
