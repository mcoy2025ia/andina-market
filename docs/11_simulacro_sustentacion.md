# Simulacro de sustentación · 70 preguntas con respuesta

**Corte:** 1 de noviembre de 2026. Complementa [GUION_SUSTENTACION.md](GUION_SUSTENTACION.md)
(estructura de los diez minutos) y [10_storyline_finanzauto.md](10_storyline_finanzauto.md)
(deck). Este documento es el banco de preguntas y respuestas.

> **Advertencia que no se debe borrar.** Tener las respuestas escritas **no** equivale
> a saber sostenerlas. Este archivo sirve para encontrar los puntos donde la
> explicación se cae, no para memorizar. Si en el simulacro lees la respuesta en vez
> de reconstruirla, el ejercicio no sirvió. La práctica oral sigue siendo
> responsabilidad del autor y no se declara realizada por nadie más.

## Cómo usarlo

1. **Tapa la respuesta.** Responde en voz alta, cronómetro en mano, en el tiempo
   indicado. Hablar es distinto de pensar.
2. **Compara.** No busques coincidencia literal: busca si dijiste el **porqué** y si
   citaste la **cifra o el archivo**.
3. **Puntúa** con la rúbrica de abajo. Las de ❌ se repiten al día siguiente.
4. **Lo que no sepas, anótalo.** «No lo verifiqué» es respuesta válida y es el
   criterio que defiende todo el proyecto. Lo que no es válido es inventarlo.

### Rúbrica

| | Criterio |
|---|---|
| ✅ | Das el porqué, una cifra o archivo concreto, y el límite de lo que afirmas |
| ⚠️ | Describes qué hace el código pero no por qué se decidió así, o te falta el dato |
| ❌ | Afirmas algo que el repositorio no respalda, o no distingues probado de escrito |

### Las cinco frases que hunden una sustentación

1. «Funciona en Fabric» → no se ha ejecutado.
2. «Las pruebas cubren todo» → cubren lo local; la nube y SQL Server no.
3. «La IA clasifica con alta precisión» → el intervalo no lo permite afirmar.
4. «TIENDA cae por X» → el dato describe, no explica.
5. «Eso no puede fallar» → siempre hay un modo de fallo; nómbralo tú primero.

---

## Bloque 1 · Apertura y encuadre (4 preguntas)

### P1 — «Tienes 90 segundos. ¿Qué hiciste?» *(90 s)*

**Se evalúa:** si sabes priorizar bajo presión. Es la pregunta que más gente falla
por contar el proceso en vez del resultado.

**Respuesta.** Construí el camino completo de una cifra de venta, desde el archivo
crudo hasta el tablero, con tres garantías: la definición vive en un solo lugar y se
replica a cuatro dialectos de SQL y a DAX; la cadena de evidencia permite reproducir
la cifra desde el archivo original; y una compuerta impide publicar cuando Silver y
Gold no concilian. La cifra es COP 14.177.333.600 sobre 16.855 pedidos entregados, y
la reproduje con un script independiente que no usa el código del ETL. Lo que **no**
hice es ejecutarlo en SQL Server, Power BI o Fabric: eso está escrito y probado como
código, no como despliegue.

**Si insisten: «¿y qué es lo más difícil que resolviste?»** Publicar de forma
consistente en Delta, que no tiene transacción entre tablas. Lo explico en detalle
cuando lleguemos ahí.

**Señal de alarma.** Empezar por «primero leí los CSV, luego…». Nadie te pidió el
diario de trabajo.

### P2 — «¿Por qué deberíamos creerte la cifra?» *(60 s)*

**Se evalúa:** si entiendes que una cifra sin procedencia no existe.

**Respuesta.** Por tres cosas, en orden de fuerza. Primera: hay un recálculo
**independiente** en pandas que no importa una sola línea del ETL
(`scripts/recalculo_independiente.py`) y da el mismo número. Segunda: la segunda
carga de los mismos datos produce el mismo **hash** de las tablas de hechos, así que
el resultado no depende del momento en que se ejecute. Tercera: la cifra no se
publica si el agregado de Gold no coincide con Silver fila a fila, no solo en el
total. Y si quieren auditarla, cada fila de Gold se puede rastrear hasta el Parquet
de Bronze y de ahí al archivo original por su sha256.

**Señal de alarma.** «Porque las pruebas pasan». Las pruebas prueban el código, no
la cifra.

### P3 — «Esto es un caso de retail. Nosotros financiamos vehículos.» *(45 s)*

**Se evalúa:** si sabes abstraer sin fingir que conoces su negocio.

**Respuesta.** Cierto, y no voy a pretender que conozco su operación. Lo que se
traslada no es el dominio, es la clase de problema. Resolví cinco modos de fallo que
no son de retail: un indicador con tres definiciones en circulación; el mismo hecho
registrado dos veces con identificadores distintos; movimientos de dinero contra un
hecho que ya no existe; correcciones que llegan después del cierre; y una fuente cuyo
contrato no está escrito, donde nadie sabe si una fila que deja de venir es una baja
o un fallo de extracción. Si en su operación esos cinco no aparecen, me sobra medio
proyecto. Mi impresión es que aparecen todos.

**Señal de alarma.** Inventar detalles de su negocio. Si te equivocas delante de
ellos, pierdes más de lo que ganas.

### P4 — «¿Cuánto de esto lo hizo una IA?» *(45 s)*

**Se evalúa:** honestidad y si entiendes lo que firmaste.

**Respuesta.** Usé asistencia de IA en diseño, código y documentación, y está
declarado en el README. Lo que no delegué es la responsabilidad: cada decisión de
negocio del proyecto está escrita con su porqué y la puedo defender y modificar. De
hecho, el proyecto tiene una regla que va en contra de la IA: las etiquetas que
propone un modelo **no pueden** publicarse como validadas; hay una columna distinta
para eso y una revisión humana obligatoria en medio. Esa decisión la tomé
precisamente porque usé IA.

