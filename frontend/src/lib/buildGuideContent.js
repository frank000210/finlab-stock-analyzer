// 建站教學頁（/build-guide）的內容。改文字只要改這個檔，不用動版面。
// 標記語法見 guideText.js：**粗體**、`程式碼`、[文字](https://…)。
// 申請步驟與價格會隨官網改版而變：每次更新內容時一併更新 META.checkedOn 與 SOURCES。

export const META = {
  checkedOn: '2026-11-02',
  readMinutes: 15,
}

export const CHAPTERS = [
  { id: 'overview', title: '先看全貌：網站就像一間餐廳' },
  { id: 'words', title: '先認識 8 個名詞' },
  { id: 'github', title: '申請 GitHub 帳號', track: true },
  { id: 'hosting', title: '申請網路主機', track: true },
  { id: 'roles', title: '誰做什麼：人與 AI 的分工' },
  { id: 'cycle', title: '日常開發一輪長怎樣' },
  { id: 'after', title: '上線之後要顧的事' },
  { id: 'faq', title: '速查：檢查清單與常見問題', track: true },
]

export const QUICK = [
  '網站 = **程式**（存在 GitHub）＋ **主機**（一台 24 小時開機的電腦）＋ **網址**。',
  '**你**負責：開帳號、付款、決定要做什麼、驗收。**AI** 負責：寫程式、設定主機、測試、上線。',
  '每一輪只做一件小事，一定經過「機器人測試 → 上線 → 在真實網址驗證」才算完成。',
]

// 餐廳比喻：網站從想法到上線的六個動作
export const FLOW = [
  { icon: 'Lightbulb', name: '說出想法', like: '點菜', text: '用一般的話描述你要什麼，例如「我想比較幾檔 ETF 的配息」。' },
  { icon: 'Bot', name: 'AI 寫程式', like: '廚房', text: 'AI 依你的描述寫出網站的程式，並說明它做了什麼。' },
  { icon: 'GitBranch', name: '存到 GitHub', like: '食譜本', text: '所有程式與每一次修改都存在這裡，寫壞了可以退回任何一天。' },
  { icon: 'ClipboardCheck', name: '自動測試', like: '試吃', text: '機器人像客人一樣把每個按鈕點一遍；只要有一項失敗，就不准上線。' },
  { icon: 'Server', name: '放上主機', like: '店面', text: '主機是一台 24 小時開著、連著網路的電腦，網站住在裡面。' },
  { icon: 'Globe', name: '對外網址', like: '招牌', text: '別人輸入網址，就能走進你的網站。' },
]

// 本站實際配置（換成別家工具，整體流程與分工不變）
export const OUR_SETUP = [
  ['程式存放', 'GitHub'],
  ['主機', '騰訊雲 Lighthouse（新加坡，2 核 CPU、4GB 記憶體）'],
  ['網址', 'sslip.io 免費網址；連線加密（小鎖頭）由 Caddy 自動處理'],
  ['自動測試', 'Playwright：用真的瀏覽器把每個頁面點過'],
  ['資料庫', 'MongoDB，每天自動備份'],
  ['AI 助手', 'Claude Code'],
]

export const WORDS = [
  { term: 'GitHub', plain: '放程式的雲端資料夾', like: '像有完整修訂紀錄的共用雲端硬碟：誰、什麼時候、改了什麼，都查得到。' },
  { term: 'Repository（倉庫）', plain: 'GitHub 上的一個專案資料夾', like: '一個網站通常對應一個 repository。' },
  { term: 'Commit（存檔點）', plain: '把一批修改蓋章存起來，並寫一句說明', like: '像遊戲的存檔，之後可以回到這個時間點。' },
  { term: 'Push（上傳）', plain: '把存檔點送到 GitHub', like: '本站在 push 之前，必須先通過全部自動測試。' },
  { term: '主機（Server）', plain: '一台 24 小時開機的電腦', like: '網站住在上面，別人才連得到。' },
  { term: '網址與 IP', plain: '主機的門牌', like: 'IP 位址是一串數字門牌（像 1.2.3.4）；網址是好記的別名，背後指向那串數字。' },
  { term: '部署（Deploy）', plain: '把寫好的網站搬到主機上開張', like: '程式改好、存到 GitHub，不等於線上版已更新；要部署才算。' },
  { term: '資料庫', plain: '網站的記事本', like: '網站要記住的資料（例如你存下的組合）放在這裡，所以一定要備份。' },
]

// ── 申請 GitHub 帳號 ─────────────────────────────────
export const GITHUB = {
  lead: 'GitHub 帳號是你存放程式的「保險箱鑰匙」。個人使用免費：Free 方案 US$0、可建立無限個公開或私人倉庫，每月另有 2,000 分鐘的自動化額度（依 GitHub 定價頁）。',
  steps: [
    {
      id: 'g-prepare',
      title: '準備兩樣東西',
      items: [
        '一個你長期會用的 **Email**（用來收驗證碼）。不要用離職就會失效的公司信箱。',
        '一支**手機**（稍後設定兩步驟驗證會用到）。',
      ],
    },
    {
      id: 'g-signup',
      title: '註冊帳號',
      who: '這一步由你自己完成：帳號與你的身分綁在一起。',
      items: [
        '開啟 [github.com/signup](https://github.com/signup)。',
        '輸入 Email、密碼、使用者名稱；或點 **Continue with Google**（也可以用 Apple 帳號）直接註冊。',
        '依畫面完成「我不是機器人」驗證，再到信箱輸入收到的驗證碼。',
        '使用者名稱會出現在你的公開網址（`github.com/名稱`），挑一個不介意被別人看到的。',
      ],
      see: '完成後進入 GitHub 首頁，右上角有你的頭像。',
      warn: '若出現 “We couldn’t create your account”：換瀏覽器、清除 Cookie、停用瀏覽器外掛、換一個網路再試（官方建議）。GitHub 客服無法個別查詢註冊驗證失敗的原因。',
    },
    {
      id: 'g-2fa',
      title: '開啟兩步驟驗證（務必做）',
      who: '這一步由你自己完成。',
      items: [
        '點右上角頭像 → **Settings** → **Password and authentication** → **Enable two-factor authentication**。',
        '建議選「驗證器 App」（authenticator app，例如手機上的 Google Authenticator 或 Microsoft Authenticator）：掃畫面上的 QR code，再輸入 App 顯示的 6 位數字。',
        '簡訊驗證是官方最不建議的方式，沒有其他選擇時才用。',
        '在 “Save your recovery codes” 按 **Download** 存下備用碼，放在只有你找得到的地方（不要貼進聊天或公開的雲端資料夾），再按 **I have saved my recovery codes** 完成。',
      ],
      why: '帳號被盜，等於程式與網站都被盜。備用碼是手機遺失時唯一的救命繩。',
    },
    {
      id: 'g-repo',
      title: '建立第一個倉庫',
      items: [
        '點任一頁右上角的 **+** → **New repository**。',
        '在 **Repository name** 輸入英文名稱，例如 `my-first-site`。',
        '可見度選 **Private（私人）**：只有你邀請的人看得到。選 **Public（公開）** 則任何人都看得到程式。第一個網站建議先選私人。',
        '把 **Add README** 打開，按 **Create repository**。',
      ],
      see: '進入一個新頁面，網址是 `github.com/你的名稱/my-first-site`，裡面有一個 README 檔。',
    },
    {
      id: 'g-safety',
      title: '記住三條安全規則',
      items: [
        '**密碼、API 金鑰、Token（通行字串）**不要寫進程式，也不要貼進 GitHub。',
        '備用碼與私鑰檔只留在自己的電腦或密碼管理器。',
        'AI 助手要你提供密碼或金鑰時，先停下來：機密應該放在主機的設定檔，由你自己輸入，不經過對話。',
      ],
      why: '一旦機密被貼進 GitHub，即使刪掉，歷史紀錄裡仍然找得到，只能換一組新的。',
    },
  ],
  ours: '本站的程式放在 GitHub，每一次修改都留有紀錄；密碼與金鑰不放在 GitHub，只存在主機的設定檔裡。',
}

