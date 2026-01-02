const historyData = JSON.parse('{{ history_data|safe }}');
const labels = [...new Set(Object.values(historyData).flat().map(h=>h.date))].sort();
const colors = ['#3b82f6','#ef4444','#10b981','#f59e0b','#8b5cf6'];

const datasets = Object.entries(historyData).map(([name,data],i)=>({
  label:name,
  data:labels.map(d=>{
    const e=data.find(x=>x.date===d);
    return e?e.balance:null;
  }),
  borderColor:colors[i%colors.length],
  tension:.4,
  pointRadius:0,
  borderWidth:2
}));

const balanceLabelPlugin = {
  id: 'balanceLabelPlugin',
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    ctx.save();
    ctx.font = 'bold 12px Inter';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';

    const occupiedYs = [];

    chart.data.datasets.forEach((dataset) => {
      const meta = chart.getDatasetMeta(chart.data.datasets.indexOf(dataset));
      if (!meta?.data?.length) return;

      // найти последний индекс с числом
      let lastIndex = dataset.data.length - 1;
      while (lastIndex >= 0 && (dataset.data[lastIndex] === null || meta.data[lastIndex] === undefined)) {
        lastIndex--;
      }

      if (lastIndex >= 0) {
        let lastPoint = meta.data[lastIndex];
        let y = lastPoint.y;
        const x = lastPoint.x + 8;

        const minDistance = 14;
        occupiedYs.forEach(oy => {
          if (Math.abs(y - oy) < minDistance) {
            y = oy - minDistance; // смещаем текст вверх
          }
        });

        ctx.fillStyle = dataset.borderColor;
        ctx.fillText(`$${dataset.data[lastIndex].toFixed(2)}`, x, y);
        occupiedYs.push(y);
      }
    });

    ctx.restore();
  }
};



new Chart(document.getElementById('lineChart'), {
  type: 'line',
  data: { labels, datasets },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    layout: { padding: { right: 60 } },
    plugins: {
      legend: { labels: { usePointStyle: true, color: '#e5e7eb' } },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      y: { ticks: { color: '#e5e7eb', callback: v => '$' + v }},
      x: { ticks: { color: '#e5e7eb', maxRotation: 45 } }
    }
  },
  plugins: [balanceLabelPlugin]
});