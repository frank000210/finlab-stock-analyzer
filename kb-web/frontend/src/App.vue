<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isPublicMode } from './authMode'
import ThemePicker from './components/ThemePicker.vue'

const route = useRoute()
const router = useRouter()

const publicMode = ref(false)
isPublicMode().then((v) => { publicMode.value = v })

const mainNavItems = [
  { path: '/', label: 'Notebook 總覽' },
  { path: '/import', label: '資料匯入', needsLogin: true },
  { path: '/ask', label: '問答' },
]

const patentNavItems = [
  { path: '/patent-plan', label: '規劃書' },
  { path: '/patent-report', label: '示範報告' },
  { path: '/patent-review', label: '審查備注' },
]

const navItems = computed(() => mainNavItems.filter((i) => !(publicMode.value && i.needsLogin)))
const isPatentActive = computed(() => patentNavItems.some((item) => item.path === route.path))

const patentMenuOpen = ref(false)
const patentDropdownRef = ref(null)
const patentBtnRef = ref(null)
const patentMenuRef = ref(null)
const patentMenuPos = ref({ top: '56px', left: '12px' })

function updatePatentMenuPosition() {
  const btn = patentBtnRef.value
  if (!btn) return
  const rect = btn.getBoundingClientRect()
  const menuWidth = 176
  const maxLeft = Math.max(12, window.innerWidth - menuWidth - 12)
  const left = Math.max(12, Math.min(rect.left, maxLeft))
  patentMenuPos.value = {
    top: `${Math.round(rect.bottom + 6)}px`,
    left: `${Math.round(left)}px`,
  }
}

function openPatentMenu(focusIndex = null) {
  updatePatentMenuPosition()
  patentMenuOpen.value = true
  if (focusIndex !== null) {
    nextTick(() => {
      const links = patentMenuRef.value?.querySelectorAll('a[role="menuitem"]')
      if (links && links.length) {
        const idx = focusIndex < 0 ? links.length - 1 : Math.min(focusIndex, links.length - 1)
        links[idx].focus()
      }
    })
  }
}

function closePatentMenu(restoreFocus = false) {
  if (!patentMenuOpen.value) return
  patentMenuOpen.value = false
  if (restoreFocus) {
    nextTick(() => patentBtnRef.value?.focus())
  }
}

function togglePatentMenu() {
  if (patentMenuOpen.value) {
    closePatentMenu(false)
  } else {
    openPatentMenu()
  }
}

function onPatentBtnKeydown(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    openPatentMenu(0)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    openPatentMenu(-1)
  } else if (e.key === 'Escape' && patentMenuOpen.value) {
    e.preventDefault()
    closePatentMenu(true)
  }
}

function onPatentMenuKeydown(e) {
  const links = Array.from(patentMenuRef.value?.querySelectorAll('a[role="menuitem"]') || [])
  if (!links.length) return
  const currentIdx = links.indexOf(document.activeElement)

  if (e.key === 'ArrowDown') {
    e.preventDefault()
    links[(currentIdx + 1) % links.length].focus()
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    links[(currentIdx - 1 + links.length) % links.length].focus()
  } else if (e.key === 'Home') {
    e.preventDefault()
    links[0].focus()
  } else if (e.key === 'End') {
    e.preventDefault()
    links[links.length - 1].focus()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    closePatentMenu(true)
  }
}

function onDocClick(e) {
  if (patentMenuOpen.value && patentDropdownRef.value && !patentDropdownRef.value.contains(e.target)) {
    closePatentMenu(false)
  }
}

function onDocKeydown(e) {
  if (e.key === 'Escape' && patentMenuOpen.value) {
    closePatentMenu(true)
  }
}

function onViewportChange() {
  if (patentMenuOpen.value) {
    updatePatentMenuPosition()
  }
}

watch(() => route.path, () => {
  closePatentMenu(false)
})

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onDocKeydown)
  window.addEventListener('resize', onViewportChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onDocKeydown)
  window.removeEventListener('resize', onViewportChange)
})

function logout() {
  localStorage.removeItem('kb_token')
  router.push('/login')
}
</script>

