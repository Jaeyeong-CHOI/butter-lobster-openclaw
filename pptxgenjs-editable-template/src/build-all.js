const path = require('path');
const { buildDeck, THEMES } = require('./build');

(async () => {
  for (const themeName of Object.keys(THEMES)) {
    const out = path.join('output', `attention_is_all_you_need_${themeName}.pptx`);
    await buildDeck(themeName, out);
    console.log('Generated:', out);
  }
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
