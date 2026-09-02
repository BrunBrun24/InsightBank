const MONTHS = [
  'Jan',
  'Fév',
  'Mar',
  'Avr',
  'Mai',
  'Juin',
  'Juil',
  'Août',
  'Sep',
  'Oct',
  'Nov',
  'Déc',
];

function round2(v) {
  return Math.round((v + Number.EPSILON) * 100) / 100;
}

function isIncome(catName) {
  return INCOMES_LIST.includes(catName);
}

let lastLegendClickTime = 0;
let legendClickTimer = null;

function handleLegendDoubleClick(event) {
  const seriesClicked = this;
  const chart = seriesClicked.chart;
  const now = new Date().getTime();
  const doubleClickDelay = 300;

  if (now - lastLegendClickTime < doubleClickDelay) {
    clearTimeout(legendClickTimer);
    event.preventDefault();

    const visibleSeries = chart.series.filter(
      (s) => s.visible && s.options.showInLegend !== false
    );
    const isOnlyThisVisible =
      visibleSeries.length === 1 && visibleSeries[0] === seriesClicked;

    chart.series.forEach((s) => {
      if (s.options.showInLegend !== false) {
        if (isOnlyThisVisible) {
          s.setVisible(true, false);
        } else {
          s.setVisible(s === seriesClicked, false);
        }
      }
    });

    chart.redraw();
    lastLegendClickTime = 0;
    return false;
  } else {
    lastLegendClickTime = now;
  }
}

