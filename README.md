# 开源项目工作区 (Open Source Project Workspace)

本目录为开源项目集锦与开发环境配置空间，包含标准化 GitHub Codespaces / Dev Containers 隔离开发环境以及已分类整理的开源工具项目。

---

## 📁 目录组织结构 (Directory Structure)

```text
c:\Users\xuhaojie\Desktop\GitHub\
├── .devcontainer/              # GitHub Codespaces / Dev Container 容器配置文件
├── .vscode/                    # VS Code 工作区及 Docker 路径修正配置
├── GEMINI.md                   # 开源项目搜索助手顾问规范与流程指南
├── README.md                   # 本工作区项目索引与管理文档
└── projects/                   # 项目分类归档目录
    ├── quant-trading/          # 【量化交易与选股工具箱】
    │   ├── Sequoia-X/          # A 股多进程量化选股系统 V2（BaoStock + SQLite + 飞书推送）
    │   ├── ashare-quant/       # A 股 AKShare 多因子选股打分、回测与实盘风控诊断助手
    │   └── vnpy-auto-trader/   # 基于 VeighNa (vn.py) 架构的自动化量化交易与回测机器人
    │
    ├── news-radar/             # 【热点资讯与情报监控】
    │   └── TrendRadar/         # 全网新闻热点资讯实时采集、去重过滤与智能推送助手
    │
    └── scratch/                # 【临时开发与测试脚本】
        └── hello.py            # 环境验证与连通性测试脚本
```

---

## 🚀 项目功能速查与使用指南

### 1. 📈 量化交易与选股工具 (`projects/quant-trading/`)

- **`Sequoia-X`（A 股量化选股系统 V2）**
  - **用途**：面向 A 股市场的量化选股系统，基于免费数据源 `BaoStock` 拉取日 K 数据存入 SQLite 数据库，收盘后自动跑选股策略并推送至飞书。
  - **运行命令**：`cd projects/quant-trading/Sequoia-X && python main.py`

- **`ashare-quant`（A 股多因子选股与风控诊断）**
  - **用途**：基于 `AKShare` 免费金融接口，提供多因子技术面选股打分（0-100分）、历史策略回测（双均线金叉等）以及止损止盈风控计算。
  - **运行命令**：`cd projects/quant-trading/ashare-quant && python main.py`

- **`vnpy-auto-trader`（VeighNa 自动化交易机器人）**
  - **用途**：基于中国领先的开源量化交易框架 VeighNa (vn.py) 思想搭建的自动化交易与策略回测机器人，支持策略信号生成与历史数据回测。
  - **运行命令**：`cd projects/quant-trading/vnpy-auto-trader && python auto_trader.py`

---

### 2. 📰 热点资讯与情报监控 (`projects/news-radar/`)

- **`TrendRadar`（热点新闻资讯监控与推送）**
  - **用途**：全网热点新闻资讯采集工具（支持微博热搜、知乎、各大新闻榜单），提供精准去重过滤、关键词监控与多渠道（微信/飞书/钉钉）智能推送。
  - **运行命令**：`cd projects/news-radar/TrendRadar`

---

### 3. 🛠 开发环境 (Dev Containers)

本项目已配置标准的 `.devcontainer` 开发容器环境：
- **按 `F1` 键** -> 点击 **`Dev Containers: Reopen in Container`** 即可直接加载包含 **Python 3.11**、**Node.js 20**、**Docker-in-Docker**、**Zsh** 等工具链的独立隔离开发环境。
