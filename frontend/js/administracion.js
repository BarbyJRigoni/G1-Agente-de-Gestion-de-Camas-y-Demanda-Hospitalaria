/* PANEL DE ADMINISTRACIÓN - GRUPO 1 */

async function actualizarPanelAdministracion() {
  const boton = document.getElementById("tab-administracion");
  const mensaje = document.getElementById("mensajeAdministracion");
  const lista = document.getElementById("listaUsuarios");

  if (!boton || !mensaje || !lista) return;

  try {
    const respuesta = await fetch("/auth/admin/usuarios", {
      credentials: "same-origin",
      headers: { "X-Requested-With": "AgenteCamas" }
    });

    if (!respuesta.ok) {
      boton.hidden = true;
      return;
    }

    boton.hidden = false;

    const datos = await respuesta.json();
    lista.replaceChildren();

    const tabla = document.createElement("table");
    const cabecera = document.createElement("thead");
    const encabezados = document.createElement("tr");

    ["Usuario", "Correo", "Rol"].forEach(texto => {
      const th = document.createElement("th");
      th.textContent = texto;
      encabezados.appendChild(th);
    });

    cabecera.appendChild(encabezados);
    tabla.appendChild(cabecera);

    const cuerpo = document.createElement("tbody");

    datos.usuarios.forEach(usuario => {
      const fila = document.createElement("tr");

      [
        usuario.usuario,
        usuario.correo || "Sin correo",
        usuario.rol
      ].forEach(valor => {
        const td = document.createElement("td");
        td.textContent = valor;
        fila.appendChild(td);
      });

      cuerpo.appendChild(fila);
    });

    tabla.appendChild(cuerpo);
    lista.appendChild(tabla);

    mensaje.textContent =
      `${datos.usuarios.length} usuario(s) registrado(s).`;

  } catch (error) {
    boton.hidden = true;
    mensaje.textContent = "No se pudo cargar Administración.";
  }
}

document.getElementById("recargarUsuarios")
  ?.addEventListener("click", actualizarPanelAdministracion);
actualizarPanelAdministracion();
