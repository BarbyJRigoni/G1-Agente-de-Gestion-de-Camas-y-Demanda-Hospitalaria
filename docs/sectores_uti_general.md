# UTI y general: simulacion con parametros explicitos

## Que se conoce y que se supone
HDHI aporta ingresos hospitalarios historicos. No registra las fechas de entrada y salida de UTI y no se confirmo la convencion de conteo de su duracion UTI. Por eso no se convierte esa variable a noches, no se resta del total hospitalario para inferir la estancia general y no se usa su frecuencia para recomendar un reparto de ingresos o de traslados.
La proyeccion agregada, sus estadisticas y su evaluacion se conservan. UTI/general es una simulacion de flujos con parametros explicitos, sin validacion observacional por sector.

## Entradas obligatorias
POST /proyeccion-camas recibe sectores.uti y sectores.general con ocupadas (entero >= 0) y capacidad (entero > 0). Ademas requiere proporcion_ingresos_uti [0,1], estancia_media_uti y estancia_media_general [1,365] dias, y fraccion_salidas_uti_a_general [0,1]. Se rechazan nulos, parametros omitidos, valores no finitos y censos actuales por encima de las camas habilitadas del sector. La demanda futura por encima de capacidad se muestra aparte. origen_parametros indica supuestos_usuario o ejemplo_ficticio; no certifica que los datos sean observados.
Con sectores no se aceptan capacidad ni dias_internados agregados. La fuente de ingresos es HDHI y la proyeccion principal es de siete dias. No se unen pacientes de las tres fuentes.
GET /sectores/parametros verifica la fecha y el minimo de 148 dias de historia; devuelve una auditoria descriptiva de episodios anteriores. parametros_inferidos=false. Nunca completa parametros operativos.

## Ejemplos explicitamente ficticios
Censo UTI 7, capacidad 20; censo general 90, capacidad 170. Estancia media UTI 2 dias, general 5; ingreso inicial UTI 20%; salida UTI hacia general 80%. Son numeros ilustrativos, no mediciones HDHI. El ejemplo de capacidad UTI reducida cambia solo su capacidad a 8. Los resultados muestran persistentemente el origen ficticio o los supuestos ingresados por el usuario.

## Balance de pacientes
Para ocupadas U y G al inicio del dia, medias Lu y Lg, ingreso hospitalario I, reparto UTI p y traslado q:
- Salidas UTI = U/Lu; traslado = q*salidas UTI; altas desde UTI = (1-q)*salidas UTI.
- Altas general = G/Lg.
- U siguiente = U - salidas UTI + p*I.
- G siguiente = G - altas general + traslado + (1-p)*I.
Se suponen tiempos geometricos sin memoria. Las salidas no dependen de dias transcurridos, edad ni patologia. Los nuevos ingresos y los traslados no egresan en el mismo paso. Los traslados se cancelan en el balance hospitalario: no son ingresos externos ni altas hospitalarias.
El balance se verifica en tiempo de ejecucion con tolerancia numerica; si falla se cancela la simulacion. La respuesta declara control_balance y valida tipos, finitud y no negatividad de cada flujo.

## Capacidad y alertas
Cada sector activa Alerta de Saturacion cuando demanda/capacidad > 0.90, antes de redondear. Exactamente 90% no activa la alerta. Los estados del censo y de la proyeccion son independientes. Las camas generales no compensan una UTI saturada.
No se simulan bloqueos, espera, reingresos UTI ni general a UTI. Si la demanda supera la capacidad se informa demanda_sin_cama teorica; no se ubican pacientes en camas inexistentes.

## Evidencia y limites
nivel_evidencia=simulacion_sectorial_no_validada. Los ingresos se estiman con el modelo historico seleccionado hasta el censo, pero esa validacion no se transfiere a UTI/general. No se ofrecen P90, probabilidades ni garantias de precision por sector.
Para validar: censo por sector y fecha, ingresos externos, egresos y traslados fechados entre sectores, capacidad habilitada diaria y definiciones consistentes de duracion. Hace falta comparar pronosticos con movimientos reales posteriores sin usar esos resultados al entrenar.
La interfaz conserva cuatro solapas, colores, ayudas y graficos locales. Al editar entradas se invalidan resultados anteriores y las respuestas atrasadas se descartan.
