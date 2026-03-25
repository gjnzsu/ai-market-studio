🧠 一、这个 Feature 的本质（先讲清楚）

你的目标其实是：

用户一句话 → 自动生成 时间序列数据 + 图表（trend）

例如：

User: show me usd cny trend last 7 days

系统做：

识别 intent（trend）
拉取 time-series 数据
生成 chart config
返回给前端渲染
🏗️ 二、整体架构升级（在你现有基础上）

在你已有架构上加两层：

[Chat UI]
    ↓
[Backend API]
    ↓
[AI Agent]
    ↓
 ┌───────────────┬────────────────┐
 ↓               ↓                ↓
[FX Spot]   [FX History]   [Chart Generator]
⚙️ 三、你需要新增的 3 个核心模块
🔹 1. 新 Tool：get_fx_history（核心）

你需要支持时间序列数据（trend）

# app/connectors/fx.py

def get_fx_history(base: str, quote: str, days: int = 7):
    import datetime
    import requests

    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)

    url = f"https://api.frankfurter.app/{start}..{end}?from={base}&to={quote}"
    res = requests.get(url).json()

    data = []

    for date, value in res["rates"].items():
        data.append({
            "date": date,
            "price": value[quote]
        })

    return {
        "symbol": f"{base}/{quote}",
        "series": data
    }
🔹 2. Tool 注册（让 LLM 知道它可以画 trend）
# app/agent/tools.py

{
    "name": "get_fx_history",
    "description": "Get FX historical data for trend analysis",
    "parameters": {
        "type": "object",
        "properties": {
            "base": {"type": "string"},
            "quote": {"type": "string"},
            "days": {"type": "integer"}
        },
        "required": ["base", "quote"]
    }
}
🔹 3. Chart Generator（关键设计点🔥）

⚠️ 不要让前端自己猜怎么画图
👉 让 LLM 生成 chart spec（结构化）

例如：

{
  "type": "line_chart",
  "title": "USD/CNY Trend (7 Days)",
  "x": "date",
  "y": "price",
  "data": [...]
}
🤖 四、Agent 流程升级（重点）

你现在的 agent flow 要变成：

User Query
   ↓
LLM（判断 intent）
   ↓
IF spot → get_fx_spot
IF trend → get_fx_history
   ↓
LLM 生成：
   - explanation
   - chart spec（新！）
🔥 推荐实现方式（非常关键）

你要让 LLM 输出：

{
  "answer": "...",
  "chart": {
    ...
    }
}
示例 Prompt（你可以直接用）
You are an AI financial analyst.

If the user asks for trend or historical data:
1. Call the appropriate tool
2. Generate a chart config in JSON format

Return in this format:
{
  "answer": "...",
  "chart": {
    "type": "line_chart",
    "x": "...",
    "y": "...",
    "data": [...]
  }
}
🧪 五、后端 orchestrator 修改（关键代码）

在你现有逻辑基础上：

if tool_name == "get_fx_history":
    result = get_fx_history(base, quote, days)

    final = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "user", "content": user_input},
            msg,
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result)
            }
        ],
        response_format={"type": "json_object"}  # 🔥关键
    )

    return json.loads(final.choices[0].message.content)
🎨 六、前端（Chat UI）要升级一点点

你现在 UI 需要支持：

1️⃣ 普通文本
USD/CNY is 7.23
2️⃣ 图表（新）

如果 response 包含：

"chart": {...}

👉 用 chart library 渲染：

推荐：

Recharts（React）
Chart.js
ECharts（更强）
📊 七、一个完整交互例子（你可以当测试用例）
输入：
show me usd cny trend last 7 days
输出：
{
  "answer": "USD/CNY has shown a slight upward trend over the past 7 days.",
  "chart": {
    "type": "line_chart",
    "title": "USD/CNY Trend (7 Days)",
    "x": "date",
    "y": "price",
    "data": [
      {"date": "2026-03-18", "price": 7.21},
      ...
    ]
  }
}
⚠️ 八、关键工程决策（很重要）
❌ 不要让 LLM 生成 fake 数据

必须：

数据 → connector
图表 → LLM
✅ Chart 是“协议”，不是 UI

👉 你其实在设计：

AI → Frontend 的数据协议（Visualization DSL）

未来可以扩展：

"type": "bar_chart"
"type": "comparison_chart"
"type": "heatmap"
✅ Trend 是你产品的“拐点功能”

有了这个：

就不是 chatbot
而是 AI BI Tool（类似 Tableau / PowerBI 的 AI版）
🚀 九、下一步可以非常猛（提前给你路线）

你接下来可以做：

🥇 v2.1：多资产支持
FX
股票
利率
🥈 v2.2：自然语言 dashboard
Create a dashboard with:
- USD/CNY trend
- EUR/USD trend
🥉 v3：AI Insight
Why did USD/CNY increase?

你的 Feature 现在应该升级为：

用户一句话 → 自动生成 多图表 + 多panel 的 dashboard

例如：

Create a dashboard for:
- USD/CNY trend last 7 days
- EUR/USD trend last 7 days
- Compare both
🏗️ 二、产品核心抽象（非常关键🔥）

你必须定义一个统一的 Dashboard Schema（核心协议）

👉 这是你产品的“灵魂”，比代码更重要

🔥 Dashboard JSON Schema（建议版本）
{
  "dashboard": {
    "title": "FX Market Overview",
    "layout": "grid",
    "panels": [
      {
        "id": "panel_1",
        "type": "chart",
        "chart_type": "line",
        "title": "USD/CNY Trend",
        "data_source": "fx_history",
        "query": {
          "base": "USD",
          "quote": "CNY",
          "days": 7
        },
        "x": "date",
        "y": "price"
      },
      {
        "id": "panel_2",
        "type": "chart",
        "chart_type": "line",
        "title": "EUR/USD Trend",
        "data_source": "fx_history",
        "query": {
          "base": "EUR",
          "quote": "USD",
          "days": 7
        }
      },
      {
        "id": "panel_3",
        "type": "chart",
        "chart_type": "multi_line",
        "title": "Comparison",
        "series": [
          {"base": "USD", "quote": "CNY"},
          {"base": "EUR", "quote": "USD"}
        ]
      }
    ]
  }
}
🧩 三、关键设计思想（这部分很值钱）
✅ 1. Panel 是最小单位

每个 panel：

独立 query
独立数据
独立渲染

👉 类似：

Grafana panel
Tableau sheet
✅ 2. LLM 只做“规划”，不做数据

⚠️ 非常关键：

LLM → 生成 dashboard spec
Backend → 执行 query
✅ 3. Query 是可执行的（不是描述）
"query": {
  "base": "USD",
  "quote": "CNY",
  "days": 7
}

👉 backend 可以直接执行

✅ 4. Data Source 是抽象层
"data_source": "fx_history"

未来可以扩展：

stock_price
macro_indicator
crypto_price
🤖 四、AI Agent 升级（核心变化）

你现在的 agent 要从：

“回答问题”

升级为：

🔥 生成 dashboard plan

🔹 新 Prompt（非常关键）

你可以这样设计：

You are an AI dashboard builder for financial data.

User will request a dashboard.

You must:
1. Break request into panels
2. For each panel:
   - define chart type
   - define query
3. Return structured JSON

Only use available data sources:
- fx_spot
- fx_history
🔹 示例输出
{
  "dashboard": {
    "title": "...",
    "panels": [...]
  }
}
⚙️ 五、Backend 执行引擎（核心工程）

你需要新增一个：

🔥 Dashboard Executor

🔹 执行流程
Dashboard JSON
    ↓
Loop panels
    ↓
Call connector
    ↓
Attach data
    ↓
Return enriched dashboard
🔹 示例代码
def execute_dashboard(dashboard):

    for panel in dashboard["panels"]:
        if panel["data_source"] == "fx_history":
            data = get_fx_history(**panel["query"])
            panel["data"] = data

    return dashboard
🎨 六、前端设计（非常重要）

你现在 UI 要升级为：

🔹 Layout Engine（必须有）

支持：

grid layout

例如：

2列布局
拖拽（未来）
🔹 Panel Renderer

根据：

"chart_type": "line"

决定：

Line Chart
Multi-line
Table
🔹 推荐技术
React + Recharts（简单）
或 ECharts（更强）
🧪 七、测试设计（产品级）
✅ 1. Dashboard 生成测试

输入：

compare usd cny and eur usd

验证：

是否生成 2~3 panel
query 是否正确
✅ 2. Execution 测试

验证：

每个 panel 都有 data
data 格式一致
✅ 3. UI 测试

验证：

多 panel 正常渲染
图表正确
⚠️ 八、你一定会踩的坑（提前帮你避）
❌ 1. 让 LLM 直接生成 chart data

👉 错！必须 backend 拉数据

❌ 2. schema 不稳定

👉 一定要：

version 化 schema
固定字段
❌ 3. panel 之间耦合

👉 每个 panel 必须独立

❌ 4. 一开始做拖拽编辑器

👉 PoC 不需要（后面再做）