// Frank Portal 3D Isometric Agent Studio
// Spacious Non-Overlapping Layout + Big Lounge Behind Foreman (Basketball / Arcade / Tea) + 10 Role-Specific Animated Workshops
(function () {
  // Spacious, zero-occlusion coordinates (cm): screenX ~ (x - y)*0.707, screenY ~ (x + y)*0.354
  var STATION_POS = {
    'foreman':               { x:  -4, y:  -4, zone: 'command', buildIdx: 2 },
    // Left Wing: Portal 4 Bespoke Workshops (all pairwise screen distance >= 10cm)
    'portal-agent':          { x: -26, y:   4, zone: 'portal',  buildIdx: 3 },
    'share-agent':           { x: -11, y:  14, zone: 'portal',  buildIdx: 4 },
    'revival-agent':         { x: -31, y:  19, zone: 'portal',  buildIdx: 5 },
    'kb-agent':              { x: -16, y:  28, zone: 'portal',  buildIdx: 6 },
    // Right Wing: FinLab 5 Bespoke Workshops (staggered, zero overlap)
    'finlab-decision-agent': { x:   4, y: -26, zone: 'finlab',  buildIdx: 7 },
    'finlab-stock-agent':    { x:  14, y: -11, zone: 'finlab',  buildIdx: 8 },
    'finlab-market-agent':   { x:  19, y: -31, zone: 'finlab',  buildIdx: 9 },
    'finlab-risk-agent':     { x:  28, y: -16, zone: 'finlab',  buildIdx: 10 },
    'finlab-platform-agent': { x:  24, y:  -1, zone: 'finlab',  buildIdx: 11 },
    // Front-Center Observer Plaza: Intern Yo-Yo Water Balloon & Study Booth
    'intern-agent':          { x:   3, y:  13, zone: 'portal',  buildIdx: 12 }
  };

  // Large Leisure Lounge BEHIND Foreman: x in [-40..-12], y in [-40..-12] (28x28cm!)
  // 3 leisure zones: Basketball Court (left), Arcade & Gaming (top), Japanese Tea House (right)
  var LOUNGE_SLOTS = {
    // Basketball Half-Court (3 players, well spaced)
    'finlab-market-agent':   { x: -30.5, y: -18.5, activity: 'basketball', shooter: true },
    'finlab-risk-agent':     { x: -24.5, y: -21.5, activity: 'basketball', shooter: false },
    'portal-agent':          { x: -27.5, y: -14.2, activity: 'basketball', shooter: false },
    // Arcade & Console Gaming Corner (3 players)
    'finlab-platform-agent': { x: -34.2, y: -31.8, activity: 'arcade' },
    'finlab-decision-agent': { x: -28.0, y: -34.5, activity: 'arcade' },
    'finlab-stock-agent':    { x: -28.5, y: -27.5, activity: 'gaming' },
    // Japanese Tea House & Tatami Table (4 guests)
    'share-agent':           { x: -20.0, y: -34.0, activity: 'tea' },
    'revival-agent':         { x: -14.8, y: -28.5, activity: 'tea' },
    'kb-agent':              { x: -18.8, y: -22.8, activity: 'tea' },
    'intern-agent':          { x: -14.5, y: -34.2, activity: 'tea' }
  };

  // Foreman Briefing / Reporting Plaza right in front of Foreman (-4, -4)
  var FOREMAN_MEET_SLOTS = [
    { x: -4.0, y:  2.8 },
    { x:  1.2, y: -0.2 },
    { x: -7.8, y:  1.8 },
    { x:  2.4, y: -4.6 },
    { x: -1.0, y:  4.6 },
    { x: -6.2, y:  5.4 },
    { x:  3.6, y:  2.2 },
    { x: -9.5, y: -1.5 },
    { x:  0.5, y:  6.4 },
    { x:  4.0, y: -1.8 }
  ];

  // MongoDB Data Core placed cleanly at front-bottom hub
  var MONGO_POS = { x: 16, y: 16, z: 0 };

  var _matCache = {};
  function makeMat(hex) {
    if (!hex || hex[0] !== '#') hex = '#38bdf8';
    if (_matCache[hex]) return _matCache[hex];
    var rgb = hexRgb(hex);
    var toHex = function (c) {
      return '#' + c.map(function (v) {
        var n = Math.max(0, Math.min(255, Math.round(v)));
        return (n < 16 ? '0' : '') + n.toString(16);
      }).join('');
    };
    _matCache[hex] = {
      light: toHex(mixRgb(rgb, [255, 255, 255], 0.28)),
      mid: hex,
      dark: toHex(mixRgb(rgb, [14, 18, 36], 0.34))
    };
    return _matCache[hex];
  }

  function isLightTheme() {
    var th = document.documentElement.getAttribute('data-theme') || 'dark';
    return th === 'light' || th === 'paper' || th === 'solarized';
  }

  function studioPalette() {
    if (isLightTheme()) {
      return {
        bgTop: '#edf2f7', bgBot: '#dfe7f0',
        slab: { light: '#faf8f2', mid: '#e7e2d5', dark: '#cfc8b6' },
        grid: 'rgba(30, 41, 59, 0.07)',
        zoneCmd: { light: '#fef3c7', mid: '#f5d77b', dark: '#d4b04c' },
        zonePortal: { light: '#dff4ec', mid: '#b7e2d2', dark: '#8ec4b0' },
        zoneFinlab: { light: '#e0ecfc', mid: '#bad3f4', dark: '#90b3e2' },
        zoneLounge: { light: '#fde8cc', mid: '#f3cfa0', dark: '#d6a972' },
        court: { light: '#f4a261', mid: '#e07a3d', dark: '#b85b25' },
        tatami: { light: '#d9e7b8', mid: '#b8cc88', dark: '#92a861' },
        wood: { light: '#d9a774', mid: '#b67d4a', dark: '#8a582d' },
        deskTop: { light: '#fffbf2', mid: '#f2e6d0', dark: '#d7c5a6' },
        casing: { light: '#f6f7f9', mid: '#d8dde6', dark: '#aeb6c4' },
        plant: { light: '#4ade80', mid: '#16a34a', dark: '#15803d' },
        pot: { light: '#e08b63', mid: '#c2643d', dark: '#8f4324' },
        arcade: { light: '#60a5fa', mid: '#2563eb', dark: '#1d4ed8' },
        arcade2: { light: '#c084fc', mid: '#9333ea', dark: '#6b21a8' },
        shadow: 'rgba(15, 23, 42, 0.14)',
        labelInk: '#334155',
        loungeInk: '#7c2d12'
      };
    }
    return {
      bgTop: '#121a2b', bgBot: '#0b1120',
      slab: { light: '#253147', mid: '#1c2638', dark: '#131b2b' },
      grid: 'rgba(148, 163, 184, 0.08)',
      zoneCmd: { light: '#3f3422', mid: '#2f271a', dark: '#211b12' },
      zonePortal: { light: '#1d3632', mid: '#162926', dark: '#101f1d' },
      zoneFinlab: { light: '#1c2c46', mid: '#162338', dark: '#101a2a' },
      zoneLounge: { light: '#3b2c25', mid: '#2d211c', dark: '#201714' },
      court: { light: '#9c4a26', mid: '#7c371a', dark: '#592510' },
      tatami: { light: '#3e4d33', mid: '#2f3b26', dark: '#212a1b' },
      wood: { light: '#8f633e', mid: '#6e492b', dark: '#4d311c' },
      deskTop: { light: '#384660', mid: '#2b364d', dark: '#1f283b' },
      casing: { light: '#556178', mid: '#3d475c', dark: '#293040' },
      plant: { light: '#4ade80', mid: '#16a34a', dark: '#14532d' },
      pot: { light: '#d97757', mid: '#b45333', dark: '#7c331c' },
      arcade: { light: '#3b82f6', mid: '#1d4ed8', dark: '#1e3a8a' },
      arcade2: { light: '#a855f7', mid: '#7e22ce', dark: '#581c87' },
      shadow: 'rgba(2, 6, 23, 0.38)',
      labelInk: '#cbd5e1',
      loungeInk: '#fdba74'
    };
  }

  function conduitPoints(from, to) {
    var mx = (from.x + to.x) * 0.5;
    return [
      [from.x, from.y, 0.3],
      [mx, from.y, 0.24],
      [mx, to.y, 0.24],
      [to.x, to.y, 0.3]
    ];
  }

  function samplePolyline(pts, t) {
    if (!pts || pts.length < 2) return pts ? pts[0] : [0, 0];
    var total = 0, segs = [];
    for (var i = 0; i < pts.length - 1; i++) {
      var d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]);
      segs.push(d); total += d;
    }
    if (total <= 0.001) return pts[0];
    var target = clamp(t, 0, 1) * total, acc = 0;
    for (var j = 0; j < segs.length; j++) {
      if (acc + segs[j] >= target || j === segs.length - 1) {
        var frac = segs[j] > 0.001 ? (target - acc) / segs[j] : 0;
        return [lerp(pts[j][0], pts[j + 1][0], frac), lerp(pts[j][1], pts[j + 1][1], frac)];
      }
      acc += segs[j];
    }
    return pts[pts.length - 1];
  }

  function drawStudioFloor(G, pal, timeSec, buildProg, model) {
    var root = new Xf(0, 0, 0, 0);
    var pFloor = backOut(clamp(buildProg / 0.22));
    var fXf = new Xf(0, 0, (1 - pFloor) * -8, 0);

    // Main architectural studio floor slab [-42..-42] to [34..34]
    drawBox(G, fXf, [-42, -42, -1.8], [34, 34, 0], pal.slab, { lw: 1.5 });

    // Drafting grid
    onPlane(G, fXf.p([-40, -40, 0.02]), [1, 0, 0], [0, 1, 0], function (c) {
      c.strokeStyle = pal.grid;
      c.lineWidth = 0.09;
      for (var gx = 0; gx <= 72; gx += 4) { c.beginPath(); c.moveTo(gx, 0); c.lineTo(gx, 72); c.stroke(); }
      for (var gy = 0; gy <= 72; gy += 4) { c.beginPath(); c.moveTo(0, gy); c.lineTo(72, gy); c.stroke(); }
    });

    // 1. BIG LEISURE LOUNGE BEHIND FOREMAN: [-40, -40] to [-11, -11] (29x29cm!)
    drawBox(G, fXf, [-40, -40, 0], [-11, -11, 0.16], pal.zoneLounge, { lw: 1.2 });
    // Sub-floor 1A: Basketball Half-Court (left of lounge)
    drawBox(G, fXf, [-38.5, -24.5, 0.16], [-21.5, -12.2, 0.24], pal.court, { lw: 0.9 });
    onPlane(G, fXf.p([-38.5, -24.5, 0.26]), [1, 0, 0], [0, 1, 0], function (c) {
      c.strokeStyle = 'rgba(255,255,255,0.75)';
      c.lineWidth = 0.16;
      c.strokeRect(0.6, 0.6, 15.8, 11.1);
      // Paint key & 3-point arc facing hoop at x=1.6
      c.strokeRect(0.6, 3.6, 5.2, 5.1);
      c.beginPath(); c.arc(5.8, 6.15, 2.55, -Math.PI * 0.5, Math.PI * 0.5); c.stroke();
      c.beginPath(); c.arc(2.2, 6.15, 7.6, -Math.PI * 0.42, Math.PI * 0.42); c.stroke();
    });
    // Sub-floor 1B: Japanese Tatami Tea Mat (right of lounge)
    drawBox(G, fXf, [-21.5, -38.5, 0.16], [-12.2, -20.5, 0.24], pal.tatami, { lw: 0.9 });
    onPlane(G, fXf.p([-21.5, -38.5, 0.26]), [1, 0, 0], [0, 1, 0], function (c) {
      c.strokeStyle = 'rgba(20, 40, 20, 0.35)';
      c.lineWidth = 0.14;
      c.strokeRect(0.3, 0.3, 8.7, 17.4);
      c.beginPath(); c.moveTo(0.3, 9.0); c.lineTo(9.0, 9.0); c.stroke();
    });

    // 2. Center Command Plaza (Foreman + Briefing Mat)
    drawBox(G, fXf, [-10, -10, 0], [7, 8, 0.16], pal.zoneCmd, { lw: 1.1 });
    onPlane(G, fXf.p([-8.8, 0.2, 0.18]), [1, 0, 0], [0, 1, 0], function (c) {
      c.strokeStyle = 'rgba(234, 179, 8, 0.58)';
      c.lineWidth = 0.15;
      c.setLineDash([0.55, 0.35]);
      c.strokeRect(0, 0, 12.6, 6.4);
      c.setLineDash([]);
      c.font = '800 1.08px "Noto Sans TC", sans-serif';
      c.fillStyle = isLightTheme() ? '#92400e' : '#fde047';
      c.fillText('📋 工頭派工／匯報區', 0.5, 5.7);
    });

    // 3. Left Wing: Portal 4 Bespoke Workshops
    drawBox(G, fXf, [-39, -3, 0], [-7, 32, 0.16], pal.zonePortal, { lw: 1.1 });
    // 4. Right Wing: FinLab 5 Bespoke Workshops
    drawBox(G, fXf, [-3, -39, 0], [32, 5, 0.16], pal.zoneFinlab, { lw: 1.1 });

    // Clean zone floor labels (right-handed planes -> readable left-to-right!)
    onPlane(G, fXf.p([-38.0, 30.8, 0.18]), [1, 0, 0], [0, 1, 0], function (c) {
      c.font = '800 1.42px "Noto Sans TC", sans-serif';
      c.fillStyle = pal.labelInk;
      c.fillText('🏮 PORTAL 夜市（撈魚·飛鏢·套圈圈·彈珠台）', 0, 0);
    });
    onPlane(G, fXf.p([30.8, -4.5, 0.18]), [0, -1, 0], [1, 0, 0], function (c) {
      c.font = '800 1.38px "Noto Sans TC", sans-serif';
      c.fillStyle = pal.labelInk;
      c.fillText('🏮 FINLAB 夜市（射擊·夾娃娃·麻將·打地鼠·九宮格）', 0, 0);
    });
    onPlane(G, fXf.p([-38.5, -11.4, 0.19]), [1, 0, 0], [0, 1, 0], function (c) {
      c.font = '800 1.48px "Noto Sans TC", sans-serif';
      c.fillStyle = pal.loungeInk;
      c.fillText('LOUNGE · 休閒區（🏀 籃球 · 🎮 電玩 · 🍵 喝茶）', 0, 0);
    });

    // Floor conduits connecting MongoDB Core <-> Foreman & active Workshops
    var wireProg = clamp((buildProg - 0.15) / 0.25);
    if (wireProg <= 0) return;

    var fPos = STATION_POS['foreman'];
    var spineCol = model.blockedCount > 0 ? '#ef4444' : (model.doingCount > 0 ? '#22c55e' : '#eab308');
    var spinePts = drawWire(G, root, conduitPoints(fPos, MONGO_POS), spineCol, {
      w: 0.34, prog: wireProg,
      glow: (model.doingCount > 0 || model.blockedCount > 0) ? (model.blockedCount > 0 ? 'rgba(239,68,68,0.28)' : 'rgba(34,197,94,0.25)') : null
    });
    if (wireProg >= 1 && spinePts && (model.doingCount > 0 || model.queuedCount > 0 || model.blockedCount > 0)) {
      var ptS = samplePolyline(spinePts, (timeSec * 0.55) % 1);
      glowAt(G.ctx, ptS[0], ptS[1], 7 * LWS, model.blockedCount > 0 ? 'rgba(248,113,113,0.9)' : 'rgba(74,222,128,0.9)');
    }

    (model.agents || []).forEach(function (a) {
      if (a.id === 'foreman') return;
      var pos = STATION_POS[a.id];
      if (!pos) return;
      var info = model.agentInfo[a.id] || {};
      var isHot = info.isWorking || info.isBlocked || info.isQueued || model.selectedAgentId === a.id || model.hoveredAgentId === a.id;
      if (model.activeOnly && !isHot) return;

      var col = '#64748b', glow = null, speed = 0;
      if (info.isBlocked) { col = '#ef4444'; glow = 'rgba(239,68,68,0.34)'; speed = 0.85; }
      else if (info.isWorking) { col = '#22c55e'; glow = 'rgba(34,197,94,0.28)'; speed = 0.72; }
      else if (info.isQueued) { col = '#8b5cf6'; glow = 'rgba(139,92,246,0.32)'; speed = 0.55; }
      else if (model.selectedAgentId === a.id || model.hoveredAgentId === a.id) { col = a.accentColor || '#38bdf8'; glow = 'rgba(56,189,248,0.28)'; speed = 0.45; }
      else if (info.isDone) { col = '#3b82f6'; }

      var sp = drawWire(G, root, conduitPoints(MONGO_POS, pos), col, { w: isHot ? 0.27 : 0.18, prog: wireProg, glow: glow });
      if (wireProg >= 1 && sp && speed > 0) {
        var ph1 = (timeSec * speed) % 1;
        var p1 = samplePolyline(sp, info.isQueued ? (1 - ph1) : ph1);
        var pulseCol = info.isBlocked ? 'rgba(248,113,113,0.95)' : (info.isQueued ? 'rgba(167,139,250,0.95)' : 'rgba(74,222,128,0.95)');
        glowAt(G.ctx, p1[0], p1[1], 6.5 * LWS, pulseCol);
      }
    });
  }

  function drawMongoCore(G, pal, timeSec, buildProg, model) {
    var prog = backOut(clamp((buildProg - 0.08) / 0.24));
    if (prog <= 0.01) return;
    var xf = new Xf(MONGO_POS.x, MONGO_POS.y, 0.16 + (1 - prog) * 14, 0);
    var sh = shadowPts(G, cylCorners(new Xf(MONGO_POS.x, MONGO_POS.y, 0.16, 0), [0, 0, 3.6], 'z', 3.4, 7.2), 0.18);
    fillStroke(G, sh, pal.shadow, 0);

    drawPrism(G, xf, rrPlan(-3.6, -3.6, 3.6, 3.6, 1.0, 4), 0, 1.0, pal.casing, { lw: 1.5 });
    drawCyl(G, xf, [0, 0, 1.25], 'z', 2.9, 0.5, M.brass, { lw: 1.2, seg: 28 });

    var tierMat = { light: '#4ade80', mid: '#16a34a', dark: '#14532d' };
    var darkTier = { light: '#334155', mid: '#1e293b', dark: '#0f172a' };
    drawCyl(G, xf, [0, 0, 2.25], 'z', 2.55, 1.2, darkTier, { lw: 1.3, seg: 28 });
    drawCyl(G, xf, [0, 0, 3.0], 'z', 2.62, 0.28, tierMat, { lw: 1.0, seg: 28 });
    drawCyl(G, xf, [0, 0, 3.85], 'z', 2.55, 1.2, darkTier, { lw: 1.3, seg: 28 });
    drawCyl(G, xf, [0, 0, 4.6], 'z', 2.62, 0.28, tierMat, { lw: 1.0, seg: 28 });
    drawCyl(G, xf, [0, 0, 5.45], 'z', 2.55, 1.2, darkTier, { lw: 1.3, seg: 28 });

    var pulse = 0.5 + 0.5 * Math.sin(timeSec * 3.2);
    var topMat = model.blockedCount > 0 ? M.ledR : (model.doingCount > 0 ? M.ledG : M.ledB);
    drawCyl(G, xf, [0, 0, 6.28], 'z', 1.85, 0.42, M.steel, { lw: 1.2, seg: 24 });
    drawSphere(G, xf, [0, 0, 6.95], 0.72, topMat, { lw: 1.3 });
    var topScreen = G.cam.p(xf.p([0, 0, 6.95]));
    glowAt(G.ctx, topScreen[0], topScreen[1], (9 + pulse * 5) * LWS,
      model.blockedCount > 0 ? 'rgba(239,68,68,0.45)' : 'rgba(52,211,153,0.42)');

    drawBox(G, xf, [-2.5, 3.3, 0.15], [2.5, 3.8, 0.92], M.blk, {
      lw: 1.0,
      py: function (c) {
        c.fillStyle = '#0f172a'; c.fillRect(0.12, 0.08, 4.76, 0.62);
        c.font = '800 0.44px monospace'; c.fillStyle = '#4ade80';
        c.fillText('MONGO · REV #' + (model.revision || 0), 0.35, 0.52);
      }
    });
    drawBox(G, xf, [3.3, -2.0, 0.15], [3.8, 2.0, 0.92], M.blk, {
      lw: 1.0,
      px: function (c) {
        c.fillStyle = '#0f172a'; c.fillRect(0.12, 0.08, 3.76, 0.62);
        c.font = '800 0.40px monospace'; c.fillStyle = '#38bdf8';
        c.fillText('TASKS: ' + (model.tasks ? model.tasks.length : 0), 0.35, 0.52);
      }
    });
  }

  window._SIMULAB_INTERNALS = {
    STATION_POS: STATION_POS,
    LOUNGE_SLOTS: LOUNGE_SLOTS,
    FOREMAN_MEET_SLOTS: FOREMAN_MEET_SLOTS,
    MONGO_POS: MONGO_POS,
    makeMat: makeMat,
    isLightTheme: isLightTheme,
    studioPalette: studioPalette,
    drawStudioFloor: drawStudioFloor,
    drawMongoCore: drawMongoCore
  };
})();


