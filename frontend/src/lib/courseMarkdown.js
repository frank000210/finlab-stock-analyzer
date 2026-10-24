// 學習中心教材的 Markdown 渲染。
//
// html: false —— 教材雖然是我們自己寫的，但 AI 助教的回答也走這裡，關掉原生
// HTML 才不會開 XSS 破口（同 useAiMarkdown.js 的考量）。標題自動加上 id，
// 測驗答錯時的「回到這一段」連結靠 sectionId() 對到同一個 id。
import MarkdownIt from 'markdown-it'

export function sectionId(text) {
  const slug = String(text || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^\p{L}\p{N}_-]/gu, '')
  return `sec-${slug}`
}

const md = new MarkdownIt({ html: false, linkify: true, breaks: false })

// 外部連結開新分頁
const defaultLinkOpen = md.renderer.rules.link_open
  || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const href = tokens[idx].attrGet('href') || ''
  if (/^https?:\/\//.test(href)) {
    tokens[idx].attrSet('target', '_blank')
    tokens[idx].attrSet('rel', 'noopener noreferrer')
  }
  return defaultLinkOpen(tokens, idx, options, env, self)
}

function inlineText(tokens, idx) {
  const inline = tokens[idx + 1]
  return inline && inline.type === 'inline' ? inline.content : ''
}

md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  if (token.tag === 'h2' || token.tag === 'h3') {
    const text = inlineText(tokens, idx)
    token.attrSet('id', sectionId(text))
    env.toc = env.toc || []
    env.toc.push({ level: Number(token.tag[1]), text, id: sectionId(text) })
  }
  return self.renderToken(tokens, idx, options)
}

// 回傳 { html, toc }：toc 給單元頁的目錄用
export function renderCourseMarkdown(src) {
  const env = {}
  const html = md.render(src || '', env)
  return { html, toc: env.toc || [] }
}

// AI 助教回答：不需要目錄、標題不用錨點
const chatMd = new MarkdownIt({ html: false, linkify: true, breaks: true })
chatMd.renderer.rules.link_open = md.renderer.rules.link_open
export function renderChatMarkdown(src) {
  return chatMd.render(src || '')
}