if (!HAS_ONLY_INCOMES_OR_EXPENSES) {
  (function initBarChart() {
    let barChart;
    let viewMode = 'years';
    let detailLevel = 'none';
    let selectedYear = YEARS.length > 0 ? YEARS[0] : new Date().getFullYear();

    const yearSelect = document.getElementById('yearSelect');
    if (yearSelect) {
      yearSelect.innerHTML = '';
      YEARS.forEach((y, i) => {
        const opt = document.createElement('option');
        opt.value = y;
        opt.text = y;
        if (i === 0) opt.selected = true;
        yearSelect.appendChild(opt);
      });
      // Gestion du changement d'année
      yearSelect.onchange = () => {
        selectedYear = Number(yearSelect.value);
        renderBarChart();
      };
      // Toggle de la classe CSS is-hidden selon viewMode
      yearSelect.classList.toggle('is-hidden', viewMode !== 'months');
    }

    function buildBarSeries() {
      let categories = viewMode === 'years' ? [...YEARS].sort((a, b) => a - b) : MONTHS;
      let columnSeries = [];
      let depSeries = [],
        revSeries = [];

      if (detailLevel === 'none') {
        const depData = categories.map((label, idx) => {
          const y = viewMode === 'years' ? label : selectedYear;
          return round2(
            Object.keys(DATA_GLOBAL)
              .filter((c) => !isIncome(c))
              .reduce((s, c) => {
                return (
                  s +
                  Object.values(DATA_GLOBAL[c]).reduce((s2, sub) => {
                    if (!sub[y]) return s2;
                    return (
                      s2 +
                      (viewMode === 'years'
                        ? sub[y].reduce((a, b) => a + b, 0)
                        : sub[y][idx])
                    );
                  }, 0)
                );
              }, 0)
          );
        });

        const revData = categories.map((label, idx) => {
          const y = viewMode === 'years' ? label : selectedYear;
          return round2(
            Object.keys(DATA_GLOBAL)
              .filter((c) => isIncome(c))
              .reduce((s, c) => {
                return (
                  s +
                  Object.values(DATA_GLOBAL[c]).reduce((s2, sub) => {
                    if (!sub[y]) return s2;
                    return (
                      s2 +
                      (viewMode === 'years'
                        ? sub[y].reduce((a, b) => a + b, 0)
                        : sub[y][idx])
                    );
                  }, 0)
                );
              }, 0)
          );
        });

        columnSeries.push({
          name: 'Dépenses',
          type: 'column',
          stack: 'depenses',
          color: '#2CAFFE',
          data: depData,
        });
        columnSeries.push({
          name: 'Revenus',
          type: 'column',
          stack: 'revenus',
          color: '#544FC5',
          data: revData,
        });
      } else if (detailLevel === 'category') {
        Object.keys(DATA_GLOBAL).forEach((cat) => {
          const isInc = isIncome(cat);
          const data = categories.map((label, idx) => {
            const y = viewMode === 'years' ? label : selectedYear;
            return round2(
              Object.values(DATA_GLOBAL[cat]).reduce(
                (s, sub) =>
                  s +
                  (viewMode === 'years'
                    ? sub[y]?.reduce((a, b) => a + b, 0) || 0
                    : sub[y]?.[idx] || 0),
                0
              )
            );
          });
          if (data.some((v) => v !== 0)) {
            const s = {
              name: cat,
              type: 'column',
              stack: isInc ? 'revenus' : 'depenses',
              data,
            };
            isInc ? revSeries.push(s) : depSeries.push(s);
          }
        });
      } else if (detailLevel === 'subcategory') {
        Object.keys(DATA_GLOBAL).forEach((cat) => {
          const isInc = isIncome(cat);
          Object.keys(DATA_GLOBAL[cat]).forEach((sub) => {
            const data = categories.map((label, idx) => {
              const y = viewMode === 'years' ? label : selectedYear;
              return viewMode === 'years'
                ? round2(DATA_GLOBAL[cat][sub][y]?.reduce((a, b) => a + b, 0) || 0)
                : round2(DATA_GLOBAL[cat][sub][y]?.[idx] || 0);
            });
            if (data.some((v) => v !== 0)) {
              const s = {
                name: sub,
                type: 'column',
                stack: isInc ? 'revenus' : 'depenses',
                data,
              };
              isInc ? revSeries.push(s) : depSeries.push(s);
            }
          });
        });
      }

      if (detailLevel !== 'none') {
        depSeries.sort((a, b) => a.name.localeCompare(b.name));
        revSeries.sort((a, b) => a.name.localeCompare(b.name));
        columnSeries = [...depSeries, ...revSeries];
      }

      columnSeries.push({
        name: 'Épargne nette',
        type: 'line',
        yAxis: 1,
        color: '#00E272',
        data: categories.map(() => 0),
        lineWidth: 2,
        showInLegend: false,
        marker: { enabled: true, symbol: 'circle', radius: 4 },
        zones: [{ value: 0, color: '#FF0000' }, { color: '#00E272' }],
      });

      return { categories, series: columnSeries };
    }

    function updateNetSavings() {
      if (!barChart) return;
      const net = barChart.series.find((s) => s.name === 'Épargne nette');
      if (!net) return;
      const data = barChart.xAxis[0].categories.map((_, i) => {
        const r = barChart.series
          .filter((s) => s.visible && s.options.stack === 'revenus')
          .reduce((s, ser) => s + (ser.data[i]?.y || 0), 0);
        const d = barChart.series
          .filter((s) => s.visible && s.options.stack === 'depenses')
          .reduce((s, ser) => s + (ser.data[i]?.y || 0), 0);
        return round2(r - d);
      });
      net.setData(data, true);
    }

    function renderBarChart() {
      const data = buildBarSeries();
      if (!barChart) {
        barChart = Highcharts.chart('container_bar', {
          chart: { type: 'column' },
          title: { text: 'Analyse Financière Globale' },
          xAxis: { categories: data.categories, crosshair: true },
          yAxis: [
            {
              title: { text: 'Montant' },
              labels: { format: `{value} ${CURRENCY_SYMBOL}` },
            },
            {
              title: { text: 'Épargne nette' },
              opposite: true,
              labels: { format: `{value} ${CURRENCY_SYMBOL}` },
            },
          ],
          tooltip: {
            shared: false,
            useHTML: true,
            formatter: function () {
              let colorAmount;
              const stack = this.series.userOptions.stack;
              const name = this.series.name;

              if (stack === 'depenses') colorAmount = '#FF0000';
              else if (stack === 'revenus') colorAmount = '#00E272';
              else if (name === 'Épargne nette')
                colorAmount = this.y >= 0 ? '#00E272' : '#FF0000';

              const sign = this.y > 0 ? '+' : '';
              let html =
                `<span style="color:${colorAmount}">●</span> <b>${this.series.name}</b><br/>` +
                `Montant: <b style="color:${colorAmount}">${sign}${this.y} ${CURRENCY_SYMBOL}</b>`;

              if (this.series.name === 'Épargne nette' && viewMode === 'years') {
                const index = this.point.index;
                if (index > 0) {
                  const prevY = this.series.points[index - 1].y;
                  if (prevY && prevY !== 0) {
                    const change = ((this.y - prevY) / Math.abs(prevY)) * 100;
                    const colorV = change >= 0 ? '#00E272' : '#FF0000';
                    html += `<br/>Variation: <b style="color:${colorV}">${change > 0 ? '+' : ''}${change.toFixed(1)}%</b>`;
                  }
                }
              }
              return html;
            },
          },
          plotOptions: {
            column: { stacking: 'normal' },
            series: {
              events: {
                legendItemClick: function (e) {
                  const res = handleLegendDoubleClick.call(this, e);
                  setTimeout(updateNetSavings, 50);
                  return res;
                },
              },
            },
          },
          series: data.series,
        });
      } else {
        while (barChart.series.length) barChart.series[0].remove(false);
        data.series.forEach((s) => barChart.addSeries(s, false));
        barChart.xAxis[0].setCategories(data.categories, false);
        barChart.redraw();
      }
      updateNetSavings();
    }

    document.querySelectorAll('input[name="granularity"]').forEach((r) => {
      r.onchange = (e) => {
        detailLevel = e.target.value;
        renderBarChart();
      };
    });

    document.querySelectorAll('input[name="viewMode"]').forEach((r) => {
      r.onchange = (e) => {
        viewMode = e.target.value;
        if (yearSelect) {
          yearSelect.classList.toggle('is-hidden', viewMode !== 'months');
        }
        renderBarChart();
      };
    });

    renderBarChart();
  })();
}

