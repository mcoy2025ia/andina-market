# Storyline del deck para Finanzauto · método McKinsey

> **Quién habla aquí.** Este documento está escrito desde el oficio de un *Engagement
> Manager* formado en la escuela McKinsey: principio de pirámide, títulos de acción,
> MECE, prueba del «¿y qué?» y respeto absoluto por la procedencia del dato. No es una
> afiliación: es un método, y se aplica a un contenido técnico que ya existe y está
> verificado en este repositorio.
>
> **Qué entrega.** El número de láminas, la idea rectora, y el comportamiento exacto
> de cada lámina: qué dice, qué muestra, de qué archivo sale el dato, qué pregunta
> anticipa y cuánto dura.

---

## 1. La respuesta corta: 18 láminas

**Se vende con 18 láminas. Punto.** A eso se añade un apéndice técnico de 14 que
**no se proyecta**: existe para que no improvises cuando alguien pregunte.

| Bloque | Láminas | Minutos | Función |
|---|---|---|---|
| A · Síntesis ejecutiva | 3 | 3 | La respuesta antes que el relato |
| B · Diagnóstico | 4 | 6 | Qué dicen los datos y qué no prueban |
| C · Arquitectura general | 4 | 8 | Cómo se garantiza una sola cifra |
| D · Arquitectura detallada | 5 | 14 | Dónde vive el rigor; es el corazón técnico |
| E · Evidencia, riesgo y plan | 2 | 4 | Qué está probado, qué no, y qué sigue |
| **Deck principal** | **18** | **35** | |
| F · Apéndice técnico | 14 | bajo demanda | Munición para preguntas |

Por qué 18 y no 40: con 40 láminas no hay deck, hay un documento proyectado. Y por
qué no 10: te piden una sustentación **técnica** para un rol de liderazgo de datos;
diez láminas te obligan a saltarte precisamente lo que te están evaluando, que es el
razonamiento de ingeniería. Dieciocho es el punto donde cada lámina sigue teniendo un
mensaje propio y ninguna es relleno.

**Tres recorridos, un solo deck.** No se construyen tres versiones: se marca la ruta.

| Tiempo | Láminas | Cuándo |
|---|---|---|
| 10 min | 1, 2, 3, 6, 8, 10, 14, 17, 18 | Comité, o si te recortan la agenda |
| 25 min | Las 18, saltando D3 y D5 | Entrevista técnica estándar |
| 45 min | Las 18 + apéndice dirigido | Panel técnico con preguntas |

---

## 2. La idea rectora

Todo deck tiene **una** frase que, si el auditorio solo retuviera eso, bastaría. La
tuya:

> **«Una cifra de venta no es un número: es una definición, una cadena de evidencia y
> una compuerta que impide publicarla cuando no cuadra. Las tres están construidas y
> se pueden auditar; lo que falta no es ingeniería, son decisiones de negocio.»**

La pirámide que la sostiene (tres argumentos, MECE):

```
                    Una cifra única, auditable y defendible
                    ya está construida y verificada
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   1. La definición            2. La cadena               3. La compuerta
      es explícita                de evidencia               impide publicar
      y vive en un                reproduce la               lo que no concilia
      solo lugar                  cifra desde el             y lo declara
                                  archivo crudo
        │                           │                           │
   venta neta =                Bronze inmutable →          conciliación por
   bruto − descuento,          Silver con reglas →         día/canal/categoría,
   ENTREGADO,                  Gold recalculado;           no solo por total;
   por fecha_pedido;           hash por fila y por         umbrales configurables;
   mismo SQL en                archivo; recálculo          transacción local y
   4 dialectos + DAX           independiente concilia      puntero de run en Delta
```

**La prueba del «¿y qué?»**: si una lámina no mueve uno de esos tres argumentos,
sale del deck principal y se va al apéndice. Aplica esa tijera sin piedad.

---

## 3. Reglas de artesanía que no se negocian

