const API = location.protocol === "file:" ? "http://localhost:8000" : "";
const NOMBRE = { media_28d: "Media 28 días", semana_anterior: "Semana anterior", dia_semana_8sem: "Día de semana (8 sem.)",
                 estacional: "Estacional (mes × día)", regresion: "Regresión Ridge" };
const charts = {};
let datasets = [], proy = null, real = null;
let consultaProyeccion = 0;

const $ = s => document.querySelector(s);
const fmt = f => new Date(f + "T00:00").toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "numeric" });
const fmtLargo = f => new Date(f + "T00:00").toLocaleDateString("es-AR");
async function api(url, opciones = {}) {
  const r = await fetch(API + url, {...opciones, credentials:"same-origin", headers:{...opciones.headers,"X-Requested-With":"AgenteCamas"}});
  if(r.status===401){ document.querySelector("main").hidden=true;location.replace("/ingresar");throw new Error("La sesion finalizo. Inicia sesion nuevamente."); }
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(datos.detail ? JSON.stringify(datos.detail) : `${url}: ${r.status}`);
  return datos;
}
function grafico(id, cfg) {
  if (typeof Chart === "undefined") {
    const canvas = $(id);
    let aviso = canvas.parentElement.querySelector(".error-grafico");
    if (!aviso) { aviso = document.createElement("p"); aviso.className = "error error-grafico"; canvas.parentElement.appendChild(aviso); }
    aviso.textContent = "No se pudo cargar el grafico. Los valores siguen disponibles en las tablas.";
    return;
  }
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart($(id), cfg);
}
const opc = extra => ({ maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
  plugins: { legend: { labels: { boxWidth: 14 } } }, ...extra });

// ---------------- Proyección ----------------
async function proyectar() {
  const consulta = ++consultaProyeccion;
  const dataset = $("#dataset").value, fecha = $("#fecha").value;
  const textoCapacidad = $("#capacidad").value.trim();
  const cap = textoCapacidad === "" ? null : Number(textoCapacidad);
  const dias = Number($("#horizonte").value) || 7;   // 7 (horizonte controlado), 15 o 30
  $("#mensaje").textContent = dias > 7 ? `Calculando proyeccion a ${dias} dias (la primera vez puede tardar unos segundos)...` : "Calculando proyeccion...";
  proy = null; real = null;
  $("#resumenCamas").replaceChildren();
  $("#kpis").replaceChildren(); $("#camas").replaceChildren(); $("#tDias").replaceChildren();
  $("#dia").value = 0; $("#diaTxt").textContent = "Calculando...";
  if (charts["#gProy"]) { charts["#gProy"].destroy(); delete charts["#gProy"]; }

  document.querySelectorAll("#casos button").forEach(b =>
    b.setAttribute("aria-pressed", "false"));
  try {
    const periodo = PERIODOS_PROYECCION[dataset];

    if (!fecha) {
      throw new Error("Elegí una fecha para el censo histórico.");
    }

    if (fecha < periodo.desde || fecha > periodo.hasta) {
      const desde = periodo.desde.split("-").reverse().join("/");
      const hasta = periodo.hasta.split("-").reverse().join("/");

      throw new Error(
        `Para esta fuente, elegí una fecha entre ${desde} y ${hasta}.`
      );
    }

    if (cap !== null && (!Number.isSafeInteger(cap) || cap <= 0)) {
      throw new Error("La capacidad debe ser un entero mayor a cero.");
    }
    const [nuevaProy, nuevoReal] = await Promise.all([
      api("/proyeccion-camas", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dataset, fecha, capacidad: cap, dias }) }),
      api(`/modelo/ocupacion-real?dataset=${dataset}&desde=${fecha}&dias=${dias}`).catch(() => null),
    ]);
    if (consulta !== consultaProyeccion) return;
    proy = nuevaProy; real = nuevoReal;
  } catch (e) {
    if (consulta !== consultaProyeccion) return;
    proy = null; real = null;
    $("#kpis").innerHTML = ""; $("#camas").innerHTML = "";
    $("#tDias").innerHTML = ""; $("#dia").value = 0;
    $("#diaTxt").textContent = "Sin proyeccion";
    if (charts["#gProy"]) { charts["#gProy"].destroy(); delete charts["#gProy"]; }
    $("#mensaje").className = "alerta";
    $("#mensaje").innerHTML = `<span class="error">No se pudo proyectar: ${e.message}</span>`;
    return;
  }
  const m = $("#mensaje");
  const superaEnCenso = proy.camas_ocupadas_hoy / proy.capacidad > .90;
  m.className = proy.alerta_saturacion || superaEnCenso ? "alerta" : proy.alerta_preventiva ? "preventiva" : "";
  const estadoCenso = superaEnCenso ? "CENSO: supera el 90 % de la capacidad simulada." : "CENSO: no supera el 90 % de la capacidad simulada.";
  const mensajeFuturo = proy.mensaje.replace(/^Sin alerta:/, "Sin saturacion proyectada:");
  m.innerHTML = `<div class="estados"><div><span class="estado-titulo">CENSO · ${fmtLargo(proy.fecha_censo)}</span><span class="estado-valor">${estadoCenso}</span></div><div><span class="estado-titulo">PROXIMOS ${proy.proyeccion.length} DIAS</span><span class="estado-valor">${mensajeFuturo}</span></div></div><details><summary>Ver cómo se calculó</summary><small>Censo del ${fmtLargo(proy.fecha_censo)} (${proy.origen_censo}).
    Ingresos estimados con: ${NOMBRE[proy.metodo_ingresos] || proy.metodo_ingresos}, seleccionado con historia hasta ${fmtLargo(proy.fecha_censo)}. Ocupacion: ${proy.metodo_ocupacion || (proy.dataset === "hdhi" ? "Ridge de ocupacion por horizonte" : "estancias historicas")}. Altas inferidas por balance. La estimación de excedencia es orientativa y no es una probabilidad clínica validada.</small></details>`;
  const kpi = (v, t) => `<div class="kpi"><b>${v}</b><span>${t}</span></div>`;
  $("#kpis").innerHTML =
    kpi(`${proy.tasa_ocupacion_hoy_pct}%`, `ocupacion al censo (${proy.camas_ocupadas_hoy} de ${proy.capacidad})`) +
    kpi(`${proy.tasa_ocupacion_maxima_pct}%`, "tasa de ocupación proyectada máxima") +
    kpi(`${proy.prob_max_superar_umbral_pct}%`, "Estimación máxima de excedencia · orientativa") +
    kpi(`${proy.alos_historico} días`, "ALOS de egresos anteriores al censo") +
    kpi(fmt(proy.dia_pico), "Día de mayor ocupación esperada");
  $("#dia").max = proy.proyeccion.length;
  document.querySelectorAll(".txtDias").forEach(e => { e.textContent = proy.proyeccion.length; });
  dibujarCamas(+$("#dia").value);
  dibujarProyeccion();
  $("#tDias").innerHTML = `<thead><tr><th>Día</th><th>Ingresos</th><th>Altas (balance)</th><th>Ocupadas</th><th>Superior nominal (P90)</th>
    <th>Libres</th><th>Ocupación</th><th>Excedencia estimada</th><th>Real</th><th>Alerta</th></tr></thead><tbody>` +
    proy.proyeccion.map((d, i) => `<tr><td>${fmt(d.fecha)}</td><td>${d.ingresos_previstos}</td><td>${d.altas_previstas}</td>
      <td>${d.camas_ocupadas}</td><td>${d.camas_ocupadas_p90 ?? "–"}</td><td>${d.camas_libres}</td><td>${d.tasa_ocupacion_pct}%</td>
      <td>${d.prob_superar_umbral_pct ?? "–"}%</td><td>${real?.camas_ocupadas[i] ?? "–"}</td>
      <td class="${d.alerta_saturacion ? "si" : ""}">${d.alerta_saturacion ? "Saturación" : "–"}</td></tr>`).join("") + "</tbody>";
}

function dibujarCamas(dia) {
  const cap = proy.capacidad;
  const d = dia === 0 ? null : proy.proyeccion[dia - 1];
  const ocup = dia === 0 ? proy.camas_ocupadas_hoy : Math.round(d.camas_ocupadas);
  const p90 = dia === 0 ? ocup : Math.round(d.camas_ocupadas_p90 ?? d.camas_ocupadas);
  $("#diaTxt").textContent = dia === 0 ? "Fecha del censo" : `Día ${dia}, ${fmt(d.fecha)}`;
  const libres = Math.max(0, cap - ocup);
  const exceso = Math.max(0, ocup - cap);
  const tasa = 100 * ocup / cap;
  $("#resumenCamas").innerHTML = `<div class="resumen-texto"><b>${ocup} ocupadas de ${cap}</b><span>${libres} libres${exceso ? ` · ${exceso} por encima de la capacidad` : ""}</span></div><div class="barra-camas ${tasa > 90 ? "alta" : ""}" aria-hidden="true"><span style="width:${Math.min(100, tasa)}%"></span></div><small>${dia === 0 ? "Censo histórico reconstruido" : "Ocupación esperada, redondeada para este mapa"} · ${tasa.toFixed(1)} % de la capacidad supuesta.</small>`;
  const total = Math.max(cap, p90);
  const escala = Math.max(1, Math.ceil(total / 2000));
  const bloques = Math.ceil(total / escala);
  const cols = Math.ceil(Math.sqrt(bloques * 1.8));
  let html = "";
  for (let i = 0; i < bloques; i++) {
    const cama = i * escala;
    const c = cama >= cap ? "excede" : cama < ocup ? "ocupada" : cama < p90 ? "p90" : "";
    html += `<div class="cama ${c}"></div>`;
  }
  $("#camas").style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  $("#camas").innerHTML = html;
  let notaEscala = $("#escalaCamas");
  if (!notaEscala) { notaEscala = document.createElement("p"); notaEscala.id = "escalaCamas"; notaEscala.className = "nota"; $("#camas").after(notaEscala); }
  notaEscala.textContent = escala > 1 ? `Cada bloque representa hasta ${escala} camas; los indicadores muestran los valores exactos.` : "Cada bloque representa una cama.";
}

