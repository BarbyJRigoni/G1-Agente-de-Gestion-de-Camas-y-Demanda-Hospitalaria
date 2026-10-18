const form = document.querySelector('#formAcceso');
const mensaje = document.querySelector('#mensajeAcceso');
const boton = document.querySelector('#entrar');

// Mostrar u ocultar la contraseña.
document.querySelector('#mostrarClave').addEventListener('click', () => {
    const clave = document.querySelector('#clave');
    const mostrar = clave.type === 'password';
    clave.type = mostrar ? 'text' : 'password';

    const botonMostrar = document.querySelector('#mostrarClave');
    botonMostrar.textContent = mostrar ? 'Ocultar' : 'Mostrar';
    botonMostrar.setAttribute('aria-pressed', String(mostrar));
});

// Iniciar sesión.
form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (boton.disabled || !form.reportValidity()) return;

    boton.disabled = true;
    mensaje.className = '';
    mensaje.textContent = 'Verificando tu acceso…';

    try {
        const respuesta = await fetch('/auth/ingresar', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'AgenteCamas'
            },
            body: JSON.stringify({
                usuario: document.querySelector('#usuario').value,
                clave: document.querySelector('#clave').value
            })
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                typeof datos.detail === 'string'
                    ? datos.detail
                    : 'Revisá el usuario y la contraseña.'
            );
        }

        document.querySelector('#clave').value = '';
        location.replace('/panel');

    } catch (error) {
        mensaje.className = 'error';
        mensaje.textContent = error.message;
        document.querySelector('#clave').value = '';
        document.querySelector('#clave').focus();
    } finally {
        boton.disabled = false;
    }
});

// Comprobar si existe una sesión activa.
fetch('/auth/sesion', { credentials: 'same-origin' })
    .then(r => r.json())
    .then(datos => {
        if (datos.autenticado) {
            location.replace('/panel');
        } else if (!datos.acceso_configurado) {
            mensaje.textContent =
                'El acceso todavía no está configurado. Solicitá tu cuenta a la persona responsable.';
        }
    })
    .catch(() => {
        mensaje.textContent =
            'No se pudo conectar con el servidor. Volvé a intentar.';
    });

// Actualizar la página si vuelve desde el historial.
window.addEventListener('pageshow', (e) => {
    if (e.persisted) location.reload();
});