// ── 申請網路主機 ─────────────────────────────────────
export const HOSTING = {
  lead: '主機是網站住的地方。先選路線，再照本站實際用的方式（騰訊雲 Lighthouse）一步步申請。',
  routes: {
    head: ['路線', '像什麼', '優點', '要注意', '適合'],
    rows: [
      ['託管平台（把程式交給平台，由它代為上線）', '住進附家具的公寓', '設定最少；多數可綁 GitHub，改完自動上線', '平台政策由別人決定，說關就關；進階需求受限；費用常隨用量變動', '純展示、小型網站'],
      ['雲端主機（租一台虛擬電腦；本站用此路線）', '租一間空店面自己裝潢', '月費固定、完全自己掌控、隨時可搬家', '要有人設定與維護（可交給 AI，但你要看得懂風險）', '有資料庫、有多個功能的網站'],
      ['自己的電腦或公司機房', '在自家客廳開店', '不用租金', '要 24 小時開機、固定 IP；停電、斷網、資安都自己扛', '內部測試'],
    ],
  },
  lesson: {
    title: '本站的真實經驗：平台會倒，所以要能搬家',
    text: '本站原本放在託管平台 Zeabur。該平台在 2026-10 宣布將於 2026-12-31 停止營運，且發生過資安事件。本站在不到兩週內搬到自己租的主機，並更換資料庫與後台的密碼。能搬得快，是因為三件事：程式在 GitHub、網站用 Docker 封裝（像標準貨櫃，搬到哪台主機都能開張）、資料有備份。',
  },
  steps: [
    {
      id: 'h-account',
      title: '註冊騰訊雲（國際站）帳號',
      who: '這一步由你自己完成：涉及你的身分與付款，AI 不能也不該代辦。',
      items: [
        '開啟 [intl.cloud.tencent.com](https://intl.cloud.tencent.com)，按右上角 **Sign Up Free**。',
        '選擇**註冊地區**（會決定稅率，**註冊後無法更改**），輸入 Email 與登入密碼，按 **Send code** 填入信箱收到的驗證碼，勾選服務條款後按 **Sign up**。也可改用 Google 帳號註冊。',
        '依畫面填寫帳號名稱（個人填姓名）、地址、產業，輸入手機號碼與簡訊驗證碼，按 **Next**。',
        '綁定付款卡：支援 VISA、MasterCard、AMEX、銀聯、JCB 等。官方會先預授權 1 美元驗卡，1 至 5 個工作天內退回；**不支援虛擬卡與禮品卡**，部分簽帳金融卡可能失敗，換一張即可。',
      ],
      see: '進入 Tencent Cloud 主控台。要實際購買主機前，必須已綁定付款卡或完成授信。',
      warn: '實名認證：官方文件指出，必須完成認證的是購買「中國大陸地區」的服務；選新加坡等境外地區，官方文件沒有要求。若購買時畫面要求認證，依指示辦理。',
    },
    {
      id: 'h-create',
      title: '建立主機',
      who: '付款由你操作；選項可以請 AI 陪你確認。',
      items: [
        '登入後進入 **Lighthouse**（輕量應用伺服器）主控台，按 **Create** 進入購買頁。',
        '依序選：**地區**（離使用者近的；本站選新加坡）、**映像**（作業系統；本站用 Ubuntu 24.04，網路上教學最多）、**方案**（本站規格：2 核 CPU、4GB 記憶體、60GB 硬碟）、主機名稱、購買時長與數量（1 台）。',
        '確認金額後付款，等狀態變成 Running（運行中）。',
      ],
      see: '主機列表多了一筆新主機，並顯示一組「公網 IP（Public IP）」。把它記下來，後面會用到。',
    },
    {
      id: 'h-firewall',
      title: '檢查防火牆',
      items: [
        '防火牆像大樓門禁：只留需要的門，其他全部鎖上。',
        '新建主機預設會開放網頁（80、443）與遠端管理（22）。本站的原則是**只開這三個**，沒用到的規則一律刪除。',
        '到該主機的**防火牆**頁面，逐條確認。',
      ],
      why: '開的門越多，被攻擊的機會越大。',
    },
    {
      id: 'h-login',
      title: '建立登入用的金鑰',
      items: [
        '遠端管理主機要「登入」。本站不用密碼，改用**金鑰**：一對檔案，**公鑰**像鎖（放在主機上），**私鑰**像鑰匙（只放在你的電腦）。',
        '這一步可以請 AI 一步步帶你做，或請有經驗的同事協助。',
        '私鑰**絕不外傳**，也不要貼進對話、信件或 GitHub。',
        '做完後，請 AI 把主機改成「只接受金鑰登入」，並關閉密碼登入。',
      ],
    },
    {
      id: 'h-domain',
      title: '決定網址',
      items: [
        '**免費方案：sslip.io。** 把主機的 IP 寫進網址就能用，例如主機 IP 是 1.2.3.4，網址就是 `1-2-3-4.sslip.io`。本站就是這樣做的。',
        'sslip.io 是免費的公共服務，沒有服務保證。要長期對外服務，建議**購買自己的網域**（通常每年約 10 至 20 美元，依後綴與註冊商而異，以註冊商報價為準）。',
        '買了網域後，到註冊商的 **DNS 設定**新增一筆 A 記錄，把網址指向主機 IP，就是告訴全世界「這個招牌對應這個門牌」。這一步可請 AI 列出要填的欄位。',
        '網址前面出現小鎖頭，代表連線已加密。本站用 Caddy（網站服務軟體）自動取得並更新憑證，不用人工處理。',
      ],
      see: '在瀏覽器輸入網址，能看到網站首頁，網址列有小鎖頭。',
    },
    {
      id: 'h-cost',
      title: '記下費用與到期日',
      items: [
        '官方價格頁列出：2 核 4GB 的 Linux 方案，在新加坡等境外地區約 **US$6 至 8.5／月**（Starter 60GB 約 US$6.00；Razor Speed 約 US$8.50；價格頁更新於 2026-09-24，以購買頁為準）。',
        '方案內含每月流量，超出會另外計費（新加坡約每 GB US$0.081）。',
        '計費、續費與退款規則以官方 **Billing Overview** 為準。不要以為「關機」就不收費。',
        '把到期日記進行事曆；不再使用時，到主控台正式退租。',
      ],
    },
  ],
}