---

## Bloque 2 · La cifra y las definiciones de negocio (7 preguntas)

### P5 — «Comercial tiene otra cifra. ¿Quién se equivoca?» *(60 s)*

**Respuesta.** Probablemente nadie: estamos midiendo cosas distintas. Mi cifra
depende de tres decisiones explícitas, y cualquiera de las tres explica una
diferencia. Una: solo cuentan los pedidos **ENTREGADO**; los cancelados y devueltos
no suman, y son 2.415 de los 19.270 válidos. Dos: venta neta es **bruto menos
descuento**, no bruto. Tres: se atribuye a **fecha_pedido**, no a fecha de entrega,
así que un pedido de fin de mes entregado el mes siguiente cae en el mes del pedido.
Si comercial usa otra de las tres, la diferencia es explicable y reconciliable. Lo
que no acepto es que la diferencia quede sin explicar.

### P6 — «¿Por qué fecha_pedido y no fecha de entrega?» *(45 s)*

**Respuesta.** Porque es lo que fija el caso, y lo dejé como **parámetro**, no como
supuesto escondido: vive en `config.py`. Si negocio decide atribuir a la entrega, el
cambio toca `store.py`, `star.py`, las cuatro variantes de SQL y las medidas DAX, y
obliga a recalcular todo el histórico con `--recalcular-gold`. No es un ajuste
visual: cambia la cifra de cada mes y hay que versionar el contrato. Tengo el mapa de
ese cambio escrito en `docs/GUION_SUSTENTACION.md`.

### P7 — «¿Cuántos clientes hay?» *(30 s)*

**Se evalúa:** si distingues registro de persona. Es una pregunta trampa.

**Respuesta.** Depende de qué cuente usted. Hay **6.040 identificadores de cliente**
y **6.000 personas**: 40 están registrados dos veces con el mismo documento. Para la
recompra uso personas, porque si no, alguien que compró con sus dos registros
aparecería como dos clientes que nunca repitieron. La unificación es una **vista**
(`v_cliente_maestro`), no una columna congelada, para que siempre refleje el estado
actual de Silver.

### P8 — «¿Qué es la recompra exactamente?» *(60 s)*

**Respuesta.** La persona hace **otro** pedido entregado, en fecha posterior a su
primer pedido entregado, dentro de N meses calendario. La cohorte es el mes de
registro. Y lo importante es el denominador: solo cuento a quien ya tiene la **ventana
completa** dentro de los datos, que terminan el 2026-09-30. Sin ese control de
madurez, las cohortes recientes saldrían artificialmente mal solo por no haber tenido
tiempo de repetir.

### P9 — «Entonces la recompra cayó. ¿Qué tan seguro estás?» *(60 s)*

**Respuesta.** La caída se sostiene con dos bases distintas, que es lo que le da
fuerza. Con mi base (personas con primer pedido entregado y ventana madura), la
recompra a 3 meses pasa de **63,2 %** en cohortes de 2025 a **49,2 %** en 2026. Con
una base más exigente —todos los registrados de la cohorte— pasa de 60,9 % a 46,4 %.
Mismo sentido, misma magnitud. A 1 mes, de 32,1 % a 26,1 %. La salvedad está a 6
meses: solo las cohortes de enero a marzo de 2026 tienen ventana completa, son 856
personas, así que esa comparación es válida pero con base menor.

### P10 — «¿Meses calendario o 90 días?» *(30 s)*

**Respuesta.** Calendario, y es una decisión que debería firmarse. No son
equivalentes: tres meses calendario desde el 31 de enero no son 90 días, y la
diferencia cambia a quién se cuenta en el borde. Está en la lista de contratos
pendientes de ratificar.

### P11 — «Dame la lectura de negocio en tres líneas.» *(60 s)*

**Respuesta.** Uno: la venta suma 14.177 millones, con APP aportando 42,8 %, WEB
32,5 % y TIENDA 24,7 %, y desde diciembre de 2025 se estancó entre 780 y 950 millones
mensuales. Dos: entre junio y septiembre de 2026 TIENDA cayó 51 %, de 217,6 a 105,8
millones, mientras APP creció 19,2 % y WEB quedó plana; ahí está la señal de alerta.
Tres: la recompra a 3 meses se deterioró de 63,2 % a 49,2 %. Las tres son
descripciones; ninguna prueba su causa.

---

## Bloque 3 · Calidad de datos (7 preguntas)

### P12 — «¿Cuántos registros descartaste?» *(45 s)*

**Respuesta.** Ninguno se descartó: se **aislaron** 1.223, y todos conservan su fila
original completa en JSON. Son 464 pedidos de 19.734 (2,35 %) y 759 pagos de 20.883
(3,63 %). La palabra importa: están disponibles para auditoría y, si la fuente se
corrige, vuelven a entrar solos en la siguiente corrida.

### P13 — «¿Por qué 511 violaciones pero 464 pedidos?» *(45 s)*

**Se evalúa:** si entiendes tu propio modelo de cuarentena.

**Respuesta.** Porque la cuarentena guarda una fila por **(registro, regla
violada)**, no por registro. Hay 47 pedidos que incumplen dos reglas a la vez —por
ejemplo, descuento inválido y entrega anterior al pedido—. Por eso, para contar
registros afectados se usa `COUNT(DISTINCT id_registro)` y nunca se suman los
conteos por regla. Si los sumara, reportaría 511 pedidos malos cuando son 464.

### P14 — «¿Cuáles son los problemas que encontraste?» *(90 s)*

