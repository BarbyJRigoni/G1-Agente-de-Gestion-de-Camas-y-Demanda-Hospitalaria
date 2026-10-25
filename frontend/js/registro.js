const abrirRegistro = document.querySelector('#abrirRegistro');
const formRegistro = document.querySelector('#formRegistro');
const mensajeRegistro = document.querySelector('#mensajeRegistro');
const guardarRegistro = document.querySelector('#guardarRegistro');
const formAcceso = document.querySelector('#formAcceso');
const tituloAcceso = document.querySelector('#tituloAcceso');
const descripcionAcceso = tituloAcceso?.nextElementSibling;
const tituloInternoRegistro = formRegistro.querySelector('h3');

// Conservar los textos actuales de la pantalla de ingreso.
const textoTituloIngreso = tituloAcceso?.textContent;
const textoDescripcionIngreso = descripcionAcceso?.textContent;

// El mismo botón sirve para abrir el registro y para volver al ingreso.
// Se coloca después del formulario, sin crear otro botón ni otro evento.
formRegistro.after(abrirRegistro);
abrirRegistro.setAttribute('aria-controls', 'formRegistro');

function mostrarRegistro(mostrar) {
    formRegistro.hidden = !mostrar;
    formAcceso.hidden = mostrar;
    abrirRegistro.textContent = mostrar ? 'Volver a ingresar' : 'Registrarse';
    abrirRegistro.setAttribute('aria-expanded', String(mostrar));
    abrirRegistro.classList.toggle('volver-acceso', mostrar);

    if (tituloAcceso) {
        tituloAcceso.textContent = mostrar
            ? 'Crear una cuenta'
            : textoTituloIngreso;
    }

    if (descripcionAcceso?.tagName === 'P') {
        descripcionAcceso.textContent = mostrar
            ? 'Completá tus datos para registrarte'
            : textoDescripcionIngreso;
    }

    // El título principal reemplaza al segundo título dentro del formulario.
    if (tituloAcceso && tituloInternoRegistro) {
        tituloInternoRegistro.hidden = true;
    }

    formRegistro.closest('.acceso')?.classList.toggle('modo-registro', mostrar);
}

mostrarRegistro(!formRegistro.hidden);

abrirRegistro.addEventListener('click', () => {
    if (guardarRegistro.disabled) return;

    mostrarRegistro(formRegistro.hidden);
    mensajeRegistro.textContent = '';
    mensajeRegistro.className = '';

    if (!formRegistro.hidden) {
        document.querySelector('#nuevoUsuario').focus();
    } else {
        document.querySelector('#usuario').focus();
    }
});

// Crear una nueva cuenta: se conserva el endpoint y sus datos de entrada.
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
    abrirRegistro.disabled = true;
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
        mostrarRegistro(false);

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
        abrirRegistro.disabled = false;
    }
});

// Mostrar u ocultar las contraseñas del registro.
function ocultarClavesRegistro() {
    formRegistro.querySelectorAll('[data-clave-registro]').forEach(boton => {
        const campo = document.getElementById(boton.dataset.claveRegistro);

        campo.type = 'password';
        boton.textContent = 'Mostrar';
        boton.setAttribute('aria-pressed', 'false');
    });
}

formRegistro.querySelectorAll('[data-clave-registro]').forEach(boton => {
    boton.addEventListener('click', () => {
        const campo = document.getElementById(boton.dataset.claveRegistro);
        const mostrar = campo.type === 'password';

        campo.type = mostrar ? 'text' : 'password';
        boton.textContent = mostrar ? 'Ocultar' : 'Mostrar';
        boton.setAttribute('aria-pressed', String(mostrar));
    });
});

// Al cambiar de formulario o completar el registro,
// las contraseñas vuelven a quedar ocultas.
abrirRegistro.addEventListener('click', ocultarClavesRegistro);
formRegistro.addEventListener('reset', ocultarClavesRegistro);