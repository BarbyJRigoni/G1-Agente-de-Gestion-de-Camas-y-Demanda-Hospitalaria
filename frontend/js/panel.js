const API = location.protocol === "file:" ? "http://localhost:8000" : "";
const NOMBRE = { media_28d: "Media 28 días", semana_anterior: "Semana anterior", dia_semana_8sem: "Día de semana (8 sem.)",
                 estacional: "Estacional (mes × día)", regresion: "Regresión Ridge" };
const charts = {};
let datasets = [], proy = null, real = null;
let consultaProyeccion = 0;

const $ = s => document.querySelector(s);
const fmt = f => new Date(f + "T00:00").toLocaleDateString("es-AR", { weekday: "short", day: "numeric", month: "numeric" });
const fmtLargo = f => new Date(f + "T00:00").toLocaleDateString("es-AR");
// Indicador de carga: se muestra mientras haya consultas a la API en curso
// (con una demora corta para que no parpadee en las respuestas rápidas).
let consultasEnCurso = 0, temporizadorCarga = null;
function actualizarTextoCarga() {
  const seccion = document.querySelector('#solapas-principales [aria-selected="true"]')?.dataset.tab;
  const textos = {estadisticas:'Consultando las estancias…', evaluacion:'Evaluando el modelo…',
    sectores:'Consultando la simulación UTI/general…', administracion:'Consultando datos…'};
  const dias = Number($('#horizonte').value) || 7;
  $('#cargandoTexto').textContent = textos[seccion] || `Calculando la proyección a ${dias} días…`;
}

function indicadorCarga(delta) {
  consultasEnCurso = Math.max(0, consultasEnCurso + delta);
  const caja = $('#cargando');
  if (!caja) return;
  if (consultasEnCurso > 0) {
    actualizarTextoCarga();
    if (caja.hidden && temporizadorCarga === null) {
      temporizadorCarga = setTimeout(() => {
        temporizadorCarga = null;
        if (consultasEnCurso > 0) caja.hidden = false;
      }, 200);
    }
    $('#contenidoAplicacion').setAttribute('aria-busy', 'true');
  } else {
    clearTimeout(temporizadorCarga);
    temporizadorCarga = null;
    caja.hidden = true;
    $('#contenidoAplicacion').removeAttribute('aria-busy');
  }
}

async function api(url, opciones = {}) {
  indicadorCarga(+1);
  try {
    return await consultarApi(url, opciones);
  } finally {
    indicadorCarga(-1);
  }
}
async function consultarApi(url, opciones = {}) {
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
  charts[id] = new Chart($(id), estilizarGrafico(id, cfg));
}
const opc = extra => ({ maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
  plugins: { legend: { labels: { boxWidth: 14 } } }, ...extra });

// PRESENTACIÓN DE GRÁFICOS. No modifica respuestas, métricas ni pronósticos.
function degradadoGrafico(inicio, fin) {
  return contexto => {
    const grafico = contexto.chart, area = grafico.chartArea;
    if (!area || !grafico.ctx?.createLinearGradient) return inicio;
    const gradiente = grafico.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradiente.addColorStop(0, inicio); gradiente.addColorStop(1, fin);
    return gradiente;
  };
}

const etiquetasBarras = {
  id:'etiquetasBarrasVivas',
  afterDatasetsDraw(grafico, argumentos, opciones) {
    const contexto = grafico.ctx;
    contexto.save(); contexto.font='600 11px system-ui'; contexto.fillStyle='#36566b';
    contexto.textAlign='left'; contexto.textBaseline='middle';
    const meta = grafico.getDatasetMeta(0), dataset = grafico.data.datasets[0];
    meta.data.forEach((barra, indice) => {
      if (!Number.isFinite(Number(dataset.data[indice]))) return;
      if (opciones.puntos) {
        contexto.beginPath();contexto.arc(barra.x,barra.y,6,0,Math.PI*2);
        contexto.fillStyle=Array.isArray(dataset.backgroundColor)?dataset.backgroundColor[indice]:'#087f83';
        contexto.fill();contexto.strokeStyle='#fff';contexto.lineWidth=2;contexto.stroke();
      }
      contexto.fillStyle='#36566b';
      contexto.fillText(numeroVisual(dataset.data[indice])+(opciones.sufijo||''),barra.x+11,barra.y);
    });
    contexto.restore();
  }
};

function estilizarGrafico(id, configuracion) {
  const opciones = configuracion.options || (configuracion.options = {});
  const series = configuracion.data.datasets;
  const reducido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  opciones.animation = reducido ? false : {duration:350};
  opciones.plugins = opciones.plugins || {};
  const leyenda = opciones.plugins.legend || (opciones.plugins.legend = {});
  if (leyenda.display !== false) {
    leyenda.position='bottom';
    leyenda.labels={...leyenda.labels,usePointStyle:true,boxWidth:9,padding:18,color:'#4f667b'};
  }
  opciones.plugins.tooltip = {
    backgroundColor:'#203d50',titleColor:'#fff',bodyColor:'#e5f3f5',padding:13,
    cornerRadius:11,boxPadding:5,...opciones.plugins.tooltip
  };
  if (opciones.scales) Object.entries(opciones.scales).forEach(([nombre,eje]) => {
    eje.border={display:false,...eje.border};
    eje.ticks={color:'#62788b',font:{size:11},...eje.ticks};
    eje.grid={color:'#e8eff4',drawTicks:false,...eje.grid};
  });
  if (id==='#gProy' || id==='#gBack') {
    const elegida=series.find(s=>s.label==='Esperada'||s.label.startsWith('Pronóstico:'));
    if (elegida) {
      elegida.backgroundColor=degradadoGrafico('#18aaa947','#18aaa903');elegida.fill=true;
      elegida.borderWidth=3;elegida.pointBorderColor='#fff';elegida.pointBorderWidth=2;elegida.pointHoverRadius=7;
    }
    series.filter(s=>s.label==='Real'||s.label==='Ingresos reales').forEach(s=>{s.borderDash=[3,3];s.borderColor='#7d91a8';});
  }
  if (id==='#gMovimientos') {
    series[0].backgroundColor=degradadoGrafico('#21c3bc','#087f83');
    series[1].backgroundColor=degradadoGrafico('#a8b6ed','#587bad');
    series.forEach(s=>{s.borderRadius=8;s.borderSkipped=false;s.maxBarThickness=26;});
  }
  if (id==='#gPatologias' || id.startsWith('#gMetodos-')) {
    const patologia=id==='#gPatologias';
    series[0].barThickness=18;series[0].borderRadius=7;
    const maximo=Math.max(0,...series[0].data.filter(v=>typeof v==='number'&&Number.isFinite(v)));
    opciones.layout={...opciones.layout,padding:{right:65}};
    opciones.scales.x.suggestedMax=Math.max(opciones.scales.x.suggestedMax||0,maximo*1.25);
    configuracion.plugins=[...(configuracion.plugins||[]),etiquetasBarras];
    opciones.plugins.etiquetasBarrasVivas={puntos:false,sufijo:patologia?' días':' %'};
  }
  if (id==='#gHorizonte') {
    series[0].backgroundColor=degradadoGrafico('#23c4bb','#087f83');
    series[0].borderRadius=7;series[0].maxBarThickness=34;series[0].order=1;
    series.slice(1).forEach((s,i)=>{
      s.type='line';s.order=0;s.borderColor=i?'#587bad':'#9272c7';s.backgroundColor=s.borderColor;
      s.borderWidth=2;s.borderDash=i?[3,4]:[7,4];s.pointRadius=4;s.pointHoverRadius=6;
      s.pointStyle=i?'rectRot':'circle';s.fill=false;s.tension=.15;
    });
  }
  if (id==='#gSectores') {
    configuracion.type='bar';
    series.slice(0,2).forEach((s,i)=>{
      s.type='bar';s.order=1;s.backgroundColor=i?degradadoGrafico('#28c6bd','#087f83'):degradadoGrafico('#9ec8ef','#4b78b0');
      s.borderColor=i?'#087f83':'#4b78b0';s.borderWidth=0;s.borderRadius=6;s.maxBarThickness=27;
    });
    series[2].type='line';series[2].order=0;series[2].borderWidth=2;series[2].pointRadius=0;
  }
  if (id==='#gDispersion') {
    series[0].backgroundColor='#16b7b080';series[0].borderColor='#087f83';
    series[0].pointBorderWidth=1.5;series[0].pointRadius=5;series[0].pointHoverRadius=8;
  }
  return configuracion;
}

