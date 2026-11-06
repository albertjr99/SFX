/* Comportamentos globais. Sem dependências; carregado em todas as páginas. */
(() => {
  "use strict";

  const $ = (sel, raiz = document) => raiz.querySelector(sel);
  const $$ = (sel, raiz = document) => Array.from(raiz.querySelectorAll(sel));

  window.SFX = {
    csrf: () => $('meta[name="csrf-token"]')?.content || "",
    lerJSON: (id) => {
      const el = document.getElementById(id);
      return el ? JSON.parse(el.textContent) : null;
    },
    escapar: (texto) =>
      String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]),
  };

  // Menu lateral no celular
  const app = $("#app");
  const botaoMenu = $("[data-menu]");
  botaoMenu?.addEventListener("click", () => {
    const aberto = app.classList.toggle("menu-aberto");
    botaoMenu.setAttribute("aria-expanded", String(aberto));
  });
  document.addEventListener("click", (e) => {
    if (app?.classList.contains("menu-aberto") && !e.target.closest(".lateral, [data-menu]")) {
      app.classList.remove("menu-aberto");
      botaoMenu?.setAttribute("aria-expanded", "false");
    }
  });

  // Menu lateral recolhível (preferência guardada neste navegador)
  const botaoRecolher = $("[data-recolher]");
  if (app && botaoRecolher) {
    let pref = null;
    try { pref = localStorage.getItem("sfx-menu"); } catch (_) { /* sem storage */ }
    const recolher = pref ? pref === "recolhido" : window.innerWidth < 1600;
    app.classList.toggle("recolhida", recolher);
    botaoRecolher.addEventListener("click", () => {
      const r = app.classList.toggle("recolhida");
      try { localStorage.setItem("sfx-menu", r ? "recolhido" : "expandido"); } catch (_) { /* sem storage */ }
    });
    $(".perfil")?.addEventListener("click", () => {
      if (app.classList.contains("recolhida")) botaoRecolher.click();
    });
  }

  // Seletor de mês: troca o ano dentro do quadro sem recarregar
  $$("[data-mes-nav]").forEach((nav) => {
    const modelo = nav.dataset.modelo;
    const anoAtual = Number(nav.dataset.ano);
    const mesAtual = Number(nav.dataset.mes);
    let ano = anoAtual;
    const exibido = nav.querySelector("[data-ano-exibido]");
    const atualizar = () => {
      exibido.textContent = ano;
      nav.querySelectorAll(".mes-grade a").forEach((a) => {
        const m = Number(a.dataset.mes);
        a.href = modelo.replace("ano=9999", `ano=${ano}`).replace("mes=99", `mes=${m}`);
        a.classList.toggle("selecionado", ano === anoAtual && m === mesAtual);
        a.classList.toggle("hoje", ano === Number(nav.dataset.hojeAno) && m === Number(nav.dataset.hojeMes));
      });
    };
    nav.querySelectorAll("[data-mudar-ano]").forEach((b) =>
      b.addEventListener("click", () => {
        ano += Number(b.dataset.mudarAno);
        atualizar();
      })
    );
    const det = nav.querySelector("details");
    document.addEventListener("click", (e) => {
      if (det.open && !det.contains(e.target)) det.open = false;
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") det.open = false;
    });
  });

  // Tela cheia
  $("[data-tela-cheia]")?.addEventListener("click", () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
    else document.exitFullscreen?.();
  });

  // Avisos
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-fechar-aviso]");
    if (b) b.closest(".aviso")?.remove();
  });
  $$(".aviso-sucesso, .aviso-info").forEach((el) => setTimeout(() => el.remove(), 7000));

  // Mostrar/ocultar blocos
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-alternar]");
    if (!b) return;
    const alvo = document.getElementById(b.dataset.alternar);
    if (!alvo) return;
    alvo.hidden = !alvo.hidden;
    if (!alvo.hidden) alvo.querySelector("input:not([type=hidden]), select, textarea")?.focus();
  });

  // Selects que enviam o formulário ao mudar
  $$("[data-auto-enviar]").forEach((s) => s.addEventListener("change", () => s.form.submit()));

  // Confirmações
  document.addEventListener("submit", (e) => {
    const msg = e.target.dataset?.confirmar;
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Imprimir página
  $$("[data-imprimir-pagina]").forEach((b) => b.addEventListener("click", () => window.print()));

  // Textareas que crescem com o conteúdo
  const ajustar = (t) => {
    t.style.height = "auto";
    t.style.height = t.scrollHeight + 2 + "px";
  };
  $$("textarea[data-autoaltura]").forEach((t) => {
    ajustar(t);
    t.addEventListener("input", () => ajustar(t));
  });
  window.SFX.ajustarTextarea = ajustar;

  // Pendências: semanas conforme o mês escolhido
  const formPend = $("[data-form-pendencia]");
  if (formPend) {
    const semanas = window.SFX.lerJSON("semanas-ano") || {};
    const selMes = formPend.querySelector('[name="mes"]');
    const selSemana = formPend.querySelector('[name="semana"]');
    const preencher = () => {
      selSemana.innerHTML = (semanas[selMes.value] || [])
        .map((s) => `<option value="${window.SFX.escapar(s)}">${window.SFX.escapar(s)}</option>`)
        .join("");
    };
    selMes.addEventListener("change", preencher);
    preencher();
  }

  // Busca de processos (grade)
  $$("[data-busca]").forEach((caixa) => {
    const input = caixa.querySelector("input");
    const lista = caixa.querySelector(".busca-resultados");
    let timer;
    let controle;
    const fechar = () => (lista.hidden = true);
    const buscar = async () => {
      const q = input.value.trim();
      if (q.length < 2) return fechar();
      controle?.abort();
      controle = new AbortController();
      try {
        const r = await fetch(`${caixa.dataset.url}?q=${encodeURIComponent(q)}`, {
          signal: controle.signal,
          headers: { Accept: "application/json" },
        });
        const { resultados } = await r.json();
        const esc = window.SFX.escapar;
        lista.innerHTML = resultados.length
          ? resultados
              .map(
                (x) => `<a href="${esc(x.url)}"><strong>${esc(x.numero_processo || "Sem número")}</strong> · ${esc(x.nome_do_segurado)}
                <small>${esc(x.mes)}/${esc(x.ano)} · semana de ${esc(x.semana)}${x.analista ? " · " + esc(x.analista) : ""}${x.status ? " · " + esc(x.status) : ""}</small></a>`
              )
              .join("")
          : `<div class="vazio">Nada encontrado para “${esc(q)}”.</div>`;
        lista.hidden = false;
      } catch (err) {
        if (err.name !== "AbortError") {
          lista.innerHTML = '<div class="vazio">A busca falhou. Tente de novo.</div>';
          lista.hidden = false;
        }
      }
    };
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(buscar, 250);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        clearTimeout(timer);
        buscar();
      } else if (e.key === "Escape") fechar();
      else if (e.key === "ArrowDown") lista.querySelector("a")?.focus();
    });
    document.addEventListener("click", (e) => {
      if (!caixa.contains(e.target)) fechar();
    });
  });

  // Destaque de linha vinda da busca (#linha-123)
  const destacar = () => {
    const el = location.hash.startsWith("#linha-") && document.querySelector(location.hash);
    if (!el) return;
    el.classList.add("destacada");
    setTimeout(() => el.scrollIntoView({ block: "center" }), 50);
    setTimeout(() => el.classList.remove("destacada"), 3500);
  };
  window.addEventListener("hashchange", destacar);
  destacar();
})();
