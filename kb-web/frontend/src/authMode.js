// 後端 KB_WEB_PUBLIC=1 時為公開模式：瀏覽與問答免登入，只有匯入要 token。
// 只查一次，整個 SPA 共用同一個結果。
let modePromise = null

export function isPublicMode() {
  if (!modePromise) {
    modePromise = fetch('/api/auth-mode')
      .then((r) => (r.ok ? r.json() : { public: false }))
      .then((d) => d.public === true)
      .catch(() => false)
  }
  return modePromise
}
