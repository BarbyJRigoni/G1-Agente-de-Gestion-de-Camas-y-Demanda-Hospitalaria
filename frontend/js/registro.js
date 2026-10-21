
const abrirRegistro = document.querySelector('#abrirRegistro');
const formRegistro = document.querySelector('#formRegistro');
const mensajeRegistro = document.querySelector('#mensajeRegistro');
const guardarRegistro = document.querySelector('#guardarRegistro');
const formAcceso = document.querySelector('#formAcceso');

// Mostrar u ocultar el formulario de registro.
abrirRegistro.addEventListener('click', () => {
    formRegistro.hidden = !formRegistro.hidden;
    formAcceso.hidden = !formRegistro.hidden;

    abrirRegistro.textContent = formRegistro.hidden
        ? 'Registrarse'
        : 'Cancelar';

    mensajeRegistro.textContent = '';
    mensajeRegistro.className = '';

    if (!formRegistro.hidden) {
        document.querySelector('#nuevoUsuario').focus();
    }
});

// Crear una nueva cuenta.
formRegistro.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (guardarRegistro.disabled || !formRegistro.reportValidity()) return;

    const usuario = document.querySelector('#nuevoUsuario').value;
    const correo = document.querySelector('#nuevoCorreo').value.trim();
    const clave = document.querySelector('#nuevaClave').value;
    const confirmar = document.querySelector('#confirmarClave').value;

    if (clave !== confirmar) {
        mensajeRegistro.className = 'error';
        mensajeRegistro.textContent = 'Las contraseñas no coinciden.';
        return;
    }

    guardarRegistro.disabled = true;
    mensajeRegistro.className = '';
    mensajeRegistro.textContent = 'Creando tu cuenta…';

    try {
        const respuesta = await fetch('/auth/registrar', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'AgenteCamas'
            },
            body: JSON.stringify({ usuario, correo, clave })
        });

        const datos = await respuesta.json();

        if (!respuesta.ok) {
            throw new Error(
                typeof datos.detail === 'string'
                    ? datos.detail
                    : 'No se pudo crear la cuenta. Revisá los datos.'
            );
        }

        formRegistro.reset();

        // Volver al formulario de inicio de sesión.
        formRegistro.hidden = true;
        formAcceso.hidden = false;
        abrirRegistro.textContent = 'Registrarse';

        document.querySelector('#usuario').value = datos.usuario;
        document.querySelector('#mensajeAcceso').className = '';
        document.querySelector('#mensajeAcceso').textContent =
            '¡Cuenta creada correctamente! Ya podés iniciar sesión.';

        document.querySelector('#clave').focus();

    } catch (error) {
        mensajeRegistro.className = 'error';
        mensajeRegistro.textContent = error.message;
    } finally {
        guardarRegistro.disabled = false;
    }
});
