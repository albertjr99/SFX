/* Gráficos das páginas de estatística (Chart.js servido localmente). */
(() => {
  "use strict";
  if (!window.Chart) return;
  const dados = window.SFX.lerJSON("dados-grafico");
  if (!dados) return;

  const cor = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  Chart.defaults.font.family = cor("--fonte");
  Chart.defaults.font.size = 12;
  Chart.defaults.color = cor("--texto-suave");
  Chart.defaults.borderColor = cor("--linha");
  Chart.defaults.maintainAspectRatio = false;
  Chart.defaults.plugins.legend.labels.boxWidth = 12;

  // Paleta categórica: tons da identidade, distinguíveis entre si.
  const paleta = ["#2c6493", "#e0a526", "#45a079", "#c4577f", "#6b5ca5", "#3a9bb5", "#a8643a", "#7f8c99", "#1f3f5c"];
  const barras = (labels, valores, rotulo) => ({
    type: "bar",
    data: { labels, datasets: [{ label: rotulo, data: valores, backgroundColor: cor("--pasta"), borderRadius: 3, maxBarThickness: 48 }] },
    options: {
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { grid: { display: false } } },
    },
  });

  document.querySelectorAll("canvas[data-grafico]").forEach((canvas) => {
    const tipo = canvas.dataset.grafico;
    let cfg;
    if (tipo === "atividades") {
      cfg = barras(dados.atividades, dados.valores, "Atividades");
      cfg.options.indexAxis = "y";
      cfg.options.scales = { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { grid: { display: false } } };
    } else if (tipo === "semanas") {
      cfg = barras(dados.semanas, dados.por_semana, "Atividades na semana");
    } else if (tipo === "meses") {
      cfg = barras(dados.meses.map((m) => m.slice(0, 3)), dados.por_mes, "Atividades no mês");
    } else if (tipo === "setor") {
      cfg = {
        type: "bar",
        data: {
          labels: dados.meses.map((m) => m.slice(0, 3)),
          datasets: dados.series.map((s, i) => ({ label: s.rotulo, data: s.valores, backgroundColor: paleta[i % paleta.length] })),
        },
        options: {
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { position: "bottom" } },
          scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } },
        },
      };
    }
    if (cfg) new Chart(canvas, cfg);
  });
})();
