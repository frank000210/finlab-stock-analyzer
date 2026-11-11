// 入口頁與知識分享共用的色彩主題選單（和主站同一組 6 個主題）。
// 放在 <head> 內同步載入：先把 data-theme 設好再繪製畫面，不會閃一下預設色。
// 選擇存在 localStorage（入口頁與 /share/ 同一個網域，共用；主站與知識庫是別的網域，各自記）。
(function () {
  var KEY = 'finlab.colorTheme.v1';
  var THEMES = [
    { id: 'notebook', name: '手帳米白', hint: '預設・淺色', sw: ['#FFFDF7', '#2B2B33', '#12706C'] },
    { id: 'dark', name: '夜間深色', hint: '深色', sw: ['#0D1322', '#E8EDF5', '#4FD1C5'] },
    { id: 'solarized', name: 'Solarized', hint: '淺色・低對比', sw: ['#FDF6E3', '#073642', '#146A64'] },
    { id: 'nord', name: 'Nord', hint: '深色・冷灰藍', sw: ['#2E3440', '#ECEFF4', '#9CC7C6'] },
    { id: 'dracula', name: 'Dracula', hint: '深色・紫粉', sw: ['#282A36', '#F8F8F2', '#BD93F9'] },
    { id: 'gruvbox', name: 'Gruvbox', hint: '深色・復古暖棕', sw: ['#282828', '#EBDBB2', '#8EC07C'] }
  ];
  var root = document.documentElement;

  function valid(id) { return THEMES.some(function (t) { return t.id === id; }); }
  function read() { try { return localStorage.getItem(KEY); } catch (e) { return null; } }
  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* 無痕模式：這次有效就好 */ } }
  function osDefault() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'notebook';
  }
  function current() { var id = read(); return valid(id) ? id : osDefault(); }
  function apply(id) { root.setAttribute('data-theme', id); }
  function meta(id) { return THEMES.filter(function (t) { return t.id === id; })[0]; }

  apply(current());

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function swatch(colors, cls) {
    var s = el('span', cls);
    s.setAttribute('aria-hidden', 'true');
    colors.forEach(function (c) { var i = el('i'); i.style.background = c; s.appendChild(i); });
    return s;
  }

  function build() {
    var bar = el('div', 'theme-bar');
    var box = el('div', 'tp');
    var btn = el('button', 'tp-btn');
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', '選擇色彩主題');
    btn.setAttribute('data-testid', 'theme-picker-btn');
    var menu = el('div', 'tp-menu');
    menu.setAttribute('role', 'listbox');
    menu.setAttribute('aria-label', '色彩主題');
    menu.hidden = true;
    menu.appendChild(el('p', 'tp-title', '色彩主題'));

    function paintButton() {
      var m = meta(current());
      btn.textContent = '';
      btn.appendChild(swatch(m.sw, 'tp-dots'));
      btn.appendChild(el('span', 'tp-name', m.name));
      btn.appendChild(el('span', 'tp-caret', '▾'));
      Array.prototype.forEach.call(menu.querySelectorAll('.tp-item'), function (b) {
        var on = b.getAttribute('data-theme-id') === current();
        b.setAttribute('aria-selected', on ? 'true' : 'false');
        b.querySelector('.tp-ck').textContent = on ? '✓' : '';
      });
    }
    function close() { menu.hidden = true; btn.setAttribute('aria-expanded', 'false'); }
    function open() { menu.hidden = false; btn.setAttribute('aria-expanded', 'true'); }

    THEMES.forEach(function (t) {
      var b = el('button', 'tp-item');
      b.type = 'button';
      b.setAttribute('role', 'option');
      b.setAttribute('data-theme-id', t.id);
      b.appendChild(swatch(t.sw, 'tp-sw'));
      var lb = el('span', 'tp-lb');
      lb.appendChild(el('strong', null, t.name));
      lb.appendChild(el('small', null, t.hint));
      b.appendChild(lb);
      b.appendChild(el('span', 'tp-ck'));
      b.addEventListener('click', function () { write(t.id); apply(t.id); paintButton(); close(); btn.focus(); });
      menu.appendChild(b);
    });

    btn.addEventListener('click', function () { if (menu.hidden) open(); else close(); });
    document.addEventListener('click', function (e) { if (!menu.hidden && !box.contains(e.target)) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !menu.hidden) { close(); btn.focus(); } });

    box.appendChild(btn);
    box.appendChild(menu);
    bar.appendChild(box);
    document.body.insertBefore(bar, document.body.firstChild);
    paintButton();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
