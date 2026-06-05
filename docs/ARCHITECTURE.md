# StopQuant 个人量化研究平台 - 系统架构设计

> **合规声明**：本平台仅用于个人金融学习、量化策略研究与数据分析练习，不对接任何券商交易接口，无实盘交易功能。

## 一、平台定位

面向个人开发者与小型量化研究团队的**轻量化离线量化分析平台**，专注 A 股、场内基金、大盘指数的行情分析、策略研发、历史回测、实时盯盘预警。

## 二、分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      展示层 (Presentation)                   │
│              Flask Web UI / 命令行入口 main.py               │
├─────────────────────────────────────────────────────────────┤
│                      告警层 (Alert)                          │
│         本地声音 / 邮件 / 企业微信 Webhook 多渠道推送         │
├─────────────────────────────────────────────────────────────┤
│                      盯盘层 (Monitor)                        │
│              实时轮询、策略信号检测、盯盘池管理                 │
├─────────────────────────────────────────────────────────────┤
│                      回测层 (Backtest)                       │
│         回测引擎、绩效统计、收益/回撤可视化、交易日志           │
├─────────────────────────────────────────────────────────────┤
│                      策略层 (Strategy)                       │
│    策略基类 + MA/MACD/KDJ/成交量策略 + 自定义策略扩展接口       │
├─────────────────────────────────────────────────────────────┤
│                      指标层 (Indicators)                     │
│         MA/MACD/KDJ/BOLL/RSI/成交量/量比/换手率 等             │
├─────────────────────────────────────────────────────────────┤
│                      数据层 (Data)                           │
│         数据清洗、SQLite 持久化、增量更新、本地调取             │
├─────────────────────────────────────────────────────────────┤
│                      接口层 (API)                            │
│    东方财富公开 API 统一封装、限频、重试、熔断、异常处理          │
└─────────────────────────────────────────────────────────────┘
```

## 三、目录结构

```
stop_quantification/
├── main.py                     # 平台主入口（CLI + Web 启动）
├── requirements.txt            # Python 依赖
├── README.md                   # 使用教程与部署说明
├── config/
│   ├── __init__.py
│   └── settings.py             # 全局配置（数据库、API、告警等）
├── docs/
│   └── ARCHITECTURE.md         # 本架构文档
├── data/                       # SQLite 数据库（自动创建）
├── logs/                       # 系统日志（自动创建）
├── output/                     # 回测图表、报表输出
└── quant_platform/
    ├── __init__.py
    ├── api/                    # 【接口层】东方财富 API
    │   ├── __init__.py
    │   ├── client.py           # HTTP 客户端（限频/重试/熔断）
    │   ├── eastmoney.py        # 行情/K线/分时/列表接口
    │   └── models.py           # 统一数据模型
    ├── data/                   # 【数据层】
    │   ├── __init__.py
    │   ├── database.py         # SQLite 建表与 CRUD
    │   ├── cleaner.py          # 数据清洗与标准化
    │   └── repository.py       # 数据仓库（缓存+增量更新）
    ├── indicators/             # 【指标层】
    │   ├── __init__.py
    │   └── technical.py        # 技术指标计算
    ├── strategy/               # 【策略层】
    │   ├── __init__.py
    │   ├── base.py             # 策略抽象基类
    │   ├── ma_strategy.py      # 均线策略
    │   ├── macd_strategy.py    # MACD 策略
    │   ├── kdj_strategy.py     # KDJ 策略
    │   └── volume_strategy.py  # 成交量策略
    ├── backtest/               # 【回测层】
    │   ├── __init__.py
    │   ├── engine.py           # 回测引擎
    │   ├── metrics.py          # 绩效指标统计
    │   └── visualizer.py       # 回测可视化
    ├── monitor/                # 【盯盘层】
    │   ├── __init__.py
    │   ├── watcher.py          # 实时盯盘
    │   └── alert.py            # 多渠道告警
    ├── ui/                     # 【展示层】
    │   ├── __init__.py
    │   ├── app.py              # Flask 应用
    │   ├── templates/          # HTML 模板
    │   └── static/             # 静态资源
    └── utils/
        ├── __init__.py
        └── logger.py           # 统一日志
```

## 四、模块功能说明

| 模块 | 职责 | 核心类/函数 |
|------|------|-------------|
| api.client | HTTP 请求、限频、重试、熔断 | `HttpClient` |
| api.eastmoney | 东方财富接口统一封装 | `EastMoneyAPI` |
| data.database | SQLite 自动建表、去重、增量写入 | `DatabaseManager` |
| data.cleaner | 空值/异常值清洗、单位标准化 | `DataCleaner` |
| data.repository | 本地缓存优先、接口补全 | `DataRepository` |
| indicators.technical | 技术指标批量计算 | `TechnicalIndicators` |
| strategy.base | 策略开发接口 | `BaseStrategy` |
| backtest.engine | 历史 K 线模拟交易 | `BacktestEngine` |
| backtest.metrics | 收益率/回撤/夏普等 | `PerformanceMetrics` |
| monitor.watcher | 盯盘池轮询监控 | `MarketWatcher` |
| monitor.alert | 声音/邮件/微信告警 | `AlertManager` |
| ui.app | Web 可视化界面 | Flask Routes |

## 五、数据流

```
东方财富公开 API
      ↓ (限频请求)
  api.eastmoney
      ↓ (原始 JSON)
  data.cleaner (清洗标准化)
      ↓
  data.database (SQLite 持久化)
      ↓
  data.repository (本地调取)
      ↓
  indicators.technical (指标计算)
      ↓
  strategy.* (策略信号生成)
      ↓
  backtest.engine / monitor.watcher
      ↓
  ui.app / alert (展示与告警)
```

## 六、扩展接口

- **新增指标**：在 `indicators/technical.py` 添加静态方法
- **新增策略**：继承 `BaseStrategy`，实现 `generate_signals()` 方法
- **新增告警渠道**：在 `AlertManager` 中添加发送方法
- **新增数据源**：实现与 `EastMoneyAPI` 相同的方法签名（预留）

## 七、技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| 数据库 | SQLite | 零配置、单文件、适合个人离线研究 |
| Web 框架 | Flask | 轻量、易部署、适合本地 GUI 替代 |
| 数据处理 | pandas/numpy | 量化行业标准 |
| 可视化 | matplotlib/plotly | K 线与交互图表兼顾 |
