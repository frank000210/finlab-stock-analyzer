// 外觀主題自訂：讓使用者在「設定」頁調整頁面/區塊/卡片的底色與邊界，
// 即時套到 :root（inline style，權重高於 stylesheet），並存 localStorage。
// 也支援把目前設定另存為「組合」，以及刪除自訂組合。
import { reactive } from 'vue'

const STORAGE_KEY = 'finlab_theme_v1'
const PRESETS_KEY = 'finlab_theme_presets_v1'

// 可調整欄位（key＝對應的 CSS 變數）。type: color=色票、width=邊界粗細(px)。
export const THEME_FIELDS = [
  { key: '--bg-primary', label: '頁面背景顏色', type: 'color' },
  { key: '--bg-card', label: '區塊背景顏色', type: 'color' },
  { key: '--block-border-width', label: '區塊邊界粗細', type: 'width' },
  { key: '--block-border-color', label: '區塊邊界顏色', type: 'color' },
  { key: '--card-inner-bg', label: '卡片背景顏色', type: 'color' },
  { key: '--card-inner-border-width', label: '卡片邊界粗細', type: 'width' },
  { key: '--card-inner-border-color', label: '卡片邊界顏色', type: 'color' },
]

// 預設值＝目前 main.css 的「純黑終端機」外觀。
export const DEFAULT_THEME = {
  '--bg-primary': '#000000',
  '--bg-card': '#131b30',
  '--block-border-width': '1px',
  '--block-border-color': '#24304a',
  '--card-inner-bg': '#1a2540',
  '--card-inner-border-width': '1px',
  '--card-inner-border-color': '#24304a',
}

// 內建常見組合（不可刪，永遠可選）。
export const BUILT_IN_PRESETS = [
  {
    id: 'builtin-terminal', name: '純黑終端機', builtin: true,
    values: { ...DEFAULT_THEME },
  },
  {
    id: 'builtin-navy', name: '經典深藍', builtin: true,
    values: {
      '--bg-primary': '#0b1121', '--bg-card': '#1a2540',
      '--block-border-width': '1px', '--block-border-color': '#2a3a5c',
      '--card-inner-bg': '#1f2d47', '--card-inner-border-width': '1px', '--card-inner-border-color': '#2a3a5c',
    },
  },
  {
    id: 'builtin-graphite', name: '石墨灰', builtin: true,
    values: {
      '--bg-primary': '#0e0f13', '--bg-card': '#1c1e26',
      '--block-border-width': '1px', '--block-border-color': '#33363f',
      '--card-inner-bg': '#24272f', '--card-inner-border-width': '1px', '--card-inner-border-color': '#33363f',
    },
  },
  {
    id: 'builtin-midnight', name: '午夜藍光', builtin: true,
    values: {
      '--bg-primary': '#050a16', '--bg-card': '#0f1b2e',
      '--block-border-width': '2px', '--block-border-color': '#1d3a5f',
      '--card-inner-bg': '#122540', '--card-inner-border-width': '1px', '--card-inner-border-color': '#1d3a5f',
    },
  },
  {
    id: 'builtin-highcontrast', name: '高對比描邊', builtin: true,
    values: {
      '--bg-primary': '#000000', '--bg-card': '#0d1220',
      '--block-border-width': '2px', '--block-border-color': '#3b82f6',
      '--card-inner-bg': '#141b2e', '--card-inner-border-width': '1px', '--card-inner-border-color': '#38507e',
    },
  },
]

function loadCurrent() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    return { ...DEFAULT_THEME, ...(saved && typeof saved === 'object' ? saved : {}) }
  } catch {
    return { ...DEFAULT_THEME }
  }
}

function loadPresets() {
  try {
    const saved = JSON.parse(localStorage.getItem(PRESETS_KEY) || '[]')
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

const state = reactive({
  current: loadCurrent(),
  presets: loadPresets(),
})

function applyToDom(values) {
  const root = document.documentElement
  Object.entries(values).forEach(([key, val]) => {
    if (val != null && val !== '') root.style.setProperty(key, val)
  })
}

// App 啟動時呼叫一次，把上次儲存的主題套回。
export function applySavedTheme() {
  applyToDom(state.current)
}

export function useTheme() {
  function setField(key, value) {
    state.current[key] = value
    applyToDom({ [key]: value })
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.current))
  }

  function applyPreset(values) {
    state.current = { ...DEFAULT_THEME, ...values }
    applyToDom(state.current)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.current))
  }

  function resetDefault() {
    applyPreset(DEFAULT_THEME)
  }

  // 把目前設定另存為新組合
  function addPreset(name) {
    const trimmed = (name || '').trim()
    if (!trimmed) return false
    state.presets.push({
      id: `custom-${Date.now()}`,
      name: trimmed,
      builtin: false,
      values: { ...state.current },
    })
    localStorage.setItem(PRESETS_KEY, JSON.stringify(state.presets))
    return true
  }

  function deletePreset(id) {
    const idx = state.presets.findIndex((p) => p.id === id)
    if (idx >= 0) {
      state.presets.splice(idx, 1)
      localStorage.setItem(PRESETS_KEY, JSON.stringify(state.presets))
    }
  }

  return { state, THEME_FIELDS, BUILT_IN_PRESETS, setField, applyPreset, resetDefault, addPreset, deletePreset }
}
