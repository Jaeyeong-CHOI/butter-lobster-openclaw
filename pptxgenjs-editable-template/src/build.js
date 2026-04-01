const path = require('path');
const PptxGenJS = require('pptxgenjs');
const { THEMES } = require('./themes');

const META = {
  author: 'Jaeyeong CHOI',
  title: 'Attention Is All You Need Presentation',
  date: '2026-04-01',
};

function parseArgs(argv) {
  const args = { theme: 'dgist-report', out: null };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--theme' && argv[i + 1]) { args.theme = argv[++i]; continue; }
    if (a.startsWith('--theme=')) { args.theme = a.split('=')[1]; continue; }
    if (a === '--out' && argv[i + 1]) { args.out = argv[++i]; continue; }
    if (a.startsWith('--out=')) { args.out = a.split('=')[1]; continue; }
  }
  return args;
}

function addMeta(slide, C, FONT, dark = false) {
  const footerColor = dark ? C.light : C.muted;
  const dateColor = dark ? C.light : 'FFFFFF';

  // top-right date (white on body top blue ribbon)
  slide.addText(META.date, {
    x: 11.0, y: 0.05, w: 2.2, h: 0.18,
    fontFace: FONT, fontSize: 9, bold: true, color: dateColor, align: 'right',
  });

  // bottom meta
  slide.addText(META.author, {
    x: 0.3, y: 7.2, w: 3.8, h: 0.2,
    fontFace: FONT, fontSize: 9, color: footerColor,
  });
  slide.addText(META.title, {
    x: 8.0, y: 7.2, w: 5.0, h: 0.2,
    fontFace: FONT, fontSize: 9, color: footerColor, align: 'right',
  });
}

function addBodyFrame(pptx, slide, C, FONT, sec, title, subtitle) {
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 13.33, h: 0.28, fill: { color: C.blue }, line: { color: C.blue } });

  slide.addShape(pptx.ShapeType.roundRect, {
    x: 0.65, y: 0.55, w: 0.48, h: 0.34,
    rectRadius: 0.03,
    fill: { color: C.blue },
    line: { color: C.blue },
  });
  slide.addText(String(sec), {
    x: 0.65, y: 0.60, w: 0.48, h: 0.2,
    fontFace: FONT, fontSize: 12, bold: true, color: 'FFFFFF', align: 'center',
  });

  slide.addText(title, {
    x: 1.25, y: 0.50, w: 10.8, h: 0.42,
    fontFace: FONT, fontSize: 28, bold: true, color: C.navy,
  });
  slide.addShape(pptx.ShapeType.line, {
    x: 1.25, y: 0.95, w: 10.9, h: 0,
    line: { color: C.blue, pt: 1.5 },
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 1.28, y: 1.00, w: 10.8, h: 0.24,
      fontFace: FONT, fontSize: 12, color: C.muted,
    });
  }
  addMeta(slide, C, FONT, false);
}

function addCard(pptx, slide, C, FONT, x, y, w, h, title, opts = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: opts.fill || C.card },
    line: { color: C.line, pt: 1 },
  });
  if (title) {
    slide.addText(title, {
      x: x + 0.18, y: y + 0.10, w: w - 0.35, h: 0.25,
      fontFace: FONT, fontSize: 12, bold: true, color: opts.titleColor || C.blue,
    });
  }
}

function addBullets(slide, C, FONT, x, y, w, lines, size = 16) {
  const runs = lines.map((line) => ({ text: `• ${line}\n`, options: { breakLine: true } }));
  slide.addText(runs, {
    x, y, w, h: 2.8,
    fontFace: FONT, fontSize: size, color: C.text,
    valign: 'top', margin: 2,
  });
}

