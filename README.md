# StopQuant 个人量化研究平台

> **合规声明**：本平台仅用于个人金融学习、量化策略研究与数据分析练习。不对接任何券商交易接口，无实盘交易功能，禁止商用。

## 平台简介

StopQuant 是一款面向个人开发者与小型量化研究团队的**轻量化离线量化分析平台**，专注 A 股、场内基金、大盘指数的行情数据分析、量化策略研发、历史回测、实时盯盘预警。

### 核心特性

- **合规数据源**：仅使用东方财富官方公开免费 API，限频请求、异常重试、接口熔断
- **Web 界面**：可视化 Dashboard，K 线蜡烛图、BOLL/RSI/KDJ/MACD、回测收益曲线
- **7 套内置策略**：均线、MACD、KDJ、成交量、BOLL、RSI、多指标共振
- **专业回测**：T+1、涨跌停限制、基准对比（沪深300）、Sortino/Calmar/信息比率
- **策略对比**：多策略并行回测、收益曲线叠加对比
- **参数优化**：网格搜索自动寻优
- **因子研究**：动量/波动率因子、IC 检验（对标 Qlib 轻量版）
- **条件选股**：5 种预置选股条件（对标聚宽选股器）
- **数据导出**：K 线 CSV、回测交易明细 CSV
- **Docker 部署**：Gunicorn 容器 + ECS 宿主机 Nginx 反代（无内置 Nginx 容器）
- **云数据库**：支持 PostgreSQL / MySQL 云数据库（阿里云 RDS、腾讯云等）

## 快速开始

### 1. 环境要求

- Python 3.9+
- Windows / macOS / Linux

### 2. 安装依赖

```bash
cd stop_quantification
pip install -r requirements.txt
```

### 3. 启动 Web 界面

```bash
python main.py
```

浏览器访问 http://127.0.0.1:5000

## 功能模块一览

| 模块 | 对标平台 | 功能 |
|------|----------|------|
| 行情分析 | 聚宽/米筐 | K线、BOLL、MA、MACD、RSI、KDJ、成交量 |
| 策略回测 | 米筐/RQAlpha | T+1、涨跌停、佣金印花税、基准超额收益 |
| 策略对比 | vnpy cta_backtester | 多策略并行回测、曲线对比 |
| 参数优化 | 聚宽参数扫描 | 网格搜索、按夏普/收益排序 |
| 因子研究 | Qlib/米筐因子库 | 动量/波动率因子、IC/IR 检验 |
| 条件选股 | 聚宽选股器 | 金叉/超卖/放量/布林等 5 种条件 |
| **基本面** | **F10/聚宽财务** | **公司概况、季度/年度营收利润、重大合同、中标公告** |
| 数据导出 | vnpy datamanager | K线/回测 CSV 导出 |
| 实时盯盘 | vnpy trader | 盯盘池、行情刷新 |

## Docker 生产部署（ECS + RDS MySQL）

> 完整图文步骤见 **[docs/DEPLOY_ECS_MYSQL.md](docs/DEPLOY_ECS_MYSQL.md)**

### 1. RDS MySQL 准备

- 创建 MySQL 8.0 实例，与 ECS **同一 VPC**
- 创建数据库 `stopquant` 和账号（见 `scripts/init_rds_mysql.sql`）
- 白名单添加 ECS **内网 IP**

### 2. ECS 配置 `.env`

```bash
cp .env.example .env
vim .env
```

```env
DB_TYPE=mysql
DB_HOST=rm-xxxxxxxx.mysql.rds.aliyuncs.com   # RDS 内网地址
DB_PORT=3306
DB_USER=stopquant
DB_PASSWORD=你的RDS密码
DB_NAME=stopquant
SECRET_KEY=随机32位字符串
APP_BIND_PORT=8000
```

### 3. 启动 Docker 并配置 Nginx

```bash
chmod +x scripts/deploy_ecs.sh
./scripts/deploy_ecs.sh
```

宿主机 Nginx 反代示例见 [docs/examples/nginx-host-stopquant.conf](docs/examples/nginx-host-stopquant.conf)。

