/**
 * StopQuant 前端交互逻辑（增强版）
 */

const App = {
    currentCode: '600519',
    currentTab: 'market',

    init() {
        this.bindEvents();
        this.loadQuote();
        this.loadKline();
        this.loadWatchlist();
        this.loadBacktestHistory();
        this.updateExportLink();
    },

    updateExportLink() {
        const period = document.getElementById('kline-period')?.value || '101';
        document.getElementById('btn-export').href =
            `/api/export/kline/${this.currentCode}?limit=500&period=${period}`;
    },

    bindEvents() {
        document.getElementById('btn-search').addEventListener('click', () => this.searchCode());
        document.getElementById('code-input').addEventListener('keydown', e => { if (e.key === 'Enter') this.searchCode(); });
        document.getElementById('btn-backtest').addEventListener('click', () => this.runBacktest());
        document.getElementById('btn-compare').addEventListener('click', () => this.runCompare());
        document.getElementById('btn-optimize').addEventListener('click', () => this.runOptimize());
        document.getElementById('btn-screener').addEventListener('click', () => this.runScreener());
        document.getElementById('btn-add-watch').addEventListener('click', () => this.addWatch());
        document.getElementById('btn-poll-watch').addEventListener('click', () => this.pollWatch());
        document.querySelectorAll('.nav-tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
        document.getElementById('kline-period').addEventListener('change', () => {
            this.updateExportLink();
            this.loadKline();
        });
    },

    switchTab(name) {
        this.currentTab = name;
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === `pane-${name}`));
        if (name === 'watch') this.pollWatch();
        if (name === 'history') this.loadBacktestHistory();
        if (name === 'factors') this.loadFactors();
        if (name === 'fundamental') this.loadFundamental();
    },

    toast(msg) {
        const el = document.createElement('div');
        el.className = 'toast'; el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(() => el.remove(), 3000);
    },

    async api(url, options = {}) {
        const resp = await fetch(url, options);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || '请求失败');
        return data;
    },

    searchCode() {
        const code = document.getElementById('code-input').value.trim();
        if (!code) return;
        this.currentCode = code;
        this.updateExportLink();
        this.loadQuote();
        this.loadKline();
        if (this.currentTab === 'fundamental') {
            this.loadFundamental();
        } else {
            this.switchTab('market');
        }
    },

    formatNum(n) {
        if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿';
        if (n >= 1e4) return (n / 1e4).toFixed(0) + '万';
        return n;
    },

    async loadQuote() {
        try {
            const q = await this.api(`/api/quote/${this.currentCode}`);
            const cls = q.change_pct >= 0 ? 'up' : 'down';
            const sign = q.change_pct >= 0 ? '+' : '';
            document.getElementById('quote-bar').innerHTML =
                `<span><strong>${q.name || q.code}</strong> ${q.code}</span>
                 <span class="price ${cls}">${q.price}</span>
                 <span class="${cls}">${sign}${q.change_pct}%</span>
                 <span style="color:var(--text-secondary)">量 ${this.formatNum(q.volume)}</span>`;
        } catch (e) {
            document.getElementById('quote-bar').innerHTML = `<span style="color:var(--text-secondary)">行情加载失败</span>`;
        }
    },

    async loadKline() {
        const container = document.getElementById('kline-chart');
        container.innerHTML = '<div class="loading"><div class="spinner"></div>加载 K 线...</div>';
        const period = document.getElementById('kline-period')?.value || '101';
        try {
            const data = await this.api(`/api/kline/${this.currentCode}?limit=200&period=${period}`);
            this.renderCandlestick(data, container);
            this.renderVolume(data);
            this.renderMacd(data);
            this.renderRsi(data);
            this.renderKdj(data);
        } catch (e) {
            container.innerHTML = `<div class="empty-state">${e.message}</div>`;
        }
    },

    renderCandlestick(data, container) {
        const traces = [{
            x: data.map(d => d.datetime), open: data.map(d => d.open), high: data.map(d => d.high),
            low: data.map(d => d.low), close: data.map(d => d.close),
            type: 'candlestick', increasing: { line: { color: '#ef4444' }, fillcolor: '#ef4444' },
            decreasing: { line: { color: '#10b981' }, fillcolor: '#10b981' },
        }];
        if (data[0]?.boll_upper) {
            traces.push({ x: data.map(d => d.datetime), y: data.map(d => d.boll_upper), type: 'scatter', mode: 'lines', name: 'BOLL上', line: { width: 1, dash: 'dot', color: '#8899aa' } });
            traces.push({ x: data.map(d => d.datetime), y: data.map(d => d.boll_lower), type: 'scatter', mode: 'lines', name: 'BOLL下', line: { width: 1, dash: 'dot', color: '#8899aa' } });
        }
        if (data[0]?.ma5) {
            traces.push({ x: data.map(d => d.datetime), y: data.map(d => d.ma5), type: 'scatter', mode: 'lines', name: 'MA5', line: { width: 1, color: '#f59e0b' } });
            traces.push({ x: data.map(d => d.datetime), y: data.map(d => d.ma20), type: 'scatter', mode: 'lines', name: 'MA20', line: { width: 1, color: '#3b82f6' } });
        }
        Plotly.newPlot(container, traces, {
            title: `${this.currentCode} K线`, paper_bgcolor: '#1a2332', plot_bgcolor: '#111827',
            font: { color: '#e8edf5' }, xaxis: { gridcolor: '#2d3a4f', rangeslider: { visible: false } },
            yaxis: { gridcolor: '#2d3a4f' }, margin: { t: 40, b: 40, l: 50, r: 20 },
        }, { responsive: true, displayModeBar: false });
    },

    _subChart(id, traces, title, height = 160) {
        Plotly.newPlot(id, traces, {
            title, paper_bgcolor: '#1a2332', plot_bgcolor: '#111827', font: { color: '#e8edf5', size: 11 },
            xaxis: { gridcolor: '#2d3a4f' }, yaxis: { gridcolor: '#2d3a4f' },
            margin: { t: 30, b: 25, l: 45, r: 10 }, height, showlegend: false,
        }, { responsive: true, displayModeBar: false });
    },

    renderVolume(data) {
        const colors = data.map(d => d.close >= d.open ? '#ef4444' : '#10b981');
        this._subChart('volume-chart', [{ x: data.map(d => d.datetime), y: data.map(d => d.volume), type: 'bar', marker: { color: colors } }], '成交量');
    },

    renderMacd(data) {
        if (!data[0]?.macd_dif) return;
        this._subChart('macd-chart', [
            { x: data.map(d => d.datetime), y: data.map(d => d.macd_dif), type: 'scatter', mode: 'lines', name: 'DIF', line: { color: '#3b82f6', width: 1 } },
            { x: data.map(d => d.datetime), y: data.map(d => d.macd_dea), type: 'scatter', mode: 'lines', name: 'DEA', line: { color: '#f59e0b', width: 1 } },
            { x: data.map(d => d.datetime), y: data.map(d => d.macd_hist), type: 'bar', marker: { color: data.map(d => d.macd_hist >= 0 ? '#ef4444' : '#10b981') } },
        ], 'MACD');
    },

    renderRsi(data) {
        if (!data[0]?.rsi) return;
        this._subChart('rsi-chart', [
            { x: data.map(d => d.datetime), y: data.map(d => d.rsi), type: 'scatter', mode: 'lines', line: { color: '#a855f7', width: 1.5 } },
            { x: data.map(d => d.datetime), y: Array(data.length).fill(70), type: 'scatter', mode: 'lines', line: { color: '#ef4444', width: 1, dash: 'dash' } },
            { x: data.map(d => d.datetime), y: Array(data.length).fill(30), type: 'scatter', mode: 'lines', line: { color: '#10b981', width: 1, dash: 'dash' } },
        ], 'RSI');
    },

    renderKdj(data) {
        if (!data[0]?.kdj_k) return;
        this._subChart('kdj-chart', [
            { x: data.map(d => d.datetime), y: data.map(d => d.kdj_k), type: 'scatter', mode: 'lines', line: { color: '#3b82f6', width: 1 } },
            { x: data.map(d => d.datetime), y: data.map(d => d.kdj_d), type: 'scatter', mode: 'lines', line: { color: '#f59e0b', width: 1 } },
            { x: data.map(d => d.datetime), y: data.map(d => d.kdj_j), type: 'scatter', mode: 'lines', line: { color: '#a855f7', width: 1 } },
        ], 'KDJ');
    },

    backtestPayload(extra = {}) {
        return {
            code: this.currentCode,
            strategy: document.getElementById('strategy-select').value,
            initial_capital: parseFloat(document.getElementById('capital-input').value) || 200000,
            benchmark: document.getElementById('benchmark-input').value || '000300',
            ...extra,
        };
    },

    async runBacktest() {
        this.switchTab('backtest');
        document.getElementById('backtest-result').innerHTML = '<div class="loading"><div class="spinner"></div>回测运行中...</div>';
        try {
            const data = await this.api('/api/backtest', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.backtestPayload()),
            });
            this.renderBacktestResult(data);
            this.loadBacktestHistory();
            this.toast('回测完成');
        } catch (e) {
            document.getElementById('backtest-result').innerHTML = `<div class="empty-state">${e.message}</div>`;
        }
    },

    renderBacktestResult(data) {
        const m = data.metrics;
        const retCls = m.total_return >= 0 ? 'positive' : 'negative';
        let html = `<div class="metrics-grid">
            ${this.metricCard('累计收益', m.total_return + '%', retCls)}
            ${this.metricCard('年化收益', m.annual_return + '%')}
            ${this.metricCard('最大回撤', m.max_drawdown + '%')}
            ${this.metricCard('夏普比率', m.sharpe_ratio)}
            ${this.metricCard('Sortino', m.sortino_ratio || '-')}
            ${this.metricCard('Calmar', m.calmar_ratio || '-')}
            ${this.metricCard('胜率', m.win_rate + '%')}
            ${this.metricCard('交易次数', m.trade_count)}`;
        if (m.benchmark_return != null) {
            html += `${this.metricCard('基准收益', m.benchmark_return + '%')}
                ${this.metricCard('超额收益', m.excess_return + '%')}
                ${this.metricCard('信息比率', m.info_ratio || '-')}`;
        }
        html += `</div>${this.renderTradesTable(data.trades)}`;
        document.getElementById('backtest-result').innerHTML = html;

        const traces = [];
        if (data.equity_curve) traces.push({ x: data.equity_curve.dates, y: data.equity_curve.values, type: 'scatter', name: '策略', line: { color: '#3b82f6', width: 2 } });
        if (data.benchmark_curve) traces.push({ x: data.benchmark_curve.dates, y: data.benchmark_curve.values, type: 'scatter', name: '基准', line: { color: '#8899aa', width: 1.5, dash: 'dash' } });
        if (traces.length) Plotly.newPlot('equity-chart', traces, {
            paper_bgcolor: '#1a2332', plot_bgcolor: '#111827', font: { color: '#e8edf5' },
            xaxis: { gridcolor: '#2d3a4f' }, yaxis: { gridcolor: '#2d3a4f', title: '权益' },
            margin: { t: 20, b: 40, l: 60, r: 20 }, height: 300, legend: { orientation: 'h' },
        }, { responsive: true, displayModeBar: false });
    },

    metricCard(label, value, cls = '') {
        return `<div class="metric-card"><div class="value ${cls}">${value}</div><div class="label">${label}</div></div>`;
    },

    renderTradesTable(trades) {
        if (!trades?.length) return '';
        const rows = trades.map(t => `<tr><td>${t.trade_date}</td><td><span class="tag tag-${t.action}">${t.action === 'buy' ? '买入' : '卖出'}</span></td><td>${t.price?.toFixed(2)}</td><td>${t.shares}</td><td>${t.signal_reason || '-'}</td></tr>`).join('');
        return `<table class="data-table"><thead><tr><th>日期</th><th>方向</th><th>价格</th><th>股数</th><th>信号</th></tr></thead><tbody>${rows}</tbody></table>`;
    },

    async runCompare() {
        this.switchTab('compare');
        document.getElementById('compare-table').innerHTML = '<div class="loading"><div class="spinner"></div>多策略对比中...</div>';
        try {
            const data = await this.api('/api/backtest/compare', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...this.backtestPayload(), strategies: ['ma', 'macd', 'kdj', 'combo', 'boll'] }),
            });
            const rows = data.comparison.map(r => {
                const cls = r.total_return >= 0 ? 'positive' : 'negative';
                return `<tr><td>${r.strategy}</td><td class="${cls}">${r.total_return}%</td><td>${r.annual_return}%</td><td>${r.max_drawdown}%</td><td>${r.sharpe_ratio}</td><td>${r.win_rate}%</td><td>${r.trade_count}</td></tr>`;
            }).join('');
            document.getElementById('compare-table').innerHTML =
                `<table class="data-table"><thead><tr><th>策略</th><th>累计收益</th><th>年化</th><th>回撤</th><th>夏普</th><th>胜率</th><th>交易</th></tr></thead><tbody>${rows}</tbody></table>`;

            const curves = data.equity_curves;
            const colors = ['#3b82f6', '#10b981', '#f59e0b', '#a855f7', '#ef4444', '#8899aa'];
            const traces = Object.entries(curves).map(([name, s], i) => ({
                x: s.dates, y: s.values, type: 'scatter', mode: 'lines', name,
                line: { color: colors[i % colors.length], width: name === '基准' ? 1.5 : 2, dash: name === '基准' ? 'dash' : 'solid' },
            }));
            Plotly.newPlot('compare-chart', traces, {
                title: '策略收益曲线对比', paper_bgcolor: '#1a2332', plot_bgcolor: '#111827',
                font: { color: '#e8edf5' }, xaxis: { gridcolor: '#2d3a4f' }, yaxis: { gridcolor: '#2d3a4f' },
                margin: { t: 40, b: 40, l: 60, r: 20 }, height: 350, legend: { orientation: 'h' },
            }, { responsive: true, displayModeBar: false });
            this.toast('策略对比完成');
        } catch (e) {
            document.getElementById('compare-table').innerHTML = `<div class="empty-state">${e.message}</div>`;
        }
    },

    async runOptimize() {
        const strategy = document.getElementById('strategy-select').value;
        this.toast('参数优化运行中，请稍候...');
        try {
            const data = await this.api('/api/backtest/optimize', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...this.backtestPayload(), strategy, metric: 'sharpe_ratio' }),
            });
            this.switchTab('backtest');
            const top = data.results.slice(0, 10);
            const rows = top.map((r, i) => `<tr><td>${i + 1}</td><td>${JSON.stringify(r.params)}</td><td>${r.score}</td><td>${r.total_return}%</td><td>${r.max_drawdown}%</td><td>${r.trade_count}</td></tr>`).join('');
            document.getElementById('backtest-result').innerHTML =
                `<div class="card-title">参数优化 Top10（按${data.metric}）</div>
                 <table class="data-table"><thead><tr><th>#</th><th>参数</th><th>得分</th><th>收益</th><th>回撤</th><th>交易</th></tr></thead><tbody>${rows}</tbody></table>`;
            this.toast('参数优化完成');
        } catch (e) { this.toast(e.message); }
    },

    async runScreener() {
        this.switchTab('screener');
        const condition = document.getElementById('screener-select').value;
        document.getElementById('screener-table').innerHTML = '<tr><td colspan="6"><div class="loading"><div class="spinner"></div>选股中...</div></td></tr>';
        try {
            const data = await this.api('/api/screener', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ condition, pool_size: 30 }),
            });
            document.getElementById('screener-table').innerHTML = data.results.length
                ? data.results.map(r => `<tr>
                    <td>${r.code}</td><td>${r.close}</td><td>${r.change_pct}%</td>
                    <td>${r.reason}</td><td>${r.datetime}</td>
                    <td><button class="btn btn-sm" onclick="App.pickStock('${r.code}')">查看</button></td></tr>`).join('')
                : '<tr><td colspan="6" class="empty-state">未找到符合条件的标的</td></tr>';
            this.toast(`选股完成，共 ${data.count} 只`);
        } catch (e) {
            document.getElementById('screener-table').innerHTML = `<tr><td colspan="6" class="empty-state">${e.message}</td></tr>`;
        }
    },

    pickStock(code) {
        document.getElementById('code-input').value = code;
        this.searchCode();
    },

    async loadFundamental() {
        const profileEl = document.getElementById('fundamental-profile');
        profileEl.innerHTML = '<div class="loading"><div class="spinner"></div>加载基本面数据...</div>';
        try {
            const data = await this.api(`/api/fundamental/${this.currentCode}`);
            const p = data.profile || {};
            profileEl.innerHTML = `
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                    <div>
                        <h3 style="margin-bottom:8px;color:var(--accent)">${data.name || p.name} (${data.code})</h3>
                        <p style="font-size:13px;color:var(--text-secondary);line-height:1.6">
                            <strong>行业：</strong>${p.industry || '-'}<br>
                            <strong>地区：</strong>${p.region || '-'}<br>
                            <strong>上市日期：</strong>${p.listing_date || '-'}<br>
                            <strong>主营业务：</strong>${(p.main_business || '-').slice(0, 120)}
                        </p>
                    </div>
                    <div>
                        <p style="font-size:13px;color:var(--text-secondary);line-height:1.6;max-height:120px;overflow-y:auto">
                            ${p.company_intro || '暂无公司简介'}
                        </p>
                    </div>
                </div>`;

            const s = data.latest_summary || {};
            document.getElementById('fundamental-summary').innerHTML = [
                ['报告期', s.report_type || s.report_date || '-'],
                ['营业收入', s.total_revenue || '-'],
                ['营收同比', s.revenue_yoy || '-'],
                ['净利润', s.net_profit || '-'],
                ['利润同比', s.net_profit_yoy || '-'],
                ['EPS', s.eps ?? '-'],
                ['ROE', s.roe || '-'],
                ['毛利率', s.gross_margin || '-'],
                ['总资产', s.total_assets || '-'],
            ].map(([l, v]) => this.metricCard(l, v)).join('');

            const reports = data.financial_reports || [];
            document.getElementById('fundamental-table').innerHTML = reports.map(r => `
                <tr>
                    <td>${r.report_date}</td><td>${r.report_type}</td>
                    <td>${r.total_revenue || '-'}</td><td>${r.revenue_yoy || '-'}</td>
                    <td>${r.net_profit || '-'}</td><td>${r.net_profit_yoy || '-'}</td>
                    <td>${r.eps ?? '-'}</td><td>${r.roe || '-'}</td><td>${r.gross_margin || '-'}</td>
                </tr>`).join('');

            const chart = data.revenue_chart || {};
            if (chart.dates?.length) {
                Plotly.newPlot('fundamental-revenue-chart', [
                    { x: chart.dates, y: chart.revenue, type: 'bar', name: '营业收入(亿)', marker: { color: '#3b82f6' } },
                    { x: chart.dates, y: chart.net_profit, type: 'bar', name: '净利润(亿)', marker: { color: '#10b981' } },
                ], {
                    paper_bgcolor: '#1a2332', plot_bgcolor: '#111827', font: { color: '#e8edf5' },
                    barmode: 'group', xaxis: { gridcolor: '#2d3a4f' }, yaxis: { gridcolor: '#2d3a4f', title: '亿元' },
                    margin: { t: 30, b: 80, l: 60, r: 20 }, height: 320, legend: { orientation: 'h' },
                }, { responsive: true, displayModeBar: false });
            }

            this.renderEventList('fundamental-contracts', data.contracts, '暂无重大合同公告');
            this.renderEventList('fundamental-bids', data.bid_wins, '暂无中标公告');
            this.renderExtended(data.extended || {});
        } catch (e) {
            profileEl.innerHTML = `<div class="empty-state">${e.message}</div>`;
        }
    },

    renderExtended(ext) {
        const avail = ext.availability || {};
        document.getElementById('fundamental-extended-status').innerHTML = [
            ['分钟K线', avail.minute_kline],
            ['三大报表', avail.financial_statements],
            ['盈利预测', avail.analyst_forecast],
            ['北向资金', avail.northbound],
            ['龙虎榜', avail.dragon_tiger],
            ['股东研究', avail.shareholder],
            ['巨潮PDF', avail.cninfo_pdf],
        ].map(([label, on]) => this.metricCard(label, on ? '已启用' : '已关闭')).join('');

        const fc = ext.analyst_forecast || {};
        const pred = fc.predict_eps || {};
        document.getElementById('fundamental-forecast').innerHTML = `
            <div class="metrics-grid" style="margin-bottom:8px">
                ${this.metricCard('覆盖机构', fc.rating_org_num ?? '-')}
                ${this.metricCard('买入/增持', `${fc.rating_buy ?? 0}/${fc.rating_add ?? 0}`)}
                ${this.metricCard('中性', fc.rating_neutral ?? '-')}
                ${this.metricCard('减持/卖出', `${fc.rating_reduce ?? 0}/${fc.rating_sell ?? 0}`)}
            </div>
            <p style="font-size:13px;color:var(--text-secondary)">
                EPS 预测：${pred.year1 || '-'} → ${pred.eps1 ?? '-'}，
                ${pred.year2 || '-'} → ${pred.eps2 ?? '-'}，
                ${pred.year3 || '-'} → ${pred.eps3 ?? '-'}
            </p>
            ${(fc.reports || []).slice(0, 5).map(r => `
                <div style="font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)">
                    ${r.publish_date} · ${r.org} · ${r.rating}<br>${r.title}
                </div>`).join('') || '<div class="empty-state">暂无研报</div>'}`;

        const sh = ext.shareholder || {};
        document.getElementById('fundamental-holders').innerHTML = `
            <p style="font-size:13px;margin-bottom:8px">股东人数：${sh.holder_count ?? '-'} ${sh.holder_count_change ? `(变化 ${sh.holder_count_change})` : ''}</p>
            ${(sh.top10_holders || []).map(h => `
                <div style="display:flex;justify-content:space-between;font-size:12px;padding:4px 0">
                    <span>${h.name}</span><span>${h.shares || '-'} (${h.ratio ?? '-'}%)</span>
                </div>`).join('') || '<div class="empty-state">暂无股东数据</div>'}`;

        const lhb = ext.dragon_tiger || [];
        document.getElementById('fundamental-lhb').innerHTML = lhb.length
            ? lhb.map(r => `<tr>
                <td>${r.date}</td><td>${r.change_pct ?? '-'}%</td>
                <td>${r.turnover || '-'}</td><td>${r.reason || '-'}</td></tr>`).join('')
            : '<tr><td colspan="4" class="empty-state">暂无龙虎榜记录</td></tr>';

        const stmts = ext.financial_statements || {};
        const stmtHtml = ['income', 'balance', 'cashflow'].map(key => {
            const rows = stmts[key] || [];
            if (!rows.length) return '';
            const title = { income: '利润表', balance: '资产负债表', cashflow: '现金流量表' }[key];
            return `<div style="margin-bottom:12px"><strong>${title}</strong>
                ${rows.slice(0, 3).map(r => `<div style="font-size:12px;color:var(--text-secondary)">${r.report_date}</div>`).join('')}
            </div>`;
        }).join('');
        document.getElementById('fundamental-statements').innerHTML = stmtHtml || '<div class="empty-state">暂无报表数据</div>';

        const nb = (ext.northbound_market || []).slice().reverse();
        if (nb.length) {
            Plotly.newPlot('fundamental-northbound-chart', [{
                x: nb.map(r => r.date), y: nb.map(r => r.net_buy_raw),
                type: 'bar', name: '净买入(元)',
                marker: { color: nb.map(r => (r.net_buy_raw >= 0 ? '#ef4444' : '#10b981')) },
            }], {
                paper_bgcolor: '#1a2332', plot_bgcolor: '#111827', font: { color: '#e8edf5' },
                xaxis: { gridcolor: '#2d3a4f' }, yaxis: { gridcolor: '#2d3a4f', title: '净买入' },
                margin: { t: 20, b: 60, l: 60, r: 20 }, height: 280,
            }, { responsive: true, displayModeBar: false });
        } else {
            document.getElementById('fundamental-northbound-chart').innerHTML =
                '<div class="empty-state">北向数据未启用或无数据</div>';
        }

        const cn = ext.cninfo || {};
        document.getElementById('fundamental-cninfo').innerHTML = cn.disclosure_search
            ? `公告 PDF 原文（巨潮资讯，免费）：<a href="${cn.disclosure_search}" target="_blank" style="color:var(--accent)">检索 ${ext.code} 公告</a>
               · <a href="${cn.company_page}" target="_blank" style="color:var(--accent)">公司披露页</a>
               ${ext.level2_note ? `<br><span style="color:#f59e0b">${ext.level2_note}</span>` : ''}`
            : '';
    },

    renderEventList(elId, events, emptyText) {
        const el = document.getElementById(elId);
        if (!events?.length) {
            el.innerHTML = `<div class="empty-state">${emptyText}</div>`;
            return;
        }
        el.innerHTML = events.map(e => `
            <div class="watch-item" style="flex-direction:column;align-items:flex-start;gap:4px;padding:10px 0">
                <div style="font-size:12px;color:var(--text-secondary)">${e.notice_date} · ${e.event_type}${e.amount ? ' · ' + e.amount : ''}</div>
                <div style="font-size:13px">${e.detail_url
                    ? `<a href="${e.detail_url}" target="_blank" style="color:var(--accent);text-decoration:none">${e.title}</a>`
                    : e.title}</div>
            </div>`).join('');
    },

    async loadFactors() {
        try {
            const data = await this.api(`/api/factors/${this.currentCode}`);
            const fv = data.factors;
            document.getElementById('factor-values').innerHTML =
                `<div class="metrics-grid">${Object.entries(fv).map(([k, v]) => this.metricCard(k, v)).join('')}</div>`;
            document.getElementById('factor-ic-table').innerHTML = data.ic_analysis.map(ic =>
                `<tr><td>${ic.factor || '-'}</td><td>${ic.ic_mean}</td><td>${ic.ic_std}</td><td>${ic.ic_ir}</td><td>${ic.forward_days || 5}</td></tr>`
            ).join('');
        } catch (e) {
            document.getElementById('factor-values').innerHTML = `<div class="empty-state">${e.message}</div>`;
        }
    },

    async loadWatchlist() {
        try {
            const list = await this.api('/api/watchlist');
            document.getElementById('watchlist').innerHTML = list.length
                ? list.map(w => `<div class="watch-item"><span>${w.code} ${w.name || ''}</span><button class="btn btn-sm btn-outline" onclick="App.removeWatch('${w.code}')">移除</button></div>`).join('')
                : '<div class="empty-state" style="padding:12px">暂无盯盘</div>';
        } catch (e) { /* ignore */ }
    },

    async addWatch() {
        const code = document.getElementById('watch-code').value.trim();
        if (!code) return;
        await this.api('/api/watchlist', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
        document.getElementById('watch-code').value = '';
        this.loadWatchlist();
        this.toast(`已添加 ${code}`);
    },

    async removeWatch(code) {
        await this.api('/api/watchlist', { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code }) });
        this.loadWatchlist();
    },

    async pollWatch() {
        const tbody = document.getElementById('watch-table');
        tbody.innerHTML = '<tr><td colspan="5"><div class="loading"><div class="spinner"></div>刷新中...</div></td></tr>';
        try {
            const data = await this.api('/api/watchlist/poll');
            tbody.innerHTML = data.length ? data.map(q => {
                const cls = q.change_pct >= 0 ? 'up' : 'down';
                return `<tr><td>${q.code}</td><td>${q.name || '-'}</td><td>${q.price}</td><td class="${cls}">${q.change_pct >= 0 ? '+' : ''}${q.change_pct}%</td><td>${this.formatNum(q.volume)}</td></tr>`;
            }).join('') : '<tr><td colspan="5" class="empty-state">盯盘池为空</td></tr>';
        } catch (e) { tbody.innerHTML = `<tr><td colspan="5" class="empty-state">${e.message}</td></tr>`; }
    },

    async loadBacktestHistory() {
        const el = document.getElementById('history-table');
        if (!el) return;
        try {
            const records = await this.api('/api/backtest/history');
            el.innerHTML = records.length ? records.map(r => {
                const cls = (r.total_return || 0) >= 0 ? 'positive' : 'negative';
                return `<tr><td>${r.created_at?.slice(0, 19) || '-'}</td><td>${r.strategy_name}</td><td>${r.code}</td>
                    <td class="${cls}">${r.total_return}%</td><td>${r.max_drawdown}%</td><td>${r.trade_count}</td>
                    <td><a href="/api/export/backtest/${r.id}" class="btn btn-sm btn-outline">CSV</a></td></tr>`;
            }).join('') : '<tr><td colspan="7" class="empty-state">暂无记录</td></tr>';
        } catch (e) { el.innerHTML = `<tr><td colspan="7" class="empty-state">${e.message}</td></tr>`; }
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
