<script setup>
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<template>
  <nav v-if="route.path !== '/login'">
    <router-link to="/">Notebook 總覽</router-link> |
    <router-link to="/import">資料匯入</router-link> |
    <router-link to="/ask">問答</router-link>
  </nav>
  <router-view />
</template>