**Respuesta.** Documenté 15 tipos. Los seis que más disparan, con sus conteos:
`DUPLICADO_LOGICO` 295 en pedidos y 344 en pagos —el mismo hecho con distinto
identificador—; `PEDIDO_EN_CUARENTENA` 345 pagos cuyo pedido fue rechazado;
`ENTREGA_ANTERIOR_A_PEDIDO` 87; `DESCUENTO_INVALIDO` 74, donde el descuento supera el
bruto o es negativo; `PAGO_HUERFANO` 70 contra un pedido que no existe;
`VALOR_BRUTO_NO_POSITIVO` 35; y 20 pedidos con fecha de 2027, fuera del rango del
caso. Fuera de la cuarentena hay dos más que no son errores sino normalización: 810
pedidos traen el canal escrito de otra forma (`app `, `PAGINA WEB`) y 1.200 fechas de
pago llegan en dos formatos.

### P15 — «345 pagos de pedidos rechazados. ¿Eso es fraude?» *(45 s)*

**Se evalúa:** si resistes la conclusión fácil. Es de las más importantes.

**Respuesta.** No lo sé, y el dato no permite decirlo. Lo que sé es que hay dinero
registrado contra un pedido que mis reglas rechazaron. Puede ser un error de la regla,
un pedido corregido que llegará después, o un problema real de recaudo. Por eso no se
borra ni se suma: se aísla, se marca y se escala a negocio con la fila original. Y hay
un detalle de diseño: esos pagos se releen en **cada** corrida aunque queden fuera de
la ventana incremental, para que entren solos el día que su pedido se corrija.

### P16 — «¿Por qué no borras los duplicados y ya?» *(45 s)*

**Respuesta.** Depende del tipo. Si el mismo **id** llega dos veces con contenido
distinto, no sé cuál versión vale: van **las dos** a cuarentena, porque elegir sería
inventar. Si es el mismo hecho con **ids distintos** —`hash_negocio` sobre cliente,
fecha, valor y categoría— sí resuelvo: gana el que ya está en Silver, y si ninguno
está, el de menor id. La regla es determinista a propósito, para que dos corridas
elijan igual y la cifra no dependa del orden de lectura.

### P17 — «¿Qué hiciste con los pedidos de clientes que no existen?» *(45 s)*

**Respuesta.** Se conservan y suman venta, con una bandera
`flag_cliente_desconocido`, y en el modelo estrella apuntan al cliente 0,
«DESCONOCIDO». Borrarlos sería perder venta real por un problema de la dimensión. Y
hay un comportamiento que me importa: si el cliente llega en una carga posterior, la
bandera se corrige sola sin que el pedido cambie, porque se revalúa en cada corrida.

### P18 — «Un ticket cerrado antes de crearse. ¿Lo botas?» *(45 s)*

**Respuesta.** No. Se conserva con `flag_cierre_invalido` y se le deja las horas de
resolución en **nulo**. Si calculara la duración daría un número negativo que
contaminaría cualquier promedio de SLA; si inventara un cero, estaría afirmando que
se resolvió instantáneamente. El nulo es la única opción honesta: el ticket existió,
su duración no se puede saber.

---

## Bloque 4 · ETL e idempotencia (8 preguntas)

### P19 — «¿Qué pasa si ejecuto la carga dos veces?» *(45 s)*

**Respuesta.** Nada. Cero insertados, cero actualizados, y lo verifico de forma más
fuerte que con los contadores: comparo el **hash sha256 de las tablas de hechos**
antes y después, y es idéntico. Bronze tampoco vuelve a aterrizar: si el sha256 del
archivo ya está en el manifiesto, se reutiliza el Parquet existente.

### P20 — «¿Qué se revierte si falla a mitad?» *(60 s)*

**Respuesta.** En local, todo salvo Bronze. Silver, cuarentena, incidencias,
watermark, Gold, el modelo estrella y el marcador de publicación se confirman en una
**sola transacción** DuckDB: o están todos o no está ninguno. Bronze queda fuera a
propósito, porque es inmutable y su valor es precisamente sobrevivir a la caída; lo
que puede quedar es un Parquet sin manifiesto confirmado, y la regla es no
interpretar su existencia como publicación. Vuelves a ejecutar y queda igual.

### P21 — «¿Cómo es el incremental de pagos?» *(60 s)*

**Respuesta.** Watermark sobre `fecha_carga` menos tres días de ventana de reproceso,
para cubrir cargas tardías o reenvíos. Con una excepción deliberada: los pagos que
están en cuarentena esperando a su pedido —huérfanos o de pedido rechazado— se releen
**siempre**, fuera de ventana. Sin esa excepción, un pago cuyo pedido llega tres
semanas después quedaría huérfano para siempre.

### P22 — «¿Eso es CDC?» *(30 s)*

**Se evalúa:** precisión terminológica. Mucha gente se cuelga aquí.

**Respuesta.** **No.** Es incremental en procesamiento y escritura, no en extracción.
Leo el snapshot completo y **después** filtro. Un CDC real leería solo los cambios en
el origen, y eso dependería de que la fuente los publique. Lo digo así de claro
porque la diferencia importa cuando se dimensiona la ventana de carga.

### P23 — «Un pedido cargado ayer hoy es inválido. ¿Qué pasa?» *(45 s)*

**Respuesta.** Sale de Silver, entra en cuarentena y su día de venta se **recalcula**,
así que la cifra baja. Es el caso que la mayoría de ETL no cubre: suelen dejar en la
tabla lo que ya entró. Puede ocurrir porque la fuente corrigió el dato o porque se
endureció una regla. Y funciona en los dos sentidos: si vuelve a ser válido, vuelve a
entrar.

### P24 — «¿Por qué Bronze si el origen ya es un archivo?» *(45 s)*

**Respuesta.** Por tres razones. Inmutabilidad: el CSV original puede cambiar o
desaparecer; el Parquet de Bronze no. Trazabilidad: cada fila lleva su run, su
archivo y el sha256 del origen, así que cualquier cifra se puede rastrear hasta el
byte. Y separación de responsabilidades: Bronze guarda **todo como texto** y no tipa
nada, porque tipar es decidir, y las decisiones van en Silver donde están las reglas y
la cuarentena.

### P25 — «Falta un archivo. ¿Qué hace el proceso?» *(30 s)*