// Part 2A: Big Leisure Lounge 3D Facilities (Basketball Court + Arcade Cabinets + Tea House)
(function () {
  var INT = window._SIMULAB_INTERNALS;

  function drawLoungeFacility(G, pal, prop, timeSec, buildProg) {
    var prog = backOut(clamp((buildProg - 0.16) / 0.25));
    if (prog <= 0.01) return;
    var dropZ = (1 - prog) * 10;
    var xf = new Xf(prop.x, prop.y, 0.22 + dropZ, 0);

    if (prop.kind === 'basketballHoop') {
      // Iconic 3D Basketball Stanchion, Pole, Translucent Backboard & Orange Rim!
      var sh = shadowPts(G, boxCorners(new Xf(prop.x, prop.y, 0.22, 0), [-1.2, -1.2, 0], [1.6, 1.2, 7.6]), 0.24);
      fillStroke(G, sh, pal.shadow, 0);
      drawBox(G, xf, [-1.1, -1.1, 0], [0.9, 1.1, 1.2], M.blk, { lw: 1.1 });
      drawCyl(G, xf, [-0.1, 0, 3.8], 'z', 0.24, 6.8, M.steel, { lw: 1.0, seg: 12 });
      // Overhang arm extending toward +x (into court)
      drawBox(G, xf, [-0.2, -0.22, 6.7], [1.45, 0.22, 7.1], M.steel, { lw: 0.9 });
      // Backboard (vertical plane facing +x)
      drawBox(G, xf, [1.35, -1.9, 5.4], [1.62, 1.9, 8.2], M.white, {
        lw: 1.15,
        px: function (c) {
          c.strokeStyle = '#ea580c'; c.lineWidth = 0.18;
          c.strokeRect(0.25, 0.25, 3.3, 2.3);
          c.strokeRect(1.25, 1.25, 1.3, 1.0);
        }
      });
      // Orange Rim & White Net frustum
      drawCyl(G, xf, [2.35, 0, 5.85], 'z', 0.72, 0.14, { light: '#fb923c', mid: '#ea580c', dark: '#9a3412' }, { lw: 1.0, seg: 16 });
      drawFrustum(G, xf, [2.35, 0, 5.25], 'z', 0.45, 0.68, 1.05, M.white, { lw: 0.8, seg: 12 });
    } else if (prop.kind === 'arcadeCab') {
      // Glowing Retro 3D Arcade Cabinet with animated pixel game screen + joystick!
      var shA = shadowPts(G, boxCorners(new Xf(prop.x, prop.y, 0.22, 0), [-1.4, -1.4, 0], [1.4, 1.4, 6.2]), 0.24);
      fillStroke(G, shA, pal.shadow, 0);
      var cabMat = prop.variant === 2 ? pal.arcade2 : pal.arcade;
      drawBox(G, xf, [-1.35, -1.35, 0], [1.35, 1.1, 2.6], cabMat, { lw: 1.2 });
      drawBox(G, xf, [-1.35, -1.35, 2.6], [1.35, 1.55, 3.15], M.blk, { lw: 1.1 }); // Control deck
      // Tiny glowing joystick & buttons
      drawCyl(G, xf, [-0.55, 1.15, 3.42], 'z', 0.1, 0.45, M.steel, { lw: 0.7, seg: 8 });
      drawSphere(G, xf, [-0.55, 1.15, 3.68], 0.2, M.ledR, { lw: 0.7 });
      drawSphere(G, xf, [0.35, 1.2, 3.24], 0.14, M.ledG, { lw: 0.6 });
      drawSphere(G, xf, [0.75, 1.1, 3.24], 0.14, M.yel, { lw: 0.6 });
      // Upper CRT cabinet with animated game display on py face
      drawBox(G, xf, [-1.35, -1.35, 3.15], [1.35, 0.85, 5.75], cabMat, {
        lw: 1.2,
        py: function (c) {
          c.fillStyle = '#090d1a'; c.fillRect(0.22, 0.25, 2.26, 2.05);
          // Animated retro space/pixel sprites!
          var bx = 0.55 + ((Math.sin(timeSec * 3.1 + (prop.variant || 1)) + 1) * 0.68);
          c.fillStyle = '#38bdf8'; c.fillRect(bx, 1.82, 0.45, 0.18);
          c.fillStyle = '#facc15';
          for (var i = 0; i < 4; i++) {
            c.fillRect(0.42 + i * 0.48, 0.55 + (Math.floor(timeSec * 3 + i) % 2) * 0.15, 0.26, 0.22);
          }
          c.fillStyle = '#f43f5e';
          c.fillRect(bx + 0.18, 0.9 + ((1 - ((timeSec * 2.2) % 1)) * 0.85), 0.09, 0.25);
        }
      });
      // Illuminated top marquee
      drawBox(G, xf, [-1.35, -1.25, 5.75], [1.35, 1.05, 6.35], M.yel, { lw: 1.0 });
      var mq = G.cam.p(xf.p([0, 0.9, 6.05]));
      glowAt(G.ctx, mq[0], mq[1], 7 * LWS, prop.variant === 2 ? 'rgba(192,132,252,0.42)' : 'rgba(56,189,248,0.42)');
    } else if (prop.kind === 'gamingCouch') {
      // Cozy console gaming beanbag/couch
      var shG = shadowPts(G, boxCorners(new Xf(prop.x, prop.y, 0.22, 0), [-2.1, -1.2, 0], [2.1, 1.2, 2.2]), 0.24);
      fillStroke(G, shG, pal.shadow, 0);
      drawBox(G, xf, [-2.0, -1.1, 0.2], [2.0, 1.1, 1.2], pal.arcade2, { lw: 1.1 });
      drawBox(G, xf, [-2.0, 0.55, 1.2], [2.0, 1.2, 2.3], pal.arcade2, { lw: 1.1 });
    } else if (prop.kind === 'teaTable') {
      // Japanese Low Wooden Tea Table + Clay Teapot + Rising Tea Steam + 4 Ceramic Teacups!
      var shT = shadowPts(G, boxCorners(new Xf(prop.x, prop.y, 0.22, 0), [-2.6, -2.1, 0], [2.6, 2.1, 1.8]), 0.24);
      fillStroke(G, shT, pal.shadow, 0);
      drawBox(G, xf, [-2.3, -1.8, 0], [-1.9, -1.4, 1.15], pal.wood, { lw: 0.9 });
      drawBox(G, xf, [1.9, -1.8, 0], [2.3, -1.4, 1.15], pal.wood, { lw: 0.9 });
      drawBox(G, xf, [-2.3, 1.4, 0], [-1.9, 1.8, 1.15], pal.wood, { lw: 0.9 });
      drawBox(G, xf, [1.9, 1.4, 0], [2.3, 1.8, 1.15], pal.wood, { lw: 0.9 });
      drawBox(G, xf, [-2.6, -2.1, 1.15], [2.6, 2.1, 1.55], pal.wood, { topM: pal.deskTop, lw: 1.2 });
      // Clay Kyusu Teapot in center
      drawSphere(G, xf, [0, 0, 2.02], 0.62, pal.pot, { lw: 1.0 });
      drawCyl(G, xf, [0, 0, 2.58], 'z', 0.3, 0.16, pal.pot, { lw: 0.8, seg: 12 });
      // 4 Tiny Jade Tea Cups
      var cupMat = { light: '#a7f3d0', mid: '#34d399', dark: '#059669' };
      drawCyl(G, xf, [-1.35, -0.8, 1.82], 'z', 0.26, 0.45, cupMat, { lw: 0.8, seg: 10 });
      drawCyl(G, xf, [1.35, -0.8, 1.82], 'z', 0.26, 0.45, cupMat, { lw: 0.8, seg: 10 });
      drawCyl(G, xf, [-1.35, 0.9, 1.82], 'z', 0.26, 0.45, cupMat, { lw: 0.8, seg: 10 });
      drawCyl(G, xf, [1.35, 0.9, 1.82], 'z', 0.26, 0.45, cupMat, { lw: 0.8, seg: 10 });
      // Animated rising fragrant tea steam!
      var st1 = (timeSec * 0.65) % 1;
      var st2 = (timeSec * 0.65 + 0.5) % 1;
      var p1 = G.cam.p(xf.p([Math.sin(timeSec * 2) * 0.18, 0, 2.75 + st1 * 2.1]));
      var p2 = G.cam.p(xf.p([Math.cos(timeSec * 1.8) * 0.16, 0.1, 2.75 + st2 * 2.1]));
      glowAt(G.ctx, p1[0], p1[1], 5.2 * LWS, 'rgba(255,255,255,' + ((1 - st1) * 0.36).toFixed(2) + ')');
      glowAt(G.ctx, p2[0], p2[1], 4.2 * LWS, 'rgba(209,250,229,' + ((1 - st2) * 0.32).toFixed(2) + ')');
    } else if (prop.kind === 'plant') {
      var shP = shadowPts(G, cylCorners(new Xf(prop.x, prop.y, 0.2, 0), [0, 0, 1.8], 'z', 1.2, 3.6), 0.22);
      fillStroke(G, shP, pal.shadow, 0);
      drawFrustum(G, xf, [0, 0, 0.85], 'z', 0.85, 1.15, 1.6, pal.pot, { lw: 1.05, seg: 16 });
      drawCyl(G, xf, [0, 0, 2.1], 'z', 0.22, 1.4, pal.wood, { lw: 0.85, seg: 10 });
      drawSphere(G, xf, [0, 0, 3.25], 1.15, pal.plant, { lw: 1.05 });
      drawSphere(G, xf, [0.7, -0.4, 2.85], 0.78, pal.plant, { lw: 0.95 });
      drawSphere(G, xf, [-0.65, 0.45, 2.95], 0.75, pal.plant, { lw: 0.95 });
    }
  }

  var LOUNGE_PROPS = [
    { kind: 'basketballHoop', x: -37.2, y: -18.4 },
    { kind: 'arcadeCab',      x: -35.8, y: -35.5, variant: 1 },
    { kind: 'arcadeCab',      x: -29.2, y: -37.2, variant: 2 },
    { kind: 'gamingCouch',    x: -28.5, y: -25.6 },
    { kind: 'teaTable',       x: -17.2, y: -28.8 },
    { kind: 'plant',          x: -13.2, y: -37.4 },
    { kind: 'plant',          x: -13.2, y: -13.4 }
  ];

  INT.LOUNGE_PROPS = LOUNGE_PROPS;
  INT.drawLoungeFacility = drawLoungeFacility;
})();


// Part 2B: 10 Bespoke Role-Specific 3D Workshops (NO generic desks!) & Animated Action Figurines
(function () {
  var INT = window._SIMULAB_INTERNALS;
  var makeMat = INT.makeMat;

  function drawWorkshop(G, pal, agent, info, actor, timeSec, buildProg, isSelected, isHovered) {
    var pos = INT.STATION_POS[agent.id];
    if (!pos) return;
    var startAt = 0.16 + (pos.buildIdx - 2) * 0.055;
    var prog = backOut(clamp((buildProg - startAt) / 0.24));
    if (prog <= 0.01) return;

    var isForeman = agent.id === 'foreman';
    var dropZ = (1 - prog) * 11;
    var baseZ = (isForeman ? 0.65 : 0.16) + dropZ;
    var xf = new Xf(pos.x, pos.y, baseZ, 0);
    var accentHex = agent.accentColor || '#38bdf8';
    var accentMat = makeMat(accentHex);
    var isHere = isForeman || (actor && actor.pose === 'work');
    var active = isHere && (info.isWorking || isForeman);
    var sk = agent.spriteKey;

    // Ground cast shadow
    var sh = shadowPts(G, boxCorners(new Xf(pos.x, pos.y, isForeman ? 0.65 : 0.16, 0), [-3.2, -2.2, 0], [3.2, 2.2, 4.8]), 0.18);
    fillStroke(G, sh, pal.shadow, 0);

    // Selection/hover ground ring if agent is working here
    if (isHere && (isSelected || isHovered)) {
      var ring = floorEllipse(G, new Xf(pos.x, pos.y, 0.19, 0), [0, 0, 0], isForeman ? 5.2 : 4.5, isForeman ? 4.4 : 3.8, 28);
      fillStroke(G, ring, isSelected ? 'rgba(250,204,21,0.20)' : 'rgba(56,189,248,0.14)', 2.0, isSelected ? '#facc15' : accentHex);
    }

    // Helper: Festive red-and-white Taiwanese Night Market lantern pair!
    function drawLanterns(yBack, zH) {
      var lanMat = { light: '#f87171', mid: '#dc2626', dark: '#7f1d1d' };
      drawSphere(G, xf, [-2.7, yBack, zH], 0.44, lanMat, { lw: 0.85 });
      drawSphere(G, xf, [2.7, yBack, zH], 0.44, lanMat, { lw: 0.85 });
      var l1 = G.cam.p(xf.p([-2.7, yBack, zH])), l2 = G.cam.p(xf.p([2.7, yBack, zH]));
      glowAt(G.ctx, l1[0], l1[1], 6.5 * LWS, 'rgba(251,146,60,0.34)');
      glowAt(G.ctx, l2[0], l2[1], 6.5 * LWS, 'rgba(251,146,60,0.34)');
    }

    // --- 10 Taiwanese Night Market Game Stalls ---
    var redM = { light: '#f87171', mid: '#dc2626', dark: '#991b1b' };
    var waterM = { light: '#7dd3fc', mid: '#38bdf8', dark: '#0284c7' };
    var goldFishM = { light: '#fdba74', mid: '#f97316', dark: '#c2410c' };

    if (sk === 'foreman') {
      // Foreman: Night Market HQ & Prize Redemption Booth + Red Lantern Arch + Lever
      drawPrism(G, new Xf(pos.x, pos.y, 0.16 + dropZ, 0), rrPlan(-4.4, -3.2, 4.4, 2.6, 0.7, 3), 0, 0.5, M.brass, { lw: 1.3 });
      drawBox(G, xf, [-3.3, -2.2, 0], [-2.9, -1.8, 5.4], redM, { lw: 0.9 });
      drawBox(G, xf, [2.9, -2.2, 0], [3.3, -1.8, 5.4], redM, { lw: 0.9 });
      drawBox(G, xf, [-3.5, -2.3, 5.2], [3.5, -1.6, 6.0], redM, { lw: 1.1 });
      drawLanterns(-1.6, 4.7);
      drawActionFigurine(G, new Xf(pos.x, pos.y - 1.5, baseZ, 0), accentMat, 'foreman', 'work', active, info.isBlocked, timeSec, 0, null);
      drawBox(G, xf, [-3.4, -0.8, 0], [3.4, 1.5, 2.35], redM, { topM: pal.deskTop, lw: 1.25 });
      drawBox(G, xf, [2.1, -0.4, 2.35], [3.1, 0.7, 2.9], M.steel, { lw: 1.0 });
      drawCyl(G, xf, [2.6, 0.15, 3.5], 'z', 0.12, 1.2, M.steel, { lw: 0.8, seg: 10 });
      drawSphere(G, xf, [2.6, 0.15, 4.2], 0.36, info.isBlocked ? M.ledR : M.ledG, { lw: 1.0 });
    } else if (sk === 'portal') {
      // 🐠 Goldfish Scooping Stall (撈金魚)
      drawBox(G, xf, [-3.3, -2.2, 0], [3.3, 0.7, 1.55], M.white, { lw: 1.2 });
      drawBox(G, xf, [-3.0, -1.9, 1.3], [3.0, 0.4, 1.62], waterM, {
        lw: 0.9,
        top: function (c) {
          c.fillStyle = '#38bdf8'; c.fillRect(0.1, 0.1, 5.8, 2.1);
          // 5 swimming orange/gold fish!
          for (var fi = 0; fi < 5; fi++) {
            var fa = timeSec * (active ? 2.4 : 0.9) + fi * 1.3;
            var fx = 2.9 + Math.cos(fa) * (1.2 + (fi % 2) * 0.9);
            var fy = 1.15 + Math.sin(fa * 1.3) * 0.65;
            c.fillStyle = (fi % 2 === 0) ? '#f97316' : '#facc15';
            c.beginPath(); c.ellipse(fx, fy, 0.32, 0.16, fa, 0, Math.PI * 2); c.fill();
          }
        }
      });
      // Bowl + stall corner poles & lanterns
      drawCyl(G, xf, [2.3, 0.1, 1.82], 'z', 0.52, 0.45, redM, { lw: 0.85, seg: 14 });
      drawBox(G, xf, [-3.1, -2.2, 1.55], [-2.85, -1.95, 4.8], pal.wood, { lw: 0.8 });
      drawBox(G, xf, [2.85, -2.2, 1.55], [3.1, -1.95, 4.8], pal.wood, { lw: 0.8 });
      drawBox(G, xf, [-3.3, -2.35, 4.65], [3.3, -1.55, 5.2], redM, { lw: 1.0 });
      drawLanterns(-1.6, 4.25);
    } else if (sk === 'share') {
      // 🎯 Balloon Dart Stall (射飛鏢氣球牆)
      drawBox(G, xf, [-3.2, -2.1, 0], [3.2, -1.45, 5.4], pal.wood, { lw: 1.2 });
      drawBox(G, xf, [-3.3, -2.3, 5.3], [3.3, -1.2, 5.85], redM, { lw: 1.0 });
      // 12 colorful balloons pinned to wall (popping & regenerating when active!)
      var bCols = ['#ef4444', '#facc15', '#3b82f6', '#22c55e', '#ec4899', '#a855f7'];
      var poppedIdx = active ? (Math.floor(timeSec * 2.5) % 12) : -1;
      for (var bi = 0; bi < 12; bi++) {
        if (bi === poppedIdx) continue;
        var bx = -2.25 + (bi % 4) * 1.5;
        var bz = 2.0 + Math.floor(bi / 4) * 1.15;
        drawSphere(G, xf, [bx, -1.22, bz], 0.42, makeMat(bCols[bi % bCols.length]), { lw: 0.8 });
      }
      drawBox(G, xf, [-3.1, -0.35, 0], [3.1, 0.45, 1.8], redM, { topM: pal.deskTop, lw: 1.0 }); // Counter
      drawLanterns(-1.2, 4.95);
    } else if (sk === 'revival') {
      // ⭕ Ring Toss Stall (套圈圈)
      drawBox(G, xf, [-3.2, -2.3, 0], [3.2, 0.2, 1.1], redM, { lw: 1.15 });
      drawBox(G, xf, [-2.8, -2.2, 1.1], [2.8, -0.6, 2.05], redM, { lw: 1.1 });
      drawBox(G, xf, [-2.3, -2.1, 2.05], [2.3, -1.2, 2.95], redM, { lw: 1.05 });
      // Colorful prize bottles & gold trophy on stepped red platform!
      var pCols = ['#22c55e', '#38bdf8', '#facc15', '#ec4899', '#a855f7'];
      for (var pi = 0; pi < 5; pi++) {
        drawCyl(G, xf, [-2.2 + pi * 1.1, -0.2, 1.72], 'z', 0.24, 1.15, makeMat(pCols[pi]), { lw: 0.8, seg: 10 });
      }
      for (var pj = 0; pj < 4; pj++) {
        drawCyl(G, xf, [-1.65 + pj * 1.1, -1.0, 2.7], 'z', 0.26, 1.2, makeMat(pCols[(pj + 2) % 5]), { lw: 0.8, seg: 10 });
      }
      drawCyl(G, xf, [0, -1.65, 3.65], 'z', 0.42, 1.25, M.brass, { lw: 0.9, seg: 14 }); // Top grand prize!
      // Tossed colorful rings landing around bottles
      drawCyl(G, xf, [-1.1, -0.2, 1.25], 'z', 0.48, 0.12, M.yel, { lw: 0.75, seg: 12 });
      drawCyl(G, xf, [1.1, -1.0, 2.18], 'z', 0.48, 0.12, M.ledG, { lw: 0.75, seg: 12 });
      drawLanterns(-1.9, 4.4);
    } else if (sk === 'kb') {
      // 🔮 Retro Taiwanese Pinball / Marble Machine (復古彈珠台)
      drawBox(G, xf, [-3.1, -2.2, 0], [3.1, 0.5, 2.2], pal.wood, { lw: 1.2 });
      // Elevated sloped pinball backboard with nails & bouncing glowing marble!
      drawBox(G, xf, [-2.85, -2.1, 2.2], [2.85, -0.9, 4.75], pal.wood, {
        lw: 1.15,
        py: function (c) {
          c.fillStyle = '#1e293b'; c.fillRect(0.25, 0.2, 5.2, 2.15);
          // Nail peg grid
          c.fillStyle = '#e2e8f0';
          for (var r = 0; r < 4; r++) {
            for (var col = 0; col < 7; col++) {
              c.beginPath(); c.arc(0.65 + col * 0.72 + (r % 2) * 0.34, 0.45 + r * 0.46, 0.08, 0, Math.PI * 2); c.fill();
            }
          }
          // Glowing bouncing marble!
          var mp = (timeSec * (active ? 1.8 : 0.5)) % 1;
          var mx = 2.85 + Math.sin(mp * 18) * 1.65;
          var my = 0.35 + mp * 1.85;
          c.fillStyle = '#facc15';
          c.beginPath(); c.arc(mx, my, 0.2, 0, Math.PI * 2); c.fill();
        }
      });
      // Spring plunger lever on right front
      var pull = active ? Math.sin(timeSec * 7.5) * 0.35 : 0;
      drawCyl(G, xf, [2.1, 0.8 + pull, 1.9], 'y', 0.16, 1.1, M.white, { lw: 0.8, seg: 10 });
      drawLanterns(-1.6, 5.1);
    } else if (sk === 'decision') {
      // 🔫 Air Rifle Shooting Gallery (空氣槍射擊攤)
      drawBox(G, xf, [-3.2, -2.2, 0], [3.2, -1.2, 2.2], M.blk, { lw: 1.15 });
      drawBox(G, xf, [-3.2, -2.2, 2.2], [3.2, -1.75, 5.2], M.blk, { lw: 1.1 });
      drawBox(G, xf, [-3.3, -2.3, 5.1], [3.3, -1.2, 5.65], M.yel, { lw: 1.0 });
      // 5 knock-down targets on rail!
      var downIdx = active ? (Math.floor(timeSec * 2.2) % 5) : -1;
      for (var ti = 0; ti < 5; ti++) {
        var tx = -2.2 + ti * 1.1;
        var th = (ti === downIdx) ? 0.3 : 1.15;
        drawBox(G, xf, [tx - 0.28, -1.55, 2.3], [tx + 0.28, -1.25, 2.3 + th], (ti % 2 === 0) ? M.ledR : M.yel, { lw: 0.85 });
      }
      drawBox(G, xf, [-3.0, -0.1, 0], [3.0, 0.65, 1.85], pal.wood, { lw: 1.0 });
      drawLanterns(-1.3, 4.75);
    } else if (sk === 'stock') {
      // 🧸 Neon Claw Machine (夾娃娃機)
      drawBox(G, xf, [-2.3, -2.1, 0], [2.3, 0.6, 2.45], { light: '#f472b6', mid: '#db2777', dark: '#831843' }, { lw: 1.2 });
      // Transparent glass cabinet + plushies inside!
      drawBox(G, xf, [-2.2, -2.0, 2.45], [2.2, 0.5, 5.65], M.acr, { lw: 1.05 });
      var plushCols = ['#facc15', '#38bdf8', '#4ade80', '#fb923c', '#c084fc'];
      for (var pl = 0; pl < 5; pl++) {
        drawSphere(G, xf, [-1.4 + pl * 0.7, -0.75 + (pl % 2) * 0.45, 2.95], 0.44, makeMat(plushCols[pl]), { lw: 0.75 });
      }
      // Animated moving metal claw crane!
      var clX = active ? Math.sin(timeSec * 2.1) * 1.35 : 0;
      var clDrop = active ? (0.5 + 0.5 * Math.sin(timeSec * 3.4)) * 1.25 : 0;
      drawCyl(G, xf, [clX, -0.75, 5.2 - clDrop * 0.5], 'z', 0.1, 0.9 + clDrop, M.steel, { lw: 0.8, seg: 8 });
      drawFrustum(G, xf, [clX, -0.75, 4.65 - clDrop], 'z', 0.52, 0.18, 0.55, M.steel, { lw: 0.9, seg: 10 });
      drawBox(G, xf, [-2.35, -2.15, 5.65], [2.35, 0.65, 6.25], { light: '#38bdf8', mid: '#0284c7', dark: '#0c4a6e' }, { lw: 1.1 });
      var cmq = G.cam.p(xf.p([0, 0.6, 5.95]));
      glowAt(G.ctx, cmq[0], cmq[1], 8 * LWS, 'rgba(244,114,182,0.42)');
    } else if (sk === 'market') {
      // 🎰 Mahjong Bingo Stall (麻將賓果攤)
      drawBox(G, xf, [-3.1, -2.1, 0], [3.1, 0.6, 2.15], redM, {
        lw: 1.2,
        top: function (c) {
          c.fillStyle = '#991b1b'; c.fillRect(0.2, 0.2, 5.8, 2.3);
          // 4x4 glowing ivory Mahjong tiles!
          var lit = active ? (Math.floor(timeSec * 3.0) % 16) : -1;
          for (var mr = 0; mr < 3; mr++) {
            for (var mc = 0; mc < 6; mc++) {
              var idx = mr * 6 + mc;
              c.fillStyle = (idx === lit) ? '#fde047' : '#fffbeb';
              c.fillRect(0.45 + mc * 0.88, 0.35 + mr * 0.72, 0.68, 0.52);
              c.fillStyle = (idx % 2 === 0) ? '#dc2626' : '#16a34a';
              c.fillRect(0.68 + mc * 0.88, 0.52 + mr * 0.72, 0.22, 0.18);
            }
          }
        }
      });
      drawLanterns(-1.8, 4.2);
    } else if (sk === 'risk') {
      // 🔨 Whac-A-Mole Arcade Stall (打地鼠機台)
      drawBox(G, xf, [-2.8, -2.0, 0], [2.8, 0.6, 2.25], M.yel, { topM: redM, lw: 1.2 });
      drawBox(G, xf, [-2.8, -2.1, 2.25], [2.8, -1.5, 4.45], redM, { lw: 1.1 });
      // 5 mole holes with animated popping brown moles!
      var moleMat = { light: '#b47b4e', mid: '#854d27', dark: '#542f16' };
      var mPos = [[-1.5, -0.9], [0, -0.9], [1.5, -0.9], [-0.8, 0.0], [0.8, 0.0]];
      for (var mi = 0; mi < 5; mi++) {
        drawCyl(G, xf, [mPos[mi][0], mPos[mi][1], 2.28], 'z', 0.44, 0.1, M.blk, { lw: 0.7, seg: 12 });
        var pop = active ? Math.max(0, Math.sin(timeSec * 5.2 + mi * 1.7)) : (mi % 2 === 0 ? 0.55 : 0);
        if (pop > 0.15) {
          drawCyl(G, xf, [mPos[mi][0], mPos[mi][1], 2.3 + pop * 0.5], 'z', 0.32, pop * 0.95, moleMat, { lw: 0.85, seg: 12 });
          drawSphere(G, xf, [mPos[mi][0], mPos[mi][1], 2.35 + pop * 0.95], 0.32, moleMat, { lw: 0.85 });
        }
      }
      drawLanterns(-1.6, 4.65);
    } else if (sk === 'platform') {
      // ⚾ 9-Square Baseball Toss Stall (九宮格棒球投準)
      drawBox(G, xf, [-3.1, -2.2, 0], [3.1, -1.4, 5.5], { light: '#60a5fa', mid: '#2563eb', dark: '#1e3a8a' }, {
        lw: 1.2,
        py: function (c) {
          c.fillStyle = '#0f172a'; c.fillRect(0.3, 0.3, 5.6, 4.9);
          var hitSq = active ? (Math.floor(timeSec * 2.0) % 9) : -1;
          for (var sq = 0; sq < 9; sq++) {
            var sx = 0.55 + (sq % 3) * 1.75;
            var sy = 0.55 + Math.floor(sq / 3) * 1.5;
            c.fillStyle = (sq === hitSq) ? '#1e293b' : ((sq % 2 === 0) ? '#f8fafc' : '#fde047');
            c.fillRect(sx, sy, 1.5, 1.25);
            if (sq !== hitSq) {
              c.font = '800 0.78px monospace'; c.fillStyle = '#1e293b';
              c.fillText(String(sq + 1), sx + 0.52, sy + 0.9);
            }
          }
        }
      });
      // Bucket of baseballs on side
      drawCyl(G, xf, [2.5, 0.4, 0.7], 'z', 0.65, 1.25, M.white, { lw: 0.95, seg: 14 });
      drawSphere(G, xf, [2.35, 0.35, 1.45], 0.25, M.white, { lw: 0.7 });
      drawSphere(G, xf, [2.7, 0.45, 1.45], 0.25, M.white, { lw: 0.7 });
      drawLanterns(-1.5, 5.65);
    } else if (sk === 'intern') {
      // 🎈 Yo-Yo Water Balloon Fishing + Study Notebook Stand (釣水球與學習筆記攤)
      var cyanRim = { light: '#67e8f9', mid: '#06b6d4', dark: '#0e7490' };
      var waterMat = { light: '#bae6fd', mid: '#38bdf8', dark: '#0284c7' };
      drawCyl(G, xf, [-0.5, -0.8, 0.75], 'z', 2.35, 1.5, cyanRim, { lw: 1.15, seg: 20 });
      drawCyl(G, xf, [-0.5, -0.8, 1.45], 'z', 2.05, 0.22, waterMat, { lw: 0.85, seg: 20 });
      var yoyoCols = ['#f472b6', '#facc15', '#a78bfa', '#4ade80', '#fb923c'];
      for (var yi = 0; yi < 5; yi++) {
        var ang = yi * 1.25 + timeSec * (active ? 0.9 : 0.25);
        var yx = -0.5 + Math.cos(ang) * 1.15;
        var yy = -0.8 + Math.sin(ang) * 1.05;
        var yz = 1.85 + Math.sin(timeSec * 3.8 + yi) * 0.14;
        drawSphere(G, xf, [yx, yy, yz], 0.42, makeMat(yoyoCols[yi]), { lw: 0.8 });
      }
      // Side study podium with open notebook for logging team learnings!
      drawBox(G, xf, [1.85, -1.6, 0], [3.15, -0.2, 2.3], pal.wood, { lw: 1.0 });
      drawBox(G, xf, [1.95, -1.45, 2.3], [3.05, -0.35, 2.52], M.white, { lw: 0.85 });
      drawLanterns(-1.8, 4.3);
    }

    // Status beacon post on corner of every workshop
    var bMat = info.isBlocked ? M.ledR : (info.isWorking ? M.ledG : (info.isQueued ? M.cellB : M.can));
    drawCyl(G, xf, [-3.3, 1.6, 0.7], 'z', 0.22, 1.4, M.steel, { lw: 0.8, seg: 10 });
    drawSphere(G, xf, [-3.3, 1.6, 1.55], 0.34, bMat, { lw: 0.9 });
    if (info.isWorking || info.isBlocked) {
      var bp = G.cam.p(xf.p([-3.3, 1.6, 1.55]));
      glowAt(G.ctx, bp[0], bp[1], 7 * LWS, info.isBlocked ? 'rgba(239,68,68,0.65)' : 'rgba(34,197,94,0.55)');
    }
  }

  function drawHead(G, fxf, hx, hy, hz, skinMat, hairMat, spriteKey) {
    drawSphere(G, fxf, [hx, hy, hz], 0.98, skinMat, { lw: 1.3 });
    if (spriteKey === 'foreman') {
      drawCyl(G, fxf, [hx, hy, hz + 0.65], 'z', 1.16, 0.22, M.hub, { lw: 1.1, seg: 18 });
      drawSphere(G, fxf, [hx, hy, hz + 0.8], 0.86, M.yel, { lw: 1.2 });
    } else if (spriteKey === 'decision' || spriteKey === 'platform') {
      drawCyl(G, fxf, [hx, hy, hz + 0.7], 'z', 0.96, 0.25, hairMat, { lw: 1.0, seg: 16 });
      drawBox(G, fxf, [hx - 0.82, hy + 0.68, hz - 0.1], [hx + 0.82, hy + 1.02, hz + 0.27], M.term, { lw: 0.9 });
    } else if (spriteKey === 'intern') {
      // Student cap + fresh cyan badge!
      drawSphere(G, fxf, [hx - 0.06, hy - 0.12, hz + 0.48], 0.84, hairMat, { lw: 1.05 });
      drawBox(G, fxf, [hx - 0.95, hy - 0.95, hz + 0.82], [hx + 0.95, hy + 0.95, hz + 1.02], makeMat('#06b6d4'), { lw: 0.95 });
    } else {
      drawSphere(G, fxf, [hx - 0.08, hy - 0.16, hz + 0.47], 0.82, hairMat, { lw: 1.1 });
    }
  }

  // Draws articulated 3D Figurine with Role-Specific Working Animations & Lounge Activities!
  function drawActionFigurine(G, xf, accentMat, sk, pose, isWorking, isBlocked, timeSec, walkPhase, loungeAct) {
    var skinMat = { light: '#ffe3c4', mid: '#f3c396', dark: '#c99366' };
    var hairMat = { light: '#475569', mid: '#262d3d', dark: '#111622' };
    var pantsMat = { light: '#334155', mid: '#1e293b', dark: '#0f172a' };

    var isWalk = (pose === 'walk');
    var isWork = (pose === 'work');
    var isBball = (pose === 'lounge' && loungeAct === 'basketball');
    var isArcade = (pose === 'lounge' && (loungeAct === 'arcade' || loungeAct === 'gaming'));
    var isTea = (pose === 'lounge' && loungeAct === 'tea');

    // Dynamic body motion per activity!
    var stride = isWalk ? Math.sin(walkPhase) * 0.48 : (isWork && (sk === 'kb' || sk === 'platform' || sk === 'market') ? Math.sin(timeSec * 5.2) * 0.32 : 0);
    var shiftX = (isWork && (sk === 'portal' || sk === 'share' || sk === 'stock' || sk === 'kb' || sk === 'platform')) ? Math.sin(timeSec * 2.8) * 1.05 : 0;
    var hop = isWalk ? Math.abs(Math.sin(walkPhase)) * 0.35
      : (isBball ? Math.abs(Math.sin(timeSec * 4.2)) * 0.55
      : (isWork ? Math.abs(Math.sin(timeSec * 6.0)) * 0.22
      : (pose === 'reporting' ? Math.abs(Math.sin(timeSec * 4.5)) * 0.18 : Math.sin(timeSec * 2.0) * 0.07)));

    var baseXf = new Xf(xf.x + shiftX, xf.y, xf.z, 0);
    var bodyXf = baseXf.lift(hop);

    // Legs (seated crouch when tea/gaming, striding when walking/carrying/basketball!)
    var legTop = isTea ? 1.05 : 1.55;
    drawBox(G, baseXf, [-0.65, -0.35 + stride, 0.05], [-0.12, 0.35 + stride, legTop], pantsMat, { lw: 1.0 });
    drawBox(G, baseXf, [0.12, -0.35 - stride, 0.05], [0.65, 0.35 - stride, legTop], pantsMat, { lw: 1.0 });

    // Torso
    var tBot = legTop;
    var tTop = tBot + 1.85;
    drawBox(G, bodyXf, [-0.92, -0.58, tBot], [0.92, 0.58, tTop], accentMat, { lw: 1.25 });

    // Arms + Role-Matched Props!
    var aL = isWalk ? -stride * 0.9 : (isWork ? Math.sin(timeSec * 7.5) * 0.45 : (isArcade ? Math.sin(timeSec * 12) * 0.22 : 0));
    var aR = isWalk ? stride * 0.9 : (isWork ? -Math.sin(timeSec * 7.5) * 0.45 : (isArcade ? -Math.sin(timeSec * 12) * 0.22 : 0));
    drawBox(G, bodyXf, [-1.32, -0.32 + aL * 0.5, tBot + 0.3 + aL * 0.35], [-0.92, 0.32 + aL * 0.5, tTop - 0.2 + aL * 0.35], accentMat, { lw: 1.05 });
    drawBox(G, bodyXf, [0.92, -0.32 + aR * 0.5, tBot + 0.3 + aR * 0.35], [1.32, 0.32 + aR * 0.5, tTop - 0.2 + aR * 0.35], accentMat, { lw: 1.05 });

    // --- Taiwanese Night Market Game Action Props! ---
    if (isWork) {
      if (sk === 'portal') {
        // 🐠 Paper goldfish scoop (撈魚紙網勺) dipping gently across the pool!
        var dip = Math.sin(timeSec * 4.5) * 0.45;
        drawCyl(G, bodyXf, [1.15, -1.05, 1.9 + dip * 0.4], 'y', 0.08, 1.3, M.ledR, { lw: 0.7, seg: 8 });
        drawCyl(G, bodyXf, [1.15, -1.85, 1.85 + dip * 0.4], 'z', 0.52, 0.1, M.white, { lw: 0.85, seg: 12 });
      } else if (sk === 'share') {
        // 🎯 Throwing a dart flying toward the balloon wall!
        var dFly = (timeSec * 2.2) % 1;
        drawCyl(G, bodyXf, [1.1, -0.8 - dFly * 2.2, 3.1 + Math.sin(dFly * Math.PI) * 0.55], 'y', 0.09, 0.85, M.ledR, { lw: 0.75, seg: 8 });
      } else if (sk === 'revival') {
        // ⭕ Tossing colorful plastic ring in a parabolic arc!
        var rFly = (timeSec * 1.9) % 1;
        drawCyl(G, bodyXf, [0.9 - rFly * 0.6, -0.7 - rFly * 2.2, 2.7 + Math.sin(rFly * Math.PI) * 1.65], 'z', 0.54, 0.14, M.yel, { lw: 0.85, seg: 14 });
      } else if (sk === 'kb') {
        // 🔮 Pulling pinball spring launcher!
        drawSphere(G, bodyXf, [1.15, -0.95, 2.25 + Math.sin(timeSec * 7.5) * 0.25], 0.28, M.yel, { lw: 0.75 });
      } else if (sk === 'decision') {
        // 🔫 Aiming toy air rifle toward targets!
        drawBox(G, bodyXf, [0.75, -2.05, 2.75], [1.15, -0.35, 3.05], M.blk, { lw: 0.85 });
        if (Math.sin(timeSec * 14) > 0.7) {
          var mz = G.cam.p(bodyXf.p([0.95, -2.2, 2.9]));
          glowAt(G.ctx, mz[0], mz[1], 7 * LWS, 'rgba(250,204,21,0.85)');
        }
      } else if (sk === 'stock') {
        // 🧸 Working claw machine joystick & button!
        drawCyl(G, bodyXf, [0.85, -0.95, 2.35], 'z', 0.12, 0.55, M.ledR, { lw: 0.75, seg: 8 });
      } else if (sk === 'market') {
        // 🎰 Placing ivory Mahjong tile on bingo board!
        drawBox(G, bodyXf, [0.85, -1.15, 2.3 + Math.abs(Math.sin(timeSec * 4.5)) * 0.4], [1.45, -0.65, 2.65 + Math.abs(Math.sin(timeSec * 4.5)) * 0.4], M.white, { lw: 0.8 });
      } else if (sk === 'risk') {
        // 🔨 Swinging giant red inflatable Whac-A-Mole mallet!
        var swingZ = 2.6 + Math.sin(timeSec * 11.0) * 1.05;
        drawCyl(G, bodyXf, [1.15, -0.85, swingZ - 0.3], 'z', 0.1, 1.15, M.yel, { lw: 0.7, seg: 8 });
        drawCyl(G, bodyXf, [1.15, -1.05, swingZ + 0.45], 'x', 0.42, 1.05, M.ledR, { lw: 0.9, seg: 12 });
      } else if (sk === 'platform') {
        // ⚾ Pitching white baseball in an arc toward the 9-square board!
        var pFly = (timeSec * 2.0) % 1;
        drawSphere(G, bodyXf, [1.0 - pFly * 0.8, -0.6 - pFly * 2.4, 3.0 + Math.sin(pFly * Math.PI) * 1.1], 0.32, M.white, { lw: 0.85 });
      } else if (sk === 'intern') {
        // 🎈 Fishing a bouncy Yo-Yo water balloon + holding study notebook!
        var yBob = Math.sin(timeSec * 5.2) * 0.42;
        drawCyl(G, bodyXf, [1.1, -1.0, 2.35 + yBob * 0.3], 'y', 0.06, 1.25, M.white, { lw: 0.65, seg: 8 });
        drawSphere(G, bodyXf, [1.1, -1.75, 1.9 + yBob * 0.45], 0.36, makeMat('#f472b6'), { lw: 0.8 });
        drawBox(G, bodyXf, [-1.55, -0.85, 2.2], [-0.92, -0.15, 2.85], M.white, { lw: 0.8 });
      }
    }

    // --- Lounge Leisure Props! ---
    if (isBball) {
      // Animated bouncing orange 3D basketball!
      var ballZ = 0.55 + Math.abs(Math.sin(timeSec * 5.2)) * 2.5;
      drawSphere(G, baseXf, [1.45, 0.55, ballZ], 0.56, { light: '#fb923c', mid: '#ea580c', dark: '#9a3412' }, { lw: 1.0 });
    } else if (isArcade) {
      // Gamepad controller in hands
      drawBox(G, bodyXf, [-0.75, -0.95, 2.25], [0.75, -0.45, 2.6], M.blk, { lw: 0.85 });
    } else if (isTea) {
      // Warm ceramic jade teacup in hand!
      drawCyl(G, bodyXf, [1.18, 0.42, tBot + 0.7], 'z', 0.26, 0.48, { light: '#a7f3d0', mid: '#34d399', dark: '#059669' }, { lw: 0.85, seg: 10 });
    }

    // Briefing or Reporting at Foreman: holding clipboard/tablet
    if (pose === 'briefing' || pose === 'reporting') {
      drawBox(G, bodyXf, [0.85, -0.75, 2.25], [1.62, 0.05, 2.95], pose === 'reporting' ? M.yel : M.cellB, { lw: 0.9 });
    }

    drawHead(G, bodyXf, 0, 0, tTop + 0.88, skinMat, hairMat, sk);
  }

  function drawRoamingActor(G, pal, agent, actor, info, timeSec, buildProg, isSelected, isHovered) {
    var prog = backOut(clamp((buildProg - 0.28) / 0.25));
    if (prog <= 0.01) return;
    var dropZ = (1 - prog) * 9;
    var xf = new Xf(actor.x, actor.y, 0.22 + dropZ, 0);
    var accentHex = agent.accentColor || '#38bdf8';
    var accentMat = makeMat(accentHex);

    var sh = floorEllipse(G, new Xf(actor.x, actor.y, 0.22, 0), [0.3, 0.3, 0], 1.45, 1.15, 18);
    fillStroke(G, sh, pal.shadow, 0);

    if (isSelected || isHovered || actor.pose === 'briefing' || actor.pose === 'reporting') {
      var ringCol = isSelected ? '#facc15' : (actor.pose === 'reporting' ? '#f97316' : (actor.pose === 'briefing' ? '#a78bfa' : accentHex));
      var ringFill = isSelected ? 'rgba(250,204,21,0.22)' : (actor.pose === 'reporting' ? 'rgba(249,115,22,0.18)' : 'rgba(167,139,250,0.16)');
      var ring = floorEllipse(G, new Xf(actor.x, actor.y, 0.23, 0), [0, 0, 0], 2.15, 1.85, 22);
      fillStroke(G, ring, ringFill, 1.8, ringCol);
    }

    if (actor.pose === 'briefing' || actor.pose === 'reporting') {
      var fPos = INT.STATION_POS['foreman'];
      var pFrom = G.cam.p([fPos.x, fPos.y + 1.2, 3.6]);
      var pTo = G.cam.p([actor.x, actor.y, 3.4]);
      var ctx = G.ctx;
      ctx.save();
      ctx.strokeStyle = actor.pose === 'reporting' ? 'rgba(251, 146, 60, 0.75)' : 'rgba(167, 139, 250, 0.8)';
      ctx.lineWidth = 2.0 * LWS;
      ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(pFrom[0], pFrom[1]); ctx.lineTo(pTo[0], pTo[1]); ctx.stroke();
      ctx.restore();
      var ph = (timeSec * 0.9) % 1;
      var tDot = actor.pose === 'reporting' ? (1 - ph) : ph;
      glowAt(ctx, lerp(pFrom[0], pTo[0], tDot), lerp(pFrom[1], pTo[1], tDot), 6.2 * LWS,
        actor.pose === 'reporting' ? 'rgba(251,146,60,0.95)' : 'rgba(196,181,253,0.95)');
    }

    var lSlot = INT.LOUNGE_SLOTS[agent.id];
    drawActionFigurine(G, xf, accentMat, agent.spriteKey, actor.pose, info.isWorking, info.isBlocked, timeSec, actor.walkPhase || 0, lSlot ? lSlot.activity : null);
  }

  INT.drawWorkshop = drawWorkshop;
  INT.drawRoamingActor = drawRoamingActor;
})();


// Part 3: Spatial State Machine (Big Lounge <-> Foreman <-> Bespoke Workshops) & Lifecycle Demo
(function () {
  var INT = window._SIMULAB_INTERNALS;
  var STATION_POS = INT.STATION_POS;
  var LOUNGE_SLOTS = INT.LOUNGE_SLOTS;
  var FOREMAN_MEET_SLOTS = INT.FOREMAN_MEET_SLOTS;
  var LOUNGE_PROPS = INT.LOUNGE_PROPS;
  var MONGO_POS = INT.MONGO_POS;

  var ctrl = {
    canvas: null, overlay: null, ctx: null, rafId: null,
    active: false, activeOnly: false, data: null,
    selectedAgentId: null, hoveredAgentId: null,
    onSelectAgent: null, getBubbleMeta: null,
    hitBoxes: [], calloutEls: {}, labelEls: {},
    buildStartMs: 0, buildDurationMs: 1750, lastFrameMs: 0,
    actors: {}, demo: null,
    camCur: { zoom: 11.2, tx: -5, ty: -5, tz: 2.0 },
    camDst: { zoom: 11.2, tx: -5, ty: -5, tz: 2.0 },
    userPan: { dx: 0, dy: 0, dz: 1 },
    dragging: false, dragMoved: false, dragLast: [0, 0]
  };

  function defaultCamForWidth(w, h) {
    // Fit the expanded [-42..34] studio cleanly with generous breathing room
    var zx = (w - 86) / 88;
    var zy = (h - 92) / 44;
    var z = clamp(Math.min(zx, zy), 6.8, 13.8);
    return { zoom: z, tx: -5.0, ty: -5.0, tz: 2.0 };
  }

  function agentLivePos(agentId) {
    var actor = ctrl.actors[agentId];
    if (actor) return { x: actor.x, y: actor.y };
    var sp = STATION_POS[agentId];
    return sp ? { x: sp.x, y: sp.y } : { x: 0, y: 0 };
  }

  function updateTargetCamera() {
    if (!ctrl.canvas) return;
    var w = ctrl.canvas.clientWidth || 1200;
    var h = ctrl.canvas.clientHeight || 520;
    var base = defaultCamForWidth(w, h);
    if (ctrl.selectedAgentId && STATION_POS[ctrl.selectedAgentId]) {
      var lp = agentLivePos(ctrl.selectedAgentId);
      ctrl.camDst = { zoom: Math.min(22, base.zoom * 1.72), tx: lp.x, ty: lp.y, tz: 2.6 };
      ctrl.userPan = { dx: 0, dy: 0, dz: 1 };
    } else {
      ctrl.camDst = {
        zoom: base.zoom * ctrl.userPan.dz,
        tx: base.tx + ctrl.userPan.dx,
        ty: base.ty + ctrl.userPan.dy,
        tz: base.tz
      };
    }
  }

  function computeModel() {
    var d = ctrl.data || { agents: [], tasks: [], meta: {} };
    var agents = d.agents || [], tasks = d.tasks || [];
    var agentInfo = {}, doingCount = 0, blockedCount = 0, queuedCount = 0;

    agents.forEach(function (a) {
      agentInfo[a.id] = { isWorking: false, isBlocked: false, isQueued: false, isDone: a.status === 'done', counts: { todo: 0, in_progress: 0, blocked: 0, done: 0 } };
    });
    tasks.forEach(function (t) {
      if (t.status === 'in_progress') doingCount++;
      if (t.status === 'blocked') blockedCount++;
      if ((t.status === 'todo' || t.approval === 'approved') && t.dispatch === 'queued') queuedCount++;
      var info = agentInfo[t.agentId];
      if (!info) return;
      if (info.counts[t.status] !== undefined) info.counts[t.status]++;
      if (t.status === 'blocked') info.isBlocked = true;
      if (t.status === 'in_progress') info.isWorking = true;
      if (t.status === 'todo' && t.dispatch === 'queued') info.isQueued = true;
    });
    agents.forEach(function (a) {
      var info = agentInfo[a.id];
      if (a.status === 'blocked') info.isBlocked = true;
      if (a.status === 'working') info.isWorking = true;
    });
    return {
      agents: agents, tasks: tasks, agentInfo: agentInfo,
      doingCount: doingCount, blockedCount: blockedCount, queuedCount: queuedCount,
      revision: (d.meta && d.meta.revision) || 0,
      selectedAgentId: ctrl.selectedAgentId, hoveredAgentId: ctrl.hoveredAgentId, activeOnly: ctrl.activeOnly
    };
  }

  function buildCorridorPath(fromX, fromY, toX, toY) {
    var pts = [];
    // Route smoothly around Foreman podium (-4, -4) when moving between Back Lounge and Front Plaza/Wings
    if ((fromX < -10 && fromY < -10) !== (toX < -10 && toY < -10)) {
      if (toX < toY) pts.push({ x: -12.5, y: -4.5 });
      else pts.push({ x: -4.5, y: -12.5 });
    }
    pts.push({ x: toX, y: toY });
    return pts;
  }

  function foremanSlotFor(agentId, agents) {
    var idx = 0;
    for (var i = 0; i < agents.length; i++) {
      if (agents[i].id === 'foreman') continue;
      if (agents[i].id === agentId) break;
      idx++;
    }
    return FOREMAN_MEET_SLOTS[idx % FOREMAN_MEET_SLOTS.length];
  }

  function workStandPos(agentId) {
    var sp = STATION_POS[agentId] || { x: 0, y: 0 };
    if (agentId === 'foreman') return { x: sp.x, y: sp.y - 1.5 };
    return { x: sp.x, y: sp.y + 1.35 };
  }

  function desiredRoleFor(agentId, info) {
    if (agentId === 'foreman') return 'work';
    if (ctrl.demo && ctrl.demo.agentId === agentId) return ctrl.demo.desiredRole;
    if (info.isWorking) return 'working';
    if (info.isBlocked) return 'reporting';
    if (info.isQueued) return 'briefing';
    return 'lounge';
  }

  function queueTrip(actor, steps) {
    actor.waypoints = [];
    var curX = actor.x, curY = actor.y;
    for (var i = 0; i < steps.length; i++) {
      var st = steps[i];
      var leg = buildCorridorPath(curX, curY, st.x, st.y);
      for (var k = 0; k < leg.length; k++) {
        var isLast = (k === leg.length - 1);
        actor.waypoints.push({
          x: leg[k].x, y: leg[k].y,
          endPose: isLast ? st.pose : 'walk',
          holdSec: isLast ? (st.holdSec || 0) : 0,
          bubbleOverride: isLast ? (st.bubble || null) : (st.walkBubble || null)
        });
      }
      curX = st.x; curY = st.y;
    }
  }

  function updateDemoScript(nowMs, agents) {
    var banner = document.getElementById('lab-demo-banner');
    var demoBtn = document.getElementById('btn-lab-demo');
    if (!ctrl.demo) {
      if (banner) banner.style.display = 'none';
      if (demoBtn) { demoBtn.classList.remove('active'); demoBtn.textContent = '🚶 演練派工流'; }
      return;
    }
    var elapsed = (nowMs - ctrl.demo.startMs) * 0.001;
    var targetAgent = agents.find(function (a) { return a.id === ctrl.demo.agentId; });
    var aName = targetAgent ? targetAgent.name : ctrl.demo.agentId;
    var actMap = { basketball: '打籃球 🏀', arcade: '打街機 🎮', gaming: '打電動 🎮', tea: '品茗喝茶 🍵' };
    var lSlot = LOUNGE_SLOTS[ctrl.demo.agentId];
    var actTxt = (lSlot && actMap[lSlot.activity]) || '休息';

    var stageText = '';
    if (elapsed < 1.2) {
      ctrl.demo.desiredRole = 'lounge';
      stageText = '① 工頭後方大休息區：' + aName + ' 正在' + actTxt;
    } else if (elapsed < 5.0) {
      ctrl.demo.desiredRole = 'briefing';
      stageText = '② 有工作指派！' + aName + ' 走到工頭前領取新任務 📋';
    } else if (elapsed < 10.2) {
      ctrl.demo.desiredRole = 'working';
      stageText = '③ 前往夜市遊戲攤開工：' + aName + ' 展開夜市遊玩動作 🏮';
    } else if (elapsed < 14.4) {
      ctrl.demo.desiredRole = 'reporting';
      stageText = '④ 工作完成！' + aName + ' 回到工頭前做成果匯報 📣';
    } else if (elapsed < 19.0) {
      ctrl.demo.desiredRole = 'lounge';
      stageText = '⑤ 確認結案！' + aName + ' 走回後方休息區繼續' + actTxt;
    } else {
      ctrl.demo = null;
      if (banner) banner.style.display = 'none';
      if (demoBtn) { demoBtn.classList.remove('active'); demoBtn.textContent = '🚶 演練派工流'; }
      return;
    }
    if (banner) { banner.style.display = 'inline-flex'; banner.textContent = stageText; }
    if (demoBtn) { demoBtn.classList.add('active'); demoBtn.textContent = '⏹ 停止演練'; }
  }

  function stepActors(model, nowMs, dtSec) {
    var agents = model.agents || [];
    updateDemoScript(nowMs, agents);

    agents.forEach(function (a) {
      var info = model.agentInfo[a.id] || {};
      var desired = desiredRoleFor(a.id, info);
      var fSlot = foremanSlotFor(a.id, agents);
      var lSlot = LOUNGE_SLOTS[a.id] || { x: -24, y: -24 };
      var wSlot = workStandPos(a.id);

      var actor = ctrl.actors[a.id];
      if (!actor) {
        var initPos = (a.id === 'foreman' || desired === 'working') ? wSlot : (desired === 'lounge' ? lSlot : fSlot);
        var initPose = (a.id === 'foreman' || desired === 'working') ? 'work' : desired;
        ctrl.actors[a.id] = { x: initPos.x, y: initPos.y, pose: initPose, desiredRole: desired, waypoints: [], holdUntilMs: 0, walkPhase: 0, bubbleOverride: null };
        return;
      }
      if (a.id === 'foreman') { actor.x = wSlot.x; actor.y = wSlot.y; actor.pose = 'work'; return; }

      if (actor.desiredRole !== desired) {
        var prev = actor.desiredRole;
        actor.desiredRole = desired;
        actor.holdUntilMs = 0;

        if (desired === 'working') {
          if (prev === 'lounge') {
            queueTrip(actor, [
              { x: fSlot.x, y: fSlot.y, pose: 'briefing', holdSec: 2.0,
                walkBubble: { cls: 'queued', icon: '🚶', id: '報到', title: '前往工頭領取任務' },
                bubble:     { cls: 'queued', icon: '📋', id: '領單', title: '向工頭領取工作' } },
              { x: wSlot.x, y: wSlot.y, pose: 'work', holdSec: 0,
                walkBubble: { cls: 'working', icon: '🚶', id: '開工', title: '前往工坊展開作業' },
                bubble: null }
            ]);
          } else {
            queueTrip(actor, [{ x: wSlot.x, y: wSlot.y, pose: 'work', holdSec: 0, walkBubble: { cls: 'working', icon: '🚶', id: '開工', title: '前往工坊開工' }, bubble: null }]);
          }
        } else if (desired === 'briefing') {
          queueTrip(actor, [{ x: fSlot.x, y: fSlot.y, pose: 'briefing', holdSec: 0, walkBubble: { cls: 'queued', icon: '🚶', id: '派工', title: '前往工頭領取任務' }, bubble: { cls: 'queued', icon: '📋', id: '領單', title: '在工頭這邊領任務' } }]);
        } else if (desired === 'reporting') {
          queueTrip(actor, [{ x: fSlot.x, y: fSlot.y, pose: 'reporting', holdSec: 0, walkBubble: { cls: 'blocked', icon: '🚶', id: '匯報', title: '工作完成，回工頭匯報' }, bubble: null }]);
        } else if (desired === 'lounge') {
          if (prev === 'working') {
            queueTrip(actor, [
              { x: fSlot.x, y: fSlot.y, pose: 'reporting', holdSec: 2.0,
                walkBubble: { cls: 'done', icon: '🚶', id: '匯報', title: '工作完成，回工頭匯報' },
                bubble:     { cls: 'done', icon: '📣', id: '匯報', title: '向工頭匯報結案' } },
              { x: lSlot.x, y: lSlot.y, pose: 'lounge', holdSec: 0,
                walkBubble: { cls: 'idle', icon: '🚶', id: '收工', title: '結案確認，回後方休息區' },
                bubble: null }
            ]);
          } else if (prev === 'reporting') {
            queueTrip(actor, [
              { x: fSlot.x, y: fSlot.y, pose: 'reporting', holdSec: 1.0, bubble: { cls: 'done', icon: '✅', id: '結案', title: '確認結束，回休息區' } },
              { x: lSlot.x, y: lSlot.y, pose: 'lounge', holdSec: 0, walkBubble: { cls: 'idle', icon: '🚶', id: '收工', title: '返回後方休息區' }, bubble: null }
            ]);
          } else {
            queueTrip(actor, [{ x: lSlot.x, y: lSlot.y, pose: 'lounge', holdSec: 0, walkBubble: { cls: 'idle', icon: '🚶', id: '休息', title: '前往後方休息區' }, bubble: null }]);
          }
        }
      }

      if (actor.waypoints.length > 0) {
        if (actor.holdUntilMs > nowMs) return;
        var wp = actor.waypoints[0];
        var dx = wp.x - actor.x, dy = wp.y - actor.y, dist = Math.hypot(dx, dy), speed = 18.0;
        if (dist <= speed * dtSec + 0.08) {
          actor.x = wp.x; actor.y = wp.y; actor.pose = wp.endPose;
          actor.bubbleOverride = wp.bubbleOverride || null;
          actor.waypoints.shift();
          if (wp.holdSec > 0) actor.holdUntilMs = nowMs + wp.holdSec * 1000;
        } else {
          actor.pose = 'walk';
          actor.x += (dx / dist) * speed * dtSec;
          actor.y += (dy / dist) * speed * dtSec;
          actor.walkPhase = (actor.walkPhase || 0) + dtSec * 14.0;
          actor.bubbleOverride = wp.bubbleOverride || actor.bubbleOverride;
        }
      }
    });

    if (ctrl.selectedAgentId && ctrl.actors[ctrl.selectedAgentId]) {
      ctrl.camDst.tx = ctrl.actors[ctrl.selectedAgentId].x;
      ctrl.camDst.ty = ctrl.actors[ctrl.selectedAgentId].y;
    }
  }

  function ensureOverlayElements(agents) {
    if (!ctrl.overlay) return;
    agents.forEach(function (a) {
      if (!ctrl.calloutEls[a.id]) {
        var el = document.createElement('button');
        el.type = 'button'; el.className = 'lab-callout'; el.setAttribute('data-agent-id', a.id);
        el.addEventListener('click', function (ev) { ev.stopPropagation(); if (ctrl.onSelectAgent) ctrl.onSelectAgent(a.id); });
        el.addEventListener('mouseenter', function () { ctrl.hoveredAgentId = a.id; });
        el.addEventListener('mouseleave', function () { if (ctrl.hoveredAgentId === a.id) ctrl.hoveredAgentId = null; });
        ctrl.overlay.appendChild(el); ctrl.calloutEls[a.id] = el;
      }
      if (!ctrl.labelEls[a.id]) {
        var lb = document.createElement('div');
        lb.className = 'lab-nameplate'; lb.textContent = a.name;
        ctrl.overlay.appendChild(lb); ctrl.labelEls[a.id] = lb;
      }
    });
  }

  function escHtml(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function loungeEmoji(agentId) {
    var ls = LOUNGE_SLOTS[agentId];
    if (!ls) return '🍵';
    if (ls.activity === 'basketball') return '🏀';
    if (ls.activity === 'arcade' || ls.activity === 'gaming') return '🎮';
    return '🍵';
  }

  function syncCallouts(hitBoxes, agents, buildProg, w, h) {
    if (!ctrl.overlay) return;
    ensureOverlayElements(agents);
    var agentMap = {};
    agents.forEach(function (a) { agentMap[a.id] = a; });
    var boxes = hitBoxes.slice().sort(function (a, b) { return a.by - b.by; });
    var placed = [];

    boxes.forEach(function (hb) {
      var a = agentMap[hb.agentId], el = ctrl.calloutEls[hb.agentId], lb = ctrl.labelEls[hb.agentId];
      if (!a || !el || !lb) return;

      var inView = hb.bx >= -30 && hb.bx <= w + 30 && hb.by >= 38 && hb.by <= h + 20;
      var vis = buildProg > 0.35 && inView;
      el.style.opacity = vis ? '1' : '0';
      el.style.pointerEvents = vis ? 'auto' : 'none';
      lb.style.opacity = (buildProg > 0.35 && hb.lx >= 0 && hb.lx <= w && hb.ly >= 26 && hb.ly <= h - 8) ? '1' : '0';

      var actor = ctrl.actors[a.id];
      var bm;
      if (actor && actor.bubbleOverride) {
        bm = { cls: actor.bubbleOverride.cls || 'queued', icon: actor.bubbleOverride.icon || '🚶', label: actor.bubbleOverride.id || '移動中', id: actor.bubbleOverride.id || '動態', title: actor.bubbleOverride.title || '' };
      } else {
        bm = ctrl.getBubbleMeta ? ctrl.getBubbleMeta(a) : { cls: a.status || 'idle', icon: '🍵', label: '', id: '—', title: a.statusText || '' };
        if (actor && actor.pose === 'lounge' && bm.cls === 'done') {
          bm = { cls: 'idle', icon: loungeEmoji(a.id), label: '休息區休閒中（前項已完成）', id: bm.id, title: bm.title };
        }
      }

      var isCompact = (actor && actor.pose === 'lounge' && !actor.bubbleOverride && ctrl.selectedAgentId !== a.id && ctrl.hoveredAgentId !== a.id);
      var iconTxt = (actor && actor.pose === 'lounge' && !actor.bubbleOverride) ? loungeEmoji(a.id) : bm.icon;
      var sig = bm.cls + '|' + iconTxt + '|' + bm.id + '|' + bm.title + '|' + (ctrl.selectedAgentId === a.id ? '1' : '0') + '|' + (isCompact ? 'c' : 'f');
      if (el.getAttribute('data-sig') !== sig) {
        el.setAttribute('data-sig', sig);
        el.className = 'lab-callout ' + bm.cls + (ctrl.selectedAgentId === a.id ? ' selected' : '') + (isCompact ? ' compact-lounge' : '');
        el.title = '[' + bm.label + '] ' + bm.id + ' ' + bm.title + '（點擊聚焦「' + a.name + '」）';
        el.innerHTML = isCompact
          ? '<span class="sb-icon">' + escHtml(iconTxt) + '</span><span class="sb-id">' + escHtml(bm.id) + '</span>'
          : '<span class="sb-icon">' + escHtml(iconTxt) + '</span><span class="sb-id">' + escHtml(bm.id) + '</span><span class="sb-title">' + escHtml(bm.title) + '</span>';
      }

      var cx = clamp(hb.bx, isCompact ? 42 : 88, Math.max(90, w - (isCompact ? 42 : 88)));
      var cy = clamp(hb.by - 6, 48, Math.max(50, h - 42));
      if (vis) {
        var minDx = isCompact ? 62 : 152, minDy = isCompact ? 20 : 26;
        for (var p = 0; p < placed.length; p++) {
          if (Math.abs(placed[p].x - cx) < minDx && Math.abs(placed[p].y - cy) < minDy) {
            cy = Math.max(46, placed[p].y - minDy);
          }
        }
        placed.push({ x: cx, y: cy });
      }
      el.style.transform = 'translate3d(' + cx.toFixed(1) + 'px,' + cy.toFixed(1) + 'px,0) translate(-50%,-100%)';

      var lx = clamp(hb.lx, 44, Math.max(46, w - 44));
      var ly = clamp(hb.ly + 4, 34, Math.max(36, h - 32));
      lb.className = 'lab-nameplate' + (ctrl.selectedAgentId === a.id ? ' selected' : '');
      lb.style.transform = 'translate3d(' + lx.toFixed(1) + 'px,' + ly.toFixed(1) + 'px,0) translate(-50%,0)';
    });
  }

  function renderFrame(nowMs) {
    if (!ctrl.active || !ctrl.canvas || !ctrl.ctx) return;
    if (document.hidden) { ctrl.lastFrameMs = nowMs; ctrl.rafId = requestAnimationFrame(renderFrame); return; }

    var dtSec = ctrl.lastFrameMs ? clamp((nowMs - ctrl.lastFrameMs) * 0.001, 0.004, 0.08) : 0.016;
    ctrl.lastFrameMs = nowMs;

    var w = ctrl.canvas.clientWidth || 1200, h = ctrl.canvas.clientHeight || 540;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (ctrl.canvas.width !== Math.round(w * dpr) || ctrl.canvas.height !== Math.round(h * dpr)) {
      ctrl.canvas.width = Math.round(w * dpr); ctrl.canvas.height = Math.round(h * dpr);
      updateTargetCamera();
    }

    var model = computeModel();
    stepActors(model, nowMs, dtSec);

    var lerpK = 0.14;
    ctrl.camCur.zoom = lerp(ctrl.camCur.zoom, ctrl.camDst.zoom, lerpK);
    ctrl.camCur.tx = lerp(ctrl.camCur.tx, ctrl.camDst.tx, lerpK);
    ctrl.camCur.ty = lerp(ctrl.camCur.ty, ctrl.camDst.ty, lerpK);
    ctrl.camCur.tz = lerp(ctrl.camCur.tz, ctrl.camDst.tz, lerpK);

    var ctx = ctrl.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var pal = INT.studioPalette();
    var grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, pal.bgTop); grad.addColorStop(1, pal.bgBot);
    ctx.fillStyle = grad; ctx.fillRect(0, 0, w, h);

    var cam = new Cam(ctrl.camCur.zoom, [ctrl.camCur.tx, ctrl.camCur.ty, ctrl.camCur.tz], w * 0.5, h * 0.52);
    LWS = clamp(ctrl.camCur.zoom / 13.0, 0.72, 1.35);
    var G = { ctx: ctx, cam: cam, k: dpr, alpha: 1 };
    var timeSec = nowMs * 0.001;
    var buildProg = clamp((nowMs - ctrl.buildStartMs) / ctrl.buildDurationMs, 0, 1);

    INT.drawStudioFloor(G, pal, timeSec, buildProg, model);

    // Painter's Order across Mongo Core + Big Lounge Facilities + 10 Workshops + All 9 Specialist Actors!
    var drawables = [{ kind: 'mongo', depth: depthOf([MONGO_POS.x, MONGO_POS.y, 0]) }];
    LOUNGE_PROPS.forEach(function (prop) {
      drawables.push({ kind: 'loungeProp', prop: prop, depth: depthOf([prop.x, prop.y, 0]) });
    });
    model.agents.forEach(function (a) {
      var sp = STATION_POS[a.id];
      if (!sp) return;
      var actor = ctrl.actors[a.id];
      drawables.push({ kind: 'workshop', agent: a, actor: actor, depth: depthOf([sp.x, sp.y - 0.6, 0]) });
      if (a.id !== 'foreman' && actor) {
        drawables.push({ kind: 'actor', agent: a, actor: actor, depth: depthOf([actor.x, actor.y, 0.25]) });
      }
    });
    drawables.sort(function (a, b) { return a.depth - b.depth; });

    drawables.forEach(function (item) {
      if (item.kind === 'mongo') INT.drawMongoCore(G, pal, timeSec, buildProg, model);
      else if (item.kind === 'loungeProp') INT.drawLoungeFacility(G, pal, item.prop, timeSec, buildProg);
      else if (item.kind === 'workshop') INT.drawWorkshop(G, pal, item.agent, model.agentInfo[item.agent.id] || {}, item.actor, timeSec, buildProg, ctrl.selectedAgentId === item.agent.id, ctrl.hoveredAgentId === item.agent.id);
      else if (item.kind === 'actor') INT.drawRoamingActor(G, pal, item.agent, item.actor, model.agentInfo[item.agent.id] || {}, timeSec, buildProg, ctrl.selectedAgentId === item.agent.id, ctrl.hoveredAgentId === item.agent.id);
    });

    var hitBoxes = [];
    model.agents.forEach(function (a) {
      var sp = STATION_POS[a.id];
      if (!sp) return;
      var actor = ctrl.actors[a.id];
      var ax = (a.id === 'foreman' || !actor) ? sp.x : actor.x;
      var ay = (a.id === 'foreman' || !actor) ? sp.y : actor.y;
      var az = a.id === 'foreman' ? 0.65 : 0.22;
      var centerScreen = cam.p([ax, ay, az + 2.4]);
      var bubbleAnchor = cam.p([ax, ay, az + 5.8]);
      var labelAnchor = cam.p([ax, ay + 1.1, az + 0.2]);
      hitBoxes.push({ agentId: a.id, cx: centerScreen[0], cy: centerScreen[1], hitR: Math.max(28, 3.3 * cam.z), bx: bubbleAnchor[0], by: bubbleAnchor[1], lx: labelAnchor[0], ly: labelAnchor[1] });
    });
    ctrl.hitBoxes = hitBoxes;
    syncCallouts(hitBoxes, model.agents, buildProg, w, h);
    ctrl.rafId = requestAnimationFrame(renderFrame);
  }

  function findHit(clientX, clientY) {
    if (!ctrl.canvas) return null;
    var rect = ctrl.canvas.getBoundingClientRect();
    var mx = clientX - rect.left, my = clientY - rect.top;
    for (var i = ctrl.hitBoxes.length - 1; i >= 0; i--) {
      if (Math.hypot(mx - ctrl.hitBoxes[i].cx, my - ctrl.hitBoxes[i].cy) <= ctrl.hitBoxes[i].hitR) return ctrl.hitBoxes[i].agentId;
    }
    return null;
  }

  function bindCanvasEvents(canvas) {
    canvas.addEventListener('pointerdown', function (e) { ctrl.dragging = true; ctrl.dragMoved = false; ctrl.dragLast = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', function (e) {
      if (ctrl.dragging) {
        var dx = e.clientX - ctrl.dragLast[0], dy = e.clientY - ctrl.dragLast[1];
        if (Math.abs(dx) + Math.abs(dy) > 3) ctrl.dragMoved = true;
        ctrl.dragLast = [e.clientX, e.clientY];
        var sc = 1 / Math.max(6, ctrl.camCur.zoom);
        ctrl.userPan.dx = clamp(ctrl.userPan.dx + (-dx * 0.707 + dy * 1.414) * sc * 0.55, -26, 26);
        ctrl.userPan.dy = clamp(ctrl.userPan.dy + (dx * 0.707 + dy * 1.414) * sc * 0.55, -26, 26);
        if (!ctrl.selectedAgentId) updateTargetCamera();
        return;
      }
      var hit = findHit(e.clientX, e.clientY);
      ctrl.hoveredAgentId = hit;
      canvas.style.cursor = hit ? 'pointer' : 'grab';
    });
    canvas.addEventListener('pointerup', function (e) {
      if (ctrl.dragging && !ctrl.dragMoved) {
        var hit = findHit(e.clientX, e.clientY);
        if (hit && ctrl.onSelectAgent) ctrl.onSelectAgent(hit);
        else if (!hit && ctrl.selectedAgentId && ctrl.onSelectAgent) ctrl.onSelectAgent(null);
      }
      ctrl.dragging = false;
    });
    canvas.addEventListener('wheel', function (e) {
      e.preventDefault();
      var factor = e.deltaY < 0 ? 1.1 : 0.91;
      ctrl.userPan.dz = clamp(ctrl.userPan.dz * factor, 0.72, 2.0);
      if (ctrl.selectedAgentId) ctrl.camDst.zoom = clamp(ctrl.camDst.zoom * factor, 8, 28);
      else updateTargetCamera();
    }, { passive: false });
  }

  window.SIMULAB_STAGE = {
    mount: function (canvas, overlay, opts) {
      ctrl.canvas = canvas; ctrl.overlay = overlay; ctrl.ctx = canvas.getContext('2d');
      ctrl.onSelectAgent = opts && opts.onSelectAgent; ctrl.getBubbleMeta = opts && opts.getBubbleMeta;
      bindCanvasEvents(canvas); window.addEventListener('resize', updateTargetCamera);
    },
    start: function (data, selectedAgentId) {
      ctrl.data = data; ctrl.selectedAgentId = selectedAgentId || null;
      var wasInactive = !ctrl.active; ctrl.active = true; updateTargetCamera();
      if (wasInactive) {
        ctrl.camCur = { zoom: ctrl.camDst.zoom, tx: ctrl.camDst.tx, ty: ctrl.camDst.ty, tz: ctrl.camDst.tz };
        ctrl.buildStartMs = performance.now(); ctrl.lastFrameMs = ctrl.buildStartMs;
        ctrl.rafId = requestAnimationFrame(renderFrame);
      }
    },
    stop: function () { ctrl.active = false; if (ctrl.rafId) { cancelAnimationFrame(ctrl.rafId); ctrl.rafId = null; } },
    updateData: function (data, selectedAgentId) { ctrl.data = data; ctrl.selectedAgentId = selectedAgentId || null; updateTargetCamera(); },
    replayBuild: function () { ctrl.buildStartMs = performance.now(); },
    resetView: function () { ctrl.userPan = { dx: 0, dy: 0, dz: 1 }; if (ctrl.selectedAgentId && ctrl.onSelectAgent) ctrl.onSelectAgent(null); else updateTargetCamera(); },
    setActiveOnly: function (flag) { ctrl.activeOnly = !!flag; },
    toggleLifecycleDemo: function () {
      if (ctrl.demo) { ctrl.demo = null; return false; }
      var targetId = (ctrl.selectedAgentId && ctrl.selectedAgentId !== 'foreman') ? ctrl.selectedAgentId : 'portal-agent';
      var lSlot = LOUNGE_SLOTS[targetId] || { x: -27.5, y: -14.2 };
      if (ctrl.actors[targetId]) {
        ctrl.actors[targetId].x = lSlot.x; ctrl.actors[targetId].y = lSlot.y;
        ctrl.actors[targetId].pose = 'lounge'; ctrl.actors[targetId].desiredRole = 'lounge';
        ctrl.actors[targetId].waypoints = []; ctrl.actors[targetId].bubbleOverride = null;
      }
      ctrl.demo = { agentId: targetId, startMs: performance.now(), desiredRole: 'lounge' };
      return true;
    }
  };
})();
