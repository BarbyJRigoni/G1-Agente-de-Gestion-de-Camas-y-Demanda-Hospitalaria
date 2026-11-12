// Modo contingencia (Dario): simula una demanda excepcional, por ejemplo una pandemia.
// Usa la fuente, la fecha, la capacidad y el horizonte elegidos en el menu lateral,
// y le pide a la API la misma proyeccion con los supuestos de la contingencia.
// Usa funciones de panel.js: $, api, grafico, fmt y fmtLargo.
(() => {
  const form = $("#formContingencia");
  if (!form) return;
  const campos = ["#contAumento", "#contEstancia", "#contCamas"];
  let consulta = 0;

  function limpiar() {
    consulta++;
    $("#resultadoContingencia").hidden = true;
    if (charts["#gContingencia"]) { charts["#gContingencia"].destroy(); delete charts["#gContingencia"]; }
  }

  async function simular(event) {
    if (event) event.preventDefault();
    if (!form.reportValidity()) return;
    const yo = ++consulta;
    const textoCapacidad = $("#capacidad").value.trim();
    const cuerpo = {
      dataset: $("#dataset").value,
      fecha: $("#fecha").value || null,
      dias: Number($("#horizonte").value) || 7,
      contingencia: {
        aumento_ingresos_pct: Number($("#contAumento").value),
        estancia_extra_dias: Number($("#contEstancia").value),
        camas_contingencia: Number($("#contCamas").value),
      },
    };
    if (textoCapacidad !== "") cuerpo.capacidad = Number(textoCapacidad);

    const boton = $("#contSimular");
    boton.disabled = true; boton.textContent = "Simulando…";
    $("#resultadoContingencia").hidden = false;
    $("#mensajeContingencia").className = "";
    $("#mensajeContingencia").textContent = "Calculando la contingencia…";
    $("#kpisContingencia").replaceChildren();
    try {
      const r = await api("/proyeccion-camas", {
        method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(cuerpo),
      });
      if (yo !== consulta) return;
      mostrar(r);
    } catch (error) {
      if (yo !== consulta) return;
      $("#mensajeContingencia").className = "colapso";
      $("#mensajeContingencia").textContent = "No se pudo simular: " + error.message;
    } finally {
      boton.disabled = false; boton.textContent = "Simular contingencia";
    }
  }

  function mostrar(r) {
    const c = r.contingencia;
    const caja = $("#mensajeContingencia");
    caja.className = c.colapso ? "colapso" : c.alerta_saturacion ? "alerta" : "";
    caja.textContent = c.colapso
      ? `COLAPSO: el ${fmt(c.dia_supera_100)} la demanda supera las ${c.capacidad_total} camas. ` +
        `Pico: ${Math.round(c.dia_pico ? c.dias.find(d => d.fecha === c.dia_pico).camas_necesarias : 0)} camas necesarias ` +
        `(${Math.round(c.tasa_ocupacion_maxima_pct)} %) y ${Math.round(c.demanda_sin_cama_maxima)} pacientes sin cama.`
      : c.alerta_saturacion
        ? `ALERTA DE SATURACIÓN: desde el ${fmt(c.dia_supera_90)} se supera el 90 % (${Math.round(c.umbral_camas)} camas). ` +
          `Pico: ${Math.round(c.tasa_ocupacion_maxima_pct)} %.`
        : `El hospital absorbe la contingencia: el pico es ${Math.round(c.tasa_ocupacion_maxima_pct)} % ` +
          `de ${c.capacidad_total} camas, por debajo del 90 %.`;

    const kpi = (v, t) => `<div class="kpi"><b>${v}</b><span>${t}</span></div>`;
    $("#kpisContingencia").innerHTML =
      kpi(`${Math.round(r.tasa_ocupacion_maxima_pct)} % → ${Math.round(c.tasa_ocupacion_maxima_pct)} %`, "pico normal → pico en la contingencia") +
      kpi(c.dia_supera_90 ? fmt(c.dia_supera_90) : "No", "día en que se supera el 90 %") +
      kpi(c.dia_supera_100 ? fmt(c.dia_supera_100) : "No", "día en que se llenan todas las camas") +
      kpi(Math.round(c.demanda_sin_cama_maxima), "pacientes sin cama en el peor día") +
      kpi(c.camas_faltantes_para_90, "camas extra para no pasar el 90 %");

    const etiquetas = ["Censo", ...c.dias.map(d => fmt(d.fecha))];
    const normal = [r.camas_ocupadas_hoy, ...c.dias.map(d => d.camas_ocupadas_normal)];
    const crisis = [r.camas_ocupadas_hoy, ...c.dias.map(d => d.camas_necesarias)];
    grafico("#gContingencia", {
      type: "line",
      data: {labels: etiquetas, datasets: [
        {label: "Proyección normal", data: normal, borderColor: "#0f8b8d", backgroundColor: "#0f8b8d", borderWidth: 2.5, tension: .25, pointRadius: 3},
        {label: "Contingencia (camas necesarias)", data: crisis, borderColor: "#c0284a", backgroundColor: "#c0284a", borderWidth: 2.5, tension: .25, pointRadius: 3},
        {label: `Camas disponibles (${c.capacidad_total})`, data: etiquetas.map(() => c.capacidad_total), borderColor: "#5f6b73", borderWidth: 2, pointRadius: 0},
        {label: "Umbral 90 %", data: etiquetas.map(() => c.umbral_camas), borderColor: "#c98500", borderDash: [6, 5], borderWidth: 1.5, pointRadius: 0},
      ]},
      options: {responsive: true, maintainAspectRatio: false, interaction: {mode: "index", intersect: false},
        plugins: {tooltip: {callbacks: {label: x => `${x.dataset.label}: ${Math.round(x.raw)} camas`}}},
        scales: {y: {beginAtZero: false, title: {display: true, text: "camas"}}}},
    });

    const filas = c.dias.map(d => `<tr><td>${fmt(d.fecha)}</td><td>${d.ingresos}</td><td>${d.altas}</td>` +
      `<td>${d.camas_ocupadas_normal}</td><td><b>${d.camas_necesarias}</b></td><td>${d.tasa_ocupacion_pct} %</td>` +
      `<td>${d.demanda_sin_cama}</td><td>${d.demanda_sin_cama > 0 ? "Colapso" : d.alerta_saturacion ? "Alerta" : "Sin alerta"}</td></tr>`).join("");
    $("#tContingencia").innerHTML = `<thead><tr><th>Día</th><th>Ingresos</th><th>Altas</th><th>Camas (normal)</th>` +
      `<th>Camas necesarias</th><th>Ocupación</th><th>Sin cama</th><th>Estado</th></tr></thead><tbody>${filas}</tbody>`;
    $("#aclaracionContingencia").textContent =
      `${c.aclaracion} Estancia media: ${c.alos_base} → ${c.alos_contingencia} días. ` +
      `Camas: ${c.capacidad_base} + ${c.parametros.camas_contingencia} de contingencia = ${c.capacidad_total}.`;
  }

  form.addEventListener("submit", simular);
  document.querySelectorAll("[data-cont]").forEach(b => b.addEventListener("click", () => {
    const [aumento, estancia, camas] = b.dataset.cont.split(",");
    $("#contAumento").value = aumento; $("#contEstancia").value = estancia; $("#contCamas").value = camas;
    simular();
  }));
  campos.forEach(id => $(id).addEventListener("input", limpiar));
  // Si cambia la proyeccion de arriba (fuente, fecha, camas u horizonte), el resultado ya no corresponde
  document.addEventListener("proyeccion-actualizada", limpiar);
})();