(function initEvolutionChart() {
  let evoChart;
  let type = 'Depenses';
  let mode = 'year';
  let gran = 'total';

  const yearSelectEvo = document.getElementById('year_evo');
  if (yearSelectEvo) {
    yearSelectEvo.innerHTML = '';
    YEARS.forEach((y, i) => {
      const opt = document.createElement('option');
      opt.value = y;
      opt.text = y;
      if (i === 0) opt.selected = true;
      yearSelectEvo.appendChild(opt);
    });
    // Attachement de l'événement onchange
    yearSelectEvo.onchange = () => {
      renderEvoChart();
    };
    // Toggle de la classe CSS is-hidden selon mode
    yearSelectEvo.classList.toggle('is-hidden', mode !== 'month');
  }

  function getCurrentData() {
    if (!DATA_EVOLUTION) return {};
    return (
      DATA_EVOLUTION[type] ||
      DATA_EVOLUTION[type === 'Revenus' ? 'Revenu' : 'Depense'] ||
      {}
    );
  }

  function getColor() {
    return type === 'Revenus' ? '#544FC5' : '#2CAFFE';
  }

  function getRandomColor(i) {
    const colors = Highcharts.getOptions().colors;
    let base = Highcharts.color(colors[i % colors.length]);
    return base.brighten((Math.random() - 0.5) * 0.3).get();
  }

  function aggregate(selectedYear) {
    let result;
    const currentData = getCurrentData();
    if (mode === 'year') {
      result = YEARS.map((y) =>
        Object.values(currentData).reduce(
          (s, c) =>
            s +
            Object.values(c || {}).reduce(
              (s2, sub) => s2 + (sub[y]?.reduce((a, b) => a + b, 0) || 0),
              0
            ),
          0
        )
      );
    } else {
      result = Array.from({ length: 12 }, (_, i) =>
        Object.values(currentData).reduce(
          (s, c) =>
            s +
            Object.values(c || {}).reduce(
              (s2, sub) => s2 + (sub[selectedYear]?.[i] || 0),
              0
            ),
          0
        )
      );
    }
    return result.map(round2);
  }

  function pct(values) {
    let res = [];
    for (let i = 0; i < values.length; i++) {
      if (i === 0 || values[i - 1] === 0) res.push(null);
      else res.push(round2(((values[i] - values[i - 1]) / values[i - 1]) * 100));
    }
    return res;
  }

  function updateDynamicMetrics(chart) {
    const columnSeries = chart.series.filter(
      (s) => s.options.type === 'column' && s.visible
    );
    if (columnSeries.length === 0) return;

    const numPoints = columnSeries[0].data.length;
    let visibleTotals = Array(numPoints).fill(0);

    columnSeries.forEach((s) => {
      s.data.forEach((pt, i) => {
        visibleTotals[i] += pt.y || 0;
      });
    });

    visibleTotals = visibleTotals.map(round2);
    const avg = visibleTotals.reduce((a, b) => a + b, 0) / (visibleTotals.length || 1);

    const avgSeries = chart.series.find((s) => s.name && s.name.startsWith('Moyenne'));
    if (avgSeries) avgSeries.setData(Array(numPoints).fill(round2(avg)), false);

    const pctSeries = chart.series.find((s) => s.name === 'Variation %');
    if (pctSeries) pctSeries.setData(pct(visibleTotals), false);

    chart.redraw();
  }

  function buildEvoSeries() {
    const selectedYear = yearSelectEvo
      ? parseInt(yearSelectEvo.value) || YEARS[0]
      : YEARS[0];
    let series = [];
    const legendEvents = {
      legendItemClick: function (e) {
        const c = this.chart;
        const res = handleLegendDoubleClick.call(this, e);
        setTimeout(() => updateDynamicMetrics(c), 50);
        return res;
      },
    };

    const currentData = getCurrentData();
    const displayTypeName = type === 'Revenus' ? 'Revenus' : 'Dépenses';

    if (gran === 'total') {
      let totals = aggregate(selectedYear);
      series.push({
        name: displayTypeName,
        data: totals,
        type: 'column',
        color: getColor(),
        events: legendEvents,
      });
    }

    if (gran === 'cat') {
      Object.entries(currentData).forEach(([cat, subs]) => {
        let data =
          mode === 'year'
            ? YEARS.map((y) =>
                Object.values(subs || {}).reduce(
                  (s, sub) => s + (sub[y]?.reduce((a, b) => a + b, 0) || 0),
                  0
                )
              )
            : Object.values(subs || {}).reduce(
                (arr, sub) => arr.map((v, i) => v + (sub[selectedYear]?.[i] || 0)),
                Array(12).fill(0)
              );

        series.push({
          name: cat,
          data: data.map(round2),
          type: 'column',
          stack: 't',
          color: getRandomColor(series.length),
          events: legendEvents,
        });
      });
    }

    if (gran === 'sub') {
      Object.entries(currentData).forEach(([cat, subs]) => {
        Object.entries(subs || {}).forEach(([sub, dataObj]) => {
          let data =
            mode === 'year'
              ? YEARS.map((y) => dataObj[y]?.reduce((a, b) => a + b, 0) || 0)
              : dataObj[selectedYear] || Array(12).fill(0);

          series.push({
            name: sub,
            data: data.map(round2),
            type: 'column',
            stack: 't',
            color: getRandomColor(series.length),
            events: legendEvents,
          });
        });
      });
    }

    const totals = aggregate(selectedYear);
    const avg = totals.reduce((a, b) => a + b, 0) / (totals.length || 1);

    series.push({
      name: 'Moyenne ' + displayTypeName,
      data: Array(totals.length).fill(round2(avg)),
      type: 'line',
      dashStyle: 'Dot',
      color: '#FF0000',
      marker: { enabled: false },
      showInLegend: false,
    });

    if (mode === 'year') {
      series.push({
        name: 'Variation %',
        data: pct(totals),
        type: 'line',
        yAxis: 1,
        showInLegend: false,
        lineWidth: 2,
        marker: { enabled: true, symbol: 'circle', radius: 4 },
        zones: [{ value: 0, color: '#FF0000' }, { color: '#00E272' }],
      });
    }

    return series;
  }

  function renderEvoChart() {
    const modeEl = document.querySelector('input[name="mode_evo"]:checked');
    const granEl = document.querySelector('input[name="gran_evo"]:checked');
    if (!modeEl || !granEl) return;

    mode = modeEl.value;
    gran = granEl.value;
    const categories = mode === 'year' ? YEARS : MONTHS;
    const displayTypeName = type === 'Revenus' ? 'Revenus' : 'Dépenses';

    evoChart = Highcharts.chart('container_evolution', {
      chart: { type: 'column' },
      title: { text: 'Évolution ' + displayTypeName },
      xAxis: { categories },
      yAxis: [
        {
          title: { text: 'Montant' },
          labels: {
            format: `{value} ${CURRENCY_SYMBOL}`,
          },
        },
        {
          title: { text: 'Variation' },
          opposite: true,
          labels: {
            format: '{value} %',
          },
        },
      ],
      tooltip: {
        shared: false,
        useHTML: true,
        formatter: function () {
          const header = this.key;
          const name = this.series.name;
          const value = this.y;
          const color = this.point.color;
          let displayValue = value;
          let suffix = name === 'Variation %' ? '%' : ` ${CURRENCY_SYMBOL}`;
          let displayName = name === 'Variation %' ? 'Variation' : name;

          let valueStyle = '';
          if (name === 'Variation %') {
            const statusColor = value >= 0 ? '#00E272' : '#FF0000';
            displayValue = (value > 0 ? '+' : '') + value;
            valueStyle = `style="color:${statusColor}"`;
          }

          return (
            `<span style="font-size: 10px">${header}</span><br/>` +
            `<span style="color:${color}">●</span> ${displayName}: ` +
            `<b><span ${valueStyle}>${displayValue}${suffix}</span></b>`
          );
        },
      },
      plotOptions: { column: { stacking: gran === 'total' ? null : 'normal' } },
      series: buildEvoSeries(),
    });
  }

  const switchInput = document.getElementById('switch_type');
  if (switchInput) {
    switchInput.onchange = (e) => {
      type = e.target.checked ? 'Revenus' : 'Depenses';
      const lbl = document.getElementById('label_type');
      if (lbl) {
        lbl.innerText = type === 'Revenus' ? 'Revenus' : 'Dépenses';
        lbl.style.color = getColor();
      }
      renderEvoChart();
    };
  }

  document.querySelectorAll('input[name="mode_evo"]').forEach((r) => {
    r.onchange = (e) => {
      if (yearSelectEvo) {
        yearSelectEvo.classList.toggle('is-hidden', e.target.value !== 'month');
      }
      renderEvoChart();
    };
  });

  document.querySelectorAll('input[name="gran_evo"]').forEach((r) => {
    r.onchange = renderEvoChart;
  });

  renderEvoChart();
})();