1. **Título de acción, no de tema.** «Arquitectura de datos» no dice nada. «Dos
   motores, una sola definición: la paridad se verifica en cada corrida» sí.
   Si lees solo los 18 títulos en orden, debe entenderse el argumento completo.
   Esa es la prueba del *ghost deck*: escríbelos antes de diseñar nada.
2. **Un mensaje por lámina.** Si necesitas «y además», es otra lámina.
3. **Procedencia al pie, siempre.** Cada cifra lleva su origen: archivo, tabla y
   fecha de la corrida. En una sustentación técnica, un número sin procedencia es un
   número que no existe.
4. **El dato manda sobre el adorno.** Sin degradados, sin iconos decorativos, sin
   3D. Tinta sobre dato (Tufte) y una sola paleta.
5. **Lo que no sabes va escrito, no insinuado.** La lámina 17 es la que te da
   credibilidad, no la que te la quita.
6. **Nunca leas la lámina.** La lámina es para el que la lee después; tú cuentas
   el porqué.
7. **Anticipa, no reacciones.** Cada lámina de abajo trae la pregunta que provoca y
   dónde está la respuesta.

---

## 4. Bloque A · Síntesis ejecutiva (3 láminas · 3 min)

### Lámina 1 — Portada con tesis

| Campo | Contenido |
|---|---|
| **Título de acción** | «Una cifra, muchas decisiones: la misma definición en SQL, el ETL, el modelo y el tablero» |
| **Mensaje único** | El problema no era calcular; era que todos calcularan lo mismo. |
| **Cuerpo** | Nombre, rol al que aplicas, fecha, y **una sola cifra grande**: COP 14.177.333.600. Debajo, en 10 pt: «19.270 pedidos ENTREGADO · ene 2025–sep 2026 · recalculado de forma independiente». |
| **Procedencia** | `data/warehouse.duckdb` → `gold_venta_neta_diaria`; contraste en `scripts/recalculo_independiente.py` |
| **Anticipa** | «¿Esa cifra de dónde sale?» → la respondes en la lámina 2, no aquí |
| **Tiempo** | 20 s |
| **Trampa** | Hablar de ti. Nadie contrató tu biografía: contrataron que la cifra sea defendible. |

### Lámina 2 — La respuesta, antes del relato

| Campo | Contenido |
|---|---|
| **Título de acción** | «Lo construido está verificado de punta a punta; lo que falta son decisiones de negocio, no ingeniería» |
| **Mensaje único** | Esta es la conclusión. Las 16 láminas siguientes solo la sostienen. |
| **Cuerpo** | Tres columnas, una por brazo de la pirámide. En cada una: el titular, una cifra y el archivo. Franja inferior con tres chips: **Verificado local** · **Escrito, no ejecutado** · **Pendiente de decisión**. |
| **Procedencia** | `docs/ESTADO_IMPLEMENTACION.md` |
| **Anticipa** | «¿Entonces qué me estás pidiendo?» → lámina 18 |
| **Tiempo** | 60 s |
| **Trampa** | Guardar la conclusión para el final. En pirámide, la respuesta va primero; el suspenso es para el cine. |

### Lámina 3 — El mapa del recorrido

| Campo | Contenido |
|---|---|
| **Título de acción** | «Del archivo crudo a la decisión: cinco paradas, y en cada una se puede parar la carga» |
| **Mensaje único** | El recorrido tiene control en cada tramo, no solo al final. |
| **Cuerpo** | Barra horizontal de 5 bloques: Contrato → Bronze → Silver/Cuarentena → Gold/Estrella → Compuerta. Bajo cada uno, **qué garantiza** y **qué lo detiene**. |
| **Procedencia** | `README_ETL.md`, sección «Flujo local» |
| **Anticipa** | «¿Dónde está el control de calidad?» → señalas Silver y la compuerta |
| **Tiempo** | 60 s |
| **Trampa** | Convertirlo en diagrama de cajas y flechas sin verbos. Cada bloque debe decir qué **impide**. |

---

## 5. Bloque B · Diagnóstico (4 láminas · 6 min)

### Lámina 4 — La venta se estabilizó; la mezcla cambió

