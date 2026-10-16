/* Nội dung landing dùng chung cho mọi mẫu (docs/site/landing/*.html): chữ EN / VI, link, lệnh cài, khối dùng lại.
   Cần wisp-ui.js nạp trước (ic, mascot, island, T, L, LANG, ls…). */
const REPO = 'https://github.com/hakienit/pet-tracker';
const WIN_ZIP = REPO + '/releases/latest/download/wisp-win-x64.zip';
const MAC_DMG = REPO + '/releases/latest/download/wisp-macos-universal2.dmg';
const WIN_CMD = 'irm https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.ps1 | iex';
const MAC_CMD = 'curl -fsSL https://raw.githubusercontent.com/hakienit/pet-tracker/main/install.sh | bash';

const LC = {
  en: {
    links: ['Features', 'Customize', 'Mascots', 'Install'], github: 'GitHub',
    eyebrow: 'For Claude Code · Windows & macOS',
    h1: 'Know the moment your agents need you.',
    h1b: 'A small flame that watches your Claude Code agents.',
    sub: 'Wisp floats at the top of your screen: quota with a forecast, every running session, and a gentle nudge when one is waiting for you.',
    dlWin: 'Download for Windows', dlMac: 'macOS (beta)', orCmd: 'or install with one command', copy: 'Copy', copied: 'Copied',
    free: 'Free and open source · ~50 MB RAM · no account',
    demo: ['All quiet. Wisp sleeps at the top of your screen.', 'An agent is working: the border runs blue.',
      'It needs your approval. Fire, a sound, one click to its window.', 'Done. A short note, then back to sleep.'],
    pause: 'Pause', play: 'Play',
    fH: 'Everything at a glance', fL: 'Read straight from Claude Code on your machine. Nothing to configure.',
    feats: [
      ['bell', 'wait', 'Knows when you are needed', 'Permission prompts, questions and finished turns arrive with a sound, through Claude Code hooks.'],
      ['trend', 'warn', 'Quota with a forecast', '5-hour and 7-day usage, reset times, and when you will run out at this pace.'],
      ['run', 'run', 'Every session in one place', 'CLI, IDE and desktop, with model, effort, context, branch and the tool running now.'],
      ['open', 'done', 'One click back', 'Bring the right terminal, IDE or Claude window to the front.'],
      ['trash', 'danger', 'Clean up safely', 'Handoff, close, delete or remove merged worktrees, with a clear confirmation.'],
      ['gear', 'upd', 'Make it yours', 'Island or bubble, 6 signal styles, 40 mascots, light or dark, English or Vietnamese.'],
    ],
    cH: 'Pick your bubble', cL: 'A signal ring or a mascot that walks, jumps and dances with your sessions. Same options as in Settings.',
    mH: '40 mascots, five moods', mL: 'Idle, running, needs you, done and quota low. Click one to try it.',
    pH: 'The panel', pL: 'Grouped by what each session needs from you. Context, model and effort on every card.',
    inH: 'Install in one line', inL: 'Downloads the latest release, checks its SHA256 and starts Wisp. Run it again to update. Requires Claude Code, signed in.',
    win: 'Windows 10/11 · PowerShell', mac: 'macOS · Terminal (beta)', manual: 'Manual download',
    prH: 'Private by design', prL: 'Wisp reads Claude Code data on your machine only. Your login token goes only to api.anthropic.com for quota. Hooks post to 127.0.0.1.',
    stats: [['40', 'mascots'], ['6', 'signal styles'], ['2', 'languages'], ['0', 'accounts needed']],
    bento: { island: 'Island', panel: 'Panel', bubble: 'Bubble', mascot: 'Mascot bubble', toast: 'Notifications', quota: 'Forecast',
      tokens: 'Tokens on this device', settings: 'Settings', langs: 'English · Tiếng Việt', themes: 'Light · Dark' },
    steps: [['01', 'Install', 'One command, signed release.'], ['02', 'Enable hooks', 'One click, with a backup of your settings.'],
      ['03', 'Get back to work', 'Wisp tells you when to look.']],
    parade: 'Meet the crew', paradeL: 'Pick a mascot. It lives in your panel and, if you like, becomes the bubble.',
    foot: 'Wisp is a personal project, not an Anthropic product. Quota uses the unofficial endpoint behind Claude Code\'s /usage and may change.',
    guide: 'Guide', changelog: 'Changelog', spec: 'Design spec', theme: ['Dark', 'Light'],
  },
  vi: {
    links: ['Tính năng', 'Tuỳ biến', 'Mascot', 'Cài đặt'], github: 'GitHub',
    eyebrow: 'Cho Claude Code · Windows & macOS',
    h1: 'Biết ngay lúc agent cần bạn.',
    h1b: 'Đốm lửa nhỏ canh các agent Claude Code của bạn.',
    sub: 'Wisp nổi ở mép trên màn hình: quota có dự báo, mọi session đang chạy, và nhắc nhẹ khi có session đang chờ bạn.',
    dlWin: 'Tải cho Windows', dlMac: 'macOS (thử nghiệm)', orCmd: 'hoặc cài bằng một lệnh', copy: 'Sao chép', copied: 'Đã chép',
    free: 'Miễn phí, mã nguồn mở · ~50 MB RAM · không cần tài khoản',
    demo: ['Yên ắng. Wisp ngủ ở mép trên màn hình.', 'Agent đang làm việc: viền chạy màu lam.',
      'Cần bạn duyệt. Viền lửa, âm báo, một click về đúng cửa sổ.', 'Xong. Một thông báo ngắn rồi Wisp ngủ tiếp.'],
    pause: 'Dừng', play: 'Chạy',
    fH: 'Nhìn một lần là biết', fL: 'Đọc thẳng từ Claude Code trên máy bạn. Không cần cấu hình.',
    feats: [
      ['bell', 'wait', 'Biết khi nào cần bạn', 'Yêu cầu duyệt quyền, câu hỏi và lượt vừa xong báo kèm âm thanh, qua hooks của Claude Code.'],
      ['trend', 'warn', 'Quota có dự báo', 'Mức dùng 5 giờ và 7 ngày, giờ reset, và lúc nào sẽ hết theo tốc độ này.'],
      ['run', 'run', 'Mọi session một chỗ', 'CLI, IDE và desktop, kèm model, effort, context, branch và tool đang chạy.'],
      ['open', 'done', 'Một click về đúng cửa sổ', 'Đưa terminal, IDE hoặc Claude desktop của session lên trước.'],
      ['trash', 'danger', 'Dọn dẹp an toàn', 'Handoff, đóng, xoá session hoặc worktree đã merge, có xác nhận rõ ràng.'],
      ['gear', 'upd', 'Theo ý bạn', 'Island hoặc bóng nổi, 6 kiểu tín hiệu, 40 mascot, sáng hoặc tối, tiếng Việt hoặc tiếng Anh.'],
    ],
    cH: 'Chọn bóng nổi', cL: 'Vòng tín hiệu hoặc mascot biết đi, nhảy và múa theo session. Giống hệt trong Cài đặt.',
    mH: '40 mascot, năm biểu cảm', mL: 'Rảnh, đang chạy, cần bạn, xong và gần hết quota. Bấm một mascot để thử.',
    pH: 'Panel', pL: 'Xếp theo việc mỗi session cần từ bạn. Card nào cũng có context, model và effort.',
    inH: 'Cài bằng một dòng', inL: 'Tải bản mới nhất, kiểm SHA256 rồi mở Wisp. Chạy lại để cập nhật. Cần Claude Code đã đăng nhập.',
    win: 'Windows 10/11 · PowerShell', mac: 'macOS · Terminal (thử nghiệm)', manual: 'Tải tay',
    prH: 'Riêng tư từ đầu', prL: 'Wisp chỉ đọc dữ liệu Claude Code trên máy bạn. Token chỉ gửi tới api.anthropic.com để lấy quota. Hooks chỉ gửi tới 127.0.0.1.',
    stats: [['40', 'mascot'], ['6', 'kiểu tín hiệu'], ['2', 'ngôn ngữ'], ['0', 'tài khoản cần tạo']],
    bento: { island: 'Island', panel: 'Panel', bubble: 'Bóng nổi', mascot: 'Bóng mascot', toast: 'Thông báo', quota: 'Dự báo',
      tokens: 'Token trên máy này', settings: 'Cài đặt', langs: 'Tiếng Việt · English', themes: 'Sáng · Tối' },
    steps: [['01', 'Cài đặt', 'Một lệnh, bản phát hành có chữ ký.'], ['02', 'Bật hooks', 'Một click, có backup settings của bạn.'],
      ['03', 'Quay lại làm việc', 'Wisp báo khi nào cần nhìn.']],
    parade: 'Làm quen cả đội', paradeL: 'Chọn một mascot. Nó sống ở đầu panel và, nếu thích, làm luôn bóng nổi.',
    foot: 'Wisp là dự án cá nhân, không phải sản phẩm của Anthropic. Quota dùng endpoint không chính thức của lệnh /usage trong Claude Code, có thể đổi.',
    guide: 'Hướng dẫn', changelog: 'Lịch sử thay đổi', spec: 'Spec thiết kế', theme: ['Tối', 'Sáng'],
  },
};
const C = () => LC[LANG];
{
  const q = new URLSearchParams(location.search);
  if (!ls('wisp-lang') && !q.get('lang')) LANG = (navigator.language || 'en').toLowerCase().startsWith('vi') ? 'vi' : 'en';
}
const escH = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
// tô màu lệnh giống code block trên GitHub: PowerShell tô "//host/" và từng "/" màu lam, "|" màu đỏ; bash chỉ tô "|"
function cmdHL(cmd) {
  const e = escH(cmd).replace(/ \| /g, ' <span class="p">|</span> ');
  if (!cmd.startsWith('irm ')) return e;
  return e.replace(/https:(\/\/[^/\s]+\/)([^\s<]+)/, (m, host, path) => 'https:<span class="u">' + host + '</span>' + path.replace(/\//g, '<span class="u">/</span>'));
}
// một dòng, không xuống dòng, không thanh cuộn (vẫn cuộn ngang được khi màn hình hẹp), icon copy bên phải; khối co theo độ dài lệnh
const cmdBlock = (cmd) => `<div class="ghcmd"><code>${cmdHL(cmd)}</code>${copyBtn(cmd)}</div>`;
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

// ?shot=<khối>: chỉ hiện một khối [data-shot] trên nền trong suốt, góc bo (tools/shoot_landing.py chụp làm ảnh README).
// ?stage=<trạng thái>: dừng demo ở một trạng thái (chụp từng khung cho ảnh động).
const QS = new URLSearchParams(location.search);
const SHOT = QS.get('shot');
const FIXED_STAGE = QS.get('stage');

// chu trình demo: rảnh -> chạy -> cần bạn -> xong
const DEMO = ['idle', 'run', 'wait', 'done'];
function demoLoop(onStep, ms = 2800) {
  let i = FIXED_STAGE ? Math.max(0, DEMO.indexOf(FIXED_STAGE)) : REDUCED ? 2 : 0, timer = null;
  const go = () => { onStep(DEMO[i], i); i = (i + 1) % DEMO.length; };
  const api = {
    playing: !REDUCED && !FIXED_STAGE,
    toggle() { this.playing = !this.playing; if (this.playing) start(); else clearInterval(timer); return this.playing; },
  };
  function start() { clearInterval(timer); timer = setInterval(go, ms); }
  go();
  if (api.playing) start();
  return api;
}

// nút sao chép dạng icon (giống nút copy của GitHub): chép xong đổi thành dấu ✓ 1,5 giây
const ICON_COPY = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5.5A1.5 1.5 0 0 0 14.5 4h-9A1.5 1.5 0 0 0 4 5.5v9A1.5 1.5 0 0 0 5.5 16H8"/></svg>';
const ICON_OK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
function copyBtn(cmd, cls = '') {
  return `<button class="cp ${cls}" data-copy="${cmd === WIN_CMD ? 'win' : 'mac'}" aria-label="${C().copy}" title="${C().copy}">${ICON_COPY}</button>`;
}
function wireCopy(root = document) {
  root.addEventListener('click', (e) => {
    const b = e.target.closest('[data-copy]');
    if (!b) return;
    e.stopPropagation();
    const txt = b.dataset.copy === 'win' ? WIN_CMD : MAC_CMD;
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => {
      b.innerHTML = ICON_OK;
      b.classList.add('ok');
      b.setAttribute('aria-label', C().copied);
      setTimeout(() => { b.innerHTML = ICON_COPY; b.classList.remove('ok'); b.setAttribute('aria-label', C().copy); }, 1500);
    }, () => {});
  }, true);
}

// CSS chung cho mọi mẫu: khối lệnh kiểu GitHub, nút copy dạng icon, chế độ chụp
document.head.insertAdjacentHTML('beforeend', `<style>
button.cp{display:inline-grid;place-items:center;width:34px;height:34px;min-height:34px;flex:none;cursor:pointer;line-height:0}
button.cp.ok{color:#3fb950!important}
.ghcmd{display:flex;align-items:center;gap:12px;box-sizing:border-box;max-width:100%;min-width:0;margin:0;padding:12px 10px 12px 16px;border-radius:6px;
  background:var(--cmd-bg,#151b23);border:1px solid var(--cmd-line,#3d444d66);color:var(--cmd-fg,#f0f6fc);text-align:left;
  font:13.6px/1.45 ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace}
.ghcmd code{all:unset;flex:1;min-width:0;white-space:pre;overflow-x:auto;scrollbar-width:none;font:inherit;color:inherit}
.ghcmd code::-webkit-scrollbar{display:none}
.ghcmd .u{color:var(--cmd-url,#79c0ff)}.ghcmd .p{color:var(--cmd-pipe,#ff7b72)}
.ghcmd .cp{all:unset;box-sizing:border-box;display:grid;place-items:center;flex:none;width:32px;height:32px;border-radius:6px;border:1px solid transparent;
  color:var(--cmd-mut,#9198a1);cursor:pointer;line-height:0}
.ghcmd .cp:hover{border-color:var(--cmd-line,#3d444d);background:var(--cmd-hover,#262c36);color:var(--cmd-fg,#f0f6fc)}
.ghcmd .cp:focus-visible{outline:2px solid #4493f8;outline-offset:0}
.ghcmd .cp.ok{color:#3fb950}
.cmdbox{margin-top:16px;width:fit-content;max-width:100%}.cmdlbl{margin-top:16px;font-size:13px;color:var(--mut)}.cmdlbl+.cmdbox{margin-top:8px}
.cmdbox.wide,.hero>.wide{grid-column:1/-1;justify-self:start;margin-top:0}.wide .term-cmd{width:fit-content;max-width:100%}
.inst .ghcmd{margin:0 0 12px}
.play{align-items:stretch!important}
.bigb{flex-wrap:wrap;align-content:center;justify-content:center;column-gap:0!important;row-gap:34px!important}
.bigb .cell{flex:0 0 42%}.bigb:has(.cell:nth-child(5)) .cell{flex-basis:31%}
.inst{grid-template-columns:minmax(0,1fr)!important}
.term-cmd pre{white-space:pre!important;scrollbar-width:none}.term-cmd pre::-webkit-scrollbar{display:none}
.term-cmd .u{color:#79c0ff}.term-cmd .p{color:#ff7b72}
body.shot{margin:0;padding:0;background:transparent!important;background-image:none!important}
body.shot::before{display:none!important}
.shot-on{width:1000px!important;max-width:none!important;margin:0!important;border-radius:28px;overflow:hidden;background-color:var(--bg);padding:40px 44px!important;border:0!important}
</style>`);
let SHOT_DONE = false;
function applyShot() {
  if (!SHOT || SHOT_DONE) return;
  const target = document.querySelector(`[data-shot="${SHOT}"]`);
  if (!target) return;
  SHOT_DONE = true;
  document.body.classList.add('shot');
  target.classList.add('shot-on');
  document.body.replaceChildren(target);  // chỉ giữ khối cần chụp
  // tools/shoot_landing.py đọc chiều cao qua title để đặt cỡ cửa sổ chụp
  const measure = () => { document.title = 'H=' + Math.ceil(target.getBoundingClientRect().height); };
  measure();
  requestAnimationFrame(() => requestAnimationFrame(measure));
  if (document.fonts) document.fonts.ready.then(measure);
}
const langSwitch = (cls = '') => `<div class="${cls}" role="group" aria-label="Language">${['en', 'vi'].map((l) => `<button data-l="${l}" aria-pressed="${LANG === l}">${l.toUpperCase()}</button>`).join('')}</div>`;
const SITE_BASE = /\/landing\/[^/]*$/.test(location.pathname) ? '../' : '';  // mẫu trong landing/ lùi một cấp
const footLinks = () => `<a href="${REPO}/blob/main/docs/GUIDE.md">${C().guide}</a> · <a href="${REPO}/blob/main/CHANGELOG.md">${C().changelog}</a> · <a href="${SITE_BASE}design.html">${C().spec}</a> · <a href="${REPO}">GitHub</a>`;
