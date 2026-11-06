/* Plano de ação: totais e variação ao vivo, gráfico e salvamento. */
(() => {
  "use strict";
  const tabela = document.querySelector("[data-plano]");
  if (!tabela) return;

  const estado = document.querySelector("[data-estado]");
  const botao = document.querySelector("[data-salvar-plano]");
  const nota = document.querySelector("[data-nota]");
  const caixas = ["caixa_pa", "caixa_in_p", "caixa_conferencia_p", "caixa_p_sem_pensao"];
  const linhas = () => Array.from(tabela.tBodies[0].rows);
  const fmt = (n) => n.toLocaleString("pt-BR");
  const fmtPct = (n) => n.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
  let sujo = false;

  const marcar = (valor) => {
    sujo = valor;
    estado.textContent = valor ? "Alterações não salvas" : "Tudo salvo";
    estado.classList.toggle("sujo", valor);
  };

  const calcular = () => {
    let anterior = null;
    return linhas().map((tr) => {
      const vals = caixas.map((c) => tr.querySelector(`[data-campo="${c}"]`).value);
      const vazio = vals.every((v) => v === "");
      const total = vazio ? null : vals.reduce((s, v) => s + (parseInt(v, 10) || 0), 0);
      const variacao = anterior && total !== null ? Math.round((1 - total / anterior) * 1000) / 10 : null;
      if (total !== null) anterior = total;
      const tdTotal = tr.querySelector("[data-total]");
      const tdVar = tr.querySelector("[data-variacao]");
      tdTotal.innerHTML = total === null ? "" : `<strong>${fmt(total)}</strong>`;
      tdVar.textContent = variacao === null ? "" : fmtPct(variacao);
      tdVar.className = "num " + (variacao === null ? "" : variacao >= 0 ? "var-pos" : "var-neg");
      return { id: tr.dataset.id, rotulo: tr.cells[0].querySelector("strong").textContent, total, variacao };
    });
  };

  // Gráfico
  let grafico;
  const filtro = document.querySelector("[data-filtro-meses]");
  const desenhar = () => {
    if (!window.Chart) return;
    const marcados = new Set(Array.from(filtro.querySelectorAll("input:checked")).map((i) => i.value));
    const dados = calcular().filter((d) => marcados.has(d.id));
    const cor = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
    const cfg = {
      data: {
        labels: dados.map((d) => d.rotulo),
        datasets: [
          { type: "bar", label: "Total no setor", data: dados.map((d) => d.total), backgroundColor: cor("--pasta"), borderRadius: 3, yAxisID: "y", order: 2 },
          { type: "line", label: "Variação (%)", data: dados.map((d) => d.variacao), borderColor: "#d99a12", backgroundColor: "#f3c04a",
            yAxisID: "y1", tension: 0, pointRadius: 4, spanGaps: true, order: 1 },
        ],
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom" } },
        scales: {
          y: { beginAtZero: true, title: { display: true, text: "Processos" } },
          y1: { position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Variação" }, ticks: { callback: (v) => v + "%" } },
          x: { grid: { display: false } },
        },
      },
    };
    if (grafico) {
      grafico.data = cfg.data;
      grafico.update();
    } else {
      Chart.defaults.font.family = cor("--fonte");
      Chart.defaults.color = cor("--texto-suave");
      grafico = new Chart(document.querySelector("[data-grafico-plano]"), cfg);
    }
  };

  tabela.addEventListener("input", () => {
    marcar(true);
    desenhar();
  });
  nota?.addEventListener("input", () => marcar(true));
  filtro?.addEventListener("change", desenhar);

  const salvar = async () => {
    const corpo = {
      linhas: linhas().map((tr) => {
        const item = { id: Number(tr.dataset.id) };
        tr.querySelectorAll("[data-campo]").forEach((el) => (item[el.dataset.campo] = el.value));
        return item;
      }),
      nota: nota ? nota.value : undefined,
    };
    botao.disabled = true;
    estado.textContent = "Salvando…";
    try {
      const r = await fetch(botao.dataset.url, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": window.SFX.csrf() },
        body: JSON.stringify(corpo),
      });
      if (!r.ok) throw new Error(String(r.status));
      marcar(false);
      estado.textContent = "Salvo agora";
    } catch (err) {
      estado.textContent = "Falha ao salvar — tente de novo";
      estado.classList.add("sujo");
    } finally {
      botao.disabled = false;
    }
  };
  botao.addEventListener("click", salvar);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      salvar();
    }
  });
  window.addEventListener("beforeunload", (e) => {
    if (sujo) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  desenhar();
})();
