// Baixa, pelo próprio site, o SVG 16:9 de cada gráfico pedido, no tema escuro.
//
//   node scripts/relatorio/exportar_svgs.js <porta> <slug do assunto> <lista.json> <pasta de saída>
//
// lista.json: [{"titulo": "...", "variante": "IPCA" (opcional), "arquivo": "01.svg"}]
// É o botão "Baixar > SVG" do site: o desenho é o mesmo que o leitor baixa.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const [porta, slug, listaArq, saida] = process.argv.slice(2);
  const lista = JSON.parse(fs.readFileSync(listaArq, 'utf8'));
  fs.mkdirSync(saida, { recursive: true });
  const b = await chromium.launch({
    executablePath: process.env.HOME + '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',
    args: ['--no-sandbox']
  });
  const ctx = await b.newContext({ viewport: { width: 1400, height: 1000 }, acceptDownloads: true });
  await ctx.addInitScript(() => {
    try { localStorage.setItem('ftm_analises_tema', 'dark'); localStorage.setItem('ftm_analises_tamanho', 'slide'); } catch (e) {}
  });
  const p = await ctx.newPage();
  p.on('pageerror', e => console.log('ERRO', e.message));
  await p.goto('http://127.0.0.1:' + porta + '/#assunto-' + slug, { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  await p.evaluate(s => document.querySelectorAll('#assunto-' + s + ' details').forEach(d => { d.open = true; }), slug);
  await p.waitForTimeout(800);
  const cards = await p.$$('#assunto-' + slug + ' details.card');
  const titulos = [];
  for (const c of cards) titulos.push(await c.evaluate(x => (x.querySelector('summary h3, summary .card-titulo, summary strong') || x.querySelector('summary')).textContent.trim()));
  for (const item of lista) {
    const i = titulos.findIndex(t => t.startsWith(item.titulo));
    if (i < 0) { console.log('NÃO ACHEI', item.titulo); continue; }
    const c = cards[i];
    await c.scrollIntoViewIfNeeded();
    if (item.variante) {
      const ok = await c.evaluate((card, v) => {
        const bt = [...card.querySelectorAll('.periodos button')].find(x => x.textContent.trim() === v);
        if (bt) bt.click();
        return !!bt;
      }, item.variante);
      if (!ok) console.log('sem a variante', item.variante, 'em', item.titulo);
      await p.waitForTimeout(400);
    }
    await c.evaluate(card => card.querySelector('.baixar > button').click());
    const [dl] = await Promise.all([
      p.waitForEvent('download'),
      c.evaluate(card => [...card.querySelectorAll('.baixar .menu button')].find(x => x.textContent.includes('SVG')).click())
    ]);
    await dl.saveAs(path.join(saida, item.arquivo));
    console.log('ok', item.arquivo, item.titulo, item.variante || '');
  }
  await b.close();
})();
