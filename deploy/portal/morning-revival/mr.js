// 晨興聖言：載入選單（weeks.json）、依網址 #id 或 #id/section 載入該週片段（weeks/<id>.html），
// 升級頁首 .jump 為黏性工具列（附「精簡／展開經文」開關）、文末自動補上下週導覽列，
// 並把片段裡每個 li[data-ref] 填上網上聖經恢復本的經文全文（含佔位防跳動與單條失敗重試）。
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
  var latestWeekId = null; // weeks.json 的 latest
  var currentWeekId = null;
  var loadSeq = 0;
  var lastRoutedHash = null;
  var chapterCache = {};   // "書:章" -> Promise<Map 節 -> 經文>

  function readPref(key) {
    try { return localStorage.getItem(key); } catch (e) { return null; }
  }
  function writePref(key, val) {
    try { localStorage.setItem(key, val); } catch (e) { /* 無痕模式 */ }
  }

  // 寬螢幕：整個左欄可收合成一條窄邊，選擇存在 localStorage
  var layout = document.querySelector('.layout');
  var collapseBtn = document.getElementById('sideCollapse');
  var expandBtn = document.getElementById('sideExpand');
  var SIDE_KEY = 'mr.sideCollapsed';
  function setCollapsed(on, save) {
    layout.classList.toggle('collapsed', on);
    collapseBtn.setAttribute('aria-expanded', on ? 'false' : 'true');
    if (save) writePref(SIDE_KEY, on ? '1' : '0');
  }
  setCollapsed(readPref(SIDE_KEY) === '1', false);
  collapseBtn.addEventListener('click', function () { setCollapsed(true, true); expandBtn.focus(); });
  expandBtn.addEventListener('click', function () { setCollapsed(false, true); collapseBtn.focus(); });

  toggle.addEventListener('click', function () {
    var open = side.classList.toggle('open');
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  });

  // 精簡／展開經文模式（持久化至 localStorage）
  var COMPACT_KEY = 'mr.compactVerses';
  var compactVerses = readPref(COMPACT_KEY) === '1';

  function updateVerseToggleBtn(btn) {
    if (!btn) return;
    btn.setAttribute('aria-pressed', compactVerses ? 'true' : 'false');
    btn.classList.toggle('is-active', compactVerses);
    btn.textContent = compactVerses ? '📖 顯示經文' : '📖 精簡經文';
    btn.title = compactVerses ? '展開顯示完整經文' : '切換為精簡模式（只保留經節索引）';
  }

  function setCompactVerses(on, save) {
    compactVerses = !!on;
    contentEl.classList.toggle('verses-compact', compactVerses);
    if (save) writePref(COMPACT_KEY, compactVerses ? '1' : '0');
    updateVerseToggleBtn(contentEl.querySelector('#verseToggle'));
    if (!compactVerses) {
      loadPendingVerses(contentEl);
    }
  }
  contentEl.classList.toggle('verses-compact', compactVerses);

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function prefersReducedMotion() {
    return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
  }

  function updateHash(hashStr, replace) {
    var target = hashStr.charAt(0) === '#' ? hashStr : '#' + hashStr;
    if (location.hash === target) return;
    try {
      if (replace && history.replaceState) {
        history.replaceState(null, '', target);
      } else if (history.pushState) {
        history.pushState(null, '', target);
      } else {
        location.hash = target;
      }
      lastRoutedHash = location.hash;
    } catch (e) {
      location.hash = target;
      lastRoutedHash = location.hash;
    }
  }

  function findWeek(id) {
    if (!id) return null;
    for (var i = 0; i < weeks.length; i++) {
      if (weeks[i].id === id) return weeks[i];
    }
    return null;
  }

  function defaultWeek() {
    return findWeek(latestWeekId) || weeks[0] || null;
  }

  function findSection(root, secId) {
    if (!secId) return null;
    var node = document.getElementById(secId);
    return (node && root.contains(node)) ? node : null;
  }

  function isKnownSectionAnchor(token) {
    if (!token) return false;
    if (findSection(contentEl, token)) return true;
    return /^(overview|flow|tree|apply|plan|leader|script|outline|p\d+)$/i.test(token);
  }

  // 解析 Hash：支援 #weekId/section、#weekId、以及單純章節錨點 #apply/#overview/#script/#outline
  // 若指定的週次不存在或無效，weekId 回傳 null，呼叫端一律安全回退到 data.latest（絕不誤跳清單第一篇）
  function parseHash(rawHash) {
    var raw = (rawHash || '').replace(/^#/, '').trim();
    if (raw) {
      try { raw = decodeURIComponent(raw); } catch (e) { /* 保留原字串 */ }
    }
    if (!raw) {
      return { weekId: null, sectionId: null, isSectionOnly: false };
    }
    var slash = raw.indexOf('/');
    if (slash >= 0) {
      var wPart = raw.slice(0, slash).trim();
      var sPart = raw.slice(slash + 1).trim();
      var matched = findWeek(wPart);
      return {
        weekId: matched ? matched.id : null,
        sectionId: sPart || null,
        isSectionOnly: false
      };
    }
    var weekMatch = findWeek(raw);
    if (weekMatch) {
      return { weekId: weekMatch.id, sectionId: null, isSectionOnly: false };
    }
    if (isKnownSectionAnchor(raw)) {
      return { weekId: null, sectionId: raw, isSectionOnly: true };
    }
    return { weekId: null, sectionId: null, isSectionOnly: false };
  }

  function buildMenu(data) {
    weeks = [];
    latestWeekId = data.latest || null;
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
      if (a.dataset.id === id) {
        a.setAttribute('aria-current', 'page');
        var details = a.closest('details');
        if (details) details.open = true;
      } else {
        a.removeAttribute('aria-current');
      }
    });
  }

  function markActiveSection(secId) {
    contentEl.querySelectorAll('.mr-toolbar .jump a').forEach(function (a) {
      var match = !!secId && a.dataset.section === secId;
      a.classList.toggle('is-active', match);
      if (match) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
  }

  function syncToolbarOffset() {
    var bar = contentEl.querySelector('.mr-toolbar');
    var h = bar ? Math.ceil(bar.getBoundingClientRect().height) : 0;
    contentEl.style.setProperty('--mr-toolbar-h', (h + 20) + 'px');
  }

  function scrollToSection(secId, instant) {
    var target = findSection(contentEl, secId);
    if (!target) return false;
    syncToolbarOffset();
    markActiveSection(secId);
    target.scrollIntoView({
      behavior: (instant || prefersReducedMotion()) ? 'auto' : 'smooth',
      block: 'start'
    });
    return true;
  }

  // 把片段內的 .jump 提到 <header> 之外，組成黏性工具列＋「精簡／展開經文」開關
  function enhanceToolbar(weekId) {
    var head = contentEl.querySelector('header.week-head');
    var jump = contentEl.querySelector('nav.jump');
    var hasVerses = !!contentEl.querySelector('li[data-ref]');
    if (!jump && !hasVerses) return;

    var bar = el('div', 'mr-toolbar');
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', '章節跳轉與經文顯示');

    if (jump) {
      jump.setAttribute('aria-label', '本篇目錄');
      jump.querySelectorAll('a[href^="#"]').forEach(function (a) {
        var sec = a.getAttribute('href').slice(1);
        a.dataset.section = sec;
        a.href = '#' + weekId + '/' + sec;
      });
      bar.appendChild(jump);
    }

    if (hasVerses) {
      var btn = el('button', 'verse-toggle');
      btn.type = 'button';
      btn.id = 'verseToggle';
      updateVerseToggleBtn(btn);
      btn.addEventListener('click', function () {
        setCompactVerses(!compactVerses, true);
      });
      bar.appendChild(btn);
    }

    if (head && head.parentNode === contentEl) {
      head.insertAdjacentElement('afterend', bar);
    } else {
      contentEl.insertBefore(bar, contentEl.firstChild);
    }
    syncToolbarOffset();
  }

  // 文末補上「← 上一週｜↑ 回頂部｜下一週 →」導覽列（依 weeks.json 順序）
  function appendWeekNav(weekId) {
    var idx = -1;
    for (var i = 0; i < weeks.length; i++) {
      if (weeks[i].id === weekId) { idx = i; break; }
    }
    if (idx < 0) return;

    var prev = idx > 0 ? weeks[idx - 1] : null;
    var next = idx < weeks.length - 1 ? weeks[idx + 1] : null;

    var nav = el('nav', 'week-nav');
    nav.setAttribute('aria-label', '上下週導覽');

    if (prev) {
      var prevA = el('a', 'week-nav-btn prev');
      prevA.href = '#' + prev.id;
      prevA.appendChild(el('span', 'wn-dir', '← 上一週'));
      prevA.appendChild(el('span', 'wn-title', prev.no + '　' + prev.title));
      nav.appendChild(prevA);
    } else {
      var prevSpan = el('span', 'week-nav-btn prev is-disabled');
      prevSpan.setAttribute('aria-disabled', 'true');
      prevSpan.appendChild(el('span', 'wn-dir', '← 上一週'));
      prevSpan.appendChild(el('span', 'wn-title', '已是清單第一篇'));
      nav.appendChild(prevSpan);
    }

    var topBtn = el('button', 'week-nav-btn top', '↑ 回頂部');
    topBtn.type = 'button';
    topBtn.addEventListener('click', function () {
      scrollToTop();
      if (currentWeekId && location.hash !== '#' + currentWeekId) {
        updateHash('#' + currentWeekId, true);
      }
      markActiveSection(null);
    });
    nav.appendChild(topBtn);

    if (next) {
      var nextA = el('a', 'week-nav-btn next');
      nextA.href = '#' + next.id;
      nextA.appendChild(el('span', 'wn-dir', '下一週 →'));
      nextA.appendChild(el('span', 'wn-title', next.no + '　' + next.title));
      nav.appendChild(nextA);
    } else {
      var nextSpan = el('span', 'week-nav-btn next is-disabled');
      nextSpan.setAttribute('aria-disabled', 'true');
      nextSpan.appendChild(el('span', 'wn-dir', '下一週 →'));
      nextSpan.appendChild(el('span', 'wn-title', '已是清單最後一篇'));
      nav.appendChild(nextSpan);
    }

    var foot = contentEl.querySelector('.foot');
    if (foot && foot.parentNode === contentEl) {
      contentEl.insertBefore(nav, foot);
    } else {
      contentEl.appendChild(nav);
    }
  }

  function show(w, sectionId) {
    if (!w) return;
    var seq = ++loadSeq;
    markCurrent(w.id);
    document.title = w.no + ' ' + w.title + '｜晨興聖言';
    contentEl.innerHTML = '<p class="muted">載入中…</p>';
    side.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');

    fetch('weeks/' + w.id + '.html', { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        if (seq !== loadSeq) return;
        currentWeekId = w.id;
        contentEl.innerHTML = html;
        enhanceToolbar(w.id);
        appendWeekNav(w.id);
        fillVerses(contentEl);
        if (sectionId) {
          requestAnimationFrame(function () {
            if (seq !== loadSeq) return;
            if (!scrollToSection(sectionId, false)) {
              contentEl.focus({ preventScroll: true });
              window.scrollTo(0, 0);
            }
          });
        } else {
          markActiveSection(null);
          contentEl.focus({ preventScroll: true });
          window.scrollTo(0, 0);
        }
      })
      .catch(function () {
        if (seq !== loadSeq) return;
        currentWeekId = null;
        contentEl.innerHTML = '<p class="muted">這一週的內容載入失敗，請重新整理再試一次。</p>';
      });
  }

  function routeFromHash(rawHash) {
    var parsed = parseHash(rawHash);
    var targetWeek;
    if (parsed.weekId) {
      targetWeek = findWeek(parsed.weekId);
    } else if (parsed.isSectionOnly && currentWeekId) {
      targetWeek = findWeek(currentWeekId) || defaultWeek();
    } else {
      targetWeek = defaultWeek();
    }
    if (!targetWeek) return;

    if (targetWeek.id === currentWeekId) {
      side.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
      if (parsed.sectionId) {
        scrollToSection(parsed.sectionId, false);
      } else {
        markActiveSection(null);
        scrollToTop();
      }
      return;
    }

    show(targetWeek, parsed.sectionId);
  }

  // ---- 經文 ----
  function chapter(book, ch, force) {
    var key = book + ':' + ch;
    if (force) delete chapterCache[key];
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

  function countRefVerses(refs) {
    var total = 0;
    refs.forEach(function (ref) {
      var p = ref.split(':');
      if (p[2]) total += verseList(p[2]).length;
    });
    return total || 1;
  }

  function prepareVerseItem(li) {
    if (li.dataset.verseInit === '1') return;
    var refs = li.dataset.ref.trim().split(/\s+/);
    var first = refs[0].split(':');
    var label = li.textContent.trim();
    var estCount = countRefVerses(refs);
    li.textContent = '';

    var a = el('a', 'ref', label);
    a.href = RV + '/verse/' + first[0] + '/' + first[1];
    a.target = '_blank';
    a.rel = 'noopener';
    a.title = '在網上聖經恢復本開啟';
    li.appendChild(a);

    var text = el('span', 'verse-text', '');
    li.appendChild(text);

    li.dataset.verseInit = '1';
    li.dataset.verseState = 'pending';
    li.dataset.verseCount = String(estCount);
  }

  function loadVerseItem(li, force) {
    prepareVerseItem(li);
    var text = li.querySelector('.verse-text');
    if (!text) return;

    var refs = li.dataset.ref.trim().split(/\s+/);
    var estCount = Math.min(parseInt(li.dataset.verseCount || '1', 10) || 1, 6);
    var estLines = 2.4 + (estCount - 1) * 1.45;

    li.dataset.verseState = 'loading';
    li.classList.add('is-loading');
    li.style.minHeight = estLines.toFixed(2) + 'em';
    text.className = 'verse-text loading';
    text.textContent = '經文載入中…';

    Promise.all(refs.map(function (ref) {
      var p = ref.split(':');
      return chapter(p[0], p[1], force).then(function (m) {
        return verseList(p[2]).map(function (v) { return { v: v, t: m[v] }; });
      });
    })).then(function (groups) {
      if (!li.isConnected) return;
      li.dataset.verseState = 'loaded';
      li.classList.remove('is-loading');
      li.style.minHeight = '';
      text.className = 'verse-text loaded';
      text.textContent = '';
      text.appendChild(document.createTextNode('『'));
      var last = -1;
      groups.forEach(function (g, gi) {
        g.forEach(function (x, i) {
          if (!x.t) return;
          if ((gi > 0 && i === 0) || (last >= 0 && x.v !== last + 1)) {
            text.appendChild(document.createTextNode('……'));
          }
          text.appendChild(el('sup', null, String(x.v)));
          text.appendChild(document.createTextNode(x.t));
          last = x.v;
        });
        last = -1;
      });
      text.appendChild(document.createTextNode('』'));
    }).catch(function () {
      if (!li.isConnected) return;
      li.dataset.verseState = 'failed';
      li.classList.remove('is-loading');
      li.style.minHeight = '';
      text.className = 'verse-text failed';
      text.textContent = '（經文暫時載入不到，請點左邊出處或重試）';
      var retryBtn = el('button', 'verse-retry', '↻ 重試');
      retryBtn.type = 'button';
      retryBtn.setAttribute('aria-label', '重新載入此節經文');
      retryBtn.addEventListener('click', function () {
        loadVerseItem(li, true);
      });
      text.appendChild(retryBtn);
    });
  }

  function loadPendingVerses(root) {
    root.querySelectorAll('li[data-ref]').forEach(function (li) {
      if (li.dataset.verseState === 'pending') {
        loadVerseItem(li, false);
      }
    });
  }

  function fillVerses(root) {
    root.querySelectorAll('li[data-ref]').forEach(function (li) {
      prepareVerseItem(li);
    });
    if (!compactVerses) {
      loadPendingVerses(root);
    }
  }

  // 片段內的章節連結（含黏性 .jump 工具列）：平滑捲動並更新 Hash 為 #<weekId>/<section>
  contentEl.addEventListener('click', function (e) {
    var a = e.target.closest('a[href^="#"]');
    if (!a || a.classList.contains('week-nav-btn')) return;

    var sec = a.dataset.section;
    if (!sec) {
      var hrefVal = a.getAttribute('href').slice(1);
      var slash = hrefVal.indexOf('/');
      sec = slash >= 0 ? hrefVal.slice(slash + 1) : hrefVal;
    }

    if (sec && findSection(contentEl, sec)) {
      e.preventDefault();
      if (currentWeekId) {
        updateHash('#' + currentWeekId + '/' + sec, false);
      }
      scrollToSection(sec, false);
    }
  });

  // 窄螢幕點選已在當前的週次時，也順手收合選單
  menuEl.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-id]');
    if (!a) return;
    if (a.dataset.id === currentWeekId) {
      side.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });

  function onRouteChange() {
    var h = location.hash;
    if (h === lastRoutedHash) return;
    lastRoutedHash = h;
    routeFromHash(h);
  }
  window.addEventListener('hashchange', onRouteChange);
  window.addEventListener('popstate', onRouteChange);
  window.addEventListener('resize', syncToolbarOffset);

  fetch('weeks.json', { cache: 'no-cache' })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      buildMenu(data);
      lastRoutedHash = location.hash;
      routeFromHash(location.hash);
    })
    .catch(function () {
      menuEl.innerHTML = '<p class="muted">選單載入失敗，請重新整理。</p>';
      contentEl.innerHTML = '';
    });
})();
