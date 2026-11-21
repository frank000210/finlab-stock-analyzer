// Mode A: 16-bit Pixel Art SVG Sprites (shape-rendering="crispEdges")
window.PIXEL_SPRITES = (function () {
  function build(grid, pal) {
    var out = [];
    for (var y = 0; y < grid.length; y++) {
      var r = grid[y];
      for (var x = 0; x < r.length; x++) {
        var c = r[x];
        if (c !== '.' && pal[c]) out.push('<rect x="' + x + '" y="' + y + '" width="1" height="1" fill="' + pal[c] + '"/>');
      }
    }
    return '<svg class="avatar-svg pixel-svg" viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true">' + out.join('') + '</svg>';
  }

  var baseFace = ['...KSSSSSSSSK...', '...KSKSSSKSSK...', '...KSSSSSSSSK...', '....KSSSSSSK....'];
  var glassFace = ['...KSSSSSSSSK...', '..KKGKKSSKKGKK..', '..KKGKKSSKKGKK..', '...KSSSSSSSSK...'];
  var longHair = ['....HHHHHHHH....', '...HHhHHHHhHH...', '..KHHHHHHHHHHK..', '..KHSSSSSSSSHK..', '..KHSKSSSKSSHK..', '..KHSSSSSSSSHK..', '..KHKSSSSSSKHK..'];
  var shortHair = ['....HHHHHHHH....', '...HHhHHHHhHH...', '...KHHHHHHHHK...'];
  var body = function (tie) {
    return [tie, '..KCCCccccCCCK..', '..KCCCccccCCCK..', '..KSSKCCCCKSSK..', '....KCCCCCCK....', '....KCC..CCK....', '....KKK..KKK....'];
  };

  var defs = {
    foreman: {
      pal: { K: '#1b1d28', Y: '#facc15', y: '#ca8a04', S: '#f5c29b', B: '#7c4a21', O: '#f97316', U: '#3b82f6', W: '#ffffff' },
      grid: [
        '.....YYYYYY.....', '....YYYYYYYY....', '...YYyYYYYyYY...', '..KYYYYYYYYYYK..',
        '...KSSSSSSSSK...', '...KSKSSSKSSK...', '...KSSSSSSSSK...', '...KSBBBBBBSK...',
        '....KBBBBBBK....', '...KOOOWWOOOK...', '..KOOOUUUUOOOK..', '..KOOOUUUUOOOK..',
        '..KSSKUUUUKSK...', '....KUUUUUUK....', '....KUU..UUK....', '....KKK..KKK....'
      ]
    },
    portal: {
      pal: { K: '#1b1d28', H: '#1f2937', h: '#374151', S: '#f7c9a6', W: '#f8fafc', R: '#dc2626', C: '#1e293b', c: '#0f766e' },
      grid: shortHair.concat(baseFace, ['.....KWWWWK.....'], body('...KCCWRRWCCK...'))
    },
    share: {
      pal: { K: '#1b1d28', H: '#6b4423', h: '#8b5e34', S: '#f7c9a6', G: '#bae6fd', C: '#2f855a', c: '#276749', W: '#fefce8' },
      grid: shortHair.concat(glassFace, ['....KSSSSSSK....'], body('...KCCWWWWCCK...'))
    },
    revival: {
      pal: { K: '#1b1d28', H: '#7c3f1c', h: '#9a5228', S: '#f9d2b5', C: '#7e22ce', c: '#a855f7', W: '#fef3c7', G: '#eab308' },
      grid: longHair.concat(['..KH.KWWWWK.HK..'], body('...KCCWGGWCCK...'))
    },
    kb: {
      pal: { K: '#1b1d28', H: '#1e1b4b', h: '#312e81', S: '#f9d2b5', G: '#93c5fd', C: '#2563eb', c: '#1d4ed8', W: '#f8fafc', R: '#f43f5e' },
      grid: ['.....HHHHHH.....', '...HHHHHHHHHH...', '..KHHhHHHHhHHK..', '..KHSSSSSSSSHK..', '..KHKGKSSKGKHK..', '..KHSSSSSSSSHK..', '..KHKSSSSSSKHK..', '....KWWWRWWK....'].concat(body('...KCCWWWWCCK...'))
    },
    decision: {
      pal: { K: '#0f172a', A: '#34d399', M: '#10b981', m: '#059669', D: '#064e3b', E: '#fef08a', C: '#1e293b', c: '#059669' },
      grid: [
        '.......AA.......', '.......KK.......', '...KKKKKKKKKK...', '..KMMMMMMMMMMK..',
        '..KMDDDDDDDDMK..', '..KMDEDDDDEDMK..', '..KMDDDDDDDDMK..', '..KMMmMMMMmMMK..',
        '....KKKKKKKK....', '...KCCAAAAccK...', '..KCCCccccCCCK..', '..KCCCccccCCCK..',
        '..KMMKCCCCKMMK..', '....KCCCCCCK....', '....KCC..CCK....', '....KKK..KKK....'
      ]
    },
    stock: {
      pal: { K: '#1b1d28', H: '#4a2511', h: '#6b3a1f', S: '#f7c9a6', C: '#dc2626', c: '#b91c1c', W: '#ffffff', G: '#22c55e' },
      grid: longHair.concat(['....KKWWWWKK....'], body('...KCCWGWWCCK...'))
    },
    market: {
      pal: { K: '#1b1d28', H: '#292524', h: '#44403c', S: '#e6b08a', C: '#d97706', c: '#f59e0b', W: '#fef3c7', T: '#0d9488' },
      grid: shortHair.concat(baseFace, ['....KTTTTTTK....'], body('...KCCWWWWCCK...'))
    },
    risk: {
      pal: { K: '#1b1d28', H: '#4c1d95', h: '#6d28d9', S: '#f7c9a6', C: '#5b21b6', c: '#7c3aed', W: '#f8fafc', Y: '#fbbf24' },
      grid: longHair.concat(['....KKWWWWKK....'], body('...KCCWYYWCCK...'))
    },
    platform: {
      pal: { K: '#1b1d28', H: '#334155', h: '#64748b', S: '#f5c29b', G: '#e0f2fe', C: '#0284c7', c: '#0369a1', W: '#f8fafc', Y: '#cbd5e1' },
      grid: shortHair.concat(glassFace, ['....KSSSSSSK....'], body('...KCCWYYWCCK...'))
    },
    intern: {
      pal: { K: '#1b1d28', H: '#0f172a', h: '#334155', S: '#fad7b8', G: '#cffafe', C: '#06b6d4', c: '#0891b2', W: '#ffffff', Y: '#facc15' },
      grid: shortHair.concat(glassFace, ['....KSSSSSSK....'], body('...KCCWYYWCCK...'))
    }
  };

  return {
    get: function (key) {
      var d = defs[key] || defs.foreman;
      return build(d.grid, d.pal);
    }
  };
})();
