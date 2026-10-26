/* Administración de cuentas: se conecta a FastAPI; los permisos se controlan también en el servidor. */
let usuariosAdmin = [];
let usuarioAdminActual = null;
let editandoUsuarioAdmin = null;
let consultaUsuariosAdmin = 0;
let operacionAdmin = false;
const elementoAdmin = id => document.getElementById(id);
const nombreRolAdmin = rol => rol === 'administrador' ? 'Administrador' : 'Usuario común';
const textoBusquedaAdmin = valor => String(valor || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

async function apiAdministracion(ruta, metodo = 'GET', cuerpo) {
  const respuesta = await fetch(ruta, {
    method: metodo, credentials: 'same-origin',
    headers: { 'X-Requested-With': 'AgenteCamas', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    ...(cuerpo ? { body: JSON.stringify(cuerpo) } : {})
  });
  const datos = await respuesta.json().catch(() => ({}));
  if (!respuesta.ok) {
    const error = new Error(typeof datos.detail === 'string' ? datos.detail : 'No se pudo completar la operación. Revisá los campos.');
    error.status = respuesta.status;
    throw error;
  }
  return datos;
}

function iconoAdministracion(nombre) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('class','admin-icon'); svg.setAttribute('viewBox','0 0 24 24');
  svg.setAttribute('aria-hidden','true'); svg.setAttribute('focusable','false');
  const use = document.createElementNS('http://www.w3.org/2000/svg','use');
  use.setAttribute('href','#admin-icon-'+nombre); svg.appendChild(use); return svg;
}

function mensajeAdmin(id, texto, error = false) {
  const e = elementoAdmin(id);
  e.textContent = texto;
  e.className = error ? 'error' : 'nota';
}

async function actualizarPanelAdministracion() {
  if (!elementoAdmin('listaUsuarios')) return;
  const consulta = ++consultaUsuariosAdmin;
  mensajeAdmin('mensajeAdministracion', 'Cargando usuarios…');
  try {
    const datos = await apiAdministracion('/auth/admin/usuarios');
    if (consulta !== consultaUsuariosAdmin) return;
    usuariosAdmin = datos.usuarios;
    usuarioAdminActual = datos.usuario_actual;
    elementoAdmin('tab-administracion').hidden = false;
    const activos = usuariosAdmin.filter(u => u.activo).length;
    elementoAdmin('adminTotal').textContent = usuariosAdmin.length;
    elementoAdmin('adminActivos').textContent = activos;
    elementoAdmin('adminInactivos').textContent = usuariosAdmin.length - activos;
    dibujarUsuariosAdmin();
  } catch (error) {
    if (consulta !== consultaUsuariosAdmin) return;
    usuariosAdmin = [];
    elementoAdmin('listaUsuarios').replaceChildren();
    ['adminTotal','adminActivos','adminInactivos'].forEach(id => elementoAdmin(id).textContent = '—');
    mensajeAdmin('mensajeAdministracion', error.message, true);
    if ([401,403].includes(error.status)) {
      elementoAdmin('tab-administracion').hidden = true;
      if (elementoAdmin('dialogoUsuario').open) elementoAdmin('dialogoUsuario').close();
      if (!elementoAdmin('vista-administracion').hidden && typeof seleccionarSolapa === 'function') seleccionarSolapa('proyeccion');
    }
  }
}

function dibujarUsuariosAdmin() {
  const buscar = textoBusquedaAdmin(elementoAdmin('buscarUsuarios').value);
  const rol = elementoAdmin('filtrarRol').value;
  const estado = elementoAdmin('filtrarEstado').value;
  const filtrados = usuariosAdmin.filter(u =>
    textoBusquedaAdmin([u.nombre_completo,u.usuario,u.correo].join(' ')).includes(buscar)
    && (!rol || u.rol === rol)
    && (!estado || (estado === 'activo') === u.activo));
  const tabla = document.createElement('table');
  tabla.className = 'admin-tabla';
  const thead = tabla.createTHead();
  const titulos = thead.insertRow();
  ['Nombre completo','Usuario','Correo','Rol','Estado','Acciones'].forEach(t => {
    const th = document.createElement('th'); th.scope = 'col'; th.textContent = t; titulos.appendChild(th);
  });
  const tbody = tabla.createTBody();
  filtrados.forEach(u => {
    const fila = tbody.insertRow();
    const perfil = document.createElement('div'); perfil.className='admin-perfil';
    const avatar = document.createElement('span'); avatar.className='admin-avatar'; avatar.setAttribute('aria-hidden','true');
    avatar.textContent=(u.nombre_completo || u.usuario).trim().split(/\s+/).slice(0,2).map(p=>p[0]).join('').toUpperCase();
    const nombre = document.createElement('span'); nombre.textContent=u.nombre_completo || 'Nombre pendiente';
    perfil.append(avatar,nombre); fila.insertCell().appendChild(perfil);
    const identificador=document.createElement('span'); identificador.className='admin-identificador'; identificador.textContent=u.usuario;
    fila.insertCell().appendChild(identificador);
    fila.insertCell().textContent=u.correo || 'Sin correo';
    const rol=document.createElement('span'); rol.className='admin-rol '+(u.rol==='administrador'?'administrador':'usuario'); rol.textContent=nombreRolAdmin(u.rol);
    fila.insertCell().appendChild(rol);
    const estado = document.createElement('span'); estado.className = 'admin-estado' + (u.activo ? '' : ' inactivo');
    estado.textContent = u.activo ? 'Activo' : 'Inactivo'; fila.insertCell().appendChild(estado);
    const acciones = document.createElement('div'); acciones.className = 'admin-acciones';
    const editar = document.createElement('button'); editar.type = 'button'; editar.className = 'admin-boton'; editar.textContent = 'Editar'; editar.prepend(iconoAdministracion('editar'));
    editar.addEventListener('click', () => abrirFormularioUsuarioAdmin(u));
    const cambiar = document.createElement('button'); cambiar.type = 'button'; cambiar.className = 'admin-boton' + (u.activo ? ' desactivar' : '');
    cambiar.textContent = u.activo ? 'Desactivar' : 'Reactivar'; cambiar.prepend(iconoAdministracion(u.activo ? 'pausa' : 'reactivar'));
    cambiar.disabled = operacionAdmin || u.usuario === usuarioAdminActual;
    editar.disabled = operacionAdmin;
    cambiar.title = u.usuario === usuarioAdminActual ? 'No podés desactivar tu propia cuenta.' : 'Cambiar el acceso de ' + u.usuario;
    cambiar.addEventListener('click', () => cambiarEstadoUsuarioAdmin(u));
    acciones.append(editar,cambiar); fila.insertCell().appendChild(acciones);
  });
  elementoAdmin('listaUsuarios').replaceChildren(tabla);
  mensajeAdmin('mensajeAdministracion', `${filtrados.length} de ${usuariosAdmin.length} cuentas. ${filtrados.length ? '' : 'No hay coincidencias con estos filtros.'}`);
}

function restaurarBotonesAdmin() {
  const mensaje = elementoAdmin("mensajeAdministracion");
  const texto = mensaje.textContent, clase = mensaje.className;
  dibujarUsuariosAdmin();
  mensaje.textContent = texto; mensaje.className = clase;
}

function abrirFormularioUsuarioAdmin(usuario = null) {
  if (operacionAdmin) return;
  editandoUsuarioAdmin = usuario;
  elementoAdmin('formUsuarioAdmin').reset();
  elementoAdmin('tituloUsuarioAdmin').textContent = usuario ? 'Editar usuario' : 'Nuevo usuario';
  elementoAdmin('adminNombre').value = usuario?.nombre_completo || '';
  elementoAdmin('adminUsuario').value = usuario?.usuario || '';
  elementoAdmin('adminCorreo').value = usuario?.correo || '';
  elementoAdmin('adminRol').value = usuario?.rol || 'usuario';
  elementoAdmin('adminUsuario').disabled = Boolean(usuario);
  elementoAdmin('adminRol').disabled = usuario?.usuario === usuarioAdminActual;
  elementoAdmin('campoClaveAdmin').hidden = Boolean(usuario);
  elementoAdmin('adminClave').disabled = Boolean(usuario);
  elementoAdmin('adminClave').required = !usuario;
  mensajeAdmin('mensajeFormAdmin', '');
  elementoAdmin('dialogoUsuario').showModal();
  elementoAdmin('adminNombre').focus();
}

async function guardarUsuarioAdmin(event) {
  event.preventDefault();
  if (operacionAdmin || !elementoAdmin('formUsuarioAdmin').reportValidity()) return;
  const datos = { nombre_completo: elementoAdmin('adminNombre').value.trim(), correo: elementoAdmin('adminCorreo').value.trim(), rol: elementoAdmin('adminRol').value };
  const usuario = editandoUsuarioAdmin;
  if (!usuario) { datos.usuario = elementoAdmin('adminUsuario').value.trim(); datos.clave = elementoAdmin('adminClave').value; }
  operacionAdmin = true;
  elementoAdmin('guardarUsuarioAdmin').disabled = true;
  elementoAdmin('cancelarUsuarioAdmin').disabled = true;
  mensajeAdmin('mensajeFormAdmin','Guardando…');
  try {
    const r = await apiAdministracion(usuario ? '/auth/admin/usuarios/' + encodeURIComponent(usuario.usuario) : '/auth/admin/usuarios', usuario ? 'PATCH' : 'POST', datos);
    elementoAdmin('adminClave').value = '';
    elementoAdmin('dialogoUsuario').close();
    await actualizarPanelAdministracion();
    mensajeAdmin('mensajeAdministracion', r.mensaje);
    if (elementoAdmin('detalleAuditoria').open) await cargarAuditoriaAdmin();
  } catch (error) { mensajeAdmin('mensajeFormAdmin', error.message, true); }
  finally { operacionAdmin = false; elementoAdmin('guardarUsuarioAdmin').disabled = false; elementoAdmin('cancelarUsuarioAdmin').disabled = false; restaurarBotonesAdmin(); }
}

async function cambiarEstadoUsuarioAdmin(usuario) {
  if (operacionAdmin) return;
  const accion = usuario.activo ? 'desactivar' : 'reactivar';
  if (!window.confirm(`¿Querés ${accion} la cuenta ${usuario.usuario}?${usuario.activo ? ' Sus sesiones se cerrarán.' : ' Tendrá que iniciar sesión nuevamente.'}`)) return;
  operacionAdmin = true; dibujarUsuariosAdmin();
  try {
    const r = await apiAdministracion('/auth/admin/usuarios/' + encodeURIComponent(usuario.usuario) + '/estado', 'PATCH', { activo: !usuario.activo });
    await actualizarPanelAdministracion(); mensajeAdmin('mensajeAdministracion',r.mensaje);
    if (elementoAdmin('detalleAuditoria').open) await cargarAuditoriaAdmin();
  } catch (error) { mensajeAdmin('mensajeAdministracion',error.message,true); }
  finally { operacionAdmin = false; restaurarBotonesAdmin(); }
}

// Presentación legible: los eventos originales de la API no se modifican.
function textoValorAuditoria(valor, campo) {
  if (valor === null || valor === undefined || valor === '') return 'Sin registrar';
  if (campo === 'activo' && typeof valor === 'boolean') return valor ? 'Activo' : 'Inactivo';
  if (campo === 'rol') return nombreRolAdmin(valor);
  if (Array.isArray(valor)) return valor.map(v => textoValorAuditoria(v, campo)).join(', ');
  if (typeof valor === 'object') return Object.entries(valor).map(([k,v]) => `${k}: ${textoValorAuditoria(v,k)}`).join('; ');
  return String(valor);
}

function dibujarCambiosAuditoria(celda, cambios) {
  const nombres = { nombre_completo:'Nombre completo', correo:'Correo electrónico', rol:'Rol', activo:'Estado', usuario:'Usuario' };
  let datos = cambios;
  if (typeof datos === 'string') {
    try { datos = JSON.parse(datos); } catch { celda.textContent = datos; return; }
  }
  if (!datos || typeof datos !== 'object' || !Object.keys(datos).length) {
    celda.textContent = 'Sin detalles registrados'; return;
  }
  const lista = document.createElement('ul'); lista.className = 'admin-cambios';
  Object.entries(datos).forEach(([campo, valor]) => {
    const item = document.createElement('li');
    const etiqueta = document.createElement('strong'); etiqueta.textContent = (nombres[campo] || campo.replaceAll('_', ' ')) + ': ';
    item.appendChild(etiqueta);
    const esCambio = valor && typeof valor === 'object' && ('antes' in valor || 'despues' in valor);
    item.appendChild(document.createTextNode(esCambio
      ? `${textoValorAuditoria(valor.antes, campo)} → ${textoValorAuditoria(valor.despues, campo)}`
      : textoValorAuditoria(valor, campo)));
    lista.appendChild(item);
  });
  celda.appendChild(lista);
}

function mostrarApartadoAdmin(apartado) {
  const historial = apartado === 'historial';
  elementoAdmin('adminPanelUsuarios').hidden = historial;
  elementoAdmin('adminPanelHistorial').hidden = !historial;
  elementoAdmin('adminVerUsuarios').setAttribute('aria-pressed', String(!historial));
  elementoAdmin('adminVerHistorial').setAttribute('aria-pressed', String(historial));
  if (historial) {
    const detalle = elementoAdmin('detalleAuditoria');
    if (!detalle.open) detalle.open = true; // Su evento toggle carga el historial.
    else cargarAuditoriaAdmin();
  }
}

async function cargarAuditoriaAdmin() {
  mensajeAdmin('mensajeAuditoria','Cargando historial…');
  try {
    const r = await apiAdministracion('/auth/admin/auditoria');
    const tabla = document.createElement('table'); tabla.className = 'admin-tabla';
    const h = tabla.createTHead().insertRow();
    ['Fecha','Responsable','Acción','Usuario afectado','Cambios'].forEach(t => { const th = document.createElement('th'); th.textContent=t; th.scope='col'; h.appendChild(th); });
    const cuerpo = tabla.createTBody();
    const acciones = {crear:'Cuenta creada', editar:'Datos modificados', desactivar:'Cuenta desactivada', reactivar:'Cuenta reactivada'};
    r.eventos.forEach(e => {
      const fila = cuerpo.insertRow();
      [new Date(e.instante).toLocaleString('es-AR'), e.actor, acciones[e.accion] || e.accion, e.usuario_afectado]
        .forEach(t => fila.insertCell().textContent = t);
      dibujarCambiosAuditoria(fila.insertCell(), e.cambios);
    });
    elementoAdmin('listaAuditoria').replaceChildren(tabla);
    mensajeAdmin('mensajeAuditoria',r.eventos.length ? `${r.eventos.length} cambios registrados.` : 'Todavía no hay cambios administrativos registrados.');
  } catch (error) { elementoAdmin('listaAuditoria').replaceChildren(); mensajeAdmin('mensajeAuditoria',error.message,true); }
}

elementoAdmin('adminVerUsuarios').addEventListener('click', () => mostrarApartadoAdmin('usuarios'));
elementoAdmin('adminVerHistorial').addEventListener('click', () => mostrarApartadoAdmin('historial'));

elementoAdmin('recargarUsuarios').addEventListener('click', actualizarPanelAdministracion);
elementoAdmin('nuevoUsuarioAdmin').addEventListener('click', () => abrirFormularioUsuarioAdmin());
elementoAdmin('buscarUsuarios').addEventListener('input', dibujarUsuariosAdmin);
['filtrarRol','filtrarEstado'].forEach(id => elementoAdmin(id).addEventListener('change', dibujarUsuariosAdmin));
elementoAdmin('formUsuarioAdmin').addEventListener('submit', guardarUsuarioAdmin);
elementoAdmin('cancelarUsuarioAdmin').addEventListener('click', () => { elementoAdmin('adminClave').value=''; elementoAdmin('dialogoUsuario').close(); });
elementoAdmin('dialogoUsuario').addEventListener('cancel', e => { if(operacionAdmin)e.preventDefault(); else elementoAdmin('adminClave').value=''; });
elementoAdmin('detalleAuditoria').addEventListener('toggle', () => { if(elementoAdmin('detalleAuditoria').open)cargarAuditoriaAdmin(); });
elementoAdmin('recargarAuditoria').addEventListener('click', cargarAuditoriaAdmin);
actualizarPanelAdministracion();
