// Anatomy-style Precision Isometric SVG Telemetry Widget (45 deg / 30 deg, 4-tone shading, bevels, dial gauge)
(function () {
  var RAD = Math.PI / 180;
  var SIN_A = Math.sin(45 * RAD), COS_A = Math.cos(45 * RAD);
  var SIN_E = Math.sin(30 * RAD), COS_E = Math.cos(30 * RAD);

  function iso(x, y, z, ox, oy, s) {
    return [
      ox + (x * SIN_A - y * COS_A) * s,
      oy + ((x * COS_A + y * SIN_A) * SIN_E - z * COS_E) * s
    ];
  }

  function ptsStr(pts) {
    return pts.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
  }

  function isoBox(x0, y0, z0, x1, y1, z1, ox, oy, s, tones, ink) {
    var P = function (x, y, z) { return iso(x, y, z, ox, oy, s); };
    var top = [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)];
    var left = [P(x0, y1, z0), P(x1, y1, z0), P(x1, y1, z1), P(x0, y1, z1)];
    var right = [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)];
    var bev = [
      P(x0 + 0.15, y0 + 0.15, z1),
      P(x1 - 0.15, y0 + 0.15, z1),
      P(x1 - 0.15, y1 - 0.15, z1),
      P(x0 + 0.15, y1 - 0.15, z1)
    ];
    return (
      '<polygon points="' + ptsStr(left) + '" fill="' + tones[2] + '" stroke="' + ink + '" stroke-width="1.1" stroke-linejoin="round"/>' +
      '<polygon points="' + ptsStr(right) + '" fill="' + tones[3] + '" stroke="' + ink + '" stroke-width="1.1" stroke-linejoin="round"/>' +
      '<polygon points="' + ptsStr(top) + '" fill="' + tones[0] + '" stroke="' + ink + '" stroke-width="1.1" stroke-linejoin="round"/>' +
      '<polygon points="' + ptsStr(bev) + '" fill="none" stroke="' + tones[1] + '" stroke-width="0.7" opacity="0.7"/>'
    );
  }

  function screwDot(x, y, z, ox, oy, s, ink) {
    var p = iso(x, y, z, ox, oy, s);
    return (
      '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="1.4" fill="#94a3b8" stroke="' + ink + '" stroke-width="0.7"/>' +
      '<line x1="' + (p[0] - 0.9).toFixed(1) + '" y1="' + p[1].toFixed(1) + '" x2="' + (p[0] + 0.9).toFixed(1) + '" y2="' + p[1].toFixed(1) + '" stroke="' + ink + '" stroke-width="0.5"/>'
    );
  }

  function renderInstrument(agent, counts) {
    var total = (counts.done || 0) + (counts.in_progress || 0) + (counts.blocked || 0) + (counts.todo || 0);
    var ratio = total > 0 ? (counts.done / total) : 0;
    var pct = Math.round(ratio * 100);
    var ink = '#1d2033';
    var ox = 86, oy = 68, s = 11.5;

    var baseTones = ['#e2e8f0', '#cbd5e1', '#94a3b8', '#64748b'];
    var casingTones = ['#f8fafc', '#e2e8f0', '#cbd5e1', '#94a3b8'];
    var accent = agent.accentColor || '#38bdf8';

    // Status LED color
    var ledCol = '#94a3b8';
    var statusCode = 'IDLE';
    if (agent.status === 'working' || (counts.in_progress || 0) > 0) { ledCol = '#22c55e'; statusCode = 'RUN'; }
    if (agent.status === 'blocked' || (counts.blocked || 0) > 0) { ledCol = '#ef4444'; statusCode = 'HOLD'; }
    else if (agent.status === 'done' && (counts.todo || 0) === 0 && (counts.in_progress || 0) === 0) { ledCol = '#3b82f6'; statusCode = 'DONE'; }

    // Rubber feet + heavy base plinth (Anatomy bench instrument style)
    var svgParts = [];
    svgParts.push(isoBox(-3.6, -2.6, 0, -2.9, -1.9, 0.35, ox, oy, s, ['#475569', '#334155', '#1e293b', '#0f172a'], ink));
    svgParts.push(isoBox(2.9, -2.6, 0, 3.6, -1.9, 0.35, ox, oy, s, ['#475569', '#334155', '#1e293b', '#0f172a'], ink));
    svgParts.push(isoBox(-3.6, 1.9, 0, -2.9, 2.6, 0.35, ox, oy, s, ['#475569', '#334155', '#1e293b', '#0f172a'], ink));
    svgParts.push(isoBox(2.9, 1.9, 0, 3.6, 2.6, 0.35, ox, oy, s, ['#475569', '#334155', '#1e293b', '#0f172a'], ink));

    // Heavy machined plinth
    svgParts.push(isoBox(-3.8, -2.8, 0.35, 3.8, 2.8, 1.15, ox, oy, s, baseTones, ink));
    // Accent nameplate strip on front bevel
    svgParts.push(isoBox(-3.4, 2.55, 0.55, 3.4, 2.9, 0.95, ox, oy, s, [accent, accent, accent, accent], ink));

    // Left module: Isometric Analog Completion Dial Housing
    svgParts.push(isoBox(-3.3, -2.3, 1.15, 0.5, 2.1, 3.15, ox, oy, s, casingTones, ink));

    // Right module: 3-column physical load bar rack (Doing / Todo / Done)
    svgParts.push(isoBox(1.0, -2.2, 1.15, 3.3, 2.1, 1.55, ox, oy, s, ['#334155', '#475569', '#1e293b', '#0f172a'], ink));
    var maxBar = Math.max(1, counts.done || 0, counts.todo || 0, (counts.in_progress || 0) + (counts.blocked || 0));
    var hDone = 0.25 + ((counts.done || 0) / maxBar) * 2.1;
    var hDoing = 0.25 + (((counts.in_progress || 0) + (counts.blocked || 0)) / maxBar) * 2.1;
    var hTodo = 0.25 + ((counts.todo || 0) / maxBar) * 2.1;
    svgParts.push(isoBox(1.25, -1.8, 1.55, 1.85, -0.7, 1.55 + hTodo, ox, oy, s, ['#fcd34d', '#fbbf24', '#d97706', '#b45309'], ink));
    svgParts.push(isoBox(1.95, -0.4, 1.55, 2.55, 0.7, 1.55 + hDoing, ox, oy, s, (counts.blocked ? ['#fca5a5', '#f87171', '#ef4444', '#b91c1c'] : ['#86efac', '#4ade80', '#22c55e', '#15803d']), ink));
    svgParts.push(isoBox(2.55, 0.95, 1.55, 3.15, 1.95, 1.55 + hDone, ox, oy, s, ['#93c5fd', '#60a5fa', '#3b82f6', '#1d4ed8'], ink));

    // Corner screws on top of dial housing
    svgParts.push(screwDot(-3.0, -2.0, 3.15, ox, oy, s, ink));
    svgParts.push(screwDot(0.2, -2.0, 3.15, ox, oy, s, ink));
    svgParts.push(screwDot(-3.0, 1.8, 3.15, ox, oy, s, ink));
    svgParts.push(screwDot(0.2, 1.8, 3.15, ox, oy, s, ink));

    // Analog dial face (projected ellipse on top z=3.16)
    var dc = iso(-1.4, -0.1, 3.18, ox, oy, s);
    var rx = 18.5, ry = 10.6;
    svgParts.push(
      '<ellipse cx="' + dc[0].toFixed(1) + '" cy="' + dc[1].toFixed(1) + '" rx="' + rx + '" ry="' + ry + '" fill="#0f172a" stroke="' + ink + '" stroke-width="1.3"/>' +
      '<ellipse cx="' + dc[0].toFixed(1) + '" cy="' + dc[1].toFixed(1) + '" rx="' + (rx - 2.6) + '" ry="' + (ry - 1.6) + '" fill="#fffdf7" stroke="#64748b" stroke-width="0.8"/>'
    );
    // Tick marks around top arc (-150 deg to +30 deg)
    for (var ti = 0; ti <= 10; ti++) {
      var ang = (-210 + ti * 24) * RAD;
      var xOut = dc[0] + Math.cos(ang) * (rx - 3.6);
      var yOut = dc[1] + Math.sin(ang) * (ry - 2.2);
      var xIn = dc[0] + Math.cos(ang) * (rx - 6.8);
      var yIn = dc[1] + Math.sin(ang) * (ry - 4.0);
      svgParts.push('<line x1="' + xIn.toFixed(1) + '" y1="' + yIn.toFixed(1) + '" x2="' + xOut.toFixed(1) + '" y2="' + yOut.toFixed(1) + '" stroke="' + (ti >= 8 ? '#16a34a' : '#334155') + '" stroke-width="' + (ti % 5 === 0 ? '1.3' : '0.7') + '"/>');
    }
    // Moving dial needle reflecting completion ratio!
    var needleAng = (-210 + ratio * 240) * RAD;
    var nx = dc[0] + Math.cos(needleAng) * (rx - 4.5);
    var ny = dc[1] + Math.sin(needleAng) * (ry - 2.7);
    svgParts.push(
      '<line x1="' + dc[0].toFixed(1) + '" y1="' + dc[1].toFixed(1) + '" x2="' + nx.toFixed(1) + '" y2="' + ny.toFixed(1) + '" stroke="#dc2626" stroke-width="1.8" stroke-linecap="round"/>' +
      '<circle cx="' + dc[0].toFixed(1) + '" cy="' + dc[1].toFixed(1) + '" r="2.3" fill="#1e293b" stroke="#f8fafc" stroke-width="0.7"/>'
    );

    // Glowing status LED jewel on dial bezel
    var ledPos = iso(-2.6, 1.3, 3.22, ox, oy, s);
    svgParts.push(
      '<circle cx="' + ledPos[0].toFixed(1) + '" cy="' + ledPos[1].toFixed(1) + '" r="3.6" fill="' + ledCol + '" opacity="0.28"/>' +
      '<circle cx="' + ledPos[0].toFixed(1) + '" cy="' + ledPos[1].toFixed(1) + '" r="2.2" fill="' + ledCol + '" stroke="' + ink + '" stroke-width="0.8"/>'
    );

    return (
      '<div class="anatomy-card" title="Anatomy 精密等距儀表：完成率 ' + pct + '%（狀態 ' + statusCode + '）">' +
        '<svg class="anatomy-svg" viewBox="0 0 172 104" width="172" height="104" aria-hidden="true">' +
          svgParts.join('') +
        '</svg>' +
        '<div class="anatomy-readout">' +
          '<span class="ar-code" style="color:' + ledCol + '">● ' + statusCode + '</span>' +
          '<span class="ar-pct">完成率 ' + pct + '%</span>' +
        '</div>' +
      '</div>'
    );
  }

  window.ANATOMY_INSPECTOR = { render: renderInstrument };
})();