```bash
curl http://127.0.0.1:8000/api/health
# 期望: {"status":"ok","database":true,"dialect":"mysql"}
```

浏览器经 Nginx 访问，例如 `https://quant.apiself.online/`

### 4. 命令行使用

```bash
# 查询实时行情
python main.py --quote 600519

# 获取 K 线数据
python main.py --kline 000001

# 运行回测示例
python main.py --backtest
```

## 目录结构

```
stop_quantification/
├── main.py                 # 主入口
├── requirements.txt        # 依赖
├── config/settings.py      # 全局配置
├── docs/ARCHITECTURE.md    # 架构设计文档
├── data/                   # SQLite 数据库（自动创建）
├── logs/                   # 系统日志
├── output/                 # 回测图表输出
└── quant_platform/         # 核心平台代码
    ├── api/                # 东方财富 API 封装
    ├── data/               # 数据清洗与存储
    ├── indicators/         # 技术指标
    ├── strategy/           # 量化策略
    ├── backtest/           # 回测引擎
    ├── monitor/            # 盯盘与告警
    └── ui/                 # Web 界面
```

## 配置说明

编辑 `config/settings.py` 或通过代码修改 `get_settings()` 返回的配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `api.request_interval` | API 请求间隔（秒） | 0.5 |
| `api.max_retries` | 最大重试次数 | 3 |
| `backtest.initial_capital` | 回测初始资金 | 100,000 |
| `backtest.commission_rate` | 佣金费率 | 0.0003 |
| `backtest.slippage` | 滑点 | 0 |
| `monitor.poll_interval` | 盯盘轮询间隔（秒） | 5 |
| `alert.email_enabled` | 邮件告警开关 | false |
| `alert.wechat_webhook` | 企业微信 Webhook URL | 空 |

### 邮件告警配置示例

```python
from config.settings import get_settings

settings = get_settings()
settings.alert.email_enabled = True
settings.alert.smtp_user = "your@qq.com"
settings.alert.smtp_password = "授权码"
settings.alert.email_to = ["receiver@example.com"]
```

## 自定义策略开发

继承 `BaseStrategy` 并实现 `generate_signals()` 方法：

```python
from quant_platform.strategy.base import BaseStrategy, SignalType
import pandas as pd

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="我的策略", params={"period": 10})

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        result["signal"] = SignalType.HOLD.value
        result["signal_reason"] = ""
        # 在此编写你的策略逻辑
        return result
```

## 内置策略参数

### 均线策略 (MAStrategy)

| 参数 | 说明 | 默认 |
|------|------|------|
| fast_period | 短期均线 | 5 |
| mid_period | 中期均线 | 10 |
| slow_period | 长期均线 | 20 |
| mode | cross/bull_align/bear_align | cross |

### MACD 策略

| 参数 | 说明 | 默认 |
|------|------|------|
| mode | cross/divergence | cross |
| fast/slow/signal | MACD 参数 | 12/26/9 |

### KDJ 策略

| 参数 | 说明 | 默认 |
|------|------|------|
| mode | cross/oversold/resonance | resonance |
| oversold/overbought | 超卖/超买阈值 | 20/80 |

### 成交量策略

| 参数 | 说明 | 默认 |
|------|------|------|
| mode | breakout/pullback/resonance | resonance |
| vol_ratio_high | 放量阈值 | 2.0 |

## 部署说明

### 本地开发

直接运行 `python main.py` 即可。

### 生产环境（可选）

使用 gunicorn 部署（Linux）：

```bash
pip install gunicorn
gunicorn -w 1 -b 127.0.0.1:5000 "quant_platform.ui.app:create_app()"
```

> 建议仅绑定 127.0.0.1，本平台设计为本地使用。

## 合规与免责声明

1. 本平台仅用于个人金融学习、量化策略研究、数据分析练习
2. 禁止商用、禁止非法套利
3. 不对接任何券商交易接口，不实现任何真实资金交易功能
4. 严格遵循东方财富接口使用规则，不高频请求、不恶意爬取
5. 所有数据、策略、结果仅本地存储，不上传第三方服务器
6. 平台提供的策略信号仅供参考，不构成任何投资建议

## 许可证

MIT License - 仅供学习研究使用