function dibujarDonaCamas(ocupadas, capacidad, libres, exceso, tasa) {
  // La dona divide la capacidad en dos partes excluyentes. La demanda que la
  // supera se informa aparte y nunca se oculta ni se cuenta como cama física.
  $('#resumenCamas').innerHTML = `
    <div class="ocupacion-circular">
      <div class="dona-camas"><canvas id="gDonaCamas" role="img" aria-label="${Math.min(ocupadas,capacidad)} camas de capacidad cubiertas por la demanda y ${libres} libres; ${exceso} camas de exceso de demanda"></canvas>
        <div class="centro-dona"><strong>${numeroVisual(tasa)}<small>%</small></strong><span>de la capacidad</span></div>
      </div>
      <div class="cifras-dona">
        <div><i class="punto-ocupadas" aria-hidden="true"></i><span>${exceso?'Demanda':'Ocupadas'}<b>${numeroVisual(ocupadas,0)}</b></span></div>
        <div><i class="punto-libres" aria-hidden="true"></i><span>Libres<b>${numeroVisual(libres,0)}</b></span></div>
        <p>Capacidad supuesta: <b>${numeroVisual(capacidad,0)} camas</b></p>
        ${exceso?`<p class="exceso-dona">${numeroVisual(exceso,0)} camas de demanda por encima de la capacidad.</p>`:''}
      </div>
    </div>
    <small>${$('#dia').value==='0'?'Censo histórico reconstruido':'Ocupación esperada, redondeada para esta representación'}.</small>`;
  grafico('#gDonaCamas',{type:'doughnut',data:{labels:['Capacidad ocupada por la demanda','Libre'],datasets:[{
    data:[Math.min(ocupadas,capacidad),libres],backgroundColor:contexto=>contexto.dataIndex===0
      ? (tasa>90?degradadoGrafico('#df6d88','#bd3049'):degradadoGrafico('#26c8bb','#087f83'))(contexto) : '#dcebf0',
    borderWidth:0,borderRadius:5,spacing:3,hoverOffset:5
  }]},options:{responsive:true,maintainAspectRatio:false,cutout:'80%',plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>ctx.label+': '+numeroVisual(ctx.raw,0)+' camas'}}}}});
}


// Colores con significado constante: no se usan tortas para grupos que se superponen.
const COLORES_METODOS = {media_28d:'#c99727',semana_anterior:'#587bad',dia_semana_8sem:'#139d9a',estacional:'#9272c7',regresion:'#087f83'};
const COLORES_GRUPOS = ['#087f83','#458ac2','#8a6bbb','#21a69a','#c49a36','#697fc0','#2992ad','#6b9b79'];