| Campo | Contenido |
|---|---|
| **Título de acción** | «La venta total se estabiliza desde diciembre de 2025, pero el canal que la sostiene ya no es el mismo» |
| **Cuerpo** | Serie mensual de venta neta (21 meses) con las tres series de canal. Anotar solo dos puntos: dic-2025 (inflexión) y sep-2026 (cierre). |
| **Datos** | 636 días con venta, 7.925 filas Gold al grano día/canal/categoría |
| **Procedencia** | `duckdb/01_ventas_recompra.sql`; CSV en `docs/evidencia/presentacion/ventas_mensuales.csv` |
| **Anticipa** | «¿Por qué cae TIENDA?» → **no lo sabes**, y eso va en la 5 |
| **Tiempo** | 90 s |

### Lámina 5 — Dos señales, cero causas

| Campo | Contenido |
|---|---|
| **Título de acción** | «APP +19,2 % y TIENDA −51,4 % entre junio y septiembre de 2026: el dato describe la diferencia, no la explica» |
| **Mensaje único** | La disciplina de no atribuir causa es parte del entregable. |
| **Cuerpo** | Dos tarjetas grandes con las variaciones. Debajo, el contraste que mata la conclusión fácil: **TIENDA creció +59,8 % en ese mismo intervalo de 2025**. Si el patrón no se repite, no es estacionalidad; y dos años no bastan para descartarla. |
| **Procedencia** | Gold, consulta de solo lectura; cálculo registrado en la evidencia de presentación |
| **Anticipa** | «¿Qué harías entonces?» → investigar TIENDA por ciudad, categoría y operación antes de concluir |
| **Tiempo** | 90 s |
| **Trampa** | Dejar que el auditorio se lleve una causa que tú no afirmaste. Dilo en voz alta: «esto es una señal para investigar, no un hallazgo». |

### Lámina 6 — La retención se deteriora, y eso sí es estructural

| Campo | Contenido |
|---|---|
| **Título de acción** | «La recompra a tres meses cae de 63,2 % a 49,2 % entre cohortes: el problema no es vender, es que vuelvan» |
| **Cuerpo** | Cohortes por año de registro, ventanas 1/3/6 meses. **Mostrar el denominador en la lámina.** |
| **Técnico** | Solo cuenta quien tiene primer pedido ENTREGADO **y ventana completa**: sin control de madurez, las cohortes recientes aparentan peor desempeño por no haber tenido tiempo. |
| **Procedencia** | Segunda consulta de `duckdb/01_ventas_recompra.sql` |
| **Anticipa** | «¿Meses calendario o 90 días?» → calendario, y es una decisión que debe firmarse |
| **Tiempo** | 100 s |

### Lámina 7 — Los errores no desaparecen: se vuelven visibles

| Campo | Contenido |
|---|---|
| **Título de acción** | «1.223 registros aislados con su regla y su fila original: ninguno se borró, ninguno contamina la cifra» |
| **Cuerpo** | Barras horizontales con las seis reglas que más disparan, con sus conteos reales: `DUPLICADO_LOGICO` 639 · `PEDIDO_EN_CUARENTENA` 345 · `ENTREGA_ANTERIOR_A_PEDIDO` 87 · `DESCUENTO_INVALIDO` 74 · `PAGO_HUERFANO` 70 · `VALOR_BRUTO_NO_POSITIVO` 35. Al lado: pedidos 464 aislados de 19.734 (2,35 %), pagos 759 de 20.883 (3,63 %). |
| **Técnico** | Una fila por **(registro, regla)**: un registro con dos problemas aparece dos veces, por eso los totales se cuentan con `COUNT(DISTINCT)`. La fila original se conserva en JSON. |
| **Procedencia** | Tabla `cuarentena`; catálogo en `docs/02_catalogo_calidad.md` |
| **Anticipa** | «¿345 pagos de pedidos rechazados es fraude?» → **no concluyas**: es un hallazgo que se escala a negocio |
| **Tiempo** | 100 s |

---

## 6. Bloque C · Arquitectura general (4 láminas · 8 min)

