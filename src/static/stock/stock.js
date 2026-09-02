const data = window.portfolioData || {};
let perfMode = 'PERCENT';
let valInvestMode = 'VALUES';
let tickersMode = 'PERCENT';
let repartitionMode = 'PIE';
let compareTxChartInstance = null;

function switchTab(tabId, btnElement) {
  document
    .querySelectorAll('.tab-content')
    .forEach((el) => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach((el) => el.classList.remove('active'));

  document.getElementById(tabId).classList.add('active');
  btnElement.classList.add('active');

  Highcharts.charts.forEach((chart) => {
    if (chart) {
      chart.reflow();
    }
  });
}

Highcharts.setOptions({
  colors: [
    '#38bdf8',
    '#34d399',
    '#fbbf24',
    '#f87171',
    '#a78bfa',
    '#22d3ee',
    '#f472b6',
    '#e2e8f0',
  ],
  chart: {
    backgroundColor: 'transparent',
    style: { fontFamily: 'system-ui, sans-serif' },
  },
  title: { text: null },
  xAxis: {
    gridLineColor: '#334155',
    labels: { style: { color: '#94a3b8' } },
    lineColor: '#334155',
  },
  yAxis: {
    gridLineColor: '#334155',
    labels: { style: { color: '#94a3b8' } },
    title: { style: { color: '#94a3b8' } },
  },
  legend: {
    itemStyle: { color: '#cbd5e1' },
    itemHoverStyle: { color: '#ffffff' },
  },
  plotOptions: {
    series: {
      connectNulls: false,
      events: {
        legendItemClick: function (e) {
          const chart = this.chart;
          const seriesClicked = this;
          const now = new Date().getTime();
          const lastClick = seriesClicked.lastClick || 0;

          if (now - lastClick < 350) {
            e.preventDefault();
            const allSeries = chart.series;
            const otherSeriesVisible = allSeries.some(
              (s) => s !== seriesClicked && s.visible
            );

            chart.legend.blockRedraw = true;

            if (otherSeriesVisible) {
              allSeries.forEach((s) => s.setVisible(s === seriesClicked, false));
            } else {
              allSeries.forEach((s) => s.setVisible(true, false));
            }

            chart.legend.blockRedraw = false;
            chart.xAxis[0].setExtremes(null, null);
            chart.redraw();
            seriesClicked.lastClick = 0;
          } else {
            seriesClicked.lastClick = now;
          }
        },
        marker: { enabled: false },
      },
    },
  },
  tooltip: {
    backgroundColor: '#0f172a',
    borderColor: '#334155',
    style: { color: '#f8fafc' },
  },
  credits: { enabled: false },
});

function fixTimestamps(dataArray) {
  if (!Array.isArray(dataArray) || dataArray.length === 0) return [];
  return dataArray
    .map((point) => {
      if (!point || !Array.isArray(point)) return null;
      const ts = point[0] < 1e11 ? point[0] * 1000 : point[0];
      const rawVal = point[1];
      const isValidVal = rawVal !== null && rawVal !== undefined && !isNaN(rawVal);
      const val = isValidVal ? Number(rawVal) : 0;
      return [ts, val];
    })
    .filter((point) => point !== null && point[1] !== 0);
}

function fixMultiseries(seriesArray) {
  if (!seriesArray) return [];
  return seriesArray
    .map((s) => ({
      ...s,
      data: fixTimestamps(s.data),
    }))
    .filter((s) => s.data.length > 0);
}

function filterSeriesByStatus(seriesArray, statusFilter) {
  if (statusFilter === 'ALL' || !seriesArray || seriesArray.length === 0)
    return seriesArray;

  let globalMaxTimestamp = 0;
  seriesArray.forEach((series) => {
    if (series.data && series.data.length > 0) {
      const lastPoint = series.data[series.data.length - 1];
      if (lastPoint[0] > globalMaxTimestamp) {
        globalMaxTimestamp = lastPoint[0];
      }
    }
  });

  return seriesArray.filter((series) => {
    if (!series.data || series.data.length === 0) return false;
    const lastPoint = series.data[series.data.length - 1];
    const lastTimestamp = lastPoint[0];
    const isUpToDate = globalMaxTimestamp - lastTimestamp <= 259200000;

    if (statusFilter === 'OPEN') {
      return isUpToDate;
    } else if (statusFilter === 'CLOSED') {
      return !isUpToDate;
    }
    return true;
  });
}

function renderPerfChart() {
  const isPercent = perfMode === 'PERCENT';
  const currencySymbol = data.currency || '€';
  document.getElementById('perf-chart-title').innerText = 'Performance du Portefeuille';

  const percentSeriesConfig = [
    {
      name: 'Performance Portefeuille',
      type: 'area',
      data: fixTimestamps(data.timeseries?.portfolio_pct ?? []),
      color: '#34d399',
      negativeColor: '#f87171',
      threshold: 0,
    },
    {
      name: `Benchmark (${data.benchmark_ticker || 'Indice'})`,
      type: 'line',
      data: fixTimestamps(data.timeseries?.benchmark_pct ?? []),
      color: '#fbbf24',
      lineWidth: 2,
    },
  ];

  const currencySeriesConfig = [
    {
      name: 'Gains Totaux (Latents + Réalisés)',
      type: 'area',
      data: fixTimestamps(data.timeseries?.portfolio_total_gains ?? []),
      color: '#34d399',
      negativeColor: '#f87171',
      threshold: 0,
    },
    {
      name: 'Gains Latents',
      data: fixTimestamps(data.timeseries?.portfolio_latent_gain ?? []),
      type: 'line',
      color: '#38bdf8',
    },
    {
      name: `Gains Benchmark (${data.benchmark_ticker || 'Indice'})`,
      data: fixTimestamps(data.timeseries?.benchmark_gains ?? []),
      type: 'line',
      color: '#fbbf24',
      lineWidth: 2,
    },
  ];

  Highcharts.chart('chart-portfolio-performance', {
    chart: {
      type: 'area',
      zoomType: 'x',
      events: {
        selection: function (event) {
          const perfSeries = this.series[0];
          if (event.xAxis) {
            if (perfSeries.type !== 'line') {
              perfSeries.update({ type: 'line' }, false);
            }
          } else {
            if (perfSeries.type !== 'area') {
              perfSeries.update({ type: 'area' }, false);
            }
          }
        },
      },
    },
    xAxis: { type: 'datetime' },
    yAxis: {
      title: {
        text: isPercent ? 'Performance' : 'Gains Totaux',
      },
      labels: {
        format: isPercent ? '{value} %' : `{value} ${currencySymbol}`,
      },
      plotLines: [{ value: 0, width: 1, color: '#64748b', dashStyle: 'Dash' }],
    },
    tooltip: {
      shared: true,
      valueSuffix: isPercent ? ' %' : ` ${currencySymbol}`,
    },
    series: isPercent ? percentSeriesConfig : currencySeriesConfig,
    plotOptions: {
      area: { threshold: null },
      series: {
        marker: {
          enabled: false,
        },
      },
    },
  });
}

function togglePerfView() {
  const currencySymbol = data.currency || '€';
  perfMode = perfMode === 'PERCENT' ? 'CURRENCY' : 'PERCENT';
  document.getElementById('btn-toggle-perf').innerText =
    perfMode === 'PERCENT' ? `Basculer en ${currencySymbol}` : 'Basculer en %';
  renderPerfChart();
}

function renderValInvestChart() {
  const isValues = valInvestMode === 'VALUES';
  const statusFilter = document.getElementById('select-val-invest-status').value;
  const currencySymbol = data.currency || '€';

  document.getElementById('val-invest-chart-title').innerText = isValues
    ? `Valorisation Boursière par Ticker`
    : `Capital Investi par Ticker`;

  const baseSeries = isValues
    ? fixMultiseries(data.multiseries?.ticker_values)
    : fixMultiseries(data.multiseries?.ticker_investments);

  const filteredSeries = filterSeriesByStatus(baseSeries, statusFilter);

  Highcharts.chart('chart-val-invest-evolution', {
    chart: { type: 'line', zoomType: 'x' },
    xAxis: { type: 'datetime' },
    yAxis: {
      title: { text: 'Montant' },
      labels: { format: `{value} ${currencySymbol}` },
    },
    tooltip: { valueSuffix: ` ${currencySymbol}` },
    series: filteredSeries,
    plotOptions: {
      series: {
        marker: {
          enabled: false,
        },
      },
    },
  });
}

function toggleValInvestView() {
  valInvestMode = valInvestMode === 'VALUES' ? 'INVESTED' : 'VALUES';
  document.getElementById('btn-toggle-val-invest').innerText =
    valInvestMode === 'VALUES'
      ? 'Basculer sur Montant Investi'
      : 'Basculer sur Valorisation';
  renderValInvestChart();
}

function renderTickersChart() {
  const isPercent = tickersMode === 'PERCENT';
  const statusFilter = document.getElementById('select-ticker-status').value;
  const currencySymbol = data.currency || '€';

  document.getElementById('tickers-chart-title').innerText = isPercent
    ? 'Plus-Value Latente par Ticker'
    : `Valorisation Boursière par Ticker`;

  const baseSeries = isPercent
    ? fixMultiseries(data.multiseries?.ticker_latent_gains_pct)
    : fixMultiseries(data.multiseries?.ticker_latent_gains);

  const filteredSeries = filterSeriesByStatus(baseSeries, statusFilter);

  Highcharts.chart('chart-tickers-evolution', {
    chart: { type: 'line', zoomType: 'x' },
    xAxis: { type: 'datetime' },
    yAxis: {
      title: {
        text: isPercent ? 'Performance' : 'Valeur',
      },
      labels: {
        format: isPercent ? '{value} %' : `{value} ${currencySymbol}`,
      },
    },
    tooltip: { valueSuffix: isPercent ? ' %' : ` ${currencySymbol}` },
    series: filteredSeries,
    plotOptions: {
      series: {
        marker: {
          enabled: false,
        },
      },
    },
  });
}

function toggleTickersView() {
  const currencySymbol = data.currency || '€';
  tickersMode = tickersMode === 'PERCENT' ? 'CURRENCY' : 'PERCENT';
  document.getElementById('btn-toggle-tickers').innerText =
    tickersMode === 'PERCENT' ? `Basculer en ${currencySymbol}` : 'Basculer en %';
  renderTickersChart();
}

function renderRepartitionChart() {
  const isPie = repartitionMode === 'PIE';
  const cleanData = (data.repartition || []).filter((p) => (p.y || p.value) > 0);
  const currencySymbol = data.currency || '€';

  if (isPie) {
    const pieData = cleanData.map((item) => ({
      name: item.name,
      y: item.y !== undefined ? item.y : item.value,
      amount: item.amount || 0,
    }));

    Highcharts.chart('chart-repartition', {
      chart: { type: 'pie' },
      title: { text: null },
      tooltip: {
        pointFormat: `Pourcentage: {point.percentage:.1f}%<br/>Montant: {point.amount:.2f} ${currencySymbol}`,
      },
      plotOptions: {
        pie: {
          innerSize: '60%',
          dataLabels: {
            enabled: true,
            format: '<b>{point.name}</b>: {point.percentage:.1f}%',
            style: { color: '#cbd5e1' },
          },
        },
      },
      series: [{ name: 'Part', data: pieData }],
    });
  } else {
    const treemapData = cleanData.map((item) => {
      const pctVal = item.y !== undefined ? item.y : item.value;
      const euroVal = item.amount || 0;
      return {
        name: item.name,
        value: euroVal,
        pct: pctVal,
        colorValue: euroVal,
      };
    });

    Highcharts.chart('chart-repartition', {
      chart: { type: 'treemap' },
      title: { text: null },
      colorAxis: {
        minColor: '#1e293b',
        maxColor: '#38bdf8',
        labels: {
          style: { color: '#ffffff' },
        },
      },
      tooltip: {
        pointFormat: `<b>{point.name}</b>: {point.pct:.1f}%<br/>Montant: <b>{point.value:.2f} ${currencySymbol}</b>`,
      },
      series: [
        {
          type: 'treemap',
          layoutAlgorithm: 'squarified',
          dataLabels: {
            enabled: true,
            format: '{point.name}<br/><b>{point.pct:.1f}%</b>',
            style: { color: '#ffffff', textOutline: 'none' },
          },
          data: treemapData,
        },
      ],
    });
  }
}

function toggleRepartitionView() {
  repartitionMode = repartitionMode === 'PIE' ? 'TREEMAP' : 'PIE';
  document.getElementById('btn-toggle-repartition').innerText =
    repartitionMode === 'PIE' ? 'Vue Treemap' : 'Vue Donut';
  renderRepartitionChart();
}

function initCompareTxControls() {
  const tickerSelect = document.getElementById('select-compare-ticker');
  if (!data.compare_tx_pct || Object.keys(data.compare_tx_pct).length === 0) return;

  const tickers = Object.keys(data.compare_tx_pct);
  tickerSelect.innerHTML = '';
  tickers.forEach((tck) => {
    const opt = document.createElement('option');
    opt.value = tck;
    opt.innerText = tck;
    tickerSelect.appendChild(opt);
  });

  onCompareTickerChange();
}

function onCompareTickerChange() {
  const selectedTicker = document.getElementById('select-compare-ticker').value;
  const dateSelect = document.getElementById('select-compare-date');
  dateSelect.innerHTML = '';

  const availableDates = data.compare_tx_pct?.[selectedTicker]
    ? Object.keys(data.compare_tx_pct[selectedTicker])
    : [];

  const tickerTx = (data.all_transactions || []).filter(
    (tx) => tx.ticker === selectedTicker
  );

  availableDates.forEach((d) => {
    const tx = tickerTx.find((t) => t.date === d);
    const isSell = tx && tx.type === 'sell';

    const symbol = isSell ? '🔴' : '🟢';
    const labelType = isSell ? 'Vente' : 'Achat';

    const opt = document.createElement('option');
    opt.value = d;
    opt.innerText = `${symbol} ${labelType} du ${d}`;
    opt.className = isSell ? 'tx-option-sell' : 'tx-option-buy';

    dateSelect.appendChild(opt);
  });

  renderCompareTxChart();
}

function renderCompareTxChart() {
  const ticker = document.getElementById('select-compare-ticker').value;
  const dateStr = document.getElementById('select-compare-date').value;

  if (!ticker || !dateStr) return;

  const rawPortfolioData = data.compare_tx_pct?.[ticker]?.[dateStr] ?? [];
  const portfolioSeriesData = fixTimestamps(rawPortfolioData);

  const benchmarkTickerKey =
    data.benchmark_ticker && data.benchmark_tx_pct?.[data.benchmark_ticker]
      ? data.benchmark_ticker
      : Object.keys(data.benchmark_tx_pct || {})[0];

  const rawBenchmarkData =
    benchmarkTickerKey && data.benchmark_tx_pct?.[benchmarkTickerKey]
      ? data.benchmark_tx_pct[benchmarkTickerKey][dateStr]
      : [];
  const benchmarkSeriesData = fixTimestamps(rawBenchmarkData);

  const tickerTx = (data.all_transactions || []).filter((tx) => tx.ticker === ticker);

  const buyScatterData = [];
  const sellScatterData = [];

  tickerTx.forEach((tx) => {
    const txTs = tx.timestamp < 1e11 ? tx.timestamp * 1000 : tx.timestamp;
    const pt = portfolioSeriesData.find((p) => Math.abs(p[0] - txTs) < 86400000);
    if (pt) {
      const item = {
        x: pt[0],
        y: pt[1],
        custom: tx,
      };
      if (tx.type === 'buy') buyScatterData.push(item);
      else if (tx.type === 'sell') sellScatterData.push(item);
    }
  });

  compareTxChartInstance = Highcharts.chart('chart-compare-tx', {
    chart: { type: 'line', zoomType: 'x' },
    title: { text: null },
    xAxis: {
      type: 'datetime',
      labels: { format: '{value:%d/%m/%Y}' },
    },
    yAxis: {
      title: { text: 'Performance' },
      labels: { format: '{value:.1f} %' },
      plotLines: [{ value: 0, width: 1, color: '#64748b', dashStyle: 'Dash' }],
    },
    tooltip: {
      shared: true,
      formatter: function () {
        let s = `<b>${Highcharts.dateFormat('%d/%m/%Y', this.x)}</b><br/>`;
        this.points.forEach((point) => {
          if (point.series.type === 'scatter') {
            const tx = point.point.custom;
            const op = tx.type === 'buy' ? 'Achat' : 'Vente';
            s += `<span style="color:${point.color}">●</span> <b>${op}</b> : ${tx.shares} actions à ${tx.price} (€) (Total: ${tx.amount} €)<br/>`;
          } else {
            s += `<span style="color:${point.color}">●</span> ${point.series.name}: <b>${point.y.toFixed(2)} %</b><br/>`;
          }
        });
        return s;
      },
    },
    plotOptions: {
      series: {
        marker: {
          enabled: false,
        },
      },
    },
    series: [
      {
        id: 'main-ticker-series',
        name: ticker,
        data: portfolioSeriesData,
        color: '#38bdf8',
        lineWidth: 2.5,
        zIndex: 1,
      },
      {
        name: `Benchmark (${data.benchmark_ticker || 'Indice'})`,
        data: benchmarkSeriesData,
        color: '#fbbf24',
        lineWidth: 1.5,
        zIndex: 1,
      },
      {
        type: 'scatter',
        name: 'Achats',
        linkedTo: 'main-ticker-series',
        showInLegend: false,
        data: buyScatterData,
        zIndex: 2,
        marker: {
          enabled: true,
          symbol: 'triangle',
          fillColor: '#34d399',
          lineColor: '#059669',
          lineWidth: 1,
          radius: 5,
        },
      },
      {
        type: 'scatter',
        name: 'Ventes',
        linkedTo: 'main-ticker-series',
        showInLegend: false,
        data: sellScatterData,
        zIndex: 2,
        marker: {
          enabled: true,
          symbol: 'triangle-down',
          fillColor: '#f87171',
          lineColor: '#dc2626',
          lineWidth: 1,
          radius: 5,
        },
      },
    ],
  });
}

if (data) {
  const currencySymbol = data.currency || '€';

  document.getElementById('kpi-sharpe').innerText = data.kpis?.sharpe_ratio ?? 'N/A';
  document.getElementById('kpi-sortino').innerText = data.kpis?.sortino_ratio ?? 'N/A';
  document.getElementById('kpi-volatility').innerText = data.kpis?.volatility
    ? `${data.kpis.volatility} %`
    : 'N/A';
  document.getElementById('kpi-avg-correlation').innerText =
    data.kpis?.weighted_average_correlation ?? 'N/A';

  const grossValData = fixTimestamps(data.timeseries?.portfolio_gross_value ?? []);
  const pctData = fixTimestamps(data.timeseries?.portfolio_pct ?? []);
  const divData = fixTimestamps(data.timeseries?.portfolio_dividends ?? []);

  const latestGrossVal =
    grossValData.length > 0 ? grossValData[grossValData.length - 1][1] : 0;
  const latestPerf = pctData.length > 0 ? pctData[pctData.length - 1][1] : 0;
  const latestDiv = divData.length > 0 ? divData[divData.length - 1][1] : 0;

  document.getElementById('kpi-portfolio-value').innerText =
    `${latestGrossVal.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} ${currencySymbol}`;
  document.getElementById('kpi-portfolio-perf').innerText =
    `${latestPerf >= 0 ? '+' : ''}${latestPerf} %`;
  document.getElementById('kpi-portfolio-perf').style.color =
    latestPerf >= 0 ? '#34d399' : '#f87171';
  const kpiDivsEl = document.getElementById('kpi-portfolio-dividends');
  if (kpiDivsEl) {
    kpiDivsEl.innerText = `${latestDiv.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} ${currencySymbol}`;
  }

  document.getElementById('btn-toggle-tickers').innerText =
    tickersMode === 'PERCENT' ? `Basculer en ${currencySymbol}` : 'Basculer en %';

  Highcharts.chart('chart-portfolio-gross-value', {
    chart: {
      type: 'area',
      zoomType: 'x',
      events: {
        selection: function (event) {
          const grossSeries = this.series[0];
          if (event.xAxis) {
            if (grossSeries.type !== 'line') {
              grossSeries.update({ type: 'line' }, false);
            }
          } else {
            if (grossSeries.type !== 'area') {
              grossSeries.update({ type: 'area' }, false);
            }
          }
        },
      },
    },
    xAxis: { type: 'datetime' },
    yAxis: {
      title: { text: 'Valeur' },
      labels: { format: `{value} ${currencySymbol}` },
      min: null,
      startOnTick: false,
      endOnTick: false,
    },
    plotOptions: { area: { threshold: null }, series: { marker: { enabled: false } } },
    tooltip: { shared: true, valueSuffix: ` ${currencySymbol}` },
    series: [
      { name: 'Valeur Brute Totale', data: grossValData },
      {
        name: 'Valeur des Titres',
        type: 'line',
        data: fixTimestamps(data.timeseries?.portfolio_values ?? []),
      },
      {
        name: 'Capital Déposé (Apports)',
        type: 'line',
        step: 'left',
        data: fixTimestamps(data.timeseries?.portfolio_deposit ?? []),
        dashStyle: 'ShortDash',
        color: '#fbbf24',
      },
    ],
  });

  renderPerfChart();
  renderValInvestChart();
  renderTickersChart();
  renderRepartitionChart();
  initCompareTxControls();

  Highcharts.chart('chart-monthly-returns', {
    chart: { type: 'column' },
    title: {
      text: 'Rendements Mensuels',
      style: { color: '#f8fafc', fontSize: '16px' },
    },
    legend: {
      enabled: false,
    },
    xAxis: { type: 'datetime', labels: { format: '{value:%b %Y}' } },
    yAxis: {
      title: { text: 'Gain / Perte' },
      labels: { format: '{value} %' },
    },
    tooltip: { xDateFormat: '%B %Y', valueSuffix: ' %' },
    series: [
      {
        name: 'Rendement Mensuel',
        data: fixTimestamps(data.timeseries?.portfolio_monthly_returns ?? []),
        color: '#34d399',
        negativeColor: '#f87171',
        threshold: 0,
      },
    ],
  });

  const chartDividendsEl = document.getElementById('chart-dividends');
  if (chartDividendsEl) {
    Highcharts.chart('chart-dividends', {
      chart: { type: 'line', zoomType: 'x' },
      title: {
        text: `Cumul des Dividendes Reçus par Ticker`,
        style: { color: '#f8fafc', fontSize: '16px' },
      },
      xAxis: { type: 'datetime' },
      yAxis: {
        title: { text: 'Dividendes' },
        labels: { format: `{value} ${currencySymbol}` },
      },
      tooltip: { valueSuffix: ` ${currencySymbol}` },
      plotOptions: {
        series: {
          marker: {
            enabled: false,
          },
        },
      },
      series: fixMultiseries(data.multiseries?.ticker_dividends),
    });
  }

  const chartPortfolioDividendsEl = document.getElementById('chart-portfolio-dividends');
  if (chartPortfolioDividendsEl && divData.length > 0) {
    Highcharts.chart('chart-portfolio-dividends', {
      chart: { type: 'area', zoomType: 'x' },
      title: {
        text: `Évolution des Dividendes Cumulés du Portefeuille`,
        style: { color: '#f8fafc', fontSize: '16px' },
      },
      xAxis: { type: 'datetime' },
      yAxis: {
        title: { text: 'Dividendes' },
        labels: { format: `{value} ${currencySymbol}` },
      },
      tooltip: { shared: true, valueSuffix: ` ${currencySymbol}` },
      plotOptions: {
        area: { threshold: null },
        series: { marker: { enabled: false } },
      },
      series: [
        {
          name: 'Dividendes Cumulés',
          data: divData,
          color: '#34d399',
        },
      ],
    });
  }

  if (data.correlation?.categories && data.correlation?.data) {
    Highcharts.chart('chart-correlation', {
      chart: { type: 'heatmap' },
      title: { text: null },
      xAxis: { categories: data.correlation.categories },
      yAxis: { categories: data.correlation.categories, title: null },
      colorAxis: {
        min: -1,
        max: 1,
        minColor: '#ef4444',
        midColor: '#1e293b',
        maxColor: '#3b82f6',
      },
      legend: {
        align: 'right',
        layout: 'vertical',
        margin: 0,
        verticalAlign: 'top',
        y: 25,
        symbolHeight: 280,
      },
      tooltip: {
        formatter: function () {
          return (
            'Corrélation entre <b>' +
            this.series.xAxis.categories[this.point.x] +
            '</b> et <b>' +
            this.series.yAxis.categories[this.point.y] +
            '</b>: <b>' +
            this.point.value +
            '</b>'
          );
        },
      },
      series: [
        {
          name: 'Corrélation',
          borderWidth: 1,
          borderColor: '#334155',
          data: data.correlation.data,
          dataLabels: { enabled: true, color: '#ffffff' },
        },
      ],
    });
  }
}