function dibujarEstancias(datos) {
  const patologias = [...datos.patologias].sort((a,b) => b.alos_promedio-a.alos_promedio);
  const alosGeneral = Number(datos.alos_general_dias);
  if (!Number.isFinite(alosGeneral) || alosGeneral <= 0) throw new Error('ALOS general inválido.');
  const referenciaGeneral = {
    id:'referenciaGeneralEstancias',
    afterDatasetsDraw(chart) {
      const x = chart.scales.x.getPixelForValue(alosGeneral);
      if (x < chart.chartArea.left || x > chart.chartArea.right) return;
      const ctx = chart.ctx; ctx.save(); ctx.strokeStyle='#6950ad'; ctx.lineWidth=2;
      ctx.setLineDash([6,5]); ctx.beginPath(); ctx.moveTo(x,chart.chartArea.top);
      ctx.lineTo(x,chart.chartArea.bottom); ctx.stroke(); ctx.restore();
    }
  };
  $('#referenciaAlosGeneral').textContent = 'Línea violeta: promedio general de '+numeroVisual(alosGeneral,2)+' días.';
  grafico('#gPatologias', {type:'bar',plugins:[referenciaGeneral],data:{
    labels:patologias.map(p=>p.patologia),
    datasets:[{label:'Estancia promedio (días)',data:patologias.map(p=>p.alos_promedio),
      backgroundColor:degradadoGrafico('#36afa9','#448bc2'),borderRadius:7,maxBarThickness:24,borderSkipped:false}]
  },options:opc({indexAxis:'y',plugins:{legend:{display:false},tooltip:{callbacks:{
    afterLabel:contexto=>{
      const p=patologias[contexto.dataIndex];
      return ['Internaciones con la condición: '+numeroVisual(p.cantidad_internaciones,0),
        'Mediana: '+numeroVisual(p.mediana_dias)+' días',
        'Diagnóstico desconocido: '+(p.cantidad_sin_dato == null ? 'Sin dato' : numeroVisual(p.cantidad_sin_dato,0))];
    }
  }}},scales:{x:{beginAtZero:true,suggestedMax:Math.max(alosGeneral,...patologias.map(p=>p.alos_promedio))*1.2,title:{display:true,text:'Días de estancia promedio'}},y:{grid:{display:false}}}})});

  const total = Number(datos.total_internaciones);
  const edades = datos.grupos_etarios.map((g,i)=>({nombre:g.grupo_etario,cantidad:Number(g.cantidad_internaciones),color:COLORES_GRUPOS[i%COLORES_GRUPOS.length]}));
  if (!Number.isSafeInteger(total) || total <= 0 || edades.some(g=>!Number.isSafeInteger(g.cantidad)||g.cantidad<0)) {
    throw new Error('Las cantidades por edad no son válidas.');
  }
  const conocidos = edades.reduce((s,g)=>s+g.cantidad,0);
  const sinGrupo = datos.cantidad_sin_grupo_etario == null ? total-conocidos : Number(datos.cantidad_sin_grupo_etario);
  if (!Number.isSafeInteger(sinGrupo) || sinGrupo<0 || conocidos+sinGrupo!==total) {
    throw new Error('Las cantidades por edad no coinciden con el total de episodios.');
  }
  if (sinGrupo>0) edades.push({nombre:'Sin grupo etario',cantidad:sinGrupo,color:'#8796a6'});
  $('#totalDonaEdades').textContent = numeroVisual(total,0);
  const porcentaje = cantidad => (100*cantidad/total).toLocaleString('es-AR',{minimumFractionDigits:1,maximumFractionDigits:1});
  const leyenda = $('#leyendaDonaEdades'); leyenda.replaceChildren();
  edades.forEach(g=>{
    const fila=document.createElement('div');fila.className='estancias-fila-edad';
    const nombre=document.createElement('span');const color=document.createElement('span');
    color.className='estancias-color-edad';color.style.backgroundColor=g.color;color.setAttribute('aria-hidden','true');
    nombre.append(color,document.createTextNode(g.nombre));
    const valor=document.createElement('span');valor.textContent=numeroVisual(g.cantidad,0)+' · '+porcentaje(g.cantidad)+' %';
    fila.append(nombre,valor);leyenda.appendChild(fila);
  });
  $('#gEdades').setAttribute('aria-label','Distribución de '+numeroVisual(total,0)+' episodios por edad: '+edades.map(g=>g.nombre+', '+numeroVisual(g.cantidad,0)+' episodios, '+porcentaje(g.cantidad)+' por ciento').join('; '));
  grafico('#gEdades',{type:'doughnut',data:{labels:edades.map(g=>g.nombre),datasets:[{
    label:'Episodios',data:edades.map(g=>g.cantidad),backgroundColor:edades.map(g=>g.color),
    borderWidth:0,hoverOffset:6,spacing:1
  }]},options:opc({responsive:true,cutout:'72%',interaction:{mode:'nearest',intersect:true},plugins:{legend:{display:false},tooltip:{callbacks:{
    label:contexto=>numeroVisual(contexto.raw,0)+' episodios · '+porcentaje(contexto.raw)+' % del total'
  }}}})});
}

function dibujarComparacionMetodos(modelos) {
  const contenedor=$('#comparacionVisualMetodos');
  // Destruir gráficos anteriores antes de reemplazar sus canvas.
  Object.keys(charts).filter(id=>id.startsWith('#gMetodos-')).forEach(id=>{charts[id].destroy();delete charts[id];});
  contenedor.replaceChildren();
  modelos.forEach(modelo=>{
    const bloque=document.createElement('section');bloque.className='metodos-fuente';
    const titulo=document.createElement('h4');titulo.textContent=FUENTES_PANEL[modelo.dataset]||modelo.dataset;
    const descripcion=document.createElement('p');descripcion.className='nota';descripcion.textContent='Error relativo diario (WAPE). Menor es mejor. ✓ indica el método seleccionado en esta evaluación.';
    const marco=document.createElement('div');marco.className='grafico grafico-metodos grafico-vivo';
    const canvas=document.createElement('canvas');canvas.id='gMetodos-'+modelo.dataset;
    canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Error diario por método en '+titulo.textContent);
    marco.appendChild(canvas);bloque.append(titulo,descripcion,marco);contenedor.appendChild(bloque);
    const claves=Object.keys(NOMBRE).filter(k=>modelo.backtest.metricas[k]);
    grafico('#'+canvas.id,{type:'bar',data:{labels:claves.map(k=>NOMBRE[k]+(k===modelo.metodo_elegido?' ✓':'')),datasets:[{
      label:'WAPE diario (%)',data:claves.map(k=>modelo.backtest.metricas[k].wape_pct),
      backgroundColor:claves.map(k=>COLORES_METODOS[k]),borderColor:'#21334b',
      borderWidth:claves.map(k=>k===modelo.metodo_elegido?2:0),borderRadius:6,maxBarThickness:24
    }]},options:opc({indexAxis:'y',plugins:{legend:{display:false}},scales:{x:{beginAtZero:true,title:{display:true,text:'Error relativo diario (%)'}},y:{grid:{display:false}}}})});
  });
}

function dibujarDispersionIngresos(backtest) {
  const estimados=backtest[backtest.metodo_elegido]||[];
  const puntos=backtest.real.map((real,i)=>({x:real,y:estimados[i],fecha:backtest.fechas[i]}))
    .filter(p=>typeof p.x==='number' && Number.isFinite(p.x) && typeof p.y==='number' && Number.isFinite(p.y));
  if(!puntos.length)return;
  const maximo=Math.max(1,...puntos.flatMap(p=>[p.x,p.y]));
  grafico('#gDispersion',{type:'scatter',data:{datasets:[
    {label:NOMBRE[backtest.metodo_elegido],data:puntos,backgroundColor:'#139d9a99',borderColor:'#087f83',pointRadius:4,pointHoverRadius:6},
    {type:'line',label:'Coincidencia exacta (referencia)',data:[{x:0,y:0},{x:maximo,y:maximo}],borderColor:'#9272c7',borderDash:[5,5],borderWidth:2,pointRadius:0}
  ]},options:opc({plugins:{tooltip:{callbacks:{label:contexto=>contexto.datasetIndex===0
    ? contexto.raw.fecha+': '+numeroVisual(contexto.parsed.x)+' observados / '+numeroVisual(contexto.parsed.y)+' previstos'
    : 'Referencia: previsto = observado'}}},scales:{x:{min:0,max:maximo,title:{display:true,text:'Ingresos observados'}},y:{min:0,max:maximo,title:{display:true,text:'Ingresos previstos'}}}})});
}