### Lámina 8 — El principio: una definición, cuatro dialectos

| Campo | Contenido |
|---|---|
| **Título de acción** | «La definición de venta vive en un solo sitio y se replica a cuatro dialectos; cambiarla en uno solo rompe una prueba» |
| **Mensaje único** | La consistencia no se pide por correo: se fuerza con pruebas. |
| **Cuerpo** | `config.py` en el centro. Radios hacia T-SQL, DuckDB, Fabric SQL, Databricks SQL y `medidas.dax`. Sobre cada radio, la prueba que lo vigila. |
| **Técnico** | `ESTADO_VENTA = "ENTREGADO"`, rango 2025-01-01 a 2026-09-30, venta neta = `valor_bruto − descuento` atribuida a `fecha_pedido`. |
| **Procedencia** | `src/shared/andina_etl/config.py`; dialectos en `sqlserver/`, `duckdb/`, `fabric/sql/`, `databricks/sql/` |
| **Anticipa** | «¿Y si negocio cambia la definición?» → lo demuestras en vivo (ver lámina 16) |
| **Tiempo** | 2 min |

### Lámina 9 — Medallion, con una obligación por capa

| Campo | Contenido |
|---|---|
| **Título de acción** | «Cada capa tiene una sola obligación, y por eso se puede auditar por separado» |
| **Cuerpo** | Tres franjas. En cada una: **obligación**, **qué prohíbe**, **cómo se verifica**. |
| **Técnico** | **Bronze**: copia cruda en Parquet, todo texto, versionada por sha256 en `ingest_date=…`. Prohíbe tipar. Se verifica con el manifiesto. **Silver**: tipado y reglas; lee **siempre** de Bronze, nunca del CSV. Prohíbe inventar valores. **Gold**: agregado al grano día/canal/categoría, recalculado **solo** para los días tocados. Prohíbe acumular. |
| **Procedencia** | `bronze.py`, `rules.py`, `store.refrescar_venta_neta` |
| **Anticipa** | «¿Por qué Parquet si el origen es CSV?» → inmutabilidad, tipo columnar y hash estable para detectar el mismo archivo |
| **Tiempo** | 2 min |

### Lámina 10 — Dos motores, una sola verdad

| Campo | Contenido |
|---|---|
| **Título de acción** | «El mismo diseño corre en DuckDB y en Spark/Delta, y 24 pruebas comparan sus resultados fila a fila» |
| **Mensaje único** | La portabilidad no se promete: se prueba. |
| **Cuerpo** | Dos columnas (local / nube) con los mismos cinco pasos enfrentados. En el centro, una barra vertical: «paridad verificada». |
| **Técnico** | Local: pandas + DuckDB, `pip install` y corre. Nube: PySpark + Delta para Fabric o Databricks, notebook **generado** desde el código (`build_notebook.py`), nunca editado a mano. Las pruebas comparan cuarentena por regla, filas válidas, `row_hash` y la estrella completa. |
| **Procedencia** | `tests/test_spark_paridad.py` (5) y `tests/test_spark_extensiones.py` (19) |
| **Anticipa** | «¿Por qué DuckDB y no Spark desde el inicio?» → el caso cabe en memoria; Spark aquí sería coste sin beneficio, y la paridad garantiza el salto cuando haga falta |
| **Tiempo** | 2 min |

### Lámina 11 — El contrato de consumo: modelo estrella

| Campo | Contenido |
|---|---|
| **Título de acción** | «Power BI no consulta el ETL: consulta un modelo estrella con claves estables que no se renumeran entre cargas» |
| **Cuerpo** | Diagrama estrella: `fact_pedido`, `fact_pago`, `fact_venta_neta_diaria`, `fact_ticket` alrededor de `dim_fecha`, `dim_canal`, `dim_categoria`, `dim_cliente`. |
| **Técnico** | Las dimensiones solo **crecen**; una clave emitida nunca cambia, porque si se renumeraran, cualquier informe guardado apuntaría a otra cosa. El calendario cubre **años completos** (DAX necesita el período comparable sin huecos). Cliente `0` = DESCONOCIDO, para no perder pedidos de clientes que aún no llegaron. |
| **Procedencia** | `src/shared/andina_etl/star.py`; DDL en `sqlserver/ddl_tsql.sql` |
| **Anticipa** | «¿Por qué reconstruyes los hechos en cada carga?» → auditabilidad para este volumen; **no** se presenta como carga incremental a escala |
| **Tiempo** | 2 min |