<template>
  <!-- 手繪線條用的 SVG 濾鏡（風格 8）：卡片的 ::before 邊框引用它 -->
  <svg class="sk-defs" width="0" height="0" aria-hidden="true" focusable="false">
    <defs>
      <filter id="sk-rough" x="-6%" y="-14%" width="112%" height="128%">
        <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="7" />
        <feDisplacementMap in="SourceGraphic" scale="2.6" />
      </filter>
    </defs>
  </svg>
  <div v-if="route.path === '/login'" class="login-theme"><ThemePicker /></div>
  <header v-if="route.path !== '/login'" class="topnav">
    <div class="topnav-inner">
      <div class="brand-group">
        <a
          class="portal-link"
          href="https://43-133-44-216.sslip.io/"
          title="回到 Frank 入口頁"
          data-testid="portal-back-link"
        >← 入口</a>
        <router-link to="/" class="brand" title="回到知識庫首頁">
          <span class="brand-dot"></span>
          知識庫
        </router-link>
      </div>

      <div class="nav-wrap">
        <nav aria-label="主導覽">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            :class="{ active: route.path === item.path }"
          >
            {{ item.label }}
          </router-link>

          <div class="nav-dropdown" ref="patentDropdownRef">
            <button
              ref="patentBtnRef"
              type="button"
              class="nav-dropdown-btn"
              :class="{ active: isPatentActive, open: patentMenuOpen }"
              aria-haspopup="menu"
              :aria-expanded="patentMenuOpen ? 'true' : 'false'"
              data-testid="patent-menu-btn"
              @click="togglePatentMenu"
              @keydown="onPatentBtnKeydown"
            >
              專利分析 <span class="nav-caret" aria-hidden="true">▾</span>
            </button>

            <div
              v-if="patentMenuOpen"
              ref="patentMenuRef"
              class="nav-dropdown-menu"
              role="menu"
              aria-label="專利分析子頁面"
              data-testid="patent-menu"
              :style="patentMenuPos"
              @keydown="onPatentMenuKeydown"
            >
              <router-link
                v-for="item in patentNavItems"
                :key="item.path"
                :to="item.path"
                role="menuitem"
                class="nav-dropdown-item"
                :class="{ active: route.path === item.path }"
                @click="closePatentMenu(false)"
              >
                <span>{{ item.label }}</span>
                <span v-if="route.path === item.path" class="menu-check" aria-hidden="true">✓</span>
              </router-link>
            </div>
          </div>
        </nav>
      </div>

      <div class="nav-right">
        <ThemePicker />
        <button v-if="!publicMode" class="secondary logout-btn" @click="logout">登出</button>
      </div>
    </div>
  </header>
  <main class="app-main">
    <router-view />
  </main>
</template>

<style scoped>
.topnav {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.topnav-inner {
  max-width: 940px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 24px;
}

.brand-group {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.portal-link {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-dim);
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.portal-link:hover {
  color: var(--text);
  border-color: var(--accent);
  background: var(--accent-dim);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  transition: background 0.15s ease;
}

.brand:hover {
  background: var(--surface-2);
}

.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}

.nav-wrap {
  min-width: 0;
  position: relative;
}

nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

nav > a,
.nav-dropdown-btn {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-dim);
  background: transparent;
  border: none;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.15s ease, color 0.15s ease;
}

nav > a:hover,
.nav-dropdown-btn:hover {
  color: var(--text);
  background: var(--surface-2);
}

nav > a.active,
.nav-dropdown-btn.active {
  color: var(--text);
  background: var(--accent-dim);
}

.nav-dropdown {
  position: relative;
  flex-shrink: 0;
}

.nav-dropdown-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.nav-dropdown-btn:active {
  transform: none;
}

.nav-caret {
  display: inline-block;
  font-size: 12px;
  transition: transform 0.15s ease;
}

.nav-dropdown-btn.open .nav-caret {
  transform: rotate(180deg);
}

.nav-dropdown-menu {
  position: fixed;
  z-index: 500;
  width: 176px;
  padding: 6px;
  background: var(--card);
  color: var(--ink);
  border: 1.5px solid var(--ink-2);
  border-radius: var(--radius);
  box-shadow: 0 10px 26px rgba(var(--shadow-rgb), 0.24);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-dropdown-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-dim);
  white-space: nowrap;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-dropdown-item:hover {
  color: var(--text);
  background: var(--surface-2);
}

.nav-dropdown-item.active {
  color: var(--text);
  font-weight: 600;
  background: linear-gradient(transparent 15%, var(--mark) 15%);
}

.menu-check {
  color: var(--heading);
  font-weight: 700;
  font-size: 12px;
}

.nav-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.logout-btn {
  padding: 6px 14px;
  font-size: 13px;
}

.sk-defs { position: absolute; width: 0; height: 0; overflow: hidden; }
.login-theme { position: absolute; top: 12px; right: 14px; z-index: 20; }

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

@media (max-width: 720px) {
  .topnav-inner {
    height: auto;
    padding: 10px 14px;
    flex-wrap: wrap;
    row-gap: 8px;
    column-gap: 10px;
  }

  .brand-group {
    order: 1;
    gap: 8px;
  }

  .portal-link {
    padding: 4px 8px;
    font-size: 12px;
  }

  .nav-right {
    order: 2;
    margin-left: auto;
  }

  .nav-wrap {
    order: 3;
    flex-basis: 100%;
    max-width: 100%;
  }

  /* 手機版導覽列右側漸層淡出提示可水平滑動 */
  .nav-wrap::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 28px;
    pointer-events: none;
    background: linear-gradient(to right, transparent, var(--surface) 88%);
  }

  nav {
    max-width: 100%;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-right: 26px;
  }

  nav::-webkit-scrollbar {
    display: none;
  }

  nav > a,
  .nav-dropdown-btn {
    padding: 6px 10px;
    font-size: 13px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .portal-link,
  .brand,
  nav > a,
  .nav-dropdown-btn,
  .nav-caret,
  .nav-dropdown-item {
    transition: none;
  }
}
</style>
