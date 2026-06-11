# 需求发生工具

好游快爆 · 游戏工具需求智能挖掘系统

## 项目结构

```
需求发生工具/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 入口，生命周期管理
│   │   ├── config.py          # 配置（支持 .env 覆盖）
│   │   ├── database.py        # 数据库引擎（SQLite/PostgreSQL）
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   │   ├── game.py        # 游戏信息
│   │   │   ├── platform_content.py  # 平台内容
│   │   │   ├── demand_signal.py     # 需求信号
│   │   │   ├── demand.py      # 需求卡片
│   │   │   └── daily_report.py      # 日报
│   │   ├── schemas/           # Pydantic 请求/响应模型
│   │   ├── services/          # 核心业务引擎
│   │   │   ├── data_adapter.py      # 数据接入（支持爬虫API / Mock）
│   │   │   ├── signal_engine.py     # 六维信号评分引擎
│   │   │   ├── llm_pipeline.py     # LLM 痛点提炼管线
│   │   │   ├── report_generator.py # 日报生成器
│   │   │   └── scheduler.py        # 每日定时调度
│   │   ├── api/               # REST API 路由
│   │   │   ├── games.py       # 游戏管理
│   │   │   ├── demands.py     # 需求查询/更新
│   │   │   ├── reports.py     # 日报
│   │   │   └── dashboard.py   # 看板首页聚合
│   │   └── utils/             # 工具函数
│   │       ├── text_similarity.py   # 文本相似度（重复提问检测）
│   │       └── keyword_matcher.py   # 关键词匹配（资格/工具检测）
│   ├── requirements.txt
│   └── .env
│
├── frontend/                   # React + TypeScript 前端
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/client.ts      # API 客户端
│   │   ├── types/index.ts     # TypeScript 类型定义
│   │   ├── components/
│   │   │   ├── Layout.tsx     # 全局布局（导航头）
│   │   │   ├── DemandCard.tsx # 需求卡片组件
│   │   │   └── SignalBar.tsx  # 信号进度条组件
│   │   ├── pages/
│   │   │   ├── DailyOverview.tsx    # 今日需求总览
│   │   │   ├── DemandDetail.tsx     # 需求详情（证据链）
│   │   │   ├── TrendTracking.tsx    # 趋势追踪（图表）
│   │   │   └── DemandManagement.tsx # 需求管理（筛选/状态）
│   │   └── styles/index.css
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
│
└── README.md
```

## 快速开始

### 1. 后端

```bash
cd backend

# 创建虚拟环境并安装依赖
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# 配置环境变量（编辑 .env 文件）
# LLM_API_KEY=your-key      # 填入 LLM API Key 启用 AI 分析
# CRAWLER_API_KEY=your-key  # 填入爬虫 API Key 对接真实数据

# 启动后端（开发模式，含 Mock 数据）
uvicorn app.main:app --reload --port 8000
```

首次启动会自动：
- 创建 SQLite 数据库
- 初始化 8 款热门游戏的种子数据
- 启动每日 06:00 的定时分析调度

### 2. 前端

```bash
cd frontend

npm install
npm run dev
```

前端运行在 `http://localhost:5173`，自动代理后端 API。

### 3. 首次使用

1. 打开浏览器访问 `http://localhost:5173`
2. 点击「立即分析」按钮，触发一次完整的分析管线
3. 系统将：拉取 Mock 数据 → 计算六维信号 → 规则 Fallback 分析 → 生成需求卡片和日报
4. 在需求管理页可以更改需求状态、添加备注

### 4. 配置真实 LLM

编辑 `backend/.env`：

```env
LLM_API_KEY=sk-your-key-here
LLM_API_BASE=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

配置后 LLM Pipeline 将自动启用，替代规则 Fallback，产出更精准的需求分析。

## 核心 API

| 端点 | 说明 |
|------|------|
| `GET /api/dashboard/summary` | 看板首页概览（今日需求数、趋势游戏、工具类型分布） |
| `GET /api/demands/today` | 今日需求列表 |
| `GET /api/demands/{id}` | 需求详情（含证据链、LLM 分析原文） |
| `PATCH /api/demands/{id}` | 更新需求状态/备注 |
| `GET /api/reports/latest` | 最新日报 |
| `GET /api/games` | 监控游戏列表 |
| `POST /api/pipeline/run` | 手动触发分析管线 |

## 工作流

```
爬虫API/Mock数据 → 数据接入 → 六维信号计算 → LLM痛点提炼 → 日报生成 → Web看板
                                          ↓
                                    需求卡片入库
                                          ↓
                            组员评估 → 状态跟进 → 采纳/驳回
```

## 技术栈

- **后端**：Python 3.11+ / FastAPI / SQLAlchemy (async) / APScheduler / OpenAI SDK
- **前端**：React 18 / TypeScript / Vite / Tailwind CSS / Recharts / Lucide Icons
- **数据库**：SQLite（开发）/ PostgreSQL（生产）