---

## 7. Bloque D · Arquitectura detallada (5 láminas · 14 min)

> Este es el bloque que te están evaluando. Cada lámina resuelve **un modo de fallo
> concreto**. No empieces por la solución: enuncia el fallo, y deja que la solución
> se vea inevitable.

### Lámina 12 — Fallo 1: el archivo cambió y nadie se enteró

| Campo | Contenido |
|---|---|
| **Título de acción** | «Un CSV con la cabecera cambiada detiene la corrida entera antes de tocar Bronze: sus filas ya no significan lo que el proceso cree» |
| **Cuerpo** | Secuencia: archivo → contrato → ✗ detiene / ✓ continúa. Al lado, los cuatro chequeos. |
| **Técnico** | Codificación UTF-8 (BOM permitido), cabecera única y no vacía, columnas requeridas presentes, ancho constante fila a fila. Columnas **extra** no fallan: se conservan en Bronze y se reportan. Un archivo con solo cabecera es válido: deciden las compuertas, no el contrato. Los mensajes de error **nunca** incluyen valores de las filas. |
| **Decisión de diseño** | Un archivo inválido invalida el **archivo**, no la fila. Por eso bloquea la corrida en vez de ir a cuarentena. |
| **Procedencia** | `src/shared/andina_etl/contracts.py`; prueba de rollback en `tests/test_mejoras.py::test_contrato_falla_antes_de_publicar` |
| **Anticipa** | «¿Y si solo cambió el orden de columnas?» → pasa: se valida por nombre, no por posición |
| **Tiempo** | 2,5 min |

### Lámina 13 — Fallo 2: reprocesar duplica, o pierde

| Campo | Contenido |
|---|---|
| **Título de acción** | «Ejecutar dos veces la misma carga inserta cero filas: la idempotencia es una propiedad verificada, no una intención» |
| **Cuerpo** | Tabla de tres columnas: **mecanismo** / **qué problema evita** / **cómo se comprueba**. |
| **Técnico** | • `row_hash` sobre la fila **cruda**: lo idéntico no se reescribe; lo cambiado se reemplaza. • `hash_negocio`: detecta el mismo hecho con otro id (639 duplicados lógicos); gana el que ya está en Silver, y si ninguno está, el de menor id — nunca arbitrario. • Pagos incrementales por watermark sobre `fecha_carga` menos `lookback_dias` = 3. • **La excepción que importa**: los pagos en cuarentena por `PAGO_HUERFANO` o `PEDIDO_EN_CUARENTENA` se releen **siempre**, fuera de ventana; si no, un pago cuyo pedido llega tarde quedaría huérfano para siempre. • Un registro que hoy es inválido **sale** de Silver y su día se recalcula. |
| **Procedencia** | `store.upsert`, `store.pagos_pendientes`, `store.retirar`; verificado en `scripts/verificar_entrega.py` comparando el **hash de los hechos** entre dos cargas |
| **Anticipa** | «¿Eso es CDC?» → **no**. Es incremental en escritura, no en extracción: el snapshot se lee completo y luego se filtra. Dilo tú antes de que lo pregunten. |
| **Tiempo** | 3 min |

### Lámina 14 — Fallo 3: se publica una cifra que no cuadra

| Campo | Contenido |
|---|---|
| **Título de acción** | «La conciliación compara Silver contra Gold fila a fila, no solo el total: dos errores que se compensan no pasan» |
| **Mensaje único** | Comparar totales es el error clásico; aquí se compara el agregado completo. |
| **Cuerpo** | Izquierda: `EXCEPT ALL` en los dos sentidos al grano día/canal/categoría. Derecha: los cuatro umbrales opcionales. |
| **Técnico** | Umbrales **vacíos por defecto, a propósito**: fracción de cuarentena, mínimo de pedidos, venta esperada con tolerancia y frescura. Inventar un umbral sin acordarlo sería fabricar un SLA. Si una compuerta salta, se lanza `PublicacionBloqueada`, la transacción revierte y `publicacion_actual` **sigue apuntando a la carga anterior**. |
| **Procedencia** | `src/shared/andina_etl/operations.py`; `tests/test_mejoras.py::test_gate_rollback_y_ultima_publicacion` |
| **Anticipa** | «¿Quién define los umbrales?» → negocio; está abierto como U08 y así figura en la lámina 17 |
| **Tiempo** | 2,5 min |

### Lámina 15 — Fallo 4: el proceso muere a mitad de la nube

| Campo | Contenido |
|---|---|
| **Título de acción** | «Delta no tiene transacción entre tablas; en vez de fingirla, el consumidor solo ve el run que superó las compuertas» |
| **Mensaje único** | **Esta es tu mejor lámina.** Demuestra que entiendes la diferencia entre una plataforma y otra, no solo la sintaxis. |
| **Cuerpo** | Dos mitades. **Izquierda (DuckDB)**: una transacción abarca Silver, cuarentena, incidencias, watermark, Gold, estrella y publicación. **Derecha (Delta)**: atomicidad solo por tabla → los hechos se escriben con `run_id`; se concilia; y solo entonces se mueve el puntero `publicacion_actual`, que es **una sola escritura**. Los consumidores leen vistas `v_fact_*` filtradas por el run publicado. |
| **Técnico** | Consecuencia honesta que debes decir tú: las tablas de hechos **retienen** filas de runs no publicados hasta su purga, y cada cuánto se purgan es una decisión pendiente. |
| **Procedencia** | `src/shared/spark/extensiones_spark.py`; diseño y 12 escenarios en `docs/08_traslado_delta.md` |
| **Anticipa** | «¿Lo ejecutaste en Fabric?» → **No.** Las funciones `delta_*` usan `MERGE` y no se han corrido. Está probado el cálculo, no la plataforma. |
| **Tiempo** | 3 min |
| **Trampa** | Ceder a la tentación de decir «funciona en Fabric». Si lo dices y te piden la evidencia, pierdes todo el deck. |

### Lámina 16 — Fallo 5: la IA decide sin que nadie lo haya aprobado

| Campo | Contenido |
|---|---|
| **Título de acción** | «Una etiqueta propuesta por un modelo y una decidida por una persona no comparten columna: no hay camino en el código para publicar la primera como validada» |
| **Cuerpo** | Flujo: texto → clasificador → `tipo_caso_propuesto` (PROPUESTA) ⟶ **revisión humana** ⟶ `tipo_caso` (REVISADA). La puerta entre ambos estados, resaltada. |
| **Técnico** | Importación por lote **versionado**, con validación de taxonomía (17 tipos + `otro`) y de **procedencia**: un lote `REVISADA` exige origen humano, dos anotadores y motivo. Asociación por hash del texto normalizado, no por `id_ticket`: 2.125 tickets contienen solo 34 descripciones distintas. Evaluación con **intervalo de Wilson**, matriz de confusión y **errores críticos** por consecuencia (dinero mal enrutado, derecho de datos perdido, problema cerrado como felicitación). |
| **Procedencia** | `andina_etl/etiquetas.py`, `tickets_ia/evaluacion.py`, `docs/07_clasificacion_ia.md` |
| **Anticipa** | «¿Qué exactitud tiene?» → 0,560 con IC 95 % 0,423–0,688 sobre muestra **sintética** de n=50; con ese intervalo **no se puede afirmar** que supere a las reglas |
| **Tiempo** | 3 min |

---

## 8. Bloque E · Evidencia, riesgo y plan (2 láminas · 4 min)

### Lámina 17 — La lámina roja

