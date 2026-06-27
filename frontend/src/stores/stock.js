import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useStockStore = defineStore('stock', () => {
  // Persist to localStorage
  const _symbol = ref(localStorage.getItem('finlab_stock') || '2330')
  const _name = ref(localStorage.getItem('finlab_stock_name') || '台積電')

  const symbol = computed(() => _symbol.value)
  const name = computed(() => _name.value)

  function setStock(sym, name_zh = '') {
    _symbol.value = sym
    _name.value = name_zh
    localStorage.setItem('finlab_stock', sym)
    localStorage.setItem('finlab_stock_name', name_zh)
  }

  return { symbol, name, setStock }
})