**Respuesta.** Clientes, pedidos y pagos son obligatorios: falla. Tickets de soporte
es opcional: si no está, la carga continúa y la venta no cambia, porque soporte no
participa en el cálculo.

### P26 — «Una fila desapareció del archivo. ¿La borras?» *(45 s)*

**Se evalúa:** si entiendes que un contrato de fuente no escrito es un riesgo.

**Respuesta.** No, y es deliberado. No sé si ese archivo es un snapshot completo o un
incremento. Si es un incremento, la ausencia es normal y borrar destruiría datos
buenos. Tengo un script que **reporta** las ausencias (`reconciliar_fuentes.py`) sin
aplicar ninguna baja, y el contrato de fuente está en la lista de decisiones
pendientes. Para habilitar bajas necesitaría *tombstones* o un snapshot certificado.

---

## Bloque 5 · Arquitectura y paridad (5 preguntas)

### P27 — «¿Por qué DuckDB y no Spark desde el inicio?» *(45 s)*

**Respuesta.** Porque el caso cabe en memoria: 19.734 pedidos. Spark aquí sería coste
de operación sin beneficio, y además impediría que cualquiera clone el repositorio y
lo ejecute con un `pip install`. Lo que sí hice es escribir la versión Spark en
paralelo y **verificar la paridad** con pruebas, para que el salto a la nube no sea un
rediseño cuando el volumen lo justifique.

### P28 — «¿Cómo garantizas que las dos versiones dan lo mismo?» *(60 s)*

**Respuesta.** Con 24 pruebas que ejecutan **PySpark real** y comparan contra la
versión pandas/DuckDB: misma cuarentena por regla, mismas filas válidas, el mismo
`row_hash` sobre los datos crudos, y el modelo estrella completo —las cuatro
dimensiones con sus claves y los cuatro hechos— **fila a fila**. Corren con el modo
ANSI de Spark activado, que es el más estricto: si pasan así, no dependen de que el
runtime sea permisivo con valores sucios.

### P29 — «¿El notebook lo escribiste a mano?» *(30 s)*

**Respuesta.** No: se **genera** desde el código con `build_notebook.py`, y la CI
falla si el `.ipynb` no coincide con su generador. Un notebook editado a mano se
desincroniza del código en la primera semana; así es imposible.

### P30 — «¿Por qué el mismo SQL en cuatro dialectos?» *(45 s)*

**Respuesta.** Porque el caso pide T-SQL, pero yo necesitaba poder ejecutarlo para
verificarlo, y SQL Server no estaba disponible. La versión DuckDB es la que corre y se
contrasta con el recálculo independiente; la de Fabric y Databricks existen para el
destino cloud. Y lo digo con la salvedad que toca: **no hay traducción automática**;
el T-SQL es un texto paralelo revisado línea a línea, no ejecutado.

### P31 — «¿Qué pasa con un mes sin ventas?» *(45 s)*

**Respuesta.** Aparece con cero, no desaparece. Es un error clásico: si comparas con
`LAG` sobre las filas existentes y falta un mes, el «mes anterior» es en realidad dos
meses atrás y la variación sale mal. Por eso las consultas generan un calendario
completo de los 21 meses **por canal** y lo cruzan con las ventas. Y si el mes previo
es cero o no existe, la variación es **nula**, no infinito ni un 0 % que diría que no
hubo cambio.

---

## Bloque 6 · Delta y publicación sin transacción (6 preguntas)

> Este bloque es el examen. Si lo sostienes, el resto es confirmación.

### P32 — «En DuckDB usas una transacción. En Delta no existe. ¿Qué hiciste?» *(120 s)*

**Respuesta.** Delta garantiza atomicidad **por tabla**, no entre tablas. Si el
proceso muere después de escribir `fact_pedido` y antes de `fact_pago`, el modelo
queda incoherente y cualquier informe conectado lo lee. No se puede simular la
transacción, así que invertí el problema: los hechos se escriben **marcados con el
`run_id`** de la corrida; después se concilia Gold contra Silver y se aplican las
compuertas; y **solo si todo cuadra** se mueve el puntero `publicacion_actual`, que es
una sola escritura en una sola tabla y por tanto sí es atómica. Los consumidores
—Power BI, el reporte— no leen las tablas de hechos: leen vistas `v_fact_*` que
filtran por el run publicado. Resultado: mientras el puntero no se mueva, el
consumidor ve la **carga anterior completa**, nunca una a medias ni una que no pasó
las compuertas.

**Si insisten: «¿cuál es el costo de ese diseño?»** Que las tablas de hechos retienen
filas de runs no publicados hasta que se purguen, y cada cuánto se purgan es una
decisión que no he tomado porque depende de la retención que acuerde operación.

### P33 — «¿Lo ejecutaste en Fabric?» *(20 s)*

**Respuesta.** **No.** Las funciones que usan `MERGE`, `DELETE` y `DESCRIBE HISTORY`
están escritas con sintaxis estándar de Delta y no se han corrido en ninguna
plataforma. Lo que sí está probado es el **cálculo**: la construcción de la estrella y
la conciliación, comparadas contra DuckDB. Tengo los doce escenarios de validación
escritos, con su resultado esperado y la evidencia a capturar, en
`docs/08_traslado_delta.md`.

**Señal de alarma.** Cualquier matiz que suene a «pero debería funcionar». No lo
suavices.

### P34 — «Si no lo ejecutaste, ¿qué prueban esas 19 pruebas?» *(60 s)*

**Respuesta.** Prueban la parte que decide los **valores**, que es donde está el
riesgo de que la nube dé una cifra distinta. Separé a propósito el SQL que calcula del
SQL que persiste: el que calcula se ejecuta sobre Spark con vistas temporales y se
compara con DuckDB; el que persiste son `INSERT INTO` e `INSERT OVERWRITE`, de una
línea por paso. Lo que queda sin probar es la capa Delta y las rutas de plataforma, y
está declarado como tal. No es que no pueda probarlo: es que requiere el entorno.