(function initSunburstChart() {
  if (!SUNBURST_DATA || SUNBURST_DATA.length === 0) return;

  const btnExpenses = document.getElementById('btnShowExpenses');
  const btnIncomes = document.getElementById('btnShowIncomes');
  const secExpenses = document.getElementById('sectionExpenses');
  const secIncomes = document.getElementById('sectionIncomes');

  if (btnExpenses && btnIncomes) {
    btnExpenses.addEventListener('click', function () {
      secExpenses.classList.remove('is-hidden');
      secIncomes.classList.add('is-hidden');

      btnExpenses.classList.add('active');
      btnIncomes.classList.remove('active');

      if (window['chartExpenses']) window['chartExpenses'].reflow();
    });

    btnIncomes.addEventListener('click', function () {
      secExpenses.classList.add('is-hidden');
      secIncomes.classList.remove('is-hidden');

      btnIncomes.classList.add('active');
      btnExpenses.classList.remove('active');

      if (window['chartIncomes']) window['chartIncomes'].reflow();
    });
  }

  function setupSingleSunburst(rootName, containerId, filterContainerId, globalChartKey) {
    let chartInstance = null;
    let excludedIds = new Set();

    // Recherche de la racine (support du singulier/pluriel)
    const actualRoot = SUNBURST_DATA.find(
      (item) => item.id === rootName || item.id === rootName.slice(0, -1)
    );
    if (!actualRoot) return;

    const rootId = actualRoot.id;

    const rawBranchData = SUNBURST_DATA.filter((item) => {
      if (item.id === rootId || item.parent === rootId) return true;
      const parentItem = SUNBURST_DATA.find((p) => p.id === item.parent);
      return parentItem && (parentItem.parent === rootId || parentItem.id === rootId);
    });

    const branchData = rawBranchData.map((item) => {
      if (item.id === rootId) {
        return { ...item, parent: '' };
      }
      return item;
    });

    const filterContainer = document.getElementById(filterContainerId);
    if (filterContainer) {
      const topCategories = branchData.filter((item) => item.parent === rootId);
      filterContainer.innerHTML = topCategories
        .map(
          (cat) => `
                    <label style="cursor: pointer; display: flex; align-items: center; gap: 4px;">
                        <input type="checkbox" class="sunburst-cb-${rootId}" value="${cat.id}">
                        ${cat.name}
                    </label>
                `
        )
        .join('');

      filterContainer.querySelectorAll(`.sunburst-cb-${rootId}`).forEach((cb) => {
        cb.addEventListener('change', (e) => {
          if (e.target.checked) excludedIds.add(e.target.value);
          else excludedIds.delete(e.target.value);
          updateChart();
        });
      });
    }

    function calculateBranchPercentage(point) {
      if (!point || !point.value) return 0;
      let current = point;
      while (current.parent && current.node && current.node.parent) {
        const parentPoint = current.series.points.find((p) => p.id === current.parent);
        if (!parentPoint) break;
        current = parentPoint;
      }

      const total = current.node ? current.node.childrenTotal : current.value;
      if (!total) return 0;

      return Highcharts.numberFormat((point.value / total) * 100, 1, ',', ' ');
    }

    function updateChart() {
      let activeData = branchData.filter((item) => {
        if (excludedIds.has(item.id)) return false;
        if (excludedIds.has(item.parent)) return false;
        return true;
      });

      const totalsMap = {};
      activeData.forEach((item) => {
        if (item.value) {
          totalsMap[item.id] = item.value;
          let parentId = item.parent;
          while (parentId) {
            totalsMap[parentId] = (totalsMap[parentId] || 0) + item.value;
            const parentNode = activeData.find((p) => p.id === parentId);
            parentId = parentNode ? parentNode.parent : null;
          }
        }
      });

      activeData.sort((a, b) => {
        const totalA = totalsMap[a.id] || a.value || 0;
        const totalB = totalsMap[b.id] || b.value || 0;
        return totalB - totalA;
      });

      const chartOptions = {
        chart: { type: 'sunburst' },
        title: { text: `Répartition des ${rootName}` },
        subtitle: { text: 'Cliquez sur un secteur pour zoomer' },
        series: [
          {
            type: 'sunburst',
            data: activeData,
            allowTraversingTree: true,
            cursor: 'pointer',
            borderRadius: 3,
            dataLabels: {
              formatter: function () {
                if (!this.point.value) return this.point.name;
                const percent = calculateBranchPercentage(this.point);
                return `<b>${this.point.name}</b><br>${percent} %`;
              },
              filter: { property: 'innerArcLength', operator: '>', value: 16 },
            },
            levels: [
              {
                level: 1,
                levelIsConstant: false,
                dataLabels: {
                  filter: { property: 'outerArcLength', operator: '>', value: 64 },
                },
              },
              { level: 2, colorByPoint: true },
              { level: 3, colorVariation: { key: 'brightness', to: -0.5 } },
            ],
          },
        ],
        tooltip: {
          headerFormat: '',
          pointFormatter: function () {
            if (!this.value) return `<b>${this.name}</b>`;
            const percent = calculateBranchPercentage(this);
            return `<b>${this.name}</b> : <b>${Highcharts.numberFormat(this.value, 2, ',', ' ')} ${CURRENCY_SYMBOL}</b> (${percent} %)`;
          },
        },
      };

      if (chartInstance) {
        chartInstance.destroy();
      }
      chartInstance = Highcharts.chart(containerId, chartOptions);
      window[globalChartKey] = chartInstance;
    }

    updateChart();
  }

  setupSingleSunburst(
    'Dépenses',
    'sunburstExpensesContainer',
    'sunburstFilterExpenses',
    'chartExpenses'
  );
  setupSingleSunburst(
    'Revenus',
    'sunburstIncomesContainer',
    'sunburstFilterIncomes',
    'chartIncomes'
  );
})();