function buildDeck(themeName = 'dgist-report', outPath = null) {
  const theme = THEMES[themeName];
  if (!theme) throw new Error(`Unknown theme: ${themeName}`);

  const C = theme.colors;
  const FONT = theme.font;

  const pptx = new PptxGenJS();
  pptx.layout = 'LAYOUT_WIDE';
  pptx.author = META.author;
  pptx.subject = 'Attention Is All You Need';
  pptx.title = META.title;
  pptx.company = 'DGIST';
  pptx.lang = 'ko-KR';

  // Slide 1: Cover
  {
    const s = pptx.addSlide();
    s.background = { color: C.navy };

    // keep cover identity text (requested), remove only very bottom meta line
    s.addText('DGIST / RESEARCH SEMINAR', {
      x: 4.2, y: 0.9, w: 5.0, h: 0.2,
      fontFace: FONT, fontSize: 10.5, bold: true, color: C.light, align: 'center',
    });

    s.addShape(pptx.ShapeType.roundRect, {
      x: 1.9, y: 1.8, w: 9.5, h: 2.35,
      rectRadius: 0.08,
      fill: { color: 'FFFFFF', transparency: 88 },
      line: { color: C.mid, pt: 1 },
    });

    s.addText('Attention Is All You Need', {
      x: 2.2, y: 2.2, w: 8.9, h: 0.8,
      fontFace: FONT, fontSize: 38, bold: true, color: C.light, align: 'center',
    });
    s.addText('Transformer Architecture Brief', {
      x: 2.2, y: 3.0, w: 8.9, h: 0.35,
      fontFace: FONT, fontSize: 17, color: C.light, align: 'center',
    });

    s.addText('2026년 04월 발표 자료', {
      x: 3.4, y: 4.15, w: 6.6, h: 0.35,
      fontFace: FONT, fontSize: 20, bold: true, color: C.light, align: 'center',
    });

    s.addText([
      { text: `발표자: ${META.author}\n`, options: { breakLine: true } },
      { text: `발표명: ${META.title}\n`, options: { breakLine: true } },
      { text: '소속: DGIST', options: { breakLine: true } },
    ], {
      x: 2.9, y: 4.7, w: 7.5, h: 1.2,
      fontFace: FONT, fontSize: 13, color: C.light, align: 'center',
    });
  }

  // Slide 2: Context
  {
    const s = pptx.addSlide();
    addBodyFrame(pptx, s, C, FONT, 1, 'Why this paper mattered', 'from recurrence bottlenecks to attention-first modeling');

    addCard(pptx, s, C, FONT, 0.75, 1.8, 5.95, 4.8, 'Before', { fill: C.card });
    addBullets(s, C, FONT, 0.95, 2.35, 5.55, [
      'Long-range dependency learning was difficult',
      'Sequential processing limited parallelism',
      'Scaling up increased training cost',
    ], 15.5);

    addCard(pptx, s, C, FONT, 6.9, 1.8, 5.7, 4.8, 'After', { fill: C.softOrange });
    addBullets(s, C, FONT, 7.1, 2.35, 5.35, [
      'Self-attention directly models token relations',
      'Parallel-friendly architecture improved throughput',
      'Enabled practical large-scale pretraining',
    ], 15.5);
  }

  // Slide 3: Mechanism
  {
    const s = pptx.addSlide();
    addBodyFrame(pptx, s, C, FONT, 2, 'Core mechanism', 'scaled dot-product attention');

    addCard(pptx, s, C, FONT, 0.75, 1.8, 11.85, 4.8, 'Attention formula', { fill: C.card });
    s.addText('Attention(Q, K, V) = softmax(QK^T / sqrt(d_k))V', {
      x: 1.0, y: 2.35, w: 11.3, h: 0.55,
      fontFace: FONT, fontSize: 24, bold: true, color: C.blue, align: 'left',
    });
    addBullets(s, C, FONT, 1.0, 3.1, 11.3, [
      'QK^T computes token-to-token relevance',
      'sqrt(d_k) scaling improves optimization stability',
      'Weighted V aggregation builds contextual representations',
    ], 17.5);
  }

  // Slide 4: Results table
  {
    const s = pptx.addSlide();
    addBodyFrame(pptx, s, C, FONT, 3, 'Results and impact', 'report-style table block');

    addCard(pptx, s, C, FONT, 0.75, 1.8, 11.85, 4.8, null, { fill: C.card });

    const rows = [
      [
        { text: 'Category', options: { bold: true, color: 'FFFFFF' } },
        { text: 'Impact', options: { bold: true, color: 'FFFFFF' } },
      ],
      ['Modeling', 'Shift from recurrence-centric to attention-centric sequence modeling'],
      ['Efficiency', 'Substantially improved training parallelism and scalability'],
      ['Legacy', 'Established backbone used by BERT, GPT, and modern LLM families'],
    ];

    s.addTable(rows, {
      x: 1.0, y: 2.2, w: 11.35, h: 3.95,
      colW: [2.8, 8.55],
      fontFace: FONT,
      fontSize: 12,
      color: C.text,
      border: { type: 'solid', color: C.line, pt: 1 },
      fill: C.card,
      rowH: [0.45, 0.9, 0.9, 0.9],
    });

    s.addShape(pptx.ShapeType.rect, {
      x: 1.0, y: 2.2, w: 11.35, h: 0.45,
      fill: { color: C.blue }, line: { color: C.blue, pt: 0 },
    });
    s.addText('Category', { x: 1.08, y: 2.29, w: 2.5, h: 0.2, fontFace: FONT, fontSize: 12, bold: true, color: 'FFFFFF' });
    s.addText('Impact', { x: 3.95, y: 2.29, w: 7.9, h: 0.2, fontFace: FONT, fontSize: 12, bold: true, color: 'FFFFFF' });
  }

  // Slide 5: Takeaways
  {
    const s = pptx.addSlide();
    addBodyFrame(pptx, s, C, FONT, 4, 'Limitations and takeaways', 'practical constraints and design lessons');

    addCard(pptx, s, C, FONT, 0.75, 1.8, 5.95, 4.8, 'Limitations', { fill: C.softOrange });
    addBullets(s, C, FONT, 0.95, 2.35, 5.55, [
      'Self-attention complexity grows quadratically',
      'Long-context increases memory and latency',
      'Production deployment needs efficiency tuning',
    ], 15.5);

    addCard(pptx, s, C, FONT, 6.9, 1.8, 5.7, 4.8, 'Takeaways', { fill: C.softPurple });
    addBullets(s, C, FONT, 7.1, 2.35, 5.35, [
      'Transformer literacy is core LLM literacy',
      'Quality and efficiency should be co-optimized',
      'Attention design choices shape capability',
    ], 15.5);
  }

  const finalOut = outPath || path.join('output', `attention_is_all_you_need_${themeName}.pptx`);
  return pptx.writeFile({ fileName: finalOut }).then(() => finalOut);
}

if (require.main === module) {
  const args = parseArgs(process.argv.slice(2));
  buildDeck(args.theme, args.out)
    .then((fp) => console.log(`Generated: ${fp}`))
    .catch((err) => { console.error(err); process.exit(1); });
}

module.exports = { buildDeck, THEMES };
