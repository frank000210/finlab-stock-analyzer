// Frank Portal Agent Dashboard Logic (Local MongoDB + SSE Real-Time Sync + Dual Style)
(function () {
  var LS_STYLE = 'frank.agentDash.style.v2';
  var LS_PIXEL_THEME = 'frank.agentDash.pixelTheme.v1';
  var LS_NB_THEME = 'frank.agentDash.nbTheme.v1';
  var LS_NOTIFY = 'frank.agentDash.browserNotify.v1';
  var LS_WRITE_TOKEN = 'frank.agentDash.writeToken.v1';

  var isHttp = (location.protocol === 'http:' || location.protocol === 'https:');

  var state = {
    data: window.AGENT_DASHBOARD_DATA || null,
    style: localStorage.getItem(LS_STYLE) || 'lab',
    pixelTheme: localStorage.getItem(LS_PIXEL_THEME) || 'dark',
    nbTheme: localStorage.getItem(LS_NB_THEME) || 'paper',
    browserNotify: localStorage.getItem(LS_NOTIFY) === '1',
    writeToken: localStorage.getItem(LS_WRITE_TOKEN) || '',
    writeProtected: false,
    writeUnlocked: true,
    storageLabel: 'local',
    labActiveOnly: false,
    apiConnected: false,
    sseConnected: false,
    lastRevision: -1,
    selectedAgentId: null,
    quickFilter: 'all',
    keyword: '',
    expandedTaskIds: {}
  };

  var eventSource = null;

  function esc(str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function avatarHtml(spriteKey) {
    if (state.style === 'notebook') {
      return window.NOTEBOOK_SPRITES ? window.NOTEBOOK_SPRITES.get(spriteKey) : '';
    }
    return window.PIXEL_SPRITES ? window.PIXEL_SPRITES.get(spriteKey) : '';
  }

  function bubbleIcon(status) {
    if (state.style === 'notebook') {
      if (status === 'working') return '✏️';
      if (status === 'blocked') return '❗';
      if (status === 'done') return '✅';
      return '☕';
    }
    if (status === 'working') return '>_';
    if (status === 'blocked') return '!';
    if (status === 'done') return '✓';
    return '☕';
  }

  function setConnStatus(mode, text) {
    var pill = document.getElementById('conn-pill');
    var label = document.getElementById('conn-label');
    if (!pill || !label) return;
    pill.classList.remove('online', 'polling', 'offline');
    pill.classList.add(mode);
    label.textContent = text;
    var addBtn = document.getElementById('btn-add-task');
    if (addBtn) addBtn.style.display = state.apiConnected ? 'inline-block' : 'none';
  }

  function showToast(title, message, variant) {
    var stack = document.getElementById('toast-stack');
    if (!stack) return;
    var el = document.createElement('div');
    el.className = 'toast-item' + (variant ? ' kind-' + variant : '');
    el.innerHTML =
      '<div class="toast-title">' + esc(title) + '</div>' +
      (message ? '<div class="toast-msg">' + esc(message) + '</div>' : '');
    stack.appendChild(el);
    setTimeout(function () {
      el.style.opacity = '0';
      el.style.transition = 'opacity 0.25s';
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 260);
    }, 5000);
  }

  function fireBrowserNotification(title, message) {
    if (!state.browserNotify) return;
    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    try {
      new Notification(title, { body: message || '' });
    } catch (e) {}
  }

  function updateNotifyButton() {
    var btn = document.getElementById('notify-btn');
    if (!btn) return;
    if (typeof Notification === 'undefined') {
      btn.style.display = 'none';
      return;
    }
    if (state.browserNotify && Notification.permission === 'granted') {
      btn.textContent = '🔔 桌面通知：開';
    } else {
      btn.textContent = '🔕 開啟桌面通知';
    }
  }

  function applyTheme() {
    var html = document.documentElement;
    html.setAttribute('data-style', state.style);
    html.setAttribute('data-theme', state.style === 'notebook' ? state.nbTheme : state.pixelTheme);
    var btnLab = document.getElementById('btn-style-lab');
    if (btnLab) btnLab.classList.toggle('active', state.style === 'lab');
    document.getElementById('btn-style-pixel').classList.toggle('active', state.style === 'pixel');
    document.getElementById('btn-style-notebook').classList.toggle('active', state.style === 'notebook');
    document.getElementById('pixel-theme-btn').style.display = state.style === 'notebook' ? 'none' : 'inline-block';
    document.getElementById('pixel-theme-btn').textContent = state.pixelTheme === 'dark' ? '☀️ 淺色模式' : '🌙 深色模式';
    var nbSel = document.getElementById('nb-theme-select');
    nbSel.style.display = state.style === 'notebook' ? 'inline-block' : 'none';
    nbSel.value = state.nbTheme;
    updateNotifyButton();
  }

  function countAgentTasks(agentId) {
    var c = { todo: 0, in_progress: 0, blocked: 0, done: 0 };
    (state.data.tasks || []).forEach(function (t) {
      if (t.agentId === agentId && c[t.status] !== undefined) c[t.status]++;
    });
    return c;
  }

  function pickFeaturedTask(agentId) {
    var prioRank = { P0: 0, P1: 1, P2: 2 };
    var mine = (state.data.tasks || []).filter(function (t) { return t.agentId === agentId; });
    if (!mine.length) return null;
    function stageRank(t) {
      if (t.status === 'blocked') return 0;
      if (t.status === 'in_progress') return 1;
      if (t.status === 'todo' && t.dispatch === 'queued') return 2;
      if (t.status === 'todo') return 3;
      return 4; // done
    }
    mine.sort(function (a, b) {
      var sr = stageRank(a) - stageRank(b);
      if (sr !== 0) return sr;
      if (a.status !== 'done') {
        var pr = (prioRank[a.priority] != null ? prioRank[a.priority] : 9) - (prioRank[b.priority] != null ? prioRank[b.priority] : 9);
        if (pr !== 0) return pr;
      }
      return String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''));
    });
    return mine[0];
  }

  function taskBubbleMeta(task, fallbackAgent) {
    if (!task) {
      var st = (fallbackAgent && fallbackAgent.status) || 'idle';
      return {
        cls: st,
        icon: bubbleIcon(st),
        label: st,
        id: '—',
        title: (fallbackAgent && fallbackAgent.statusText) || '待命中'
      };
    }
    if (task.status === 'blocked') {
      return { cls: 'blocked', icon: '❗', label: '待核准／卡關', id: task.id, title: task.title };
    }
    if (task.status === 'in_progress') {
      if (task.approval === 'approved' && task.dispatch === 'queued') {
        return { cls: 'working', icon: '✅', label: '已核准待執行', id: task.id, title: task.title };
      }
      return { cls: 'working', icon: '⚡', label: '進行中', id: task.id, title: task.title };
    }
    if (task.status === 'todo') {
      if (task.dispatch === 'queued') {
        return { cls: 'queued', icon: '🚀', label: '待工頭派工', id: task.id, title: task.title };
      }
      return { cls: 'idle', icon: '📌', label: '待辦', id: task.id, title: task.title };
    }
    return { cls: 'done', icon: '✅', label: '已完成', id: task.id, title: task.title };
  }

  function renderDesk(agent, isForeman) {
    var counts = countAgentTasks(agent.id);
    var selClass = state.selectedAgentId === agent.id ? ' selected' : '';
    var fClass = isForeman ? ' foreman-desk' : '';
    var st = agent.status || 'idle';
    var doingTotal = counts.in_progress + counts.blocked;
    var featured = pickFeaturedTask(agent.id);
    var bm = taskBubbleMeta(featured, agent);
    var fullTip = '[' + bm.label + '] ' + bm.id + ' ' + bm.title;
    return (
      '<div class="desk-unit status-' + esc(st) + selClass + fClass + '" data-agent-id="' + esc(agent.id) + '" title="' + esc(fullTip) + '（點擊篩選「' + esc(agent.name) + '」的工作）">' +
        '<div class="speech-bubble ' + esc(bm.cls) + '" title="' + esc(fullTip) + '">' +
          '<span class="sb-icon" aria-label="' + esc(bm.label) + '">' + esc(bm.icon) + '</span>' +
          '<span class="sb-id">' + esc(bm.id) + '</span>' +
          '<span class="sb-title">' + esc(bm.title) + '</span>' +
        '</div>' +
        '<div class="avatar-stage">' + avatarHtml(agent.spriteKey) + '</div>' +
        '<div class="desk-furniture"><div class="monitor-led"></div><div class="monitor-led"></div></div>' +
        '<div class="nameplate">' + esc(agent.name) + '</div>' +
        '<div class="role-sub">' + esc(agent.roleTitle) + '</div>' +
        '<div class="mini-counts">' +
          '<span class="mc' + (doingTotal ? ' has-doing' : '') + '">進 ' + doingTotal + '</span>' +
          '<span class="mc' + (counts.todo ? ' has-todo' : '') + '">待 ' + counts.todo + '</span>' +
          '<span class="mc">完 ' + counts.done + '</span>' +
        '</div>' +
      '</div>'
    );
  }

  function classicAgentPlace(agent) {
    if (agent.zone === 'command') return 'foreman';
    var counts = countAgentTasks(agent.id);
    var hasQueued = (state.data.tasks || []).some(function (t) {
      return t.agentId === agent.id && t.status === 'todo' && t.dispatch === 'queued';
    });
    if (counts.in_progress > 0 || agent.status === 'working') return 'desk';
    if (counts.blocked > 0 || agent.status === 'blocked' || hasQueued) return 'foreman_meet';
    return 'lounge';
  }

  function renderStage() {
    if (state.style === 'lab' && window.SIMULAB_STAGE) {
      window.SIMULAB_STAGE.start(state.data, state.selectedAgentId);
      window.SIMULAB_STAGE.updateData(state.data, state.selectedAgentId);
      return;
    }
    if (window.SIMULAB_STAGE) window.SIMULAB_STAGE.stop();

    var agents = state.data.agents || [];
    var foreman = agents.find(function (a) { return a.zone === 'command'; });
    var meetAgents = [];
    var loungeAgents = [];
    var portalActive = [];
    var finlabActive = [];

    agents.forEach(function (a) {
      if (a.zone === 'command') return;
      var place = classicAgentPlace(a);
      if (place === 'foreman_meet') meetAgents.push(a);
      else if (place === 'lounge') loungeAgents.push(a);
      else if (a.zone === 'portal') portalActive.push(a);
      else if (a.zone === 'finlab') finlabActive.push(a);
    });

    document.getElementById('foreman-slot').innerHTML = foreman ? renderDesk(foreman, true) : '';
    var meetBox = document.getElementById('foreman-meet-box');
    var meetEl = document.getElementById('foreman-meet-desks');
    if (meetBox && meetEl) {
      meetBox.style.display = meetAgents.length ? 'block' : 'none';
      meetEl.innerHTML = meetAgents.map(function (a) { return renderDesk(a, false); }).join('');
    }
    document.getElementById('portal-desks').innerHTML = portalActive.length
      ? portalActive.map(function (a) { return renderDesk(a, false); }).join('')
      : '<div class="zone-empty">☕ 成員目前皆在休息區待命</div>';
    document.getElementById('finlab-desks').innerHTML = finlabActive.length
      ? finlabActive.map(function (a) { return renderDesk(a, false); }).join('')
      : '<div class="zone-empty">☕ 成員目前皆在休息區待命</div>';
    var loungeEl = document.getElementById('lounge-desks');
    if (loungeEl) {
      loungeEl.innerHTML = loungeAgents.length
        ? loungeAgents.map(function (a) { return renderDesk(a, false); }).join('')
        : '<div class="zone-empty">⚡ 全員上工中！休息區目前空無一人</div>';
    }

    document.querySelectorAll('.desk-unit').forEach(function (el) {
      el.addEventListener('click', function () {
        var id = el.getAttribute('data-agent-id');
        state.selectedAgentId = (state.selectedAgentId === id) ? null : id;
        renderAll();
      });
    });
  }

  function renderInspector() {
    var box = document.getElementById('inspector-strip');
    if (!state.selectedAgentId) {
      box.classList.remove('visible');
      return;
    }
    var agent = (state.data.agents || []).find(function (a) { return a.id === state.selectedAgentId; });
    if (!agent) { box.classList.remove('visible'); return; }
    var c = countAgentTasks(agent.id);
    box.classList.add('visible');

    var editHtml = '';
    if (state.apiConnected) {
      editHtml =
        '<div class="inspector-edit">' +
          '<select id="insp-agent-status">' +
            '<option value="working"' + (agent.status === 'working' ? ' selected' : '') + '>⚡ 作業中</option>' +
            '<option value="idle"' + (agent.status === 'idle' ? ' selected' : '') + '>☕ 待機</option>' +
            '<option value="blocked"' + (agent.status === 'blocked' ? ' selected' : '') + '>❗ 卡關／待核准</option>' +
            '<option value="done"' + (agent.status === 'done' ? ' selected' : '') + '>✅ 已完成</option>' +
          '</select>' +
          '<input type="text" id="insp-agent-text" value="' + esc(agent.statusText || '') + '" placeholder="氣泡狀態文字…">' +
          '<button class="ctrl-btn primary-btn" id="insp-save-btn" type="button">更新成員狀態</button>' +
        '</div>';
    }

    var anatomyHtml = window.ANATOMY_INSPECTOR ? window.ANATOMY_INSPECTOR.render(agent, c) : '';
    box.innerHTML =
      '<div class="inspector-left">' +
        anatomyHtml +
        '<div class="inspector-meta">' +
          '<div><strong>' + esc(agent.name) + '</strong>（' + esc(agent.roleTitle) + '） · 狀態：<code>' + esc(agent.statusText) + '</code></div>' +
          '<div>負責範圍：<code>' + esc(agent.paths) + '</code> · Worktree：<code>' + esc(agent.worktree) + '</code> · 部署：<code>' + esc(agent.deployCmd) + '</code></div>' +
          editHtml +
        '</div>' +
      '</div>' +
      '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' +
        '<span class="pill doing">進行中 ' + (c.in_progress + c.blocked) + '</span>' +
        '<span class="pill todo">待辦 ' + c.todo + '</span>' +
        '<span class="pill done">已完成 ' + c.done + '</span>' +
        '<button class="ctrl-btn" id="clear-agent-btn">顯示全部成員</button>' +
      '</div>';

    document.getElementById('clear-agent-btn').addEventListener('click', function () {
      state.selectedAgentId = null;
      renderAll();
    });

    var saveBtn = document.getElementById('insp-save-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var newSt = document.getElementById('insp-agent-status').value;
        var newTxt = document.getElementById('insp-agent-text').value.trim();
        patchAgent(agent.id, { status: newSt, statusText: newTxt });
      });
    }
  }

  function renderBoard() {
    var agentMap = {};
    (state.data.agents || []).forEach(function (a) { agentMap[a.id] = a; });
    var kw = state.keyword.trim().toLowerCase();

    var filtered = (state.data.tasks || []).filter(function (t) {
      if (state.selectedAgentId && t.agentId !== state.selectedAgentId) return false;
      if (state.quickFilter === 'p01' && t.priority !== 'P0' && t.priority !== 'P1') return false;
      if (state.quickFilter === 'doing' && t.status !== 'in_progress' && t.status !== 'blocked') return false;
      if (state.quickFilter === 'blocked' && t.status !== 'blocked') return false;
      if (state.quickFilter === 'queued' && !(t.status === 'todo' && t.dispatch === 'queued')) return false;
      if (kw) {
        var hay = (t.title + ' ' + t.description + ' ' + t.site + ' ' + (t.tags || []).join(' ') + ' ' + (agentMap[t.agentId] ? agentMap[t.agentId].name : '')).toLowerCase();
        if (hay.indexOf(kw) === -1) return false;
      }
      return true;
    });

    function cardHtml(t) {
      var a = agentMap[t.agentId] || { name: t.agentId, spriteKey: 'foreman', accentColor: '#38bdf8' };
      var expanded = !!state.expandedTaskIds[t.id];
      var isBlocked = t.status === 'blocked';
      var isApprovedQueued = t.approval === 'approved' && t.dispatch === 'queued';
      var isQueued = (t.status === 'todo' && t.dispatch === 'queued') || isApprovedQueued;
      var isDispatched = t.status === 'in_progress' && t.dispatch === 'dispatched';
      var approvalBarHtml = '';
      var actionsHtml = '';
      if (state.apiConnected) {
        if (isBlocked) {
          approvalBarHtml =
            '<div class="approval-bar">' +
              '<button class="approve-btn" data-act="approve" data-task-id="' + esc(t.id) + '" type="button">✅ 核准執行（交給工頭自動繼續／上線）</button>' +
              '<button class="reject-btn" data-act="reject" data-task-id="' + esc(t.id) + '" type="button">↩ 退回修改</button>' +
            '</div>';
        }
        var dispatchBtn = '';
        if (t.status === 'todo') {
          dispatchBtn = isQueued
            ? '<button class="st-btn st-dispatch active" data-act="dispatch" data-task-id="' + esc(t.id) + '" data-dispatch="manual" type="button" title="取消工頭自動派工">⏸ 取消派工</button>'
            : '<button class="st-btn st-dispatch" data-act="dispatch" data-task-id="' + esc(t.id) + '" data-dispatch="queued" type="button" title="排入佇列，由工頭定時自動巡檢派工">🚀 派給工頭</button>';
        }
        var reportBtn = t.hasReport
          ? '<button class="st-btn st-report" data-act="report" data-task-id="' + esc(t.id) + '" type="button" title="檢視完整巡檢／完工報告">📄 查看報告</button>'
          : '';
        actionsHtml =
          approvalBarHtml +
          '<div class="task-actions">' +
            reportBtn +
            dispatchBtn +
            '<button class="st-btn' + (t.status === 'todo' ? ' active' : '') + '" data-act="status" data-task-id="' + esc(t.id) + '" data-status="todo" type="button">待辦</button>' +
            '<button class="st-btn' + (t.status === 'in_progress' ? ' active' : '') + '" data-act="status" data-task-id="' + esc(t.id) + '" data-status="in_progress" type="button">進行中</button>' +
            '<button class="st-btn st-blocked' + (t.status === 'blocked' ? ' active' : '') + '" data-act="status" data-task-id="' + esc(t.id) + '" data-status="blocked" type="button">卡關</button>' +
            '<button class="st-btn st-done' + (t.status === 'done' ? ' active' : '') + '" data-act="status" data-task-id="' + esc(t.id) + '" data-status="done" type="button">完成</button>' +
            '<button class="st-btn st-del" data-act="delete" data-task-id="' + esc(t.id) + '" type="button" title="刪除此工作">✕</button>' +
          '</div>';
      }
      var statusBadge = '';
      if (isBlocked) statusBadge = '<span class="blocked-badge">❗ 待核准 / 卡關</span>';
      else if (isApprovedQueued) statusBadge = '<span class="dispatch-badge approved">✅ 已核准・等待工頭自動執行</span>';
      else if (isQueued) statusBadge = '<span class="dispatch-badge queued">🚀 等待工頭自動派工</span>';
      else if (isDispatched) statusBadge = '<span class="dispatch-badge dispatched">🤖 工頭已派工</span>';
      return (
        '<article class="task-card' + (expanded ? '' : ' collapsed') + (isBlocked ? ' status-blocked' : '') + (isApprovedQueued ? ' is-approved' : (isQueued ? ' is-queued' : '')) + '" data-task-id="' + esc(t.id) + '" style="border-left-color:' + esc(isBlocked ? '#ef4444' : (isApprovedQueued ? '#22c55e' : (isQueued ? '#8b5cf6' : a.accentColor))) + '">' +
          '<div class="task-top">' +
            '<div><span class="prio prio-' + esc(t.priority) + '">' + esc(t.priority) + '</span>' + statusBadge + '</div>' +
            '<span class="task-id">' + esc(t.id) + ' · ' + esc(t.site) + '</span>' +
          '</div>' +
          '<h3 class="task-title">' + esc(t.title) + '</h3>' +
          '<p class="task-desc">' + esc(t.description) + '</p>' +
          '<div class="task-foot">' +
            '<span class="assignee-badge">' + avatarHtml(a.spriteKey) + '<span>' + esc(a.name) + '</span></span>' +
            '<div class="task-tags">' + (t.tags || []).map(function (tg) { return '<span class="tag">' + esc(tg) + '</span>'; }).join('') + '</div>' +
          '</div>' +
          actionsHtml +
        '</article>'
      );
    }

    var cols = [
      { keys: ['todo'], listId: 'col-todo', countId: 'cnt-todo' },
      { keys: ['blocked', 'in_progress'], listId: 'col-doing', countId: 'cnt-doing' },
      { keys: ['done'], listId: 'col-done', countId: 'cnt-done' }
    ];
    cols.forEach(function (col) {
      var items = filtered.filter(function (t) { return col.keys.indexOf(t.status) !== -1; });
      // Put blocked tasks at top of doing column
      if (col.listId === 'col-todo') {
        items.sort(function (a, b) {
          if (a.dispatch === 'queued' && b.dispatch !== 'queued') return -1;
          if (a.dispatch !== 'queued' && b.dispatch === 'queued') return 1;
          return 0;
        });
      }
      if (col.listId === 'col-doing') {
        items.sort(function (a, b) {
          if (a.status === 'blocked' && b.status !== 'blocked') return -1;
          if (a.status !== 'blocked' && b.status === 'blocked') return 1;
          return 0;
        });
      }
      document.getElementById(col.countId).textContent = items.length;
      document.getElementById(col.listId).innerHTML = items.length
        ? items.map(cardHtml).join('')
        : '<div class="empty-msg">目前沒有符合條件的工作</div>';
    });

    document.querySelectorAll('.task-card').forEach(function (card) {
      card.addEventListener('click', function (e) {
        if (e.target && (e.target.closest('.task-actions') || e.target.closest('.approval-bar'))) return;
        var tid = card.getAttribute('data-task-id');
        state.expandedTaskIds[tid] = !state.expandedTaskIds[tid];
        card.classList.toggle('collapsed', !state.expandedTaskIds[tid]);
      });
    });

    document.querySelectorAll('.approval-bar button').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var act = btn.getAttribute('data-act');
        var tid = btn.getAttribute('data-task-id');
        if (act === 'approve') {
          var note = prompt('確定核准執行 ' + tid + '？（可選填備註，直接按確定即可核准並排入工頭執行）', '');
          if (note === null) return;
          approveTask(tid, note);
        } else if (act === 'reject') {
          var reason = prompt('請輸入退回 ' + tid + ' 的修改意見：', '');
          if (reason === null) return;
          var requeue = confirm('是否立刻將 ' + tid + ' 重新排入工頭自動派工佇列？\n（確定＝自動重作；取消＝僅退回待辦）');
          rejectTask(tid, reason, requeue);
        }
      });
    });

    document.querySelectorAll('.task-actions .st-btn').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var act = btn.getAttribute('data-act');
        var tid = btn.getAttribute('data-task-id');
        if (act === 'report') {
          openReportModal(tid);
        } else if (act === 'status') {
          var newStatus = btn.getAttribute('data-status');
          patchTask(tid, { status: newStatus });
        } else if (act === 'dispatch') {
          var nextDispatch = btn.getAttribute('data-dispatch');
          patchTask(tid, { dispatch: nextDispatch });
        } else if (act === 'delete') {
          if (confirm('確定要從本機 MongoDB 刪除工作 ' + tid + ' 嗎？')) {
            deleteTask(tid);
          }
        }
      });
    });
  }

  function renderLogAndStats() {
    var tasks = state.data.tasks || [];
    var agents = state.data.agents || [];
    var queued = tasks.filter(function (t) { return (t.status === 'todo' && t.dispatch === 'queued') || (t.approval === 'approved' && t.dispatch === 'queued'); }).length;
    var blocked = tasks.filter(function (t) { return t.status === 'blocked'; }).length;
    var doing = tasks.filter(function (t) { return t.status === 'in_progress'; }).length;
    var todo = tasks.filter(function (t) { return t.status === 'todo'; }).length;
    var done = tasks.filter(function (t) { return t.status === 'done'; }).length;

    var qEl = document.getElementById('stat-queued');
    if (qEl) {
      qEl.style.display = queued > 0 ? 'inline-flex' : 'none';
      qEl.textContent = '🚀 待派工 ' + queued;
    }
    var blkEl = document.getElementById('stat-blocked');
    if (blkEl) {
      blkEl.style.display = blocked > 0 ? 'inline-flex' : 'none';
      blkEl.textContent = '卡關 ' + blocked;
    }
    document.getElementById('stat-doing').textContent = '進行中 ' + doing;
    document.getElementById('stat-todo').textContent = '待辦 ' + todo;
    document.getElementById('stat-done').textContent = '已完成 ' + done;
    document.getElementById('sticky-members').textContent = agents.length + ' 位成員';
    document.getElementById('sticky-doing').textContent = '進行中 ' + (doing + blocked) + ' / 待辦 ' + todo;
    var revText = (state.data.meta && state.data.meta.revision != null) ? (' · Rev #' + state.data.meta.revision) : '';
    document.getElementById('meta-updated').textContent = '最後更新：' + (state.data.meta ? state.data.meta.updatedAt : '—') + revText;

    var agentMap = {};
    agents.forEach(function (a) { agentMap[a.id] = a; });
    var logs = state.data.activityLog || [];
    document.getElementById('activity-log').innerHTML = logs.map(function (l) {
      var a = agentMap[l.agentId];
      return (
        '<div class="log-item">' +
          '<div class="log-meta"><span>' + esc(l.time) + '</span><span class="log-action">[' + esc(l.action) + ']</span><span>' + esc(a ? a.name : l.agentId) + '</span></div>' +
          '<div class="log-msg">' + esc(l.message) + '</div>' +
        '</div>'
      );
    }).join('') || '<div class="empty-msg">尚無紀錄</div>';
  }

  function populateAgentSelect() {
    var sel = document.getElementById('f-agent');
    if (!sel || !state.data || !state.data.agents) return;
    var prev = sel.value;
    sel.innerHTML = state.data.agents.map(function (a) {
      return '<option value="' + esc(a.id) + '">' + esc(a.name) + '（' + esc(a.roleTitle) + '）</option>';
    }).join('');
    if (prev) sel.value = prev;
  }

  function renderAll() {
    if (!state.data) return;
    applyTheme();
    renderStage();
    renderInspector();
    renderBoard();
    renderLogAndStats();
    populateAgentSelect();
  }

  function applyIncomingState(newData, eventInfo) {
    if (!newData || !newData.agents) return;
    var rev = newData.meta && typeof newData.meta.revision === 'number' ? newData.meta.revision : -1;
    var isUpdate = state.lastRevision !== -1 && rev > state.lastRevision;
    state.data = newData;
    state.lastRevision = rev;
    renderAll();

    if (isUpdate && eventInfo) {
      var variant = eventInfo.toStatus === 'done' ? 'done' : (eventInfo.toStatus === 'blocked' ? 'blocked' : '');
      showToast(eventInfo.title || '工作狀態已更新', eventInfo.message || '', variant);
      fireBrowserNotification(eventInfo.title || 'Agent 工作儀表板更新', eventInfo.message || '');
    }
  }

  function fetchApiState() {
    if (!isHttp) return Promise.resolve(false);
    return fetch('/api/state?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (d && d.agents) {
          state.apiConnected = true;
          applyIncomingState(d, d.meta ? d.meta.lastEvent : null);
          if (!state.sseConnected) {
            setConnStatus('polling', state.storageLabel === 'cloud' ? '☁️ 雲端 MongoDB 已連線' : 'MongoDB 已連線');
          }
          document.getElementById('live-mode-note').textContent = (state.storageLabel === 'cloud'
            ? '☁️ 雲端主機 MongoDB (agent_dashboard) · SSE 即時同步'
            : '本機 MongoDB (agent_dashboard) · SSE 即時同步＋桌面通知');
          return true;
        }
        return false;
      })
      .catch(function () {
        // Fallback to static json if served by plain http.server
        return fetch('dashboard-data.json?t=' + Date.now(), { cache: 'no-store' })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            if (d && d.agents) {
              state.apiConnected = false;
              state.data = d;
              renderAll();
              setConnStatus('polling', '靜態 JSON 輪詢');
              return true;
            }
            return false;
          })
          .catch(function () { return false; });
      });
  }

  function connectSse() {
    if (!isHttp || typeof EventSource === 'undefined') return;
    if (eventSource) {
      try { eventSource.close(); } catch (e) {}
    }
    try {
      eventSource = new EventSource('/api/events');
      eventSource.addEventListener('hello', function () {
        state.apiConnected = true;
        state.sseConnected = true;
        setConnStatus('online', state.storageLabel === 'cloud' ? '☁️ 雲端即時連線' : 'MongoDB 即時連線');
      });
      eventSource.addEventListener('state_changed', function (ev) {
        try {
          var payload = JSON.parse(ev.data);
          if (payload && payload.state) {
            state.apiConnected = true;
            state.sseConnected = true;
            setConnStatus('online', state.storageLabel === 'cloud' ? '☁️ 雲端即時連線' : 'MongoDB 即時連線');
            applyIncomingState(payload.state, payload.event);
          }
        } catch (err) {}
      });
      eventSource.onerror = function () {
        state.sseConnected = false;
        if (state.apiConnected) {
          setConnStatus('polling', '重連中（輪詢備援）');
        }
      };
    } catch (e) {}
  }

  function updateUnlockButton() {
    var btn = document.getElementById('btn-unlock-write');
    if (!btn) return;
    if (!state.apiConnected || !state.writeProtected) {
      btn.style.display = 'none';
      return;
    }
    btn.style.display = 'inline-block';
    if (state.writeUnlocked) {
      btn.textContent = '🔓 已解鎖編輯';
      btn.classList.add('active');
    } else {
      btn.textContent = '🔒 唯讀（解鎖編輯）';
      btn.classList.remove('active');
    }
  }

  function checkAuthStatus() {
    if (!isHttp) return Promise.resolve();
    var headers = state.writeToken ? { 'X-Dashboard-Token': state.writeToken } : {};
    return fetch('/api/auth/status?t=' + Date.now(), { headers: headers, cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        state.writeProtected = !!d.writeProtected;
        state.writeUnlocked = !!d.unlocked;
        state.storageLabel = d.storage || 'local';
        if (state.writeProtected && !state.writeUnlocked && state.writeToken) {
          state.writeToken = '';
          localStorage.removeItem(LS_WRITE_TOKEN);
        }
        updateUnlockButton();
        var badge = document.querySelector('.lab-badge');
        if (badge && state.storageLabel === 'cloud') {
          badge.textContent = '🏛️ SimuLab 3D × Anatomy · ☁️ 雲端 MongoDB 即時驅動';
        }
      })
      .catch(function () {});
  }

  function promptUnlockToken() {
    var entered = window.prompt('請輸入 Agent 工作儀表板管理金鑰（驗證一次即自動記住於本機瀏覽器）：', '');
    if (!entered || !entered.trim()) return Promise.resolve(false);
    var tok = entered.trim();
    return fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'X-Dashboard-Token': tok }
    }).then(function (r) {
      if (!r.ok) throw new Error('管理金鑰錯誤，請再確認');
      state.writeToken = tok;
      state.writeUnlocked = true;
      localStorage.setItem(LS_WRITE_TOKEN, tok);
      updateUnlockButton();
      showToast('🔓 已解鎖編輯權限', '可進行新增、派工、核准與更新狀態。', 'done');
      return true;
    }).catch(function (err) {
      showToast('解鎖失敗', err.message, 'blocked');
      return false;
    });
  }

  function apiWriteFetch(url, opts) {
    var run = function () {
      var o = Object.assign({}, opts || {});
      o.headers = Object.assign({}, o.headers || {});
      if (state.writeToken) o.headers['X-Dashboard-Token'] = state.writeToken;
      return fetch(url, o);
    };
    var start = (state.writeProtected && !state.writeUnlocked)
      ? promptUnlockToken().then(function (ok) { if (!ok) throw new Error('未解鎖編輯權限'); })
      : Promise.resolve();
    return start.then(run).then(function (r) {
      if (r.status === 401) {
        state.writeToken = '';
        state.writeUnlocked = false;
        localStorage.removeItem(LS_WRITE_TOKEN);
        updateUnlockButton();
        throw new Error('管理金鑰無效或未解鎖，請點上方「🔒 唯讀（解鎖編輯）」');
      }
      if (!r.ok) return r.text().then(function (t) { throw new Error(t); });
      return r.json();
    });
  }

  function createTask(payload) {
    return apiWriteFetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('新增工作失敗', err.message, 'blocked');
    });
  }

  function patchTask(taskId, payload) {
    return apiWriteFetch('/api/tasks/' + encodeURIComponent(taskId), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('更新工作失敗', err.message, 'blocked');
    });
  }

  function approveTask(taskId, note) {
    return apiWriteFetch('/api/tasks/' + encodeURIComponent(taskId) + '/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note || '', notify: true })
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('核准失敗', err.message, 'blocked');
    });
  }

  function rejectTask(taskId, note, requeue) {
    return apiWriteFetch('/api/tasks/' + encodeURIComponent(taskId) + '/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note || '', requeue: !!requeue, notify: true })
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('退回失敗', err.message, 'blocked');
    });
  }

  function deleteTask(taskId) {
    return apiWriteFetch('/api/tasks/' + encodeURIComponent(taskId), {
      method: 'DELETE'
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('刪除失敗', err.message, 'blocked');
    });
  }

  function patchAgent(agentId, payload) {
    return apiWriteFetch('/api/agents/' + encodeURIComponent(agentId), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(function () {
      if (!state.sseConnected) fetchApiState();
    }).catch(function (err) {
      showToast('更新成員狀態失敗', err.message, 'blocked');
    });
  }

  function openModal() {
    populateAgentSelect();
    if (state.selectedAgentId) {
      document.getElementById('f-agent').value = state.selectedAgentId;
    }
    var m = document.getElementById('task-modal');
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');
    document.getElementById('f-title').focus();
  }

  function closeModal() {
    var m = document.getElementById('task-modal');
    m.classList.remove('open');
    m.setAttribute('aria-hidden', 'true');
  }

  function renderInlineMd(text) {
    var s = esc(text);
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return s;
  }

  function renderSimpleMarkdown(md) {
    var lines = String(md || '').replace(/\r\n/g, '\n').split('\n');
    var html = [];
    var inUl = false;
    var inOl = false;
    var i = 0;
    function closeLists() {
      if (inUl) { html.push('</ul>'); inUl = false; }
      if (inOl) { html.push('</ol>'); inOl = false; }
    }
    while (i < lines.length) {
      var line = lines[i];
      var trimmed = line.trim();
      if (!trimmed) {
        closeLists();
        i++;
        continue;
      }
      // Markdown table
      if (trimmed.startsWith('|') && i + 1 < lines.length && /^\|[\s:-]+\|/.test(lines[i + 1].trim())) {
        closeLists();
        var headers = trimmed.split('|').slice(1, -1).map(function (c) { return '<th>' + renderInlineMd(c.trim()) + '</th>'; }).join('');
        i += 2;
        var rows = [];
        while (i < lines.length && lines[i].trim().startsWith('|')) {
          var cells = lines[i].trim().split('|').slice(1, -1).map(function (c) { return '<td>' + renderInlineMd(c.trim()) + '</td>'; }).join('');
          rows.push('<tr>' + cells + '</tr>');
          i++;
        }
        html.push('<table><thead><tr>' + headers + '</tr></thead><tbody>' + rows.join('') + '</tbody></table>');
        continue;
      }
      if (trimmed.startsWith('### ')) { closeLists(); html.push('<h3>' + renderInlineMd(trimmed.slice(4)) + '</h3>'); i++; continue; }
      if (trimmed.startsWith('## ')) { closeLists(); html.push('<h2>' + renderInlineMd(trimmed.slice(3)) + '</h2>'); i++; continue; }
      if (trimmed.startsWith('# ')) { closeLists(); html.push('<h1>' + renderInlineMd(trimmed.slice(2)) + '</h1>'); i++; continue; }
      if (/^[-*]\s+/.test(trimmed)) {
        if (inOl) { html.push('</ol>'); inOl = false; }
        if (!inUl) { html.push('<ul>'); inUl = true; }
        html.push('<li>' + renderInlineMd(trimmed.replace(/^[-*]\s+/, '')) + '</li>');
        i++;
        continue;
      }
      if (/^\d+\.\s+/.test(trimmed)) {
        if (inUl) { html.push('</ul>'); inUl = false; }
        if (!inOl) { html.push('<ol>'); inOl = true; }
        html.push('<li>' + renderInlineMd(trimmed.replace(/^\d+\.\s+/, '')) + '</li>');
        i++;
        continue;
      }
      closeLists();
      html.push('<p>' + renderInlineMd(trimmed) + '</p>');
      i++;
    }
    closeLists();
    return html.join('\n');
  }

  function openReportModal(taskId) {
    var m = document.getElementById('report-modal');
    var titleEl = document.getElementById('report-modal-title');
    var pathEl = document.getElementById('report-modal-path');
    var bodyEl = document.getElementById('report-modal-body');
    titleEl.textContent = '載入 ' + taskId + ' 報告中…';
    pathEl.textContent = '';
    bodyEl.textContent = '載入中…';
    m.classList.add('open');
    m.setAttribute('aria-hidden', 'false');

    fetch('/api/tasks/' + encodeURIComponent(taskId) + '/report?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('查無此工作的報告內容');
        return r.json();
      })
      .then(function (d) {
        titleEl.textContent = '📄 ' + d.taskId + ' — ' + d.title;
        pathEl.textContent = d.filePath || '儲存於本機 MongoDB (agent_dashboard.tasks)';
        bodyEl.innerHTML = renderSimpleMarkdown(d.markdown);
      })
      .catch(function (err) {
        titleEl.textContent = '無法載入報告';
        bodyEl.textContent = err.message;
      });
  }

  function closeReportModal() {
    var m = document.getElementById('report-modal');
    m.classList.remove('open');
    m.setAttribute('aria-hidden', 'true');
  }

  function init() {
    if (window.SIMULAB_STAGE) {
      var labCanvas = document.getElementById('lab-canvas');
      var labOverlay = document.getElementById('lab-overlay');
      if (labCanvas && labOverlay) {
        window.SIMULAB_STAGE.mount(labCanvas, labOverlay, {
          onSelectAgent: function (id) {
            state.selectedAgentId = (id && state.selectedAgentId === id) ? null : id;
            renderAll();
          },
          getBubbleMeta: function (agent) {
            return taskBubbleMeta(pickFeaturedTask(agent.id), agent);
          }
        });
      }
      var btnDemo = document.getElementById('btn-lab-demo');
      var btnReset = document.getElementById('btn-lab-reset');
      var btnReplay = document.getElementById('btn-lab-replay');
      var btnActive = document.getElementById('btn-lab-active');
      if (btnDemo) btnDemo.addEventListener('click', function () { window.SIMULAB_STAGE.toggleLifecycleDemo(); });
      if (btnReset) btnReset.addEventListener('click', function () { window.SIMULAB_STAGE.resetView(); });
      if (btnReplay) btnReplay.addEventListener('click', function () { window.SIMULAB_STAGE.replayBuild(); });
      if (btnActive) btnActive.addEventListener('click', function () {
        state.labActiveOnly = !state.labActiveOnly;
        window.SIMULAB_STAGE.setActiveOnly(state.labActiveOnly);
        btnActive.classList.toggle('active', state.labActiveOnly);
        btnActive.textContent = state.labActiveOnly ? '⚡ 只看活躍管線' : '⚡ 全部管線';
      });
    }

    var btnStyleLab = document.getElementById('btn-style-lab');
    if (btnStyleLab) {
      btnStyleLab.addEventListener('click', function () {
        state.style = 'lab';
        localStorage.setItem(LS_STYLE, 'lab');
        renderAll();
      });
    }
    document.getElementById('btn-style-pixel').addEventListener('click', function () {
      state.style = 'pixel';
      localStorage.setItem(LS_STYLE, 'pixel');
      renderAll();
    });
    document.getElementById('btn-style-notebook').addEventListener('click', function () {
      state.style = 'notebook';
      localStorage.setItem(LS_STYLE, 'notebook');
      renderAll();
    });
    document.getElementById('pixel-theme-btn').addEventListener('click', function () {
      state.pixelTheme = state.pixelTheme === 'dark' ? 'light' : 'dark';
      localStorage.setItem(LS_PIXEL_THEME, state.pixelTheme);
      applyTheme();
    });
    document.getElementById('nb-theme-select').addEventListener('change', function (e) {
      state.nbTheme = e.target.value;
      localStorage.setItem(LS_NB_THEME, state.nbTheme);
      applyTheme();
    });
    document.getElementById('notify-btn').addEventListener('click', function () {
      if (typeof Notification === 'undefined') return;
      if (state.browserNotify && Notification.permission === 'granted') {
        state.browserNotify = false;
        localStorage.setItem(LS_NOTIFY, '0');
        updateNotifyButton();
        showToast('已關閉瀏覽器桌面通知', '仍保留網頁右下／右上 Toast 與 Windows 系統通知。');
        return;
      }
      Notification.requestPermission().then(function (perm) {
        if (perm === 'granted') {
          state.browserNotify = true;
          localStorage.setItem(LS_NOTIFY, '1');
          updateNotifyButton();
          showToast('已開啟瀏覽器桌面通知', '工作狀態異動時將同步提醒。', 'done');
        } else {
          showToast('無法開啟瀏覽器通知', '瀏覽器未允許通知權限（Windows 系統通知仍正常運作）。', 'blocked');
        }
      });
    });

    document.querySelectorAll('.chip[data-filter]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        document.querySelectorAll('.chip[data-filter]').forEach(function (b) { b.classList.remove('active'); });
        btn.classList.add('active');
        state.quickFilter = btn.getAttribute('data-filter');
        if (state.quickFilter === 'all') state.selectedAgentId = null;
        renderAll();
      });
    });
    document.getElementById('search-input').addEventListener('input', function (e) {
      state.keyword = e.target.value;
      renderBoard();
    });
    document.getElementById('refresh-btn').addEventListener('click', function () {
      if (isHttp) {
        fetchApiState();
      } else {
        location.reload();
      }
    });

    // Modal handlers
    document.getElementById('btn-add-task').addEventListener('click', openModal);
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('modal-cancel-btn').addEventListener('click', closeModal);
    document.getElementById('task-modal').addEventListener('click', function (e) {
      if (e.target === e.currentTarget) closeModal();
    });
    document.getElementById('report-close-btn').addEventListener('click', closeReportModal);
    document.getElementById('report-modal').addEventListener('click', function (e) {
      if (e.target === e.currentTarget) closeReportModal();
    });
    document.getElementById('add-task-form').addEventListener('submit', function (e) {
      e.preventDefault();
      var title = document.getElementById('f-title').value.trim();
      if (!title) return;
      var tagsRaw = document.getElementById('f-tags').value.trim();
      var tags = tagsRaw ? tagsRaw.split(',').map(function (x) { return x.trim(); }).filter(Boolean) : [];
      var autoDispatch = document.getElementById('f-auto-dispatch').checked;
      var initStatus = document.getElementById('f-status').value;
      createTask({
        title: title,
        agentId: document.getElementById('f-agent').value,
        priority: document.getElementById('f-priority').value,
        status: initStatus,
        site: document.getElementById('f-site').value.trim() || '全局',
        description: document.getElementById('f-desc').value.trim(),
        tags: tags,
        dispatch: (autoDispatch && initStatus === 'todo') ? 'queued' : 'manual',
        notify: true
      }).then(function () {
        document.getElementById('add-task-form').reset();
        document.getElementById('f-auto-dispatch').checked = true;
        closeModal();
      });
    });

    var btnUnlock = document.getElementById('btn-unlock-write');
    if (btnUnlock) {
      btnUnlock.addEventListener('click', function () {
        if (state.writeUnlocked) {
          if (window.confirm('要鎖定回唯讀模式並清除本機記憶的管理金鑰嗎？')) {
            state.writeToken = '';
            state.writeUnlocked = false;
            localStorage.removeItem(LS_WRITE_TOKEN);
            updateUnlockButton();
            showToast('🔒 已切換回唯讀模式', '瀏覽不受影響，編輯前需重新輸入金鑰。');
          }
        } else {
          promptUnlockToken();
        }
      });
    }

    renderAll();

    if (isHttp) {
      checkAuthStatus().then(function () {
        return fetchApiState();
      }).then(function (ok) {
        updateUnlockButton();
        if (ok && state.apiConnected) {
          connectSse();
        }
      });
      setInterval(function () {
        if (!state.sseConnected) fetchApiState();
      }, 10000);
    } else {
      setConnStatus('offline', '離線快取模式');
      document.getElementById('live-mode-note').textContent = '離線雙擊模式（請執行 start-dashboard.ps1 連線本機 MongoDB 與即時通知）';
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
