// Imprime o HTML do relatório em PDF (uma página 2400×1350 por slide) e grava
// uma prévia PNG de cada slide ao lado do PDF, para conferir.
//
//   node scripts/relatorio/pdf.js <relatorio.html> <saida.pdf> [pasta das prévias]
const { chromium } = require('playwright');

(async () => {
  const [pagina, saida, previas] = process.argv.slice(2);
  const b = await chromium.launch({
    executablePath: process.env.HOME + '/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome',
    args: ['--no-sandbox', '--allow-file-access-from-files']
  });
  const p = await b.newPage({ viewport: { width: 2400, height: 1350 } });
  p.on('pageerror', e => console.log('ERRO', e.message));
  await p.goto('file://' + pagina, { waitUntil: 'networkidle' });
  await p.waitForTimeout(800);
  await p.pdf({ path: saida, width: '2400px', height: '1350px', printBackground: true,
                margin: { top: 0, bottom: 0, left: 0, right: 0 } });
  if (previas) {
    const slides = await p.$$('section.slide');
    for (let i = 0; i < slides.length; i++) {
      await slides[i].screenshot({ path: previas + '/slide-' + String(i + 1).padStart(2, '0') + '.png' });
    }
  }
  await b.close();
})();
