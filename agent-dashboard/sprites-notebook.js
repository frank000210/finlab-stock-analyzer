// Mode B: Hand-Drawn Notebook Illustration SVG Figurines
window.NOTEBOOK_SPRITES = (function () {
  function draw(o) {
    var glasses = o.glasses ? '<g stroke="#2B2B33" stroke-width="1.8" fill="rgba(255,255,255,0.45)"><circle cx="25.5" cy="27" r="4.5"/><circle cx="38.5" cy="27" r="4.5"/><line x1="30" y1="27" x2="34" y2="27"/></g>' : '';
    var beard = o.beard ? '<path d="M21 31 Q32 41 43 31 Q41 38 32 39 Q23 38 21 31 Z" fill="#8D5524" stroke="#2B2B33" stroke-width="1.5"/>' : '';
    var collar = o.collar || '<path d="M26 42 L32 48 L38 42" fill="#FFFDF7" stroke="#2B2B33" stroke-width="1.6"/>';
    return (
      '<svg class="avatar-svg notebook-svg" viewBox="0 0 64 64" aria-hidden="true">' +
      (o.hairBack || '') +
      '<path d="M16 58 C16 45 23 41 32 41 C41 41 48 45 48 58 Z" fill="' + o.outfit + '" stroke="#2B2B33" stroke-width="2" stroke-linejoin="round"/>' +
      collar +
      '<circle cx="32" cy="26" r="14" fill="' + (o.skin || '#FAD7B8') + '" stroke="#2B2B33" stroke-width="2"/>' +
      '<ellipse cx="22.5" cy="30.5" rx="2.6" ry="1.6" fill="#F29C9C" opacity="0.65"/>' +
      '<ellipse cx="41.5" cy="30.5" rx="2.6" ry="1.6" fill="#F29C9C" opacity="0.65"/>' +
      '<circle cx="26" cy="27" r="1.8" fill="#2B2B33"/><circle cx="38" cy="27" r="1.8" fill="#2B2B33"/>' +
      beard +
      '<path d="M28.5 32.5 Q32 35.5 35.5 32.5" fill="none" stroke="#2B2B33" stroke-width="1.7" stroke-linecap="round"/>' +
      (o.hairFront || '') + glasses + (o.hat || '') + (o.prop || '') +
      '</svg>'
    );
  }

  var svgs = {
    foreman: draw({
      outfit: '#EA7A2E', beard: true,
      collar: '<rect x="27" y="42" width="10" height="16" fill="#3B82F6" stroke="#2B2B33" stroke-width="1.6"/>',
      hat: '<path d="M16 21 C16 11 23 7 32 7 C41 7 48 11 48 21 Z" fill="#FACC15" stroke="#2B2B33" stroke-width="2"/><rect x="13" y="19" width="38" height="4" rx="2" fill="#EAB308" stroke="#2B2B33" stroke-width="1.8"/><rect x="29" y="8" width="6" height="11" rx="2" fill="#FEF08A" stroke="#2B2B33" stroke-width="1.4"/>',
      prop: '<g transform="translate(44,40) rotate(8)"><rect x="0" y="0" width="14" height="18" rx="2" fill="#DBEAFE" stroke="#2B2B33" stroke-width="1.7"/><line x1="3" y1="5" x2="11" y2="5" stroke="#2563EB" stroke-width="1.5"/><line x1="3" y1="9" x2="11" y2="9" stroke="#2563EB" stroke-width="1.5"/><line x1="3" y1="13" x2="8" y2="13" stroke="#2563EB" stroke-width="1.5"/></g>'
    }),
    portal: draw({
      outfit: '#334155',
      hairFront: '<path d="M18 24 C18 14 25 10 33 11 C41 11 46 15 46 24 C42 18 35 17 28 19 C23 20 20 22 18 24 Z" fill="#27272A" stroke="#2B2B33" stroke-width="1.8"/>',
      collar: '<path d="M25 42 L32 49 L39 42 Z" fill="#FFFDF7" stroke="#2B2B33" stroke-width="1.5"/><polygon points="28,45 32,47 28,49" fill="#C03936" stroke="#2B2B33" stroke-width="1.2"/><polygon points="36,45 32,47 36,49" fill="#C03936" stroke="#2B2B33" stroke-width="1.2"/>',
      prop: '<circle cx="52" cy="48" r="6" fill="#FFE679" stroke="#2B2B33" stroke-width="1.6"/><path d="M49 48 L51.5 50.5 L55.5 45.5" fill="none" stroke="#12706C" stroke-width="2" stroke-linecap="round"/>'
    }),
    share: draw({
      outfit: '#4D9078', glasses: true,
      hairBack: '<ellipse cx="32" cy="24" rx="16.5" ry="15" fill="#6B4423" stroke="#2B2B33" stroke-width="1.8"/>',
      hairFront: '<path d="M18 23 C22 14 42 14 46 23 C41 19 35 18 32 20 C27 18 22 19 18 23 Z" fill="#6B4423" stroke="#2B2B33" stroke-width="1.6"/>',
      prop: '<g transform="translate(46,38) rotate(-18)"><rect x="0" y="0" width="5" height="19" rx="1.5" fill="#FDE047" stroke="#2B2B33" stroke-width="1.6"/><polygon points="0,19 5,19 2.5,24" fill="#FAD7B8" stroke="#2B2B33" stroke-width="1.4"/></g>'
    }),
    revival: draw({
      outfit: '#8B5CF6',
      hairBack: '<path d="M15 26 C15 12 49 12 49 26 L49 44 C49 47 45 47 44 43 L44 30 L20 30 L20 43 C19 47 15 47 15 44 Z" fill="#7C3F1C" stroke="#2B2B33" stroke-width="1.8"/>',
      hairFront: '<path d="M18 23 C21 15 43 15 46 23 C40 19 34 18 32 21 C28 18 22 19 18 23 Z" fill="#7C3F1C" stroke="#2B2B33" stroke-width="1.6"/>',
      prop: '<g transform="translate(43,41)"><rect x="0" y="2" width="15" height="13" rx="2" fill="#FEF3C7" stroke="#2B2B33" stroke-width="1.6"/><line x1="3" y1="6" x2="12" y2="6" stroke="#92400E" stroke-width="1.4"/><line x1="3" y1="10" x2="10" y2="10" stroke="#92400E" stroke-width="1.4"/></g>'
    }),
    kb: draw({
      outfit: '#3B82F6', glasses: true,
      hairBack: '<circle cx="32" cy="11" r="6" fill="#2E2A4A" stroke="#2B2B33" stroke-width="1.8"/><path d="M17 26 C17 13 47 13 47 26 L47 37 L17 37 Z" fill="#2E2A4A" stroke="#2B2B33" stroke-width="1.8"/>',
      hairFront: '<path d="M18 24 C22 15 42 15 46 24 C40 19 24 19 18 24 Z" fill="#2E2A4A" stroke="#2B2B33" stroke-width="1.5"/>',
      prop: '<g transform="translate(44,40)"><circle cx="7" cy="7" r="6" fill="#E0F2FE" stroke="#2B2B33" stroke-width="1.8"/><line x1="11.5" y1="11.5" x2="17" y2="17" stroke="#2B2B33" stroke-width="2.6" stroke-linecap="round"/></g>'
    }),
    decision: draw({
      outfit: '#0D9488',
      hairFront: '<path d="M18 23 C19 13 28 10 35 11 C43 12 46 16 46 23 C41 18 25 18 18 23 Z" fill="#475569" stroke="#2B2B33" stroke-width="1.8"/>',
      prop: '<g transform="translate(44,41)"><circle cx="8" cy="8" r="8" fill="#FEF2F2" stroke="#C03936" stroke-width="2"/><circle cx="8" cy="8" r="4.5" fill="none" stroke="#C03936" stroke-width="1.6"/><circle cx="8" cy="8" r="1.8" fill="#C03936"/></g>'
    }),
    stock: draw({
      outfit: '#C03936',
      hairFront: '<path d="M18 24 C18 14 27 10 34 11 C42 12 46 17 46 24 C41 18 33 17 26 20 C22 21 20 22 18 24 Z" fill="#4A2511" stroke="#2B2B33" stroke-width="1.8"/>',
      prop: '<g transform="translate(42,41)"><rect x="0" y="0" width="18" height="14" rx="2" fill="#FFFDF7" stroke="#2B2B33" stroke-width="1.7"/><rect x="3" y="6" width="3" height="5" fill="#1C6E3B"/><rect x="8" y="3" width="3" height="8" fill="#C03936"/><rect x="13" y="5" width="3" height="6" fill="#C03936"/></g>'
    }),
    market: draw({
      outfit: '#D97706', skin: '#F3C69F',
      hairFront: '<path d="M18 24 C19 12 45 12 46 24 C41 18 35 17 31 19 C25 17 20 19 18 24 Z" fill="#292524" stroke="#2B2B33" stroke-width="1.8"/>',
      prop: '<g transform="translate(44,41)"><circle cx="8" cy="8" r="8" fill="#FEF3C7" stroke="#2B2B33" stroke-width="1.7"/><polygon points="8,2.5 10,8 8,13.5 6,8" fill="#C03936" stroke="#2B2B33" stroke-width="1"/></g>'
    }),
    risk: draw({
      outfit: '#6D28D9',
      hairFront: '<path d="M18 24 C18 13 46 13 46 24 C41 18 34 18 32 20 C28 17 22 19 18 24 Z" fill="#3B0764" stroke="#2B2B33" stroke-width="1.8"/>',
      prop: '<g transform="translate(44,40)"><path d="M8 0 L16 3 V9 C16 14 12 17 8 19 C4 17 0 14 0 9 V3 Z" fill="#FDE047" stroke="#2B2B33" stroke-width="1.8"/><path d="M4.5 9.5 L7.2 12 L12 6.8" fill="none" stroke="#1C6E3B" stroke-width="2" stroke-linecap="round"/></g>'
    }),
    platform: draw({
      outfit: '#0284C7', glasses: true,
      hairFront: '<path d="M18 23 C19 13 29 10 36 11 C43 12 46 16 46 23 C40 18 24 18 18 23 Z" fill="#334155" stroke="#2B2B33" stroke-width="1.8"/>',
      prop: '<g transform="translate(44,41)"><circle cx="8" cy="8" r="6" fill="#E2E8F0" stroke="#2B2B33" stroke-width="1.8" stroke-dasharray="3 2"/><circle cx="8" cy="8" r="2.4" fill="#FFFDF7" stroke="#2B2B33" stroke-width="1.5"/></g>'
    })
  };

  return {
    get: function (key) {
      return svgs[key] || svgs.foreman;
    }
  };
})();