function dibujarProyeccion() {
  const etiquetas = ["Censo", ...proy.proyeccion.map(d => fmt(d.fecha))];
  const series = [
    { label: "Esperada", data: [proy.tasa_ocupacion_hoy_pct, ...proy.proyeccion.map(d => d.tasa_ocupacion_pct)],
      borderColor: "#11888b", borderWidth: 3, tension: .25,
      pointBackgroundColor: ["#11888b", ...proy.proyeccion.map(d => d.alerta_saturacion ? "#bd3049" : "#11888b")], pointRadius: 5 },
    { label: "Superior nominal (P90)", data: [proy.tasa_ocupacion_hoy_pct, ...proy.proyeccion.map(d =>
        d.camas_ocupadas_p90 != null ? +(100 * d.camas_ocupadas_p90 / proy.capacidad).toFixed(1) : null)],
      borderColor: "#8b70ce", borderDash: [6, 4], borderWidth: 2, pointRadius: 0, tension: .25 },
    { label: "Umbral 90 %", data: etiquetas.map(() => 90), borderColor: "#bd3049", borderWidth: 2, pointRadius: 0 },
  ];
  if (real) series.splice(2, 0, { label: "Real", data: [proy.tasa_ocupacion_hoy_pct, ...real.camas_ocupadas.map(n => n == null ? null : +(100 * n / proy.capacidad).toFixed(1))],
    borderColor: "#7b8ca3", borderWidth: 2, pointRadius: 3, tension: .25 });
  grafico("#gProy", { type: "line", data: { labels: etiquetas, datasets: series },
    options: opc({ scales: { y: { suggestedMin: 50, suggestedMax: 105, ticks: { callback: v => v + "%" } } } }) });
}

// ---------------- Evaluación ----------------

// COMPARACION_CAPACIDAD_Y_ESTADOS_V1
function estadoTabla(selector, mensaje, error = false) {
  const tabla = $(selector);
  tabla.replaceChildren();
  const aviso = document.createElement("caption");
  aviso.className = error ? "error" : "nota";
  aviso.textContent = mensaje;
  tabla.appendChild(aviso);
}