### P35 — «¿Por qué reconstruyes todos los hechos en cada carga?» *(45 s)*

**Respuesta.** Por auditabilidad, y porque a este volumen cuesta segundos. Lo digo con
la salvedad explícita: **no lo presento como una carga de hechos incremental a
escala**. Si el volumen creciera, la reconstrucción completa dejaría de ser viable y
habría que pasar a actualización por partición de fecha. Está escrito así en el código
para que nadie lo lea como una solución para 50 millones de filas.

### P36 — «¿Por qué las claves de dimensión no pueden cambiar?» *(45 s)*

**Respuesta.** Porque un informe guardado, un marcador o una consulta externa que
apunten a `canal_key = 3` seguirían apuntando a 3 después de la recarga, y si ese 3
ahora es otro canal, el informe miente sin fallar. Por eso las dimensiones solo
**crecen**: se insertan los valores nuevos y los existentes no se tocan. Hay una
prueba dedicada a eso: construye la estrella dos veces y verifica que las claves no se
movieron.

### P37 — «¿Qué pasa si una compuerta salta en la nube?» *(45 s)*

**Respuesta.** Los hechos quedan escritos con su `run_id`, pero el puntero **no** se
mueve y la celda lanza el error, así que el notebook falla visiblemente. El consumidor
sigue viendo el run anterior. Es la diferencia con el local, donde la transacción
revierte también las escrituras: en Delta las escrituras quedan, pero inertes.

---

## Bloque 7 · Modelo dimensional y DAX (6 preguntas)

### P38 — «¿Por qué un modelo estrella y no consultar Silver?» *(45 s)*

**Respuesta.** Porque un tablero no debe consultar las tablas del ETL: cualquier
cambio interno rompería los informes. La estrella es el **contrato de consumo**, con
claves estables y un grano declarado. Además fuerza la consistencia: el reporte diario
lee `gold.fact_venta_neta_diaria`, la misma tabla que alimenta Power BI, y por eso no
puede dar una cifra distinta.

### P39 — «¿Qué grano tiene cada hecho?» *(30 s)*

**Respuesta.** `fact_pedido`, un pedido por fila. `fact_pago`, un pago.
`fact_ticket`, un ticket. `fact_venta_neta_diaria`, una fila por día, canal y
categoría. Que `fact_pedido` tenga grano de pedido es lo que permite contar con
`COUNTROWS` en DAX sin necesitar `DISTINCTCOUNT`.

### P40 — «Explícame la medida de variación anual.» *(90 s)*

**Respuesta.** `DATEADD(dim_fecha[fecha], -1, YEAR)` desplaza el contexto un año, así
que sirve igual para mes, trimestre o año seleccionado. Pero tiene una trampa que
resolví: la tabla de fechas cubre **años completos** porque `DATEADD` lo exige, y los
datos terminan el 30 de septiembre de 2026. Si no limitara, con el año 2026
seleccionado compararía 9 meses de 2026 contra los 12 de 2025 y la variación saldría
**+20,2 %** en vez de **+98,9 %**. Por eso hay una columna calculada
`dim_fecha[tiene_datos]` que se queda solo con las fechas con datos antes de
desplazar.

### P41 — «¿Y si no existe el período anterior?» *(30 s)*

**Respuesta.** Devuelve **vacío**, no 0 %. Un 0 % afirmaría que no hubo cambio, cuando
lo que pasa es que no hay con qué comparar. En 2025 todas las variaciones anuales
salen vacías, y es lo correcto.

### P42 — «Dame un valor que pueda verificar en Power BI.» *(30 s)*

**Respuesta.** Enero de 2026: venta neta 948.592.900, 1.085 pedidos entregados,
ticket promedio 874.279, y el mismo mes de 2025 fueron 113.198.600, así que la
variación es +737,99 %. Septiembre de 2026: 795.114.800. Y el acumulado enero–
septiembre de 2026 es 7.739.061.400 contra 3.891.305.400 de 2025, +98,88 %.

**Si insisten: «ese +738 % suena a crecimiento espectacular».** Es correcto pero
engañoso: la base de 2025 es muy baja porque el negocio arrancaba, con 113 millones en
enero. Desde diciembre de 2025 la venta mensual se mueve entre 780 y 950 millones sin
tendencia clara. Lo diría así en el comité.

### P43 — «¿Probaste el DAX?» *(20 s)*

**Respuesta.** No. Las medidas están escritas y revisadas contra el modelo de Gold, y
tengo los valores esperados calculados con SQL para comprobarlas, pero **no se
ejecutó** Power BI ni Fabric. Tener DAX escrito no equivale a haberlo ejecutado.

---

## Bloque 8 · Optimización SQL (5 preguntas)

### P44 — «La consulta tarda 20 minutos sobre 50 millones. ¿Qué harías?» *(90 s)*

**Respuesta.** Identifiqué seis problemas y los ordené por peso, que es lo que
importa. El principal: hay un `CAST(... AS VARCHAR(20))` en **ambos** lados del cruce
con tickets, sobre columnas que ya son texto de 9 caracteres. Ese CAST impide usar el
índice y obliga a recorrer los tickets por cada cliente. Segundo: una subconsulta
correlacionada para la venta del mes, que se ejecuta una vez por cliente en lugar de
agregar una sola vez. Tercero: `YEAR()` y `MONTH()` sobre la fecha hacen el predicado
no SARGable; se reemplazan por un rango. Los otros tres son buenas prácticas más que
causas: `IN (SELECT DISTINCT)`, un `TOP 1` sin índice de apoyo y `GETDATE()` en el
predicado.

### P45 — «¿Cómo sabes que el CAST es el problema principal?» *(60 s)*

**Se evalúa:** si mides o si opinas.

**Respuesta.** Lo aislé con un experimento de ablación. Con 100.000 pedidos, la
original con índices tarda 7,28 s; quitando **solo** el CAST del cruce baja a 0,06 s;
quitar además las funciones sobre la fecha apenas cambia (0,05 s). Los tiempos
absolutos varían entre equipos —en otra ejecución 10,86 / 0,09 / 0,05— pero la
proporción se mantiene y las cuatro variantes dan el mismo resultado.

