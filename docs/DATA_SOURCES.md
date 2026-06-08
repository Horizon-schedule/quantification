# 免费数据源对照表

StopQuant 面向**个人学习研究**，优先使用**无需 API Key** 的公开数据。下表说明各类进阶数据在哪些平台可免费获取，以及本项目是否已接入。

## 总览

| 数据类型 | 免费平台 | 是否需要注册 | 本项目状态 |
|---------|---------|-------------|-----------|
| 日/周/月 K 线 | 东方财富 + 腾讯财经（自动备用） | 否 | ✅ 已接入 |
| 分钟 K 线（1/5/15/30/60） | 东方财富 push2his | 否 | ✅ 已接入（需网络可达） |
| 实时行情 / 分时 | 东方财富 | 否 | ✅ 已接入 |
| 财务主表 / 利润表 | 东方财富 datacenter | 否 | ✅ 已接入 |
| 资产负债表 / 现金流量表 | 东方财富 datacenter | 否 | ✅ 已接入 |
| 机构盈利预测 / 研报 | 东方财富 datacenter + reportapi | 否 | ✅ 已接入 |
| 北向资金（沪深港通） | 东方财富 datacenter | 否 | ✅ 已接入 |
| 龙虎榜 | 东方财富 datacenter | 否 | ✅ 已接入 |
| 十大股东 / 股东人数 | 东方财富 F10 | 否 | ✅ 已接入 |
| 重大合同 / 中标公告 | 东方财富公告 API | 否 | ✅ 已接入 |
| 公告 PDF 原文 | **巨潮资讯 cninfo.com.cn** | 否 | 🔗 跳转链接（官方免费查阅） |
| 历史日线备用 | Baostock | 需免费注册 | ⏸ 预留配置项 |
| 综合数据聚合 | AKShare（开源库） | 否（爬取公开源） | ⏸ 预留配置项 |
| Tick 逐笔成交 | — | — | ❌ 无稳定免费源 |
| Level-2 十档行情 | 券商 / 付费行情 | 需开户或付费 | ❌ 不接入 |

## 平台说明

### 1. 东方财富（主数据源，推荐）

- **费用**：公开网页/API，免费
- **注册**：不需要
- **覆盖**：A 股行情、K 线、F10、财务三表、北向、龙虎榜、研报汇总
- **限制**：请控制请求频率（本项目默认 0.5～0.6 秒/次）
- **配置**：`.env` 中 `DATA_SOURCE_PRIMARY=eastmoney`

### 2. 巨潮资讯（官方披露）

- **网址**：http://www.cninfo.com.cn
- **费用**：免费查阅、下载 PDF 公告
- **用途**：合同原文、年报 PDF、重大事项公告
- **本项目**：基本面页提供检索链接，不自动下载 PDF

### 3. Baostock（备用历史数据）

- **网址**：http://baostock.com
- **费用**：免费，需注册账号
- **覆盖**：历史 K 线、部分财务
- **状态**：`DATA_SOURCE_FALLBACK=baostock` 预留，后续版本可启用

### 4. AKShare（开源 Python 库）

- **费用**：开源免费
- **说明**：聚合多家公开源，适合脚本研究；生产环境需注意稳定性与合规
- **状态**：预留，未默认启用

### 5. 不可免费获取的数据

| 数据 | 原因 |
|-----|------|
| Tick 逐笔 | 交易所 Level-1 以上，无公开免费 API |
| Level-2 十档 | 需券商交易终端或付费行情 |
| 实时 Level-2 大单 | 同上 |

## 环境变量配置

复制并编辑配置：

```bash
cp .env.example .env
```

```env
# 主数据源
DATA_SOURCE_PRIMARY=eastmoney

# 模块开关（true / false）
ENABLE_MINUTE_KLINE=true
ENABLE_FINANCIAL_STATEMENTS=true
ENABLE_ANALYST_FORECAST=true
ENABLE_NORTHBOUND=true
ENABLE_DRAGON_TIGER=true
ENABLE_SHAREHOLDER=true
ENABLE_CNINFO_LINK=true
ENABLE_LEVEL2=false
```

修改后重启服务：

```bash
python main.py
# 或
docker compose restart
```

## API 端点

| 端点 | 说明 |
|-----|------|
| `GET /api/data-sources` | 查看当前数据源开关 |
| `GET /api/kline/<code>?period=5` | K 线（period: 1/5/15/30/60/101/102/103） |
| `GET /api/fundamental/<code>` | 基本面 + 扩展数据 |
| `GET /api/extended/<code>` | 仅扩展数据 |
| `GET /api/northbound?days=30` | 北向市场流向 |

## 合规提示

1. 所有数据**仅供个人学习研究**，禁止商用与转售
2. 遵守各平台 robots 协议与访问频率限制
3. 不对接券商实盘，不提供 Level-2 等受限数据
4. 财务与预测数据存在披露延迟，回测请注意**前视偏差**