// ---------------- Proyección ----------------
async function proyectar() {
  const consulta = ++consultaProyeccion;
  const dataset = $("#dataset").value, fecha = $("#fecha").value;
  const textoCapacidad = $("#capacidad").value.trim();
  const cap = textoCapacidad === "" ? null : Number(textoCapacidad);
  const dias = Number($("#horizonte").value) || 7;   // 7 (horizonte controlado), 15 o 30
  $("#cargandoTexto").textContent = dias > 7 ? `Calculando la proyección a ${dias} días…` : "Calculando la proyección…";
  $("#exportarExcel").disabled = true;
  $("#mensaje").textContent = dias > 7 ? `Calculando proyeccion a ${dias} dias (la primera vez puede tardar unos segundos)...` : "Calculando proyeccion...";
  proy = null; real = null;
  $("#resumenCamas").replaceChildren();
  $("#kpis").replaceChildren(); $("#camas").replaceChildren(); $("#tDias").replaceChildren();
  $("#dia").value = 0; $("#diaTxt").textContent = "Calculando...";
  if (charts["#gProy"]) { charts["#gProy"].destroy(); delete charts["#gProy"]; }
  if (charts["#gMovimientos"]) { charts["#gMovimientos"].destroy(); delete charts["#gMovimientos"]; }

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
  if (charts["#gMovimientos"]) { charts["#gMovimientos"].destroy(); delete charts["#gMovimientos"]; }
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
  actualizarDisponibilidadExportacion();
  dibujarCamas(+$("#dia").value);
  dibujarProyeccion();
  $("#tDias").innerHTML = `<thead><tr><th>Día</th><th>Ingresos</th><th>Altas (balance)</th><th>Ocupadas</th><th>Límite superior estimado (P90)</th>
    <th>Libres</th><th>Ocupación</th><th>Excedencia estimada</th><th>Real</th><th>Alerta</th></tr></thead><tbody>` +
    proy.proyeccion.map((d, i) => `<tr><td>${fmt(d.fecha)}</td><td>${d.ingresos_previstos}</td><td>${d.altas_previstas}</td>
      <td>${d.camas_ocupadas}</td><td>${d.camas_ocupadas_p90 ?? "–"}</td><td>${d.camas_libres}</td><td>${d.tasa_ocupacion_pct}%</td>
      <td>${d.prob_superar_umbral_pct ?? "–"}%</td><td>${real?.camas_ocupadas[i] ?? "–"}</td>
      <td class="${d.alerta_saturacion ? "si" : ""}">${d.alerta_saturacion ? "Saturación" : "–"}</td></tr>`).join("") + "</tbody>";
  sincronizarFechaVisible();
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
  dibujarDonaCamas(ocup, cap, libres, exceso, tasa);
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
  grafico('#gMovimientos',{type:'bar',data:{labels:proy.proyeccion.map(d=>fmt(d.fecha)),datasets:[
    {label:'Ingresos previstos',data:proy.proyeccion.map(d=>d.ingresos_previstos),backgroundColor:'#139d9a',borderRadius:6,maxBarThickness:28},
    {label:'Altas estimadas (balance)',data:proy.proyeccion.map(d=>d.altas_previstas),backgroundColor:'#587bad',borderRadius:6,maxBarThickness:28}
  ]},options:opc({scales:{y:{beginAtZero:true,title:{display:true,text:'Pacientes por día (estimación)'}},x:{grid:{display:false},ticks:{maxTicksLimit:10}}}})});

  const etiquetas = ["Censo", ...proy.proyeccion.map(d => fmt(d.fecha))];
  const series = [
    { label: "Esperada", data: [proy.tasa_ocupacion_hoy_pct, ...proy.proyeccion.map(d => d.tasa_ocupacion_pct)],
      borderColor: "#11888b", backgroundColor:"#139d9a14", fill:true, borderWidth: 3, tension: .25,
      pointBackgroundColor: ["#11888b", ...proy.proyeccion.map(d => d.alerta_saturacion ? "#bd3049" : "#11888b")], pointRadius: 5 },
    { label: "Límite superior estimado (P90)", data: [proy.tasa_ocupacion_hoy_pct, ...proy.proyeccion.map(d =>
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

  dibujarComparacionMetodos(modelos);
  let filas = "";
  modelos.forEach(r => Object.keys(NOMBRE).forEach((k, i) => {
    const x = r.backtest.metricas[k];
    filas += `<tr class="${k === r.metodo_elegido ? "elegido" : ""}">
      <td>${i === 0 ? `${r.dataset} <small>(${r.ingresos_promedio_dia}/día)</small>` : ""}</td>
      <td class="texto-izquierda">${NOMBRE[k]}${k === r.metodo_elegido ? " ✓" : ""}</td>
      <td>${x.mae}</td><td>${x.wape_pct}%</td><td>${x.wape_semanal_pct}%</td><td>${x.cobertura_80pct}%</td></tr>`;
  }));
  $("#tMetodos").innerHTML = `<thead><tr><th>Dataset</th><th class="texto-izquierda">Método</th><th>MAE</th>
    <th>WAPE diario</th><th>WAPE semanal</th><th>Cobertura IC 80 %</th></tr></thead><tbody>${filas}</tbody>`;

  
    if (fallos.length) {
      const aviso = document.createElement("caption");
      aviso.className = "error";
      aviso.classList.add("nota-tabla");
      aviso.textContent = "No se pudieron cargar: " + fallos.join(" | ");
      $("#tMetodos").appendChild(aviso);
    }
    
    })().catch(e => estadoTabla("#tMetodos", "Error en modelos: " + e.message, true)),
(async () => {
const b = await api("/modelo/backtest?dataset=hdhi");
  dibujarDispersionIngresos(b);
  grafico("#gBack", { type: "line", data: { labels: b.fechas.map(f => f.slice(5)), datasets: [
    { label: "Ingresos reales", data: b.real, borderColor: "#7b8ca3", borderWidth: 1, pointRadius: 0 },
    { label: `Pronóstico: ${NOMBRE[b.metodo_elegido]} (elegido)`, data: b[b.metodo_elegido], borderColor: "#11888b", borderWidth: 2, pointRadius: 0 },
    { label: "Referencia: media de 28 días", data: b.media_28d, borderColor: "#d6a21e", borderWidth: 2, borderDash: [4, 3], pointRadius: 0 },
  ]}, options: opc({ scales: { x: { ticks: { maxTicksLimit: 10 } }, y: { title: { display: true, text: "Ingresos por día" } } } }) });
  $("#notaBack").textContent = `HDHI, ${b.fechas[0]} a ${b.fechas.at(-1)}. El modelo sigue el patrón semanal; los picos diarios no siempre son anticipados por estos metodos.`;

  
    })().catch(e => {
      $("#notaBack").classList.add("error");
      $("#notaBack").textContent = "Error en backtesting: " + e.message;
    }),
(async () => {
const ev = await api("/modelo/evaluacion-agente?dataset=hdhi");
  grafico("#gHorizonte", { type: "bar", data: {
    labels: ev.error_por_dia.mae_camas.map((_, i) => `${i + 1} día${i ? "s" : ""}`),
    datasets: [
      { label: "Agente actual (modelo de ocupación)", data: ev.error_por_dia.mae_camas, backgroundColor: "#139d9a", borderRadius:5 },
      { label: "Agente anterior (duración de internaciones)", data: ev.comparacion_referencia.mae_agente_anterior_por_dia, backgroundColor: "#9272c7", borderRadius:5 },
      { label: "Referencia simple (ocupación igual a hoy)", data: ev.comparacion_referencia.mae_camas_por_dia, backgroundColor: "#6896c2", borderRadius:5 }
    ] }, options: opc({ scales: {
      x: { title: { display: true, text: "Días de anticipación" } },
      y: { title: { display: true, text: "Error promedio (camas)" } } } }) });
  const ref = ev.comparacion_referencia;
  const cob = ev.cobertura_limite_superior;
  $("#notaHorizonte").textContent = `Evaluación con ${ev.fechas_evaluadas} censos históricos. Error promedio: agente actual ${ref.mae_global_agente}, agente anterior ${ref.mae_global_agente_anterior} y referencia simple ${ref.mae_global_referencia} camas (incluye el período de desarrollo).`;
  if (ev.validacion_posterior) {
    const v = ev.validacion_posterior;
    $("#notaHorizonte").textContent += ` Validación posterior con corte temporal (${v.fechas} censos, ${v.primer_censo} a ${v.ultimo_censo}): agente actual ${v.mae_agente}, agente anterior ${v.mae_agente_anterior} y referencia simple ${v.mae_referencia} camas.`;
  }
  if (cob.empirico_pct != null) $("#notaHorizonte").textContent += ` Límite superior estimado (P90): cobertura observada de ${cob.empirico_pct} % en ${cob.pronosticos_comparables} casos; el nivel nominal es 90 %. No garantiza cobertura futura.`;

  const reglas = { ocupacion_esperada_mayor_90: "Ocupación esperada > 90 % (consigna)",
                   p90_mayor_90: "Límite superior estimado (P90) > 90 %", probabilidad_mayor_30: "Estimacion de excedencia ≥ 30 % (preventiva)" };
  $("#tReglas").innerHTML = `<thead><tr><th>Regla</th><th>Alertas</th><th>Aciertos</th><th>Precisión</th><th>Recall</th></tr></thead><tbody>` +
    Object.entries(ev.reglas_de_alerta).map(([k, v]) => `<tr><td>${reglas[k]}</td><td>${v.alertas}</td><td>${v.aciertos}</td>
      <td>${v.precision == null ? "No aplica" : Math.round(100 * v.precision) + "%"}</td><td>${v.recall == null ? "No aplica" : Math.round(100 * v.recall) + "%"}</td></tr>`).join("") +
    `</tbody><caption class="nota nota-tabla">Semanas que realmente superaron el 90 %: ${ev.semanas_que_realmente_superaron_el_umbral} de ${ev.fechas_evaluadas}.</caption>`;

      const aviso = document.createElement("caption");
      aviso.className = "nota";
      aviso.classList.add("nota-tabla");
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
    "Cambia la cantidad de camas; la fecha y la demanda prevista se mantienen.";

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
  sincronizarFechaVisible();
}


// ---------------- Inicio ----------------
async function iniciar() {
  try { datasets = await api("/datasets"); }
  catch (e) { $("#mensaje").innerHTML = `<span class="error">No se pudo conectar con la API. ¿Está corriendo uvicorn? (${e.message})</span>`; return; }
  $("#dataset").innerHTML = datasets.map(d => `<option value="${d.clave}">${FUENTES_PANEL[d.clave] || d.nombre}</option>`).join("");
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
    dibujarEstancias(r);
    estado.textContent = "Indicadores cargados. Fuente: HDHI revisado.";
    estadisticasCargadas = true;
  } catch(e) {
    $("#kpisEstadisticas").replaceChildren();
    $("#tablaPatologias").replaceChildren();
    $("#tablaEdades").replaceChildren();
    ["#gPatologias", "#gEdades"].forEach(id => { if(charts[id]) { charts[id].destroy(); delete charts[id]; } });
    ["#referenciaAlosGeneral", "#totalDonaEdades", "#leyendaDonaEdades"].forEach(id => $(id)?.replaceChildren());
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
    b.tabIndex = activa || (nombre === "administracion" && b.dataset.tab === "proyeccion") ? 0 : -1;
  });
  ["proyeccion", "estadisticas", "evaluacion", "sectores", "administracion"].forEach(id => {
    $("#vista-" + id).hidden = id !== nombre;
  });
  $("#tab-administracion").setAttribute("aria-pressed", String(nombre === "administracion"));
  $("#controlesProyeccion").hidden = nombre !== "proyeccion";
  if (nombre === "sectores" && !referenciaSectoresCargada) cargarReferenciasSectores();
  if (nombre === "estadisticas" && !estadisticasCargadas) cargarEstadisticasHDHI();
  if (nombre === "evaluacion" && !evaluacionCargada) cargarEvaluacionSolapa();
  if (nombre === "administracion") actualizarPanelAdministracion();
  actualizarTextoCarga();
  navegarDesdeMenu();
  // Chart.js recalcula dimensiones cuando su contenedor deja de estar oculto.
  requestAnimationFrame(() => Object.values(charts).forEach(c => c.resize()));
}

$("#tab-administracion").addEventListener("click", () => {
  if (!$("#tab-administracion").hidden) seleccionarSolapa("administracion");
});

const botonesSolapa = [...document.querySelectorAll("#solapas-principales [role=tab]")];
botonesSolapa.forEach((b, i) => {
  b.addEventListener("click", () => seleccionarSolapa(b.dataset.tab));
  b.addEventListener("keydown", e => {
    const visibles = botonesSolapa.filter(boton => !boton.hidden && !boton.disabled);
    const n = visibles.length;
    let destino = visibles.indexOf(b);
    if (e.key === "ArrowDown" || e.key === "ArrowRight") destino = (destino + 1) % n;
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft") destino = (destino + n - 1) % n;
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
// Navegación lateral. No realiza consultas ni cambia cálculos del agente.
const pantallaMenuMovil = window.matchMedia('(max-width: 900px)');
let menuLateralAbierto = !pantallaMenuMovil.matches;

function establecerMenuLateral(abierto, enfocar = false) {
  menuLateralAbierto = abierto;
  const barra = $('#barraLateral');
  const boton = $('#alternarLateral');
  const movilAbierto = pantallaMenuMovil.matches && abierto;
  document.body.classList.toggle('lateral-cerrado', !abierto);
  document.body.classList.toggle('menu-movil-abierto', movilAbierto);
  barra.inert = !abierto;
  barra.setAttribute('aria-hidden', String(!abierto));
  barra.setAttribute('role', pantallaMenuMovil.matches ? 'dialog' : 'complementary');
  if (movilAbierto) barra.setAttribute('aria-modal', 'true');
  else barra.removeAttribute('aria-modal');
  $('#contenidoAplicacion').inert = movilAbierto;
  $('#fondoLateral').hidden = !movilAbierto;
  boton.setAttribute('aria-expanded', String(abierto));
  boton.setAttribute('aria-label', abierto ? 'Ocultar menú lateral' : 'Mostrar menú lateral');
  boton.title = abierto ? 'Ocultar menú' : 'Mostrar menú';
  boton.textContent = abierto ? '‹' : '☰';
  if (enfocar) {
    const activo = barra.querySelector('[role="tab"][aria-selected="true"], #tab-administracion[aria-pressed="true"]');
    if (abierto && pantallaMenuMovil.matches) activo?.focus();
    else boton.focus();
  }
  requestAnimationFrame(() => Object.values(charts).forEach(grafico => grafico.resize()));
}

function navegarDesdeMenu() {
  if (pantallaMenuMovil.matches && menuLateralAbierto) {
    establecerMenuLateral(false);
    const vista = document.querySelector('.tab-panel:not([hidden])');
    if (vista) {
      vista.setAttribute('tabindex', '-1');
      vista.focus({preventScroll:true});
    }
  }
  window.scrollTo({top:0, behavior:'auto'});
}

function inicializarMenuLateral() {
  $('#alternarLateral').addEventListener('click', () => establecerMenuLateral(!menuLateralAbierto, true));
  $('#fondoLateral').addEventListener('click', () => establecerMenuLateral(false, true));
  pantallaMenuMovil.addEventListener('change', () => establecerMenuLateral(!pantallaMenuMovil.matches));
  document.addEventListener('keydown', evento => {
    if (!menuLateralAbierto || document.querySelector('dialog[open]')) return;
    if (evento.key === 'Escape') {
      evento.preventDefault();
      establecerMenuLateral(false, true);
      return;
    }
    // Mantener el foco en el menú mientras cubre la pantalla del celular.
    if (evento.key !== 'Tab' || !pantallaMenuMovil.matches) return;
    const candidatos = [...$('#barraLateral').querySelectorAll('button,select,input,[tabindex]'), $('#alternarLateral')]
      .filter(elemento => !elemento.disabled && elemento.tabIndex >= 0 && elemento.getClientRects().length);
    const primero = candidatos[0], ultimo = candidatos[candidatos.length - 1];
    if (evento.shiftKey && document.activeElement === primero) {
      evento.preventDefault(); ultimo.focus();
    } else if (!evento.shiftKey && document.activeElement === ultimo) {
      evento.preventDefault(); primero.focus();
    }
  });
  establecerMenuLateral(menuLateralAbierto);
}


// Validaciones de interfaz de Darío, unificadas sin eventos duplicados.
// La API mantiene sus propias validaciones de seguridad y de dominio.
function inicializarValidacionNumerica() {
  const esEntero = campo => {
    const paso = campo.getAttribute('step');
    return paso !== 'any' && (paso === null || Number.isInteger(Number(paso)));
  };
  function validar(campo) {
    campo.setCustomValidity('');
    const estado = campo.validity;
    let mensaje = '';
    if (estado.valueMissing) mensaje = 'Completá este campo.';
    else if (estado.badInput) mensaje = 'Ingresá solo números.';
    else if (estado.rangeUnderflow) mensaje = `El valor mínimo es ${campo.min}.`;
    else if (estado.rangeOverflow) mensaje = `El valor máximo es ${campo.max}.`;
    else if (estado.stepMismatch) mensaje = esEntero(campo)
      ? 'Ingresá un número entero, sin decimales.'
      : `Respetá el incremento permitido: ${campo.step}.`;
    campo.setCustomValidity(mensaje);
    return mensaje === '';
  }
  document.querySelectorAll('input[type="number"]').forEach(campo => {
    campo.addEventListener('keydown', evento => {
      if (evento.ctrlKey || evento.metaKey || evento.altKey) return;
      if (['e','E','+','-'].includes(evento.key) ||
          (esEntero(campo) && ['.',','].includes(evento.key))) evento.preventDefault();
    });
    campo.addEventListener('paste', evento => {
      const texto = evento.clipboardData?.getData('text').trim();
      if (texto == null) return;
      evento.preventDefault();
      const formato = esEntero(campo) ? /^\d+$/ : /^\d+(?:[.,]\d+)?$/;
      if (!formato.test(texto)) {
        campo.setCustomValidity(esEntero(campo) ? 'Pegá un número entero, sin letras ni signos.' : 'Pegá un número válido, sin letras.');
        campo.reportValidity();
        return;
      }
      campo.value = texto.replace(',', '.');
      campo.dispatchEvent(new Event('input', {bubbles:true}));
    });
    campo.addEventListener('input', () => {
      validar(campo);
      // Conservar el cero inválido para que no se interprete como un campo vacío
      // y se use por accidente la capacidad predeterminada.
      if (campo.value !== '' && Number(campo.min) >= 1 && campo.validity.rangeUnderflow) {
        campo.reportValidity();
      }
    });
    campo.addEventListener('invalid', () => validar(campo));
    campo.addEventListener('change', evento => {
      validar(campo);
      if (!campo.checkValidity()) {
        evento.stopImmediatePropagation();
        campo.reportValidity();
      }
    }, true);
  });
}

inicializarValidacionNumerica();
inicializarMenuLateral();
verificarAcceso().then(permitido=>{if(permitido)iniciar();});

// Etiquetas de presentación: las claves internas y los CSV no cambian.
const FUENTES_PANEL={hdhi:'Admisiones hospitalarias · HDHI',lengthofstay:'Estancias hospitalarias · Microsoft',healthcare:'Atención hospitalaria · datos sintéticos'};
function numeroVisual(valor,decimales=1){return Number(valor).toLocaleString('es-AR',{maximumFractionDigits:decimales});}
function sincronizarFechaVisible(){
  const entrada=$('#fecha');let boton=$('#abrirFecha');
  if(!boton){
    boton=document.createElement('button');boton.type='button';boton.id='abrirFecha';boton.className='fecha-compacta';
    boton.setAttribute('aria-haspopup','dialog');boton.setAttribute('aria-controls','calendarioCenso');
    entrada.after(boton);entrada.classList.add('fecha-original');entrada.tabIndex=-1;
    boton.addEventListener('click',abrirCalendarioCenso);entrada.addEventListener('change',sincronizarFechaVisible);
    document.querySelector('.campo-fecha-censo>label').htmlFor='abrirFecha';
  }
  boton.replaceChildren();const texto=document.createElement('span');texto.textContent=entrada.value?fmtLargo(entrada.value):'Elegir fecha';
  const icono=document.createElement('span');icono.className='icono-fecha-compacta';icono.setAttribute('aria-hidden','true');
  icono.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v5m10-5v5M3 11h18m-13 4h2m4 0h2m-8 3h2"/></svg>';
  boton.append(texto,icono);boton.setAttribute('aria-label','Fecha del censo: '+texto.textContent+'. Abrir calendario');
  boton.title=entrada.title;
}

// El calendario muestra únicamente la proyección vigente; no genera pronósticos nuevos.
function abrirCalendarioCenso(){
  const entrada=$('#fecha'),min=entrada.min,max=entrada.max;
  if(!min||!max)return;
  const vigente=proy && proy.dataset===$('#dataset').value && proy.fecha_censo===entrada.value &&
    (!$('#capacidad').value.trim() || proy.capacidad===Number($('#capacidad').value));
  const resultados=vigente?new Map(proy.proyeccion.map(d=>[d.fecha,d])):new Map();
  const ultimoPronostico=vigente?proy.proyeccion.at(-1)?.fecha:null;
  const finVisible=ultimoPronostico && ultimoPronostico>max?ultimoPronostico:max;
  $('#calendarioCenso')?.remove();
  const dialogo=document.createElement('dialog');dialogo.id='calendarioCenso';dialogo.className='calendario-censo';
  dialogo.setAttribute('aria-labelledby','tituloCalendarioCenso');
  dialogo.innerHTML=`<div class="calendario-cabecera"><div><span></span><h2 id="tituloCalendarioCenso">Censo y demanda prevista</h2></div><button type="button" class="cerrar-calendario" aria-label="Cerrar calendario">×</button></div><p class="calendario-contexto"></p><div class="vistazo-resumen" role="status"></div><div class="calendario-navegacion"><button type="button" class="mes-previo" aria-label="Mes anterior">‹</button><label>Mes<select class="mes-calendario"></select></label><label>Año<select class="anio-calendario"></select></label><button type="button" class="mes-siguiente" aria-label="Mes siguiente">›</button></div><div class="semana-calendario" aria-hidden="true"><span>Lu</span><span>Ma</span><span>Mi</span><span>Ju</span><span>Vi</span><span>Sá</span><span>Do</span></div><div class="dias-calendario" role="group" aria-label="Fechas del censo y ocupación prevista"></div><div class="vistazo-leyenda"><span><i class="clave-censo"></i>Censo elegido</span><span><i class="clave-pronostico"></i>Con pronóstico</span><span><i class="clave-alerta"></i>Saturación prevista</span></div><p class="calendario-rango"></p><p class="calendario-ayuda">Los datos dentro de los días son estimaciones de la proyección vigente. Las fechas sin pronóstico no tienen cifras. Al elegir otra fecha habilitada se calcula un nuevo censo histórico.</p>`;
  document.body.append(dialogo);
  dialogo.querySelector('.calendario-contexto').textContent=FUENTES_PANEL[$('#dataset').value] || 'Fuente seleccionada';
  const resumen=dialogo.querySelector('.vistazo-resumen');
  if(vigente && proy.proyeccion.length){
    const dias=proy.proyeccion,alertas=dias.filter(d=>d.alerta_saturacion).length;
    resumen.textContent=`${fmtLargo(dias[0].fecha)} al ${fmtLargo(dias.at(-1).fecha)} · ${proy.capacidad} camas supuestas · ${alertas} de ${dias.length} días con saturación prevista`;
  } else resumen.textContent='Sin proyección vigente. Elegí una fecha habilitada y esperá el cálculo para ver la ocupación prevista.';
  dialogo.querySelector('.calendario-rango').textContent=`Podés elegir censos del ${fmtLargo(min)} al ${fmtLargo(max)}.`;
  const [a0,m0]=min.split('-').map(Number),[a1,m1]=finVisible.split('-').map(Number);
  const inicial=entrada.value>=min&&entrada.value<=max?entrada.value:min;
  let [anio,mes]=inicial.split('-').map(Number);mes--;
  const selMes=dialogo.querySelector('.mes-calendario'),selAnio=dialogo.querySelector('.anio-calendario');
  for(let a=a0;a<=a1;a++){const o=document.createElement('option');o.value=a;o.textContent=a;selAnio.append(o);}
  const iso=d=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  function dibujar(){
    selAnio.value=anio;selMes.replaceChildren();
    for(let m=0;m<12;m++){
      const o=document.createElement('option');o.value=m;o.textContent=new Date(anio,m,1).toLocaleDateString('es-AR',{month:'long'});
      o.disabled=(anio===a0&&m<m0-1)||(anio===a1&&m>m1-1);selMes.append(o);
    }
    selMes.value=mes;
    dialogo.querySelector('.mes-previo').disabled=anio*12+mes<=a0*12+m0-1;
    dialogo.querySelector('.mes-siguiente').disabled=anio*12+mes>=a1*12+m1-1;
    const contenedor=dialogo.querySelector('.dias-calendario');contenedor.replaceChildren();
    const primero=new Date(anio,mes,1),offset=(primero.getDay()+6)%7,total=new Date(anio,mes+1,0).getDate();
    const comienzo=new Date(anio,mes,1-offset);
    let cantidad=Math.ceil((offset+total)/7)*7;
    // Si la semana cruza de mes, se incluyen sus días para verla completa al abrir.
    if(ultimoPronostico && inicial.slice(0,7)===iso(primero).slice(0,7)){
      const fin=new Date(ultimoPronostico+'T12:00:00');
      const distancia=Math.round((Date.UTC(fin.getFullYear(),fin.getMonth(),fin.getDate())-Date.UTC(comienzo.getFullYear(),comienzo.getMonth(),comienzo.getDate()))/86400000);
      cantidad=Math.max(cantidad,Math.ceil((distancia+1)/7)*7);
    }
    for(let i=0;i<cantidad;i++){
      const fechaDate=new Date(comienzo);fechaDate.setDate(comienzo.getDate()+i);
      const fecha=iso(fechaDate),dato=resultados.get(fecha),esCenso=fecha===entrada.value;
      const b=document.createElement('button');b.type='button';b.dataset.fecha=fecha;
      b.disabled=fecha<min||fecha>max;b.className='dia-vistazo';
      if(fechaDate.getMonth()!==mes)b.classList.add('otro-mes');
      if(esCenso)b.classList.add('dia-censo');
      if(dato)b.classList.add(dato.alerta_saturacion?'dia-alerta':'dia-pronostico');
      b.setAttribute('aria-pressed',String(esCenso));
      const titulo=fechaDate.toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
      const numero=document.createElement('span');numero.className='numero-dia-vistazo';numero.textContent=fechaDate.getMonth()===mes?fechaDate.getDate():fechaDate.getDate()+' '+fechaDate.toLocaleDateString('es-AR',{month:'short'});b.append(numero);
      if(esCenso){const marca=document.createElement('small');marca.className='marca-censo';marca.textContent='Censo';b.append(marca);}
      if(dato){
        const porcentaje=document.createElement('b');porcentaje.className='ocupacion-dia-vistazo';porcentaje.textContent=numeroVisual(dato.tasa_ocupacion_pct)+' %';
        const libres=document.createElement('small');libres.textContent=numeroVisual(dato.camas_libres)+' libres';
        const estado=document.createElement('small');estado.className='estado-dia-vistazo';estado.textContent=dato.alerta_saturacion?'⚠ Saturación':'Sin saturación';
        b.append(porcentaje,libres,estado);
        b.setAttribute('aria-label',`${titulo}. Ocupación prevista ${numeroVisual(dato.tasa_ocupacion_pct)} por ciento. ${numeroVisual(dato.camas_libres)} camas libres estimadas. ${dato.alerta_saturacion?'Saturación prevista.':'Sin saturación prevista.'}${b.disabled?' Solo pronóstico; fuera del período habilitado para censos.':' Elegir como nuevo censo.'}`);
      }else b.setAttribute('aria-label',titulo+(esCenso?'. Censo elegido.':'. Sin pronóstico para este día.'));
      if(!b.disabled)b.addEventListener('click',()=>{if(esCenso){dialogo.close();return;}entrada.value=fecha;sincronizarFechaVisible();dialogo.close();entrada.dispatchEvent(new Event('change',{bubbles:true}));});
      b.title=b.getAttribute('aria-label');contenedor.append(b);
    }
  }
  const limitarMes=()=>{mes=Math.max(anio===a0?m0-1:0,Math.min(anio===a1?m1-1:11,mes));};
  selMes.addEventListener('change',()=>{mes=Number(selMes.value);dibujar();});
  selAnio.addEventListener('change',()=>{anio=Number(selAnio.value);limitarMes();dibujar();});
  for(const [clase,delta] of [['mes-previo',-1],['mes-siguiente',1]])dialogo.querySelector('.'+clase).addEventListener('click',()=>{const f=new Date(anio,mes+delta,1);anio=f.getFullYear();mes=f.getMonth();dibujar();});
  dialogo.querySelector('.cerrar-calendario').addEventListener('click',()=>dialogo.close());
  dialogo.addEventListener('close',()=>$('#abrirFecha').focus());
  contenedorTeclas();
  function contenedorTeclas(){dialogo.querySelector('.dias-calendario').addEventListener('keydown',e=>{
    if(!e.target.dataset.fecha)return;
    const salto={ArrowRight:1,ArrowLeft:-1,ArrowDown:7,ArrowUp:-7}[e.key];if(salto==null)return;e.preventDefault();
    const f=new Date(e.target.dataset.fecha+'T12:00:00');f.setDate(f.getDate()+salto);const fecha=iso(f);
    if(fecha<min||fecha>max)return;anio=f.getFullYear();mes=f.getMonth();dibujar();dialogo.querySelector(`[data-fecha="${fecha}"]`)?.focus();
  });}
  dibujar();dialogo.showModal();
  (dialogo.querySelector('[aria-pressed="true"]:not(:disabled)')||dialogo.querySelector('.dias-calendario button:not(:disabled)'))?.focus();
}


// ------------------------------------------------------------------
// Exportar a Excel lo que se ve en pantalla (SheetJS, incluido en /vendor:
// funciona sin internet). Respeta dataset, fecha, capacidad y horizonte elegidos.
// ------------------------------------------------------------------
function exportarExcel() {
  actualizarDisponibilidadExportacion();
  if ($('#exportarExcel').disabled) return;
  const nombreDataset = $("#dataset").selectedOptions[0]?.textContent || proy.dataset;
  const dias = proy.proyeccion.length;
  const resumen = [
    ["Agente de Gestión de Camas · Grupo 1"],
    [],
    ["Fuente de datos", nombreDataset],
    ["Fecha del censo", fmtLargo(proy.fecha_censo)],
    ["Capacidad (camas)", proy.capacidad],
    ["Horizonte proyectado (días)", dias],
    ["Camas ocupadas al censo", proy.camas_ocupadas_hoy],
    ["Ocupación al censo (%)", proy.tasa_ocupacion_hoy_pct],
    ["Ocupación proyectada máxima (%)", proy.tasa_ocupacion_maxima_pct],
    ["Día de mayor ocupación", proy.dia_pico],
    ["Alerta de Saturación", proy.alerta_saturacion ? "Sí" : "No"],
    ["Alerta preventiva", proy.alerta_preventiva ? "Sí" : "No"],
    ["Mensaje del agente", proy.mensaje],
    [],
    ["Exportado el", new Date().toLocaleString("es-AR")],
  ];
  const encabezados = ["Fecha", "Ingresos previstos", "Altas estimadas", "Camas ocupadas", "Límite superior estimado (P90)",
                       "Camas libres", "Ocupación (%)", "Excedencia estimada (%)", "Ocupación real (camas)", "Alerta de Saturación"];
  const filas = proy.proyeccion.map((d, i) => [
    d.fecha, d.ingresos_previstos, d.altas_previstas, d.camas_ocupadas, d.camas_ocupadas_p90 ?? "",
    d.camas_libres, d.tasa_ocupacion_pct, d.prob_superar_umbral_pct ?? "", real?.camas_ocupadas?.[i] ?? "",
    d.alerta_saturacion ? "Sí" : "No"]);
  const libro = XLSX.utils.book_new();
  const hojaResumen = XLSX.utils.aoa_to_sheet(resumen);
  hojaResumen["!cols"] = [{ wch: 32 }, { wch: 70 }];
  const hojaDias = XLSX.utils.aoa_to_sheet([encabezados, ...filas]);
  hojaDias["!cols"] = encabezados.map(t => ({ wch: Math.max(12, t.length + 2) }));
  XLSX.utils.book_append_sheet(libro, hojaResumen, "Resumen");
  XLSX.utils.book_append_sheet(libro, hojaDias, `Proyección ${dias} días`);
  XLSX.writeFile(libro, `proyeccion_${proy.dataset}_${proy.fecha_censo}_${dias}dias.xlsx`);
}
function actualizarDisponibilidadExportacion() {
  const disponible = typeof XLSX !== 'undefined';
  const vigente = proy && proy.dataset === $('#dataset').value && proy.fecha_censo === $('#fecha').value
    && proy.capacidad === Number($('#capacidad').value)
    && proy.proyeccion.length === Number($('#horizonte').value);
  $('#exportarExcel').disabled = !disponible || !vigente;
  $('#estadoExportacion').textContent = !disponible
    ? 'No se cargó la biblioteca de Excel. Revisá /vendor/xlsx.mini.min.js.'
    : proy && !vigente ? 'Calculá la proyección para los controles elegidos antes de exportar.' : '';
}
$('#exportarExcel').addEventListener('click', () => {
  try { exportarExcel(); }
  catch (error) { $('#estadoExportacion').textContent = 'No se pudo generar el Excel: ' + error.message; }
});
['dataset','fecha','capacidad','horizonte'].forEach(id => {
  $('#'+id).addEventListener('input', actualizarDisponibilidadExportacion);
});
actualizarDisponibilidadExportacion();