| Campo | Contenido |
|---|---|
| **Título de acción** | «Lo que no ejecuté, dicho antes de que me lo pregunten» |
| **Mensaje único** | Esta lámina **compra** tu credibilidad para las otras 17. |
| **Cuerpo** | Dos columnas, visualmente simétricas, sin disculpas. **Verificado**: 175 pruebas locales; 24 con PySpark real; carga completa del caso reproducida; segunda carga sin cambios en los hechos; recálculo independiente con pandas conciliado; CI en GitHub Actions; 102 páginas de PDF auditadas. **Escrito y no ejecutado**: T-SQL y DDL en SQL Server; medidas DAX en Power BI; `MERGE`/`DELETE` de Delta en Fabric o Databricks; transporte SMTP del reporte. |
| **Procedencia** | `docs/ESTADO_IMPLEMENTACION.md` |
| **Anticipa** | Desarma la pregunta hostil antes de que exista |
| **Tiempo** | 2 min |
| **Trampa** | Pedir perdón. No es una disculpa: es el criterio con el que trabajas. Dilo con el mismo tono que la lámina 2. |

### Lámina 18 — Qué necesito de ustedes

| Campo | Contenido |
|---|---|
| **Título de acción** | «Noventa días para una cifra en producción; el camino crítico son seis decisiones, no seis desarrollos» |
| **Cuerpo** | Línea de tiempo 30/60/90 arriba. Abajo, **las decisiones pendientes con dueño**: precisión monetaria y devoluciones · contrato de fuente (snapshot o incremento, y qué significa una ausencia) · umbrales y RPO/RTO · destinatarios y horario del reporte · entorno de prueba y presupuesto · revisión humana de las etiquetas. |
| **Técnico** | Cada decisión ya tiene su punto de entrada en el código como parámetro, no como supuesto escondido. Esa es la razón por la que 90 días es creíble. |
| **Procedencia** | `docs/PENDIENTES_ACTUALES.md`, secciones 3 y 4 |
| **Anticipa** | «¿Cuándo tenemos esto andando?» → depende de ellos, y queda demostrado por qué |
| **Tiempo** | 2 min |

---

## 9. Bloque F · Apéndice técnico (14 láminas, no proyectadas)

Se abren **solo** si preguntan. Una lámina, una pregunta.

| # | Lámina | Se abre cuando preguntan |
|---|---|---|
| A1 | SQL de venta y recompra, los 4 dialectos lado a lado | «¿Es el mismo SQL de verdad?» |
| A2 | Meses sin ventas y el calendario completo | «¿Qué pasa si un mes no tiene filas?» |
| A3 | Catálogo de las 15 reglas de calidad con su tratamiento | «¿Qué más detectaste?» |
| A4 | Parseo monetario exacto: enteros, sin pasar por `double` | «¿Y los decimales?» |
| A5 | Medidas DAX y el período comparable | «¿Cómo comparas ene–sep contra ene–sep?» |
| A6 | Optimización: CAST en la columna indexada y rangos | «¿Cómo optimizarías esa consulta?» |
| A7 | Evidencia del experimento en SQLite y su límite | «¿Lo mediste?» |
| A8 | Notebook Delta: las 13 celdas y qué hace cada una | «Enséñame el notebook» |
| A9 | Los 12 escenarios de validación cloud (E04) | «¿Cómo sabrías que funciona en Fabric?» |
| A10 | Recuperación: lock, respaldo en frío, restauración verificada | «¿Y si se corrompe la base?» |
| A11 | CI: dos jobs, acciones fijadas por SHA, evidencia versionada | «¿Cómo evitas regresiones?» |
| A12 | Reporte: identidad por contenido, reintentos, sin duplicados | «¿Y si el correo falla?» |
| A13 | Revisión del PR de la parte 3: los 8 bloqueantes | «¿Cómo revisas código de tu equipo?» |
| A14 | Taxonomía de tickets y los errores críticos por consecuencia | «¿Por qué esos tipos y no otros?» |

---

## 10. Traducción al negocio de Finanzauto

