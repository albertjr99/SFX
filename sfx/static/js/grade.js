/* Grade de produção: linhas, conferência documental, contagens ao vivo,
   aviso de alterações não salvas, Ctrl+S e impressão por semana. */
(() => {
  "use strict";
  const form = document.querySelector("[data-grade]");
  if (!form) return;

  const modelo = document.getElementById("modelo-linha");
  const estado = form.querySelector("[data-estado]");
  let sujo = false;
  let enviando = false;

  const marcarSujo = () => {
    if (sujo) return;
    sujo = true;
    estado.textContent = "Alterações não salvas";
    estado.classList.add("sujo");
  };

  const temConteudo = (tr) =>
    Array.from(tr.querySelectorAll("input[type=text]")).some((i) => i.value.trim()) ||
    tr.querySelector("select.status").value !== "" ||
    tr.querySelector("input[type=checkbox]:checked") !== null ||
    (tr.nextElementSibling?.querySelector("input[data-doc]:checked") ?? null) !== null;

  const renumerar = (caderno) => {
    caderno.querySelectorAll("tr.linha").forEach((tr, i) => {
      tr.querySelector(".numero").textContent = String(i + 1).padStart(2, "0");
    });
  };

  const recontar = (caderno) => {
    const totais = {};
    let total = 0;
    caderno.querySelectorAll("tr.linha input[data-atv]:checked").forEach((cb) => {
      totais[cb.dataset.atv] = (totais[cb.dataset.atv] || 0) + 1;
      total += 1;
    });
    caderno.querySelector("[data-total]").textContent = total;
    caderno.querySelectorAll("[data-cont]").forEach((el) => {
      const v = totais[el.dataset.cont] || 0;
      el.querySelector("b").textContent = v;
      el.hidden = v === 0;
    });
    const geral = Array.from(form.querySelectorAll("[data-total]")).reduce((s, el) => s + Number(el.textContent), 0);
    const placar = document.querySelector("[data-total-mes]");
    if (placar) placar.textContent = geral.toLocaleString("pt-BR");
  };

  const contarDocs = (trDocs) => {
    const n = trDocs.querySelectorAll("input[data-doc]:checked").length;
    trDocs.previousElementSibling.querySelector(".docs-cont").textContent = n ? ` ${n}` : "";
  };

  let seq = 0;
  const novaLinha = (caderno) => {
    const w = caderno.dataset.semana;
    const uid = `n${Date.now().toString(36)}${(seq++).toString(36)}`;
    const html = modelo.innerHTML.replaceAll("__UID__", uid).replaceAll("__W__", w);
    const tbody = caderno.querySelector("tbody");
    tbody.insertAdjacentHTML("beforeend", html);
    renumerar(caderno);
    const nova = tbody.querySelectorAll("tr.linha");
    nova[nova.length - 1].querySelector(".col-proc input").focus();
    marcarSujo();
  };

  form.addEventListener("click", (e) => {
    const alvo = e.target.closest("button");
    if (!alvo) return;
    const caderno = alvo.closest(".caderno");

    if (alvo.matches("[data-adicionar]")) {
      novaLinha(caderno);
    } else if (alvo.matches("[data-remover]")) {
      const tr = alvo.closest("tr.linha");
      if (temConteudo(tr) && !window.confirm("Remover esta linha? Ela será apagada ao salvar.")) return;
      tr.nextElementSibling?.classList.contains("docs") && tr.nextElementSibling.remove();
      tr.remove();
      renumerar(caderno);
      recontar(caderno);
      marcarSujo();
    } else if (alvo.matches("[data-docs]")) {
      const sub = alvo.closest("tr").nextElementSibling;
      sub.hidden = !sub.hidden;
      alvo.setAttribute("aria-expanded", String(!sub.hidden));
    } else if (alvo.matches("[data-docs-todos], [data-docs-nenhum]")) {
      const sub = alvo.closest("tr.docs");
      const marcar = alvo.matches("[data-docs-todos]");
      sub.querySelectorAll("input[data-doc]").forEach((cb) => (cb.checked = marcar));
      contarDocs(sub);
      marcarSujo();
    } else if (alvo.matches("[data-imprimir]")) {
      document.querySelectorAll("[data-imprimir-semana]").forEach((cb) => {
        document.getElementById(`semana-${cb.dataset.imprimirSemana}`).classList.toggle("oculto-impressao", !cb.checked);
      });
      alvo.closest("details").open = false;
      window.print();
    }
  });

  form.addEventListener("input", (e) => {
    marcarSujo();
    const tr = e.target.closest("tr.linha");
    if (tr) tr.classList.toggle("tem-conteudo", temConteudo(tr));
  });

  form.addEventListener("change", (e) => {
    const el = e.target;
    marcarSujo();
    if (el.matches("select.status")) el.dataset.valor = el.value;
    if (el.matches("input[data-atv]")) recontar(el.closest(".caderno"));
    if (el.matches("input[data-doc]")) contarDocs(el.closest("tr.docs"));
    const tr = el.closest("tr.linha");
    if (tr) tr.classList.toggle("tem-conteudo", temConteudo(tr));
  });

  // Enter em campo de texto não envia o formulário por engano
  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.matches("input[type=text]")) {
      e.preventDefault();
      const tr = e.target.closest("tr.linha");
      const prox = tr?.nextElementSibling?.nextElementSibling;
      const col = e.target.closest("td").cellIndex;
      prox?.cells[col]?.querySelector("input")?.focus();
    }
  });

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", () => {
    enviando = true;
    estado.textContent = "Salvando…";
    form.querySelectorAll("button[type=submit]").forEach((b) => (b.disabled = true));
  });

  window.addEventListener("beforeunload", (e) => {
    if (sujo && !enviando) {
      e.preventDefault();
      e.returnValue = "";
    }
  });

  window.addEventListener("afterprint", () => {
    document.querySelectorAll(".oculto-impressao").forEach((el) => el.classList.remove("oculto-impressao"));
  });

  // Mantém o mesmo trecho da página após salvar
  const chave = `sfx-rolagem:${location.pathname}${location.search}`;
  form.addEventListener("submit", () => {
    try { sessionStorage.setItem(chave, String(window.scrollY)); } catch (_) { /* sem storage */ }
  });
  try {
    const y = sessionStorage.getItem(chave);
    if (y && !location.hash) window.scrollTo(0, Number(y));
    sessionStorage.removeItem(chave);
  } catch (_) { /* sem storage */ }
})();
