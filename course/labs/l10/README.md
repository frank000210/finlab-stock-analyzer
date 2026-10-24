# Lab L10：期末專題

完整要求見單元內容。建議的 repo 結構：

```text
my-claude-toolkit/            ← 這個 repo 本身就是 marketplace
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── my-toolkit/
│       ├── .claude-plugin/plugin.json
│       ├── skills/
│       ├── agents/
│       ├── hooks/hooks.json
│       └── .mcp.json          （選用）
├── README.md                  ← 每個元件做什麼、為什麼選這個機制
└── PRINCIPLES.md              ← 5–10 條可帶回團隊的原則
```

`PRINCIPLES.md` 每一條用 `##` 標題開頭，內容包含：理由、Claude Code 的做法、換成其他工具要找什麼。

## 驗收

```bash
python check.py ./my-claude-toolkit
```

全部通過後，回到學習中心 L10 單元頁送出專題。
