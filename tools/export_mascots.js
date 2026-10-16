// Xuất 40 mascot từ docs/site/assets/wisp-ui.js (nguồn hình duy nhất) ra assets/mascots.json cho app Python.
// Chạy lại mỗi khi sửa hình mascot:   node tools/export_mascots.js
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'docs/site/assets/wisp-ui.js'), 'utf8');
global.localStorage = { getItem: () => null, setItem: () => {} };
global.location = { search: '' };
// eslint-disable-next-line no-eval
const { MASCOTS, CAT } = eval(src + '\n;({ MASCOTS, CAT })');

const catOf = (id) => Object.keys(CAT).find((k) => CAT[k].includes(id)) || 'fire';
const out = MASCOTS.map((m) => ({
  id: m.id, vi: m.vi, en: m.en, cat: catOf(m.id), face: m.f, eye: m.eye || null,
  sq: !!m.sq, fang: !!m.fang, body: m.body,
}));
const file = path.join(root, 'assets/mascots.json');
fs.writeFileSync(file, JSON.stringify({ version: 1, hues: [0, -30, -60, 120, 175, 145, 85, 25], mascots: out }, null, 1) + '\n');
console.log(`${file}: ${out.length} mascot`);
