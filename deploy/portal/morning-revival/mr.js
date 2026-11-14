// 晨興聖言：載入選單（weeks.json）、依網址 #id 載入該週片段（weeks/<id>.html），
// 再把片段裡每個 li[data-ref] 填上網上聖經恢復本的經文全文。
// data-ref 格式：「書卷編號:章:節」，節可寫 2-4、1,16-19；多處用空白分開，例如 "1:17:1 1:17:9-10"。
// 書卷編號同恢復本網站（創世記 1 … 啟示錄 66）。
(function () {
  'use strict';
  var RV = 'https://www.recoveryversion.com.tw';
  var menuEl = document.getElementById('menu');
  var contentEl = document.getElementById('content');
  var side = document.getElementById('side');
  var toggle = document.getElementById('menuToggle');
  var weeks = [];          // 攤平後的各週（依 weeks.json 順序）
  var chapterCache = {};   // "書:章" -> Promise<Map 節 -> 經文>

  // 寬螢幕：整個左欄可收合成一條窄邊，選擇存在 localStorage
  var layout = document.querySelector('.layout');
  var collapseBtn = document.getElementById('sideCollapse');
  var expandBtn = document.getElementById('sideExpand');
  var KEY = 'mr.sideCollapsed';
  function setCollapsed(on, save) {
    layout.classList.toggle('collapsed', on);
    collapseBtn.setAttribute('aria-expanded', on ? 'false' : 'true');
    if (save) { try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) { /* 無痕模式 */ } }
  }
  try { setCollapsed(localStorage.getItem(KEY) === '1', false); } catch (e) { setCollapsed(false, false); }
  collapseBtn.addEventListener('click', function () { setCollapsed(true, true); expandBtn.focus(); });
  expandBtn.addEventListener('click', function () { setCollapsed(false, true); collapseBtn.focus(); });

  toggle.addEventListener('click', function () {
    var open = side.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function buildMenu(data) {
    menuEl.textContent = '';
    data.trainings.forEach(function (t) {
      // 每個訓練一組，可個別收合；目前這一週所在的組會自動展開
      var group = el('details', 'group');
      group.open = true;
      group.appendChild(el('summary', null, t.title));
      var ul = el('ul');
      t.weeks.forEach(function (w) {
        weeks.push({ id: w.id, no: w.no, title: w.title, training: t.title });
        var li = el('li');
        var a = el('a');
        a.href = '#' + w.id;
        a.dataset.id = w.id;
        a.appendChild(el('span', 'no', w.no));
        a.appendChild(document.createTextNode(w.title));
        li.appendChild(a);
        ul.appendChild(li);
      });
      group.appendChild(ul);
      menuEl.appendChild(group);
    });
  }

  function markCurrent(id) {
    menuEl.querySelectorAll('a').forEach(function (a) {
      if (a.dataset.id === id) { a.setAttribute('aria-current', 'page'); a.closest('details').open = true; }
      else a.removeAttribute('aria-current');
    });
  }

  function show(id) {
    var w = weeks.filter(function (x) { return x.id === id; })[0] || weeks[0];
    if (!w) return;
    markCurrent(w.id);
    document.title = w.no + ' ' + w.title + '｜晨興聖言';
    contentEl.innerHTML = '<p class="muted">載入中…</p>';
    fetch('weeks/' + w.id + '.html', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        contentEl.innerHTML = html;
        fillVerses(contentEl);
        contentEl.focus({ preventScroll: true });
        window.scrollTo(0, 0);
      })
      .catch(function () {
        contentEl.innerHTML = '<p class="muted">這一週的內容載入失敗，請重新整理再試一次。</p>';
      });
    side.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
  }

  // ---- 經文 ----
  function chapter(book, ch) {
    var key = book + ':' + ch;
    if (!chapterCache[key]) {
      var url = RV + '/api/getVerses?VERSION=1&output[]=content&output[]=segment_code&chapter_code=' +
        book + '&section_code=' + ch + '&ORDER=id';
      chapterCache[key] = fetch(url).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (rows) {
        var m = {};
        rows.forEach(function (row) {
          var v = row.segment_code;
          m[v] = (m[v] || '') + row.content;
        });
        return m;
      });
      chapterCache[key].catch(function () { delete chapterCache[key]; });
    }
    return chapterCache[key];
  }

  function verseList(spec) {
    var out = [];
    spec.split(',').forEach(function (part) {
      var ab = part.split('-');
      var a = parseInt(ab[0], 10), b = parseInt(ab[1] || ab[0], 10);
      for (var v = a; v <= b; v++) out.push(v);
    });
    return out;
  }

  function fillVerses(root) {
    root.querySelectorAll('li[data-ref]').forEach(function (li) {
      var refs = li.dataset.ref.trim().split(/\s+/);
      var first = refs[0].split(':');
      var label = li.textContent.trim();
      li.textContent = '';
      var a = el('a', 'ref', label);
      a.href = RV + '/verse/' + first[0] + '/' + first[1];
      a.target = '_blank';
      a.rel = 'noopener';
      a.title = '在網上聖經恢復本開啟';
      li.appendChild(a);
      var text = el('span', 'verse-text loading', '經文載入中…');
      li.appendChild(text);
      Promise.all(refs.map(function (ref) {
        var p = ref.split(':');
        return chapter(p[0], p[1]).then(function (m) {
          return verseList(p[2]).map(function (v) { return { v: v, t: m[v] }; });
        });
      })).then(function (groups) {
        text.className = 'verse-text';
        text.textContent = '';
        text.appendChild(document.createTextNode('『'));
        var last = -1;
        groups.forEach(function (g, gi) {
          g.forEach(function (x, i) {
            if (!x.t) return;
            if ((gi > 0 && i === 0) || (last >= 0 && x.v !== last + 1)) text.appendChild(document.createTextNode('……'));
            text.appendChild(el('sup', null, String(x.v)));
            text.appendChild(document.createTextNode(x.t));
            last = x.v;
          });
          last = -1;
        });
        text.appendChild(document.createTextNode('』'));
      }).catch(function () {
        text.className = 'verse-text failed';
        text.textContent = '（經文暫時載入不到，請點左邊的出處到恢復本網站看）';
      });
    });
  }

  // 片段內的錨點（例如「鳥瞰」「生活應用」）只捲動，不當成換週
  contentEl.addEventListener('click', function (e) {
    var a = e.target.closest('a[href^="#"]');
    if (!a) return;
    var target = contentEl.querySelector('[id="' + a.getAttribute('href').slice(1) + '"]');
    if (target) { e.preventDefault(); target.scrollIntoView(); }
  });

  window.addEventListener('hashchange', function () { show(location.hash.slice(1)); });

  fetch('weeks.json', { cache: 'no-cache' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      buildMenu(data);
      var id = location.hash.slice(1) || data.latest || (weeks[0] && weeks[0].id);
      show(id);
    })
    .catch(function () {
      menuEl.innerHTML = '<p class="muted">選單載入失敗，請重新整理。</p>';
      contentEl.innerHTML = '';
    });
})();