### P46 — «¿En SQL Server?» *(30 s)*

**Respuesta.** No. El experimento es en **SQLite**, y lo elegí a propósito: ejecuta
las subconsultas correlacionadas fila a fila, igual que el plan que describe el
enunciado. DuckDB las reescribe solo y habría escondido el problema. Lo que demuestra
es la **forma** del problema y el crecimiento cuadrático; los tiempos absolutos de SQL
Server serán otros. La corrección de la fecha sigue siendo necesaria allí, porque con
50 millones la tabla no se lee entera, pero eso no lo puedo demostrar con este
experimento.

### P47 — «¿Qué índices propones?» *(60 s)*

**Respuesta.** Tres. `ix_pedidos_fecha (fecha_pedido) INCLUDE (id_cliente,
valor_bruto, descuento)`, para leer la venta del mes por rango sin volver a la tabla.
`ix_pedidos_devueltos (id_cliente) WHERE estado = 'DEVUELTO'`, un índice filtrado
pequeño para el `EXISTS`. Y `ix_tickets_cliente_fecha (id_cliente, fecha_creacion
DESC) INCLUDE (canal)`, para que el último ticket salga directo. Partición mensual
también, pero siendo honesto: eso es mantenimiento —archivar con `SWITCH`— más que
velocidad; la velocidad la dan los índices. Y cada índice encarece las cargas; con un
ETL por lotes diarios es aceptable.

### P48 — «¿La consulta reescrita da lo mismo?» *(30 s)*

**Respuesta.** Sí, y el script lo compara columna a columna en cada ejecución. Hay un
detalle de negocio que encontré: la original suma **todos los estados** del mes, no
solo los entregados. Mantuve ese comportamiento para que la reescritura sea
equivalente, y dejé el filtro de ENTREGADO comentado con una nota. Si la intención era
venta neta, es un error de la consulta original y hay que confirmarlo con quien la
pidió.

---

## Bloque 9 · IA y clasificación (7 preguntas)

### P49 — «¿Qué tan bien clasifica la IA?» *(60 s)*

**Se evalúa:** si sabes leer un intervalo de confianza.

**Respuesta.** Sobre las 34 descripciones reales, prácticamente perfecto, pero ese
número no significa nada: son 17 frases base repetidas y las reglas se escribieron
leyéndolas. El número que importa es el del conjunto de generalización, 150 frases
nuevas: la línea base por reglas da **0,627 de exactitud, con intervalo de confianza
al 95 % de 0,547 a 0,700**. Y sobre la partición reservada que uso para probar el
arnés, 0,560 con intervalo 0,423 a 0,688 sobre n = 50. Con un intervalo así de ancho,
**no puedo afirmar** que un método supere al otro.

### P50 — «¿Entonces para qué sirve?» *(45 s)*

**Respuesta.** Para tener una línea base medida y un arnés que permita decidir con
evidencia cuando llegue una muestra real. Lo que no sirve es desplegarlo: las frases
de generalización son **sintéticas**, las escribió una IA, y hay contaminación
declarada —corregí una regla tras ver un error en ese conjunto, así que su 0,627 es
algo optimista—. Para afirmar desempeño necesito tickets nuevos, autorizados y
etiquetados por personas.

### P51 — «¿Por qué no basta la exactitud?» *(60 s)*

**Respuesta.** Porque trata todos los errores igual, y no lo son. Confundir dos tipos
de queja de producto reparte mal el trabajo; mandar un cobro duplicado a la cola de
felicitaciones deja a una persona sin su dinero. Por eso el arnés cuenta **errores
críticos** en tres categorías: dinero mal enrutado, derecho de datos personales
perdido —que en Colombia es obligación legal, no preferencia de atención— y problema
cerrado como felicitación. En la prueba sintética salieron 4 del primero y 1 del
segundo. Y lo marco explícitamente como **propuesta**: quién atiende cada cola y qué
error es inaceptable lo define negocio, no yo.

### P52 — «Publiquemos ya las etiquetas que sacó el modelo.» *(60 s)*

**Se evalúa:** si defiendes una decisión de diseño bajo presión.

**Respuesta.** No se puede, y no por una política que haya que recordar: no hay camino
en el código. `fact_ticket.tipo_caso` se alimenta **solo** de etiquetas en estado
REVISADA, y para importar un lote como revisado hace falta origen humano, dos
anotadores y un motivo. Lo que sale del modelo entra como PROPUESTA y vive en una
columna distinta, `tipo_caso_propuesto`. Si quieren publicarlo, el camino es la
revisión humana de las 34 descripciones, que es una tarde de trabajo. Lo que no voy a
hacer es renombrar una propuesta.

### P53 — «¿Por qué asocias por texto y no por id de ticket?» *(45 s)*

**Respuesta.** Porque hay 2.125 tickets pero solo **34 descripciones distintas**. Si
etiquetara por ticket, el mismo texto podría acabar con dos tipos distintos en dos
tickets, y no habría forma de explicar cuál vale. Etiquetando el texto, la decisión es
única por contenido. El enlace es un hash del texto normalizado —minúsculas, sin
tildes, espacios colapsados— y ese hash lo calculan igual la versión pandas y la de
Spark, con una prueba que lo verifica.

### P54 — «¿Qué le mandas a la API?» *(45 s)*

**Respuesta.** Solo el **texto** de la descripción. Nunca el id de cliente, el id de
pedido ni ninguna otra columna, y hay una prueba que lo verifica inspeccionando los
mensajes enviados. Además, los errores que guardo nunca incluyen el mensaje original
de la excepción, porque puede traer texto, URLs o información de autenticación: se
guarda un código, `TRANSPORTE_TRANSITORIO` o `ERROR_PERMANENTE`.

