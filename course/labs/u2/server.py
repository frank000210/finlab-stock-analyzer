"""U2 lab：最小的 MCP server（官方 Python SDK）。

安裝：pip install mcp
加入 Claude Code：
    claude mcp add --scope project --transport stdio course-demo -- python server.py
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("course-demo")


@mcp.tool()
def word_count(text: str) -> int:
    """計算一段文字有幾個字（中文以字元計，空白不算）。"""
    return len(text.replace(" ", ""))


# TODO：加一個 reverse_text(text: str) -> str 工具，回傳反轉後的字串。
# 記得加上 @mcp.tool() 與一行 docstring——docstring 會變成工具說明，
# Claude 靠它判斷什麼時候該用這個工具。


if __name__ == "__main__":
    mcp.run()  # 預設走 stdio
