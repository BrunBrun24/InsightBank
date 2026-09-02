document.addEventListener('DOMContentLoaded', () => {
  Highcharts.setOptions({
    lang: {
      months: [
        'Janvier',
        'Février',
        'Mars',
        'Avril',
        'Mai',
        'Juin',
        'Juillet',
        'Août',
        'Septembre',
        'Octobre',
        'Novembre',
        'Décembre',
      ],
      weekdays: ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'],
      shortMonths: [
        'Janv.',
        'Févr.',
        'Mars',
        'Avril',
        'Mai',
        'Juin',
        'Juil.',
        'Août',
        'Sept.',
        'Oct.',
        'Nov.',
        'Déc.',
      ],
      rangeSelectorZoom: 'Zoom',
      resetZoom: 'Réinitialiser le zoom',
      week: '%e %B %Y',
    },
  });

  Highcharts.stockChart('heritage-global-chart', {
    chart: {
      backgroundColor: 'transparent',
      zoomType: 'x',
      zooming: {
        mouseWheel: {
          enabled: false,
        },
      },
    },
    title: {
      text: 'Évolution du Patrimoine Global',
      style: { color: '#2d3748', fontWeight: 'bold' },
    },
    rangeSelector: {
      selected: 5,
      buttons: [
        { type: 'year', count: 1, text: '1y' },
        { type: 'year', count: 3, text: '3y' },
        { type: 'year', count: 5, text: '5y' },
        { type: 'ytd', text: 'YTD' },
        { type: 'all', text: 'All' },
      ],
    },
    navigator: { enabled: false },
    scrollbar: { enabled: false },
    plotOptions: {
      series: {
        dataGrouping: {
          enabled: false,
        },
      },
    },
    xAxis: {
      gridLineWidth: 0,
      crosshair: false,
    },
    yAxis: {
      title: { text: 'Total' },
      opposite: false,
      crosshair: false,
    },
    tooltip: {
      split: false,
      shared: false,
      valueDecimals: 2,
      valueSuffix: ` ${CURRENCY}`,
      xDateFormat: '%A %e %B %Y',
    },
    series: [
      {
        name: 'Patrimoine Total',
        data: HERITAGE_SERIES_DATA,
        type: 'area',
        threshold: null,
        color: '#00e676',
        fillColor: 'rgba(0, 230, 118, 0.35)',
      },
    ],
    credits: { enabled: false },
  });

  let isolatedSeriesIndex = null;

  Highcharts.stockChart('heritage-accounts-chart', {
    chart: {
      backgroundColor: 'transparent',
      zoomType: 'x',
      zooming: {
        mouseWheel: {
          enabled: false,
        },
      },
    },
    title: {
      text: 'Évolution détaillée par compte',
      style: { color: '#2d3748', fontWeight: 'bold' },
    },
    rangeSelector: { enabled: false },
    navigator: { enabled: false },
    scrollbar: { enabled: false },
    legend: {
      enabled: true,
      layout: 'horizontal',
      align: 'center',
      verticalAlign: 'bottom',
    },
    xAxis: { gridLineWidth: 0 },
    yAxis: {
      title: { text: 'Montant' },
      opposite: false,
    },
    tooltip: { valueDecimals: 2, valueSuffix: ` ${CURRENCY}` },
    plotOptions: {
      series: {
        events: {
          legendItemClick: function (e) {
            const chart = this.chart;
            const targetSeries = this;

            const now = new Date().getTime();
            const lastClick = targetSeries.lastClickTime || 0;
            targetSeries.lastClickTime = now;

            if (now - lastClick < 300) {
              e.preventDefault();

              if (isolatedSeriesIndex === targetSeries.index) {
                chart.series.forEach((s) => s.setVisible(true, false));
                isolatedSeriesIndex = null;
              } else {
                chart.series.forEach((s) => {
                  if (s === targetSeries) {
                    s.setVisible(true, false);
                  } else {
                    s.setVisible(false, false);
                  }
                });
                isolatedSeriesIndex = targetSeries.index;
              }
              chart.redraw();
            }
          },
        },
        dataGrouping: {
          enabled: false,
        },
      },
    },
    series: ACCOUNTS_DATA.map((acc) => ({
      name: acc.name,
      data: acc.data,
      type: 'line',
    })),
    credits: { enabled: false },
  });

  const yearlyData = window.YEARLY_GROWTH_DATA || [];
  const categories = yearlyData.map((item) => item.year);
  const seriesData = yearlyData.map((item) => ({
    y: item.percentage,
    gainLoss: item.gainLoss,
    color: item.percentage >= 0 ? '#00e676' : '#ff5252',
  }));

  Highcharts.chart('yearly-growth-chart', {
    chart: {
      type: 'column',
      backgroundColor: 'transparent',
    },
    title: {
      text: 'Performance Annuelle du Patrimoine',
      style: { color: '#2d3748', fontWeight: 'bold' },
    },
    xAxis: {
      categories: categories,
      crosshair: false,
      gridLineWidth: 0,
    },
    yAxis: {
      title: { text: 'Gain / Perte' },
      labels: { format: '{value}%' },
      gridLineWidth: 1,
    },
    legend: { enabled: false },
    tooltip: {
      shared: false,
      useHTML: true,
      formatter: function () {
        const point = this.point;
        const sign = point.y >= 0 ? '+' : '';
        return `
                <div style="padding: 5px;">
                    Variation: <b>${sign}${point.y.toFixed(2)} %</b><br/>
                    Variation: <b>${sign}${point.gainLoss.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} ${CURRENCY}</b>
                </div>
            `;
      },
    },
    plotOptions: {
      column: {
        borderRadius: 4,
        borderWidth: 0,
        pointPadding: 0.2,
        groupPadding: 0.1,
      },
    },
    series: [
      {
        name: 'Performance Annuelle',
        data: seriesData,
      },
    ],
    credits: { enabled: false },
  });

  Highcharts.chart('distribution-chart', {
    chart: { type: 'pie', backgroundColor: 'transparent' },
    title: {
      text: 'Répartition Actuelle',
      style: { color: '#2d3748', fontWeight: 'bold' },
    },
    tooltip: {
      pointFormat: `Part: <b>{point.y:.2f} ${CURRENCY}</b>`,
    },
    plotOptions: {
      pie: {
        allowPointSelect: true,
        cursor: 'pointer',
        dataLabels: {
          enabled: true,
          format: '<b>{point.name}</b>: {point.percentage:.1f}%',
        },
      },
    },
    series: [
      {
        name: 'Répartition',
        colorByPoint: true,
        data: DISTRIBUTION_DATA,
      },
    ],
    credits: { enabled: false },
  });
});