// ── 人與 AI 的分工 ───────────────────────────────────
export const ROLES = {
  human: {
    title: '你負責',
    items: [
      '開帳號、驗證身分、綁定付款',
      '決定要做什麼、不做什麼（排優先順序）',
      '保管密碼、金鑰與備用碼',
      '看計畫，並按下「核准」',
      '驗收：用起來對不對、好不好懂',
      '對外負責（品管、客戶、主管）',
    ],
  },
  ai: {
    title: 'AI 負責',
    items: [
      '把需求拆成步驟，提出計畫',
      '寫程式、修錯誤、補自動測試',
      '設定主機（安裝軟體、防火牆、網站服務）',
      '部署上線，並用真實網址驗證',
      '寫改善紀錄與說明文件',
      '回答「為什麼這樣做」',
    ],
  },
  why: '帳號、付款、密碼這類動作牽涉你的身分與金錢，責任在你；多數 AI 工具也刻意不替人開帳號、輸入密碼或付款。這不是限制，是保護你。',
  gates: [
    { name: '看計畫', text: 'AI 動手之前，先讀懂它打算做什麼；同意了再回「照建議」。' },
    { name: '看預覽', text: '改好的畫面，你親眼看過一遍。' },
    { name: '看上線結果', text: '在真實網址上，用你平常的方式操作一次。' },
  ],
}

// ── 日常開發一輪 ─────────────────────────────────────
export const CYCLE = {
  lead: '以本站一次真實的品管回報為例：品管測試 ETF 比較頁，回報 5 個問題，當天全部修好、上線、回報。',
  steps: [
    { who: '你', name: '品管回報問題', text: '品管發現：畫面重新整理後出現「查詢過於頻繁，請 10 分鐘後再試」。把原話與截圖貼給 AI。' },
    { who: 'AI', name: '整理成計畫', text: 'AI 把 5 則回報整理成一張表（問題、原因、做法）。你看完，回「照建議」。' },
    { who: 'AI', name: '找原因並修正', text: '原因：限流規則把「重新整理」也算成查詢，被擋時還會越按越久。AI 改了規則，並補上自動測試。' },
    { who: 'AI', name: '本機先驗證', text: 'AI 在自己的環境開起網站，把改到的功能點一遍。' },
    { who: '機器人', name: '自動檢查把關', text: '上傳前，機器人把整個網站數百項檢查跑完；只要有一項失敗，就不准上傳。' },
    { who: 'AI', name: '上線並驗證', text: '部署到主機後，AI 在真實網址連續重新整理 20 次，確認不再被擋。' },
    { who: 'AI', name: '回報品管', text: '產出一頁 PDF，逐項寫「怎麼修的、怎麼複測」，品管照著驗收。' },
  ],
  ask: {
    bad: '網站怪怪的，幫我修一下。',
    good: '在 ETF 比較頁，我按 F5 重新整理約 5 次後，畫面出現「查詢過於頻繁，請 10 分鐘後再試」（截圖附上）。我預期重新整理不該被擋。請先告訴我原因與修法，等我同意再動手。',
    tips: [
      '說清楚：**在哪個畫面、做了什麼、看到什麼、期望什麼。**',
      '一次只交一件事；很多件就請 AI 先整理成表格。',
      '能附截圖就附。',
      '**先要計畫，再動手**：這是你最重要的一道關卡。',
    ],
  },
}