### P55 — «¿Cuánto cuesta?» *(45 s)*

**Respuesta.** Se clasifica cada texto distinto **una sola vez**: 34 llamadas, no
2.125. El cliente registra latencia y tokens por llamada, incluidos los intentos
fallidos, porque un reintento cuesta igual. Lo que **no** hago es calcular un costo:
sin una tarifa declarada por el proveedor, el informe dice «no calculado» en vez de
inventar un precio. Si me dan la tarifa, la calcula.

---

## Bloque 10 · Liderazgo (6 preguntas)

### P56 — «Revisaste el PR de un junior. Resume.» *(90 s)*

**Respuesta.** Ocho bloqueantes, siete importantes y algunas sugerencias, agrupados
por prioridad y con el porqué de cada uno, porque varios son errores muy comunes.
Los bloqueantes: una contraseña de administrador en el código, que hay que **rotar
hoy** porque ya está en el historial de Git; SQL armado con f-string, que es
inyección; un argumento por defecto mutable que mezcla los pedidos de un canal con los
del siguiente; un total que suma todos los estados mientras el ticket divide por
otros, que es un error de **negocio** y no de estilo; comparar una columna con hora
contra una fecha sin hora, que deja el reporte casi vacío; `DataFrame.append`,
eliminado en pandas 2.0; un `except: pass` que esconde los tres errores anteriores; y
una división por cero cuando no hay pedidos.

**Si insisten: «¿y el comentario más importante?»** El decimoquinto, que no es
bloqueante pero es el que más vale: la consulta lee la tabla cruda de pedidos, no la
tabla certificada. Aunque arregle todo lo demás, su cifra no coincidiría con Power BI,
porque 810 pedidos traen el canal con otra escritura y 295 duplicados se contarían dos
veces. Volveríamos a «cada área con su cifra», que es el problema que el proyecto
existe para resolver.

### P57 — «¿Cómo das esa retroalimentación sin desmotivarlo?» *(45 s)*

**Respuesta.** Empiezo reconociendo lo que está bien, y hay algo real: separó el
cálculo del envío, y esa estructura se conserva en la versión corregida. Agrupo por
prioridad para que sepa qué bloquea y qué es mejora. Explico el **porqué** de cada
punto, no solo el qué, porque varios son errores que cualquiera comete una vez. Y
cierro con una versión corregida y con pruebas, para que vea el destino y no solo la
crítica.

### P58 — «El informe muestra 40 % menos y llegó a presidencia. Son las 7:30.» *(90 s)*

**Respuesta.** Lo primero, antes de diagnosticar: aviso escrito a gerencia y
presidencia de que la cifra está en revisión y que no la usen, con hora de
compromiso —«la confirmo a las 9:30»—. Pauso envíos automáticos y nombro un
responsable y un solo canal. Después diagnostico de la fuente hacia el informe:
comparo contra Gold y el transaccional, reviso el log de la carga, la cuarentena y el
volumen frente al promedio, porque una caída del 40 % suele ser carga parcial. Miro
despliegues y cambios de las últimas 24 horas. Corrijo: revierto el despliegue o
reproceso la carga, que es idempotente, y concilio antes de enviar. Mando la cifra
corregida a los mismos destinatarios con una explicación de dos líneas. Y para que no
vuelva: la compuerta que bloquea la publicación si el volumen cae o no cuadra, más
análisis posterior en 48 horas sin buscar culpables.

**Si insisten: «¿por qué avisar antes de saber qué pasó?»** Porque el daño de una
decisión tomada con una cifra mala es mayor que el de admitir que estás revisando. A
las 7:30 ya hay gente usándola.

### P59 — «Tu desarrollador más antiguo rechaza los estándares.» *(60 s)*

**Respuesta.** Hablo a solas y con curiosidad, reconociendo lo que sabe del negocio.
Separo dos cosas: los estándares se pueden discutir, los dos fallos en producción son
hechos. Los revisamos juntos sin culpas, mirando qué paso los habría detectado. Le doy
un papel donde su experiencia valga: dueño de las pruebas de reglas de negocio.
Dejo claro qué no se negocia —PR, pruebas y revisión antes de producción— y qué sí
—herramientas y forma—. Acordamos 30 días con métricas simples: despliegues fallidos y
reversiones. Y hago que cumplir sea lo fácil con CI automático y rama protegida, para
que no dependa de mi insistencia.

### P60 — «¿Qué estándares pondrías el primer mes?» *(45 s)*

**Respuesta.** Pocos y verificables automáticamente, porque un estándar que depende de
que alguien se acuerde no es un estándar. PR obligatorio con un revisor; pruebas para
toda regla de negocio; CI que corra en cada PR; secretos fuera del código; y una
definición de «listo» que incluya evidencia reproducible. Lo demás se discute.

### P61 — «¿Qué harías distinto si empezaras hoy?» *(45 s)*

**Respuesta.** Dos cosas. Habría escrito el contrato de la fuente antes que el ETL:
casi todas las decisiones difíciles del proyecto —bajas, correcciones tardías,
duplicados— vienen de no tenerlo. Y habría pedido la revisión humana de las etiquetas
al principio, porque es la dependencia que hoy bloquea toda la parte de IA y es de las
más baratas de resolver.

---

## Bloque 11 · Operación, CI y recuperación (6 preguntas)

### P62 — «¿Qué protege el lock?» *(45 s)*

**Respuesta.** Que dos herramientas **de este proyecto** escriban a la vez en la misma
base, en la misma máquina. Se crea de forma exclusiva con el PID y la hora UTC. Lo que
**no** protege: un cliente externo que lo ignore, un entorno distribuido, o dos cargas
que compartan carpeta Bronze con bases distintas. Y una decisión deliberada: no tiene
caducidad automática. Un lock abandonado por un cierre forzado exige diagnóstico
manual, porque expirar solo habilitaría dos escritores, que es peor que estar
bloqueado.

### P63 — «¿Y si se corrompe la base?» *(60 s)*

