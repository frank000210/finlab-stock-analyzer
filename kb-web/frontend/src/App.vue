<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()

const navItems = [
  { path: '/', label: 'Notebook 總覽' },
  { path: '/import', label: '資料匯入' },
  { path: '/ask', label: '問答' },
]
</script>

<template>
  <header v-if="route.path !== '/login'" class="topnav">
    <div class="topnav-inner">
      <div class="brand">
        <span class="brand-dot"></span>
        知識庫
      </div>
      <nav>
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          :class="{ active: route.path === item.path }"
        >
          {{ item.label }}
        </router-link>
      </nav>
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
  max-width: 880px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 40px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  white-space: nowrap;
}

.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent);
}

nav {
  display: flex;
  gap: 4px;
}

nav a {
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-dim);
  transition: background 0.15s ease, color 0.15s ease;
}

nav a:hover {
  color: var(--text);
  background: var(--surface-2);
}

nav a.active {
  color: var(--text);
  background: var(--accent-dim);
}

.app-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