async function cargarEvaluacion() {
  estadoTabla("#tMetodos", "Cargando modelos de ingresos...");
  estadoTabla("#tReglas", "Cargando evaluacion de HDHI con la capacidad base configurada...");
  $("#notaBack").textContent = "Cargando backtesting de HDHI...";
  $("#notaHorizonte").textContent = "Cargando evaluacion de HDHI...";
  const tareas = [
(async () => {

  const resultados = await Promise.allSettled(datasets.map(d => api(`/modelo/demanda?dataset=${d.clave}`)));
const modelos = resultados.filter(r => r.status === "fulfilled").map(r => r.value);
const fallos = resultados.map((r, i) => r.status === "rejected"
  ? datasets[i].clave + ": " + r.reason.message : null).filter(Boolean);
if (!modelos.length) throw new Error(fallos.join(" | "));

  let filas = "";
  modelos.forEach(r => Object.keys(NOMBRE).forEach((k, i) => {
    const x = r.backtest.metricas[k];
    filas += `<tr class="${k === r.metodo_elegido ? "elegido" : ""}">
      <td>${i === 0 ? `${r.dataset} <small>(${r.ingresos_promedio_dia}/día)</small>` : ""}</td>
      <td style="text-align:left">${NOMBRE[k]}${k === r.metodo_elegido ? " ✓" : ""}</td>
      <td>${x.mae}</td><td>${x.wape_pct}%</td><td>${x.wape_semanal_pct}%</td><td>${x.cobertura_80pct}%</td></tr>`;
  }));
  $("#tMetodos").innerHTML = `<thead><tr><th>Dataset</th><th style="text-align:left">Método</th><th>MAE</th>
    <th>WAPE diario</th><th>WAPE semanal</th><th>Cobertura IC 80 %</th></tr></thead><tbody>${filas}</tbody>`;

  
    if (fallos.length) {
      const aviso = document.createElement("caption");
      aviso.className = "error";
      aviso.style.captionSide = "bottom";
      aviso.textContent = "No se pudieron cargar: " + fallos.join(" | ");
      $("#tMetodos").appendChild(aviso);
    }
    
    })().catch(e => estadoTabla("#tMetodos", "Error en modelos: " + e.message, true)),
(async () => {
const b = await api("/modelo/backtest?dataset=hdhi");
  grafico("#gBack", { type: "line", data: { labels: b.fechas.map(f => f.slice(5)), datasets: [
    { label: "Real", data: b.real, borderColor: "#7b8ca3", borderWidth: 1, pointRadius: 0 },
    { label: NOMBRE[b.metodo_elegido], data: b[b.metodo_elegido], borderColor: "#11888b", borderWidth: 2, pointRadius: 0 },
    { label: "Media 28 días", data: b.media_28d, borderColor: "#d6a21e", borderWidth: 2, borderDash: [4, 3], pointRadius: 0 },
  ]}, options: opc({ scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Ingresos por día" } } } }) });
  $("#notaBack").textContent = `HDHI, ${b.fechas[0]} a ${b.fechas.at(-1)}. El modelo sigue el patrón semanal; los picos diarios no siempre son anticipados por estos metodos.`;

  
    })().catch(e => {
      $("#notaBack").classList.add("error");
      $("#notaBack").textContent = "Error en backtesting: " + e.message;
    }),
(async () => {
const ev = await api("/modelo/evaluacion-agente?dataset=hdhi");
  grafico("#gHorizonte", { type: "bar", data: {
    labels: ev.error_por_dia.mae_camas.map((_, i) => `Dia ${i + 1}`),
    datasets: [
      { label: "Agente nuevo", data: ev.error_por_dia.mae_camas, backgroundColor: "#11888b" },
      { label: "Agente anterior", data: ev.comparacion_referencia.mae_agente_anterior_por_dia, backgroundColor: "#b47d48" },
      { label: "Mantener censo", data: ev.comparacion_referencia.mae_camas_por_dia, backgroundColor: "#9baebd" }
    ] }, options: opc({ scales: { y: { title: { display: true, text: "Error en camas" } } } }) });
  const ref = ev.comparacion_referencia;
  const cob = ev.cobertura_limite_superior;
  $("#notaHorizonte").textContent = `Evaluacion desde ${ev.fechas_evaluadas} censos. Error medio global: nuevo ${ref.mae_global_agente}; anterior ${ref.mae_global_agente_anterior}; mantener censo ${ref.mae_global_referencia} camas. Este total incluye desarrollo.`;
  if (ev.validacion_posterior) {
    const v = ev.validacion_posterior;
    $("#notaHorizonte").textContent += ` Validacion posterior (${v.fechas} censos, ${v.primer_censo} a ${v.ultimo_censo}): nuevo ${v.mae_agente}; anterior ${v.mae_agente_anterior}; mantener censo ${v.mae_referencia} camas.`;
  }
  if (cob.empirico_pct != null) $("#notaHorizonte").textContent += ` Limite superior nominal 90 %: cobertura ${cob.empirico_pct} %, sobre ${cob.pronosticos_comparables} predicciones comparables. No garantiza cobertura futura.`;

  const reglas = { ocupacion_esperada_mayor_90: "Ocupación esperada > 90 % (consigna)",
                   p90_mayor_90: "Limite superior nominal (P90) > 90 %", probabilidad_mayor_30: "Estimacion de excedencia ≥ 30 % (preventiva)" };
  $("#tReglas").innerHTML = `<thead><tr><th>Regla</th><th>Alertas</th><th>Aciertos</th><th>Precisión</th><th>Recall</th></tr></thead><tbody>` +
    Object.entries(ev.reglas_de_alerta).map(([k, v]) => `<tr><td>${reglas[k]}</td><td>${v.alertas}</td><td>${v.aciertos}</td>
      <td>${v.precision == null ? "No aplica" : Math.round(100 * v.precision) + "%"}</td><td>${v.recall == null ? "No aplica" : Math.round(100 * v.recall) + "%"}</td></tr>`).join("") +
    `</tbody><caption style="caption-side:bottom;text-align:left" class="nota">Semanas que realmente superaron el 90 %: ${ev.semanas_que_realmente_superaron_el_umbral} de ${ev.fechas_evaluadas}.</caption>`;

      const aviso = document.createElement("caption");
      aviso.className = "nota";
      aviso.style.captionSide = "bottom";
      aviso.textContent = "Evaluacion historica de HDHI con capacidad base: "
        + ev.capacidad + " camas. El campo Camas de arriba solo modifica la proyeccion.";
      $("#tReglas").appendChild(aviso);
    })().catch(e => {
      $("#notaHorizonte").classList.add("error");
      $("#notaHorizonte").textContent = "Error en evaluacion: " + e.message;
      estadoTabla("#tReglas", "Error en evaluacion: " + e.message, true);
    }),
  ];
  await Promise.all(tareas);
}


async function cargarEscenarios() {
  $("#notaEscenarios").textContent =
    "Los escenarios mantienen la fecha elegida y cambian la capacidad supuesta.";

  document.querySelectorAll("#casos button").forEach(b => {
    b.disabled = !proy;
    b.title = "Cambiar la capacidad para la fecha seleccionada";
  });
}

// Períodos de proyección comprobados para los datasets actuales.
const PERIODOS_PROYECCION = {
  hdhi: {
    desde: "2017-08-26",
    hasta: "2019-03-31"
  },
  lengthofstay: {
    desde: "2012-05-27",
    hasta: "2013-01-01"
  },
  healthcare: {
    desde: "2019-10-02",
    hasta: "2024-05-07"
  }
};

function configurarCalendario() {
  const periodo = PERIODOS_PROYECCION[$("#dataset").value];
  const calendario = $("#fecha");

  calendario.min = periodo.desde;
  calendario.max = periodo.hasta;
  calendario.required = true;

  let ayuda = $("#ayudaFecha");

  if (!ayuda) {
    ayuda = document.createElement("small");
    ayuda.id = "ayudaFecha";
    calendario.after(ayuda);
    calendario.setAttribute("aria-describedby", "ayudaFecha");
  }

  const mostrarFecha = fecha =>
    fecha.split("-").reverse().join("/");

  ayuda.textContent =
    `Podés proyectar del ${mostrarFecha(periodo.desde)} ` +
    `al ${mostrarFecha(periodo.hasta)}.`;

  calendario.title = ayuda.textContent;
  ayuda.hidden = true;
}


// ---------------- Inicio ----------------
async function iniciar() {
  try { datasets = await api("/datasets"); }
  catch (e) { $("#mensaje").innerHTML = `<span class="error">No se pudo conectar con la API. ¿Está corriendo uvicorn? (${e.message})</span>`; return; }
  $("#dataset").innerHTML = datasets.map(d => `<option value="${d.clave}">${d.nombre}</option>`).join("");
  const elegirDataset = () => {
    const d = datasets.find(x => x.clave === $("#dataset").value);
    $("#fecha").value = d.fecha_demo;
    configurarCalendario();
    $("#capacidad").value = d.capacidad_total;
    $("#casos").hidden = false;
    document.querySelectorAll("#casos button").forEach(b => b.disabled = true);
  };
  $("#dataset").addEventListener("change", async () => { elegirDataset(); await proyectar(); await cargarEscenarios(); });
  $("#fecha").addEventListener("change", proyectar);
  $("#capacidad").addEventListener("change", proyectar);
  $("#horizonte").addEventListener("change", proyectar);
    document.querySelectorAll("#casos button").forEach(b => {
    b.addEventListener("click", async () => {
      if (!proy ||
          proy.fecha_censo !== $("#fecha").value ||
          proy.dataset !== $("#dataset").value) {
        return;
      }

      const pico = Math.max(
        ...proy.proyeccion.map(d => Number(d.camas_ocupadas))
      );

      if (!Number.isFinite(pico) || pico <= 0) return;

      const capacidades = {
        normal: Math.ceil(pico / 0.80),
        limite: Math.ceil(pico / 0.90),
        critico: Math.max(1, Math.floor(pico / 0.95))
      };

      $("#capacidad").value = capacidades[b.dataset.escenario];

      document.querySelectorAll("#casos button").forEach(boton => {
        boton.disabled = true;
      });

      await proyectar();
      await cargarEscenarios();

      document.querySelectorAll("#casos button").forEach(boton => {
        boton.setAttribute(
          "aria-pressed",
          String(proy !== null && boton === b)
        );
      });
    });
  });

  $("#dia").addEventListener("input", e => {
    if (proy) dibujarCamas(+e.target.value);
  });

  elegirDataset();

  await proyectar();
  await cargarEscenarios();
}

// SOLAPAS_AGENTE_V1
let estadisticasCargadas = false;
let evaluacionCargada = false;
let cargandoEstadisticas = false;
let cargandoEvaluacion = false;

function tablaIndicadores(selector, encabezados, filas) {
  const tabla = $(selector);
  tabla.replaceChildren();
  const cabecera = document.createElement("thead");
  const tr = document.createElement("tr");
  encabezados.forEach(titulo => {
    const th = document.createElement("th");
    th.scope = "col"; th.textContent = titulo; tr.appendChild(th);
  });
  cabecera.appendChild(tr); tabla.appendChild(cabecera);
  const cuerpo = document.createElement("tbody");
  filas.forEach(fila => {
    const row = document.createElement("tr");
    fila.forEach(valor => {
      const td = document.createElement("td");
      td.textContent = valor == null ? "Sin dato" : valor;
      row.appendChild(td);
    });
    cuerpo.appendChild(row);
  });
  tabla.appendChild(cuerpo);
}

async function cargarEstadisticasHDHI() {
  if (cargandoEstadisticas) return;
  cargandoEstadisticas = true;
  const estado = $("#estadoEstadisticas");
  estado.className = "nota";
  estado.textContent = "Cargando indicadores de HDHI...";
  try {
    const r = await api("/estadisticas/hdhi");
    $("#kpisEstadisticas").replaceChildren();
    const resumen = [
      [r.total_internaciones.toLocaleString("es-AR"), "Episodios analizados"],
      [r.alos_general_dias + " dias", "ALOS general"],
      [r.cantidad_sin_grupo_etario ?? 0, "Episodios sin grupo etario"],
    ];
    resumen.forEach(([valor, etiqueta]) => {
      const caja = document.createElement("div"); caja.className = "kpi";
      const numero = document.createElement("b"); numero.textContent = valor;
      const label = document.createElement("span"); label.textContent = etiqueta;
      caja.appendChild(numero); caja.appendChild(label);
      $("#kpisEstadisticas").appendChild(caja);
    });
    tablaIndicadores("#tablaPatologias",
      ["Condicion", "Internaciones con la condicion", "ALOS (dias)", "Mediana (dias)", "Desconocidos"],
      r.patologias.map(p => [p.patologia, p.cantidad_internaciones,
        p.alos_promedio, p.mediana_dias, p.cantidad_sin_dato ?? null]));
    tablaIndicadores("#tablaEdades",
      ["Edad", "Internaciones", "ALOS (dias)", "Mediana (dias)"],
      r.grupos_etarios.map(g => [g.grupo_etario, g.cantidad_internaciones,
        g.alos_promedio, g.mediana_dias]));
    estado.textContent = "Indicadores cargados. Fuente: HDHI revisado.";
    estadisticasCargadas = true;
  } catch(e) {
    $("#kpisEstadisticas").replaceChildren();
    $("#tablaPatologias").replaceChildren();
    $("#tablaEdades").replaceChildren();
    estado.className = "error";
    estado.textContent = "No se pudieron cargar los indicadores: " + e.message;
    estadisticasCargadas = false;
  } finally { cargandoEstadisticas = false; }
}

async function cargarEvaluacionSolapa() {
  if (cargandoEvaluacion) return;
  cargandoEvaluacion = true;
  try {
    await cargarEvaluacion();
    evaluacionCargada = true;
  } finally { cargandoEvaluacion = false; }
}

function seleccionarSolapa(nombre) {
  document.querySelectorAll("#solapas-principales [role=tab]").forEach(b => {
    const activa = b.dataset.tab === nombre;
    b.setAttribute("aria-selected", String(activa));
    b.tabIndex = activa ? 0 : -1;
  });
  ["proyeccion", "estadisticas", "evaluacion", "sectores", "administracion"].forEach(id => {
    $("#vista-" + id).hidden = id !== nombre;
  });
  $("header .controles").hidden = nombre !== "proyeccion";
  if (nombre === "sectores" && !referenciaSectoresCargada) cargarReferenciasSectores();
  if (nombre === "estadisticas" && !estadisticasCargadas) cargarEstadisticasHDHI();
  if (nombre === "evaluacion" && !evaluacionCargada) cargarEvaluacionSolapa();
  if (nombre === "administracion") actualizarPanelAdministracion();
  // Chart.js recalcula dimensiones cuando su contenedor deja de estar oculto.
  requestAnimationFrame(() => Object.values(charts).forEach(c => c.resize()));
}

const botonesSolapa = [...document.querySelectorAll("#solapas-principales [role=tab]")];
botonesSolapa.forEach((b, i) => {
  b.addEventListener("click", () => seleccionarSolapa(b.dataset.tab));
  b.addEventListener("keydown", e => {
    const visibles = botonesSolapa.filter(boton => !boton.hidden && !boton.disabled);
    const n = visibles.length;
    let destino = visibles.indexOf(b);
    if (e.key === "ArrowRight") destino = (destino + 1) % n;
    else if (e.key === "ArrowLeft") destino = (destino + n - 1) % n;
    else if (e.key === "Home") destino = 0;
    else if (e.key === "End") destino = n - 1;
    else return;
    e.preventDefault();
    visibles[destino].focus();
    seleccionarSolapa(visibles[destino].dataset.tab);
  });
});



let referenciaSectoresDatos = null;
let origenParametrosSectores = "supuestos_usuario";
let referenciaSectoresCargada = false, consultaSectores = 0, consultaReferencia = 0;
const camposSectores = ["censoUTI","capUTI","estanciaUTI","censoGeneral","capGeneral","estanciaGeneral","porcentajeUTI","porcentajeTraslado"];
function limpiarSectores() {
  consultaSectores++;
  $("#resultadoSectores").hidden = true;
  $("#tarjetasSectores").replaceChildren(); $("#tablaSectores").replaceChildren();
  if(charts["#gSectores"]) {charts["#gSectores"].destroy();delete charts["#gSectores"];}
  $("#estadoSectores").textContent = "Escenario modificado. Calculá nuevamente para ver resultados actualizados.";
  $("#estadoSectores").className = "";
}
async function cargarReferenciasSectores() {
  const token = ++consultaReferencia;
  referenciaSectoresCargada = false;
  limpiarSectores();
  ["calcularSectores","ejemploSectores","criticoSectores"].forEach(id => $("#"+id).disabled=true);
  $("#referenciaSectores").textContent="Verificando rango de fechas e historia anterior al censo…";
  try {
    const r = await api("/sectores/parametros?fecha="+encodeURIComponent($("#fechaSectores").value));
    if(token!==consultaReferencia)return;
    $("#referenciaSectores").textContent=`Historia disponible. Auditoría: ${r.episodios_anteriores.toLocaleString("es-AR")} episodios egresados antes del censo, hasta ${fmtLargo(r.ultimo_egreso_utilizado)}. La duración UTI no confirma noches ni recorridos entre sectores. Por eso no se completan automáticamente los parámetros: ingresalos o cargá el ejemplo ficticio.`;
    referenciaSectoresDatos=r;
    referenciaSectoresCargada=true;
    ["calcularSectores","ejemploSectores","criticoSectores"].forEach(id => $("#"+id).disabled=false);
  } catch(e) {
    if(token!==consultaReferencia)return;
    $("#referenciaSectores").textContent="No se pudo obtener referencia: "+e.message;
  }
}
async function proyectarSectores(event) {
  if(event)event.preventDefault();
  if(!$("#formSectores").reportValidity() || !referenciaSectoresCargada)return;
  limpiarSectores();const token=consultaSectores;
  $("#estadoSectores").textContent="Calculando ingresos con historia hasta el censo y simulando los dos sectores…";
  const n = id => Number($("#"+id).value);
  const cuerpo={dataset:"hdhi",fecha:$("#fechaSectores").value,dias:7,sectores:{
    uti:{ocupadas:n("censoUTI"),capacidad:n("capUTI")}, general:{ocupadas:n("censoGeneral"),capacidad:n("capGeneral")},
    estancia_media_uti:n("estanciaUTI"),estancia_media_general:n("estanciaGeneral"),
    proporcion_ingresos_uti:n("porcentajeUTI")/100,fraccion_salidas_uti_a_general:n("porcentajeTraslado")/100,origen_parametros:origenParametrosSectores}};
  try {
    const r=await api("/proyeccion-camas",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(cuerpo)});
    if(token!==consultaSectores)return;
    const num=x=>Number(x).toLocaleString("es-AR",{maximumFractionDigits:1});
    for(const [clave,nombre] of [["uti","UTI · terapia intensiva"],["general","Internación general"]]) {
      const c=r.censo[clave],t=r.resumen[clave];
      const caja=document.createElement("div");caja.className="panel";
      caja.innerHTML=`<h3>${nombre}</h3><div class="sector-estado ${t.alerta_proyeccion?"alerta":""}">${t.alerta_proyeccion?"Alerta de Saturación en la proyección":"Sin saturación proyectada"}</div><div class="sector-kpis"><div><b>${num(c.camas_ocupadas)} / ${c.capacidad}</b><small>Censo ingresado / capacidad</small></div><div><b>${num(c.tasa_ocupacion_pct)} %</b><small>Ocupación al censo</small></div><div><b>${num(t.ocupacion_maxima_pct)} %</b><small>Máxima ocupación esperada</small></div></div><p class="nota">Censo: ${t.alerta_censo?"supera":"no supera"} el 90 %. Pico proyectado: ${fmtLargo(t.dia_pico)}. ${t.alerta_proyeccion?"Revisá la demanda y la capacidad de este sector.":"El resultado depende de los supuestos ingresados."}</p>`;
      $("#tarjetasSectores").appendChild(caja);
    }
    grafico("#gSectores",{type:"line",data:{labels:["Censo",...r.proyeccion.map(d=>fmt(d.fecha))],datasets:[
      {label:"UTI",data:[r.censo.uti.tasa_ocupacion_pct,...r.proyeccion.map(d=>d.uti.tasa_ocupacion_pct)],borderColor:"#6950ad",borderWidth:3,tension:.2},
      {label:"General",data:[r.censo.general.tasa_ocupacion_pct,...r.proyeccion.map(d=>d.general.tasa_ocupacion_pct)],borderColor:"#11888b",borderWidth:3,tension:.2},
      {label:"Umbral 90 %",data:Array(8).fill(90),borderColor:"#bd3049",borderDash:[5,4],pointRadius:0}]},options:opc({scales:{y:{suggestedMin:0,suggestedMax:100,ticks:{callback:v=>v+"%"}}}})});
    tablaIndicadores("#tablaSectores",["Día","Ingresos externos UTI","Ingresos externos general","Traslados UTI → general","Altas hospital","UTI ocupadas","General ocupadas","Libres UTI","Libres general","Alerta por sector"],r.proyeccion.map(d=>[fmt(d.fecha),num(d.uti.ingresos_externos),num(d.general.ingresos_externos),num(d.traslados_uti_a_general),num(d.altas_hospital),num(d.uti.camas_ocupadas),num(d.general.camas_ocupadas),num(d.uti.camas_libres),num(d.general.camas_libres),[d.uti.alerta_saturacion?"UTI":"",d.general.alerta_saturacion?"General":""].filter(Boolean).join(" + ")||"Sin alerta"]));
    $("#supuestosSectores").replaceChildren();r.advertencias.forEach(t=>{const li=document.createElement("li");li.textContent=t;$("#supuestosSectores").appendChild(li);});
    $("#parametrosUsadosSectores").textContent=`Método de ingresos: ${NOMBRE[r.metodo_ingresos]||r.metodo_ingresos}. Censo: ${fmtLargo(r.fecha_censo)}. Estancias supuestas: UTI ${num(r.parametros.estancia_media_uti)} días; general ${num(r.parametros.estancia_media_general)} días. Ingresos que inician UTI: ${num(100*r.parametros.proporcion_ingresos_uti)} %. Salidas UTI hacia general: ${num(100*r.parametros.fraccion_salidas_uti_a_general)} %.`;
    $("#evidenciaSectores").textContent=(r.origen_parametros==="ejemplo_ficticio"?"EJEMPLO FICTICIO: censo, capacidades y parámetros elegidos para demostrar la lógica.":"ESCENARIO CON SUPUESTOS INGRESADOS POR VOS: censo, capacidades y parámetros sin validación sectorial.")+" Los ingresos totales se estiman con HDHI hasta el censo. Balance de pacientes verificado. No es un pronóstico validado de UTI.";
    $("#resultadoSectores").hidden=false;
    $("#estadoSectores").textContent=r.origen_parametros==="ejemplo_ficticio"?"Ejemplo ficticio calculado. Revisá las alertas y el efecto de los supuestos.":"Escenario calculado con tus entradas. Resultados condicionados a los supuestos.";
    requestAnimationFrame(()=>charts["#gSectores"]?.resize());
  } catch(e) {
    if(token!==consultaSectores)return;
    $("#estadoSectores").className="error";$("#estadoSectores").textContent="No se pudo simular: "+e.message;
  }
}
$("#formSectores").addEventListener("submit",proyectarSectores);
camposSectores.forEach(id=>$("#"+id).addEventListener("input",()=>{origenParametrosSectores="supuestos_usuario";limpiarSectores();}));
$("#fechaSectores").addEventListener("change",cargarReferenciasSectores);
$("#fechaSectores").addEventListener("input",()=>{consultaReferencia++;referenciaSectoresCargada=false;limpiarSectores();["calcularSectores","ejemploSectores","criticoSectores"].forEach(id=>$("#"+id).disabled=true);});
$("#restaurarReferenciaSectores").addEventListener("click",cargarReferenciasSectores);
function ejemploSectores(critico=false) {
  if(!referenciaSectoresCargada||!referenciaSectoresDatos)return;
  origenParametrosSectores="ejemplo_ficticio";
  $("#estanciaUTI").value=2;$("#estanciaGeneral").value=5;
  $("#porcentajeUTI").value=20;$("#porcentajeTraslado").value=80;
  $("#censoUTI").value=7;$("#capUTI").value=critico?8:20;
  $("#censoGeneral").value=90;$("#capGeneral").value=170;
  proyectarSectores();
}
$("#ejemploSectores").addEventListener("click",()=>ejemploSectores(false));
$("#criticoSectores").addEventListener("click",()=>ejemploSectores(true));

async function verificarAcceso() {
  try {
    const r=await fetch("/auth/sesion",{credentials:"same-origin"});
    if(!r.ok)throw new Error("No se pudo verificar el acceso.");
    const sesion=await r.json();
    if(!sesion.autenticado){document.querySelector("main").hidden=true;location.replace("/ingresar");return false;}
    document.querySelector("main").hidden=false;
    $("#nombreSesion").textContent="Sesión de "+sesion.usuario;
    return true;
  }catch(error){document.querySelector("main").hidden=true;$("#nombreSesion").textContent="No se pudo verificar tu acceso. Recargá la página.";return false;}
}
$("#cerrarSesion").addEventListener("click",async()=>{
  const b=$("#cerrarSesion");b.disabled=true;
  try{const r=await fetch("/auth/salir",{method:"POST",credentials:"same-origin",headers:{"X-Requested-With":"AgenteCamas"}});if(!r.ok)throw new Error();document.querySelector("main").hidden=true;location.replace("/ingresar");}
  catch(error){b.textContent="Reintentar cerrar sesión";b.disabled=false;}
});
window.addEventListener("pageshow",event=>{if(event.persisted)location.reload();});
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible")verificarAcceso();});
setInterval(()=>{if(document.visibilityState==="visible")verificarAcceso();},60000);
verificarAcceso().then(permitido=>{if(permitido)iniciar();});