// ── 上線之後 ─────────────────────────────────────────
export const AFTER = [
  { title: '備份', text: '資料庫每天自動備份，保留最近 7 份；並定期把備份拉回自己的電腦存一份。備份只有「還原成功過一次」才算數。' },
  { title: '上鎖', text: '主機只接受金鑰登入；防火牆只開 22、80、443；後台要密碼，連續輸錯會被暫時擋下。' },
  { title: '機密管理', text: '密碼與金鑰只放在主機的設定檔，不進 GitHub、不貼進對話。懷疑外洩就立刻換新。' },
  { title: '能搬家', text: '程式在 GitHub、網站用 Docker 封裝、資料有備份：換主機是「重新開張」，不是「重做」。' },
  { title: '改善紀錄', text: '每次改版都寫下改了什麼、為什麼、怎麼驗證，之後接手的人（包含你自己）才看得懂。' },
  { title: '費用與到期', text: '主機是月費。把到期日與每月預算記進行事曆，別讓網站因為忘了續費而消失。' },
]

// ── 速查 ─────────────────────────────────────────────
export const CHECKLIST = [
  { id: 'c-2fa', text: 'GitHub 帳號已開啟兩步驟驗證，備用碼已存好' },
  { id: 'c-repo', text: '第一個倉庫已建立（建議先選私人）' },
  { id: 'c-secret', text: '密碼與金鑰都沒有放進程式或 GitHub' },
  { id: 'c-firewall', text: '主機已建立，防火牆只開 22、80、443' },
  { id: 'c-url', text: '網址可以打開，而且網址前有小鎖頭' },
  { id: 'c-backup', text: '資料庫備份已設定，並實際還原演練過一次' },
  { id: 'c-calendar', text: '主機到期日與費用已記進行事曆' },
  { id: 'c-accept', text: 'AI 每次改版都附「怎麼複測」，而且你會驗收' },
]

export const FAQ = [
  {
    q: '完全不會寫程式，也做得出來嗎？',
    a: '可以做出像本站這樣的網站，但你一定要會兩件事：把需求說清楚、驗收成果。AI 寫的程式要靠自動測試把關，也要有人看得懂風險；複雜的網站，建議找有經驗的人在關鍵決定上陪你看一眼。',
  },
  {
    q: '一個月大概花多少？',
    a: '主機約 US$6 至 8.5（官方列價，2026-09-24）；GitHub 個人使用免費；網址用 sslip.io 免費，買自己的網域則每年另計約 10 至 20 美元；AI 助手的費用依你選的工具與方案而定。',
  },
  {
    q: 'AI 寫錯了怎麼辦？',
    a: '有三層保護：GitHub 可以退回任何一個存檔點；自動測試會擋掉明顯壞掉的版本；你在上線前後各驗收一次。',
  },
  {
    q: '資料與密碼安全嗎？',
    a: '本站做到：金鑰登入、防火牆只開必要的門、機密不進 GitHub、資料每天備份。但沒有任何網站是百分之百安全，所以請定期換密碼、驗證備份、不放不必要的個資。',
  },
  {
    q: '想換主機或換 AI 工具怎麼辦？',
    a: '換主機是重新開張，不是重做（見「上線之後要顧的事」）。換 AI 工具，流程與分工不變：你說需求、看計畫、驗收，AI 負責動手。',
  },
  {
    q: '我看到的畫面跟教學不一樣？',
    a: '官方網站會改版。請以官方文件為準（頁尾有來源連結），並把差異告訴我們，教學頁就會更新。',
  },
]

export const LINKS = [
  { to: '/guide', title: '新手上路', text: '教你怎麼用本站做交易紀律的完整流程。' },
  { to: '/learn', title: '學習中心', text: '想進一步自己客製 Claude Code 的人，從「L0 課前準備」開始（偏工程）。' },
]

export const SOURCES = [
  { title: 'GitHub Docs：Creating an account on GitHub', url: 'https://docs.github.com/en/get-started/start-your-journey/creating-an-account-on-github' },
  { title: 'GitHub Docs：Configuring two-factor authentication', url: 'https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication' },
  { title: 'GitHub Docs：Quickstart for repositories', url: 'https://docs.github.com/en/repositories/creating-and-managing-repositories/quickstart-for-repositories' },
  { title: 'GitHub：Pricing', url: 'https://github.com/pricing' },
  { title: 'Tencent Cloud：Signing Up', url: 'https://intl.cloud.tencent.com/document/product/378/17985' },
  { title: 'Tencent Cloud：Lighthouse 價格', url: 'https://intl.cloud.tencent.com/document/product/1103/47794' },
  { title: 'Tencent Cloud：身分驗證說明', url: 'https://intl.cloud.tencent.com/doc/product/378/3629' },
  { title: 'sslip.io', url: 'https://github.com/cunnie/sslip.io' },
]