if (!HAS_ONLY_INCOMES_OR_EXPENSES) {
  (function initSankeyChart() {
    const sankeyColors = [
      '#544FC5',
      '#2CAFFE',
      '#FF7F50',
      '#32CD32',
      '#FF69B4',
      '#FFA500',
      '#8A2BE2',
      '#00CED1',
      '#DC143C',
      '#7FFF00',
    ];

    function buildSankeyLinks(selectedYear) {
      let links = [];
      const filteredData = SANKEY_DATA.filter((d) => d.year === selectedYear);

      const revenus = filteredData.filter((d) => INCOMES_LIST.includes(d.category));
      const revenusSouscat = {};
      revenus.forEach((d) => {
        revenusSouscat[d.sub_category] = (revenusSouscat[d.sub_category] || 0) + d.amount;
      });
      Object.entries(revenusSouscat).forEach(([s, v]) => {
        links.push({ from: s, to: 'Revenus', weight: round2(v) });
      });

      const depenses = filteredData
        .filter((d) => !INCOMES_LIST.includes(d.category))
        .map((d) => ({ ...d, amount: Math.abs(d.amount) }));
      const depCatsTotals = {};
      depenses.forEach((d) => {
        depCatsTotals[d.category] = (depCatsTotals[d.category] || 0) + d.amount;
      });

      let sortedDepCats = Object.entries(depCatsTotals).sort(([, a], [, b]) => b - a);

      sortedDepCats.forEach(([cat, catTotal], idx) => {
        const color = sankeyColors[idx % sankeyColors.length];
        links.push({ from: 'Revenus', to: cat, weight: round2(catTotal), color: color });

        const subs = {};
        depenses
          .filter((d) => d.category === cat)
          .forEach((d) => {
            subs[d.sub_category] = (subs[d.sub_category] || 0) + d.amount;
          });
        Object.entries(subs).forEach(([s, amt]) => {
          links.push({ from: cat, to: s, weight: round2(amt), color: color });
        });
      });

      return links;
    }

    function renderSankey(selectedYear) {
      const selectEl = document.getElementById('sankeyYearSelect');
      if (!selectedYear && selectEl) selectedYear = parseInt(selectEl.value);
      if (!selectedYear && YEARS.length > 0) selectedYear = YEARS[0];
      if (!selectedYear) return;

      const links = buildSankeyLinks(selectedYear);

      Highcharts.chart('sankeyContainer', {
        chart: { type: 'sankey', height: 850 },
        title: { text: 'Répartition des flux financiers : ' + selectedYear },
        tooltip: {
          pointFormatter: function () {
            return this.toNode.name === 'Revenus'
              ? this.fromNode.name +
                  ': <b>' +
                  this.weight.toFixed(2) +
                  ' ' +
                  CURRENCY_SYMBOL +
                  '</b>'
              : this.fromNode.name +
                  ' → ' +
                  this.toNode.name +
                  ': <b>' +
                  this.weight.toFixed(2) +
                  ' ' +
                  CURRENCY_SYMBOL +
                  '</b>';
          },
        },
        series: [
          {
            keys: ['from', 'to', 'weight', 'color'],
            data: links,
            type: 'sankey',
            dataLabels: {
              nodeFormatter: function () {
                return this.point.name;
              },
            },
          },
        ],
      });
    }

    const sankeySelect = document.getElementById('sankeyYearSelect');
    if (sankeySelect) {
      sankeySelect.addEventListener('change', (e) =>
        renderSankey(parseInt(e.target.value))
      );
    }

    renderSankey();
  })();
}