**Respuesta.** Hay respaldo en frío y restauración, ambos verificados: el respaldo
exige la base cerrada, sin WAL pendiente y sin otro escritor, se copia a un destino
**nuevo** y se abre para comprobar que el total cuadra. La restauración también va a
destino nuevo; nunca reemplaza la base activa en silencio. Con la salvedad: esto
demuestra restauración local del caso, **no** RPO ni RTO, que son objetivos que
todavía no se han acordado.

### P64 — «¿Cómo evitas regresiones?» *(45 s)*

**Respuesta.** 175 pruebas locales y un workflow con dos jobs: el núcleo en Python
3.12 y Spark en 3.11 con Java 17, separados porque tienen requisitos distintos. El job
de Spark **falla si una prueba se omite**, para que una omisión no se lea como un
éxito. Las acciones están fijadas por SHA de commit, no por etiqueta, para que nadie
cambie lo que se ejecuta bajo mis pies. Y la CI verifica que el notebook esté
regenerado desde su código.

### P65 — «Las pruebas de Spark se omiten en tu máquina. ¿Eso no es trampa?» *(45 s)*

**Se evalúa:** si eres honesto cuando la respuesta te incomoda.

**Respuesta.** Sería trampa si lo presentara como aprobado. La suite imprime el motivo
exacto de cada omisión —en Windows, PySpark 3.5 necesita Python 3.11— y la
documentación dice que una omisión no equivale a una prueba aprobada. Por eso hay un
job separado que las ejecuta sin omisiones, y además las corrí localmente con un
entorno de Python 3.11: 24 pruebas aprobadas.

### P66 — «¿El reporte se envía solo?» *(45 s)*

**Respuesta.** No, y hace falta algo más que configurarlo: el transporte por defecto
escribe a una carpeta y no abre ninguna conexión. Para que salga un correo tienen que
darse tres cosas a la vez: destinatarios declarados, una autorización escrita a
propósito, y un transporte SMTP inyectado. Está hecho así para que el camino fácil
nunca sea el que manda correo. El SMTP está escrito y **no ejecutado** contra un
servidor real.

### P67 — «¿Y si el envío falla?» *(45 s)*

**Respuesta.** Depende del fallo. Uno transitorio —tiempo de espera, 503— se reintenta
con espera creciente. Uno permanente —buzón inexistente, credencial rechazada— no se
reintenta: repetirlo no lo arregla y consume la ventana de entrega. Si se agotan los
reintentos queda como FALLIDO, **no** como enviado, así que la corrida siguiente lo
reintenta; lo contrario perdería el reporte en silencio. Y no hay duplicados: la
identidad del reporte es el hash de su **contenido**, así que reintentar no reenvía lo
mismo, pero si el dato cambió sí se envía, porque es otro reporte.

---

## Bloque 12 · Preguntas hostiles y de cierre (3 preguntas)

### P68 — «Todo esto suena sobre-ingenierizado para 19.000 pedidos.» *(60 s)*

**Se evalúa:** si defiendes sin ponerte a la defensiva. La crítica es razonable.

**Respuesta.** Para 19.000 pedidos, sí: con un script de 50 líneas sale la cifra. Pero
no me pidieron la cifra, me pidieron que la empresa pudiera **confiar** en ella, y lo
que resolví son problemas que no dependen del volumen: duplicados lógicos,
correcciones tardías, el mismo indicador con tres definiciones. Eso aparece con 19.000
filas y con 50 millones. Dicho esto, hay partes donde el tamaño sí importa y lo dejé
escrito: la reconstrucción completa de los hechos no escala, y el hash del archivo lee
el fichero entero. Si el volumen creciera, esas dos son las primeras que cambiaría.

### P69 — «¿Qué es lo que más te preocupa de este trabajo?» *(45 s)*

**Respuesta.** Que alguien lea «escrito» como «desplegado». Hay cuatro piezas en ese
estado: T-SQL y DDL en SQL Server, las medidas DAX en Power BI, las celdas Delta en
Fabric o Databricks, y el transporte SMTP. Están escritas con cuidado y revisadas,
pero no ejecutadas, y el día que se ejecuten van a aparecer cosas. Lo segundo que me
preocupa es que las decisiones pendientes —precisión monetaria, contrato de fuente,
umbrales— se queden sin dueño: están parametrizadas, pero un parámetro sin decisión es
una decisión aplazada.

### P70 — «Último minuto: ¿qué necesitas de nosotros?» *(45 s)*

**Respuesta.** Seis decisiones, no seis desarrollos. Precisión monetaria y tratamiento
de devoluciones; el contrato de la fuente, especialmente qué significa que una fila
deje de venir; los umbrales de publicación y los objetivos de recuperación;
destinatarios y horario del reporte; un entorno de prueba con presupuesto acotado para
validar SQL Server o un destino cloud; y una tarde para revisar 34 etiquetas. Cada una
ya tiene su punto de entrada en el código como parámetro. Por eso noventa días para
una cifra en producción es creíble y no es una promesa.

---

## Plan de práctica

| Día | Bloques | Objetivo |
|---|---|---|
| 1 | 1, 2, 3 | Apertura y cifra sin leer. Es lo que más se repite |
| 2 | 4, 5 | ETL e idempotencia; practicar P22 (no es CDC) |
| 3 | 6 | Delta completo. Si P32 no sale fluida, repetir el día siguiente |
| 4 | 7, 8 | DAX y optimización; memorizar los números de P42 y P45 |
| 5 | 9, 10 | IA y liderazgo; P52 en voz alta, es la de presión |
| 6 | 11, 12 | Operación y hostiles; cronometrar |
| 7 | Completo | Seguido, con cronómetro y sin notas |

**Las diez que no puedes fallar:** P1, P2, P5, P12, P15, P22, P32, P33, P49, P52.

Si alguna de esas diez sale ⚠️ o ❌ el día 7, el deck todavía no está listo para
presentarse.