> **Advertencia de método.** Lo que sigue es una **hipótesis de traducción**, no un
> hallazgo. No la presentes como conocimiento de su operación: preséntala como la
> pregunta que abre la conversación. Si te equivocas en su negocio delante de ellos,
> pierdes más de lo que ganas con la analogía.

El caso es retail; ellos financian vehículos. El puente no está en el dominio, está
en **la clase de problema**, y por eso es sólido:

| En el caso | La clase de problema | Dónde aparece en financiación de vehículos |
|---|---|---|
| Venta neta con tres definiciones en circulación | Un indicador sin dueño ni definición única | Originación, desembolso y cartera medidos distinto por área |
| 639 duplicados lógicos con distinto id | El mismo hecho registrado dos veces | Un mismo pago aplicado por dos canales de recaudo |
| 345 pagos de pedidos rechazados | Movimiento de dinero contra un hecho que no existe | Recaudo contra un crédito anulado o reestructurado |
| Pagos tardíos fuera de la ventana | Corrección que llega después del cierre | Reversos y reaplicaciones posteriores al corte |
| Ausencia ≠ baja | El contrato de la fuente no está escrito | Una obligación que deja de venir en el archivo, ¿se canceló o falló la extracción? |
| Compuerta que bloquea publicación | No publicar lo que no concilia | Indicadores de cartera antes de comité |

**Cómo usarlo en vivo:** una sola frase en la lámina 2, sin lámina propia. *«El caso
es de retail, pero los cinco modos de fallo que resolví son los mismos que aparecen
cuando el dato es de cartera; si quieren, lo aterrizamos a su operación.»* Y sigues.

---

## 11. Cómo se comporta el deck en vivo

- **Primeros 30 segundos.** Da la conclusión. Si te interrumpen en el minuto 2, ya
  dijiste lo importante.
- **Transiciones habladas, no escritas.** Entre bloques, una frase: *«Eso es lo que
  dicen los datos. Ahora, cómo se garantiza que digan lo mismo mañana.»*
- **La lámina 15 es el examen.** Si entienden que resolviste una diferencia real
  entre plataformas y no copiaste sintaxis, el puesto está ganado ahí.
- **Si te piden un cambio en vivo**, tienes ensayo ejecutable:
  `python scripts/ensayar_cambio.py` añade el canal MARKETPLACE sobre datos y base
  temporales, recalcula y verifica un incremento exacto de 90.000, sin tocar los
  originales. Enséñalo corriendo, no en una lámina.
- **Si no sabes algo**, la respuesta es: *«No lo verifiqué. Para afirmarlo
  necesitaría X.»* Es, literalmente, el criterio que defiende todo el deck.
- **Cierre.** Vuelve a la lámina 2. El último minuto repite la conclusión del
  primero; en el medio solo estuvo la evidencia.

---

## 12. Lista de verificación antes de presentar

- [ ] Los 18 títulos de acción, leídos seguidos, cuentan el argumento sin el cuerpo
- [ ] Ninguna lámina tiene dos mensajes
- [ ] Toda cifra lleva archivo, tabla y fecha de corrida al pie
- [ ] La lámina 17 está escrita antes que las demás, no al final
- [ ] Ningún verbo en pasado sobre algo que no se ejecutó
- [ ] Las tres rutas (10/25/45 min) marcadas en las notas del presentador
- [ ] El ensayo en vivo corre en una terminal ya abierta y probada
- [ ] Los PDF exportados y revisados página a página (`scripts/qa_impresion.py --pdf`)
- [ ] Cada lámina del apéndice tiene su pregunta disparadora anotada

---

### Fuentes de este documento

Todas las cifras salen del repositorio y de la corrida del **1 de noviembre de 2026**:
`data/warehouse.duckdb` (tablas `gold_venta_neta_diaria`, `cuarentena`,
`silver_tickets`), `docs/ESTADO_IMPLEMENTACION.md`, `docs/PENDIENTES_ACTUALES.md`,
`docs/02_catalogo_calidad.md`, `docs/07_clasificacion_ia.md` y
`docs/08_traslado_delta.md`. Nada en este storyline afirma una ejecución que el
repositorio no respalde.
