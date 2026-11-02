# Storyline del deck para Finanzauto · panel técnico

> **El panel.** Cuatro oficios revisaron este deck. El *Engagement Manager* es dueño de
> la estructura; los otros tres son dueños del contenido técnico y **tienen derecho de
> veto sobre lo que se afirma en su área**. Donde discreparon, la discrepancia está
> escrita: un deck que esconde el desacuerdo interno se cae en la primera pregunta.
>
> | | Oficio | De qué responde aquí |
> |---|---|---|
> | **EM** | Engagement Manager, escuela McKinsey | Pirámide, títulos de acción, recorte, prueba del «¿y qué?» |
> | **AD** | Arquitecta de datos | Modelo dimensional, contratos de dato, gobierno, corrección temporal |
> | **IF** | Ingeniero de datos · Fabric y Databricks | Plataforma, Delta, Unity Catalog, serverless, CI/CD de datos |
> | **FO** | FinOps | Modelo de costo, palancas, *unit economics*, licenciamiento |
>
> Ninguno de los cuatro afirma nada que el repositorio no respalde. Lo que no se
> ejecutó aparece marcado como tal, también cuando incomoda.

---

## 1. La discusión de encuadre

**EM.** Mi primera versión tenía 18 láminas. Sostengo el principio: con 40 no hay
deck, hay un documento proyectado.

**AD.** Y con 18 no explicas el problema real. El caso es retail —un pedido es un
evento que ocurre y se cierra—. Finanzauto no vende pedidos: origina **contratos que
viven años y cambian de estado**. Esa diferencia no es de dominio, es de **modelo de
datos**, y cambia los tipos de hecho, la dimensionalidad y la noción de «la verdad a
una fecha». Si eso no está en el deck, el deck no les habla a ellos.

**IF.** Lo mismo por mi lado. «Lo llevamos a la nube» no es una afirmación técnica.
Fabric y Databricks resuelven el problema de publicación de forma **distinta**, y
una de las dos lo resuelve mejor para este caso concreto. Si no lo dices, pareces
alguien que no ha operado ninguna de las dos.

**FO.** Y yo añado la pregunta que siempre llega y que nadie prepara: *«¿cuánto
cuesta esto al mes?»*. Los dos modelos de costo son **estructuralmente distintos**
—capacidad reservada contra consumo medido— y eso cambia la decisión de arquitectura,
no solo la factura.

**EM.** Acepto las tres, con una condición: cada lámina nueva tiene que mover uno de
los tres brazos de la pirámide. Nada se añade «porque es interesante».

### Veredicto: 24 láminas principales + 18 de apéndice

| Bloque | Láminas | Min | Dueño |
|---|---|---|---|
| A · Síntesis ejecutiva | 3 | 3 | EM |
| B · Diagnóstico del caso | 4 | 6 | EM |
| **C · De retail a financiación** | **3** | **7** | **AD** |
| D · Arquitectura general | 4 | 8 | AD + IF |
| E · Arquitectura detallada | 6 | 17 | IF |
| **F · Plataforma y costo** | **2** | **7** | **IF + FO** |
| G · Cierre | 2 | 4 | EM |
| **Deck principal** | **24** | **52** | |
| H · Apéndice técnico | 18 | bajo demanda | todos |

**Tres recorridos, un solo deck.** No se construyen tres versiones: se marca la ruta.

| Tiempo | Láminas | Cuándo |
|---|---|---|
| 10 min | 1, 2, 8, 11, 18, 21, 23, 24 | Comité o agenda recortada |
| 30 min | Todas menos 6, 16, 19, 20 | Entrevista técnica estándar |
| 50 min | Las 24 + apéndice dirigido | Panel técnico con preguntas |

---

## 2. La idea rectora

> **«Una cifra no es un número: es una definición, una cadena de evidencia y una
> compuerta que impide publicarla cuando no cuadra. Las tres están construidas y se
> pueden auditar. Lo que falta no es ingeniería: son decisiones de negocio y un
> entorno donde ejecutarlo.»**

```
                 Una cifra única, auditable y defendible,
                 ya construida y verificada
                                 │
     ┌───────────────────────────┼───────────────────────────┐
1. La definición            2. La cadena de             3. La compuerta
   es explícita                evidencia reproduce         impide publicar
   y vive en un                la cifra desde el           lo que no concilia
   solo lugar                  archivo crudo               y lo declara
     │                           │                           │
 config.py → 4 dialectos    Bronze inmutable →          conciliación por día,
 SQL + DAX; una prueba      Silver con reglas →         canal y categoría;
 por radio                  Gold recalculado;           no solo por total;
                            sha256 por archivo          puntero de run en Delta
                            y por fila
```

**AD, sobre la pirámide.** Los tres brazos son correctos para el caso. Para
Finanzauto falta un cuarto que no se añade como brazo sino que **atraviesa** los
tres: *la verdad a una fecha*. En retail, la venta de marzo es la venta de marzo
para siempre. En cartera, el saldo de marzo **cambia** cuando en abril entra un pago
retroactivo o una reestructuración. Eso no es un detalle: es lo que obliga a decidir
si el almacén responde «lo que sabemos hoy» o «lo que sabíamos entonces». Va en la
lámina 10.

---

## 3. Reglas de artesanía (EM)

1. **Título de acción, no de tema.** Leídos en orden, los 24 títulos deben contar el
   argumento completo sin el cuerpo. Es la prueba del *ghost deck*.
2. **Un mensaje por lámina.** Si necesitas «y además», es otra lámina.
3. **Procedencia al pie, siempre**: archivo, tabla y fecha de corrida.
4. **Lo que no sabes va escrito**, no insinuado. La lámina 23 compra la credibilidad
   de las otras 23.
5. **Nunca leas la lámina.** La lámina es para quien la lee después.
6. **Ninguna cifra de plataforma sin fuente.** *(FO)* Si dices un precio, di de dónde
   sale y de qué fecha es. Las tarifas cambian y la región importa.
7. **Verbo en pasado solo para lo ejecutado.** *(IF)* «Implementé» ≠ «desplegué».

---

## 4. Bloque A · Síntesis ejecutiva (3 láminas · 3 min)

### Lámina 1 — Portada con tesis
**Título de acción:** «Una cifra, muchas decisiones: la misma definición en SQL, el
ETL, el modelo y el tablero».
**Cuerpo:** nombre, rol, fecha y **una sola cifra grande**: COP 14.177.333.600. Al
pie, en 10 pt: «16.855 pedidos ENTREGADO de 19.270 válidos · ene 2025–sep 2026 ·
recalculado de forma independiente».
**Procedencia:** `gold_venta_neta_diaria`; contraste en `scripts/recalculo_independiente.py`.
**Tiempo:** 20 s. **Trampa:** hablar de ti. Contrataron que la cifra sea defendible.

### Lámina 2 — La respuesta, antes del relato
**Título de acción:** «Lo construido está verificado de punta a punta; lo que falta
son decisiones de negocio y un entorno, no ingeniería».
**Cuerpo:** tres columnas, una por brazo de la pirámide, cada una con su cifra y su
archivo. Franja inferior con tres chips: **Verificado local** · **Escrito, no
ejecutado** · **Pendiente de decisión**.
**Tiempo:** 60 s. **Trampa:** guardar la conclusión para el final.

### Lámina 3 — El mapa del recorrido
**Título de acción:** «Del archivo crudo a la decisión: cinco paradas, y en cada una
se puede detener la carga».
**Cuerpo:** barra de 5 bloques —Contrato → Bronze → Silver/Cuarentena → Gold/Estrella
→ Compuerta—. Bajo cada uno, **qué garantiza** y **qué lo detiene**.
**Tiempo:** 60 s. **Trampa:** cajas y flechas sin verbos. Cada bloque dice qué *impide*.

---

## 5. Bloque B · Diagnóstico del caso (4 láminas · 6 min)

### Lámina 4 — La venta se estabilizó; la mezcla cambió
**Título:** «La venta total se estabiliza desde diciembre de 2025, pero el canal que
la sostiene ya no es el mismo».
**Cuerpo:** serie mensual (21 meses) con las tres series de canal. Solo dos
anotaciones: dic-2025 (inflexión) y sep-2026 (cierre). Reparto: APP 42,8 %, WEB
32,5 %, TIENDA 24,7 %.
**Datos:** 636 días con venta; 7.925 filas Gold al grano día/canal/categoría.
**Tiempo:** 90 s.

### Lámina 5 — Dos señales, cero causas
**Título:** «APP +19,2 % y TIENDA −51,4 % entre junio y septiembre de 2026: el dato
describe la diferencia, no la explica».
**Cuerpo:** dos tarjetas con las variaciones y, debajo, el contraste que mata la
conclusión fácil: **TIENDA creció +59,8 % en ese mismo intervalo de 2025**.
**Tiempo:** 90 s. **Trampa:** dejar que se lleven una causa que no afirmaste.

### Lámina 6 — La retención se deteriora, y eso sí es estructural
**Título:** «La recompra a tres meses cae de 63,2 % a 49,2 % entre cohortes: el
problema no es vender, es que vuelvan».
**Técnico:** solo cuenta quien tiene primer pedido ENTREGADO **y ventana completa**;
sin control de madurez las cohortes recientes aparentan peor desempeño. La caída se
sostiene con dos denominadores distintos (60,9 % → 46,4 % con todos los registrados).
**Tiempo:** 100 s.

### Lámina 7 — Los errores no desaparecen: se vuelven visibles
**Título:** «1.223 registros aislados con su regla y su fila original: ninguno se
borró, ninguno contamina la cifra».
**Cuerpo:** barras con las reglas que más disparan, con conteos reales:
`DUPLICADO_LOGICO` 295 pedidos y 344 pagos · `PEDIDO_EN_CUARENTENA` 345 ·
`ENTREGA_ANTERIOR_A_PEDIDO` 87 · `DESCUENTO_INVALIDO` 74 · `PAGO_HUERFANO` 70 ·
`VALOR_BRUTO_NO_POSITIVO` 35 · `FECHA_FUERA_DE_RANGO` 20.
**Técnico:** una fila por **(registro, regla)**. Hay 47 pedidos que incumplen dos
reglas, por eso 511 violaciones sobre 464 registros y por eso se cuenta con
`COUNT(DISTINCT)`.
**Tiempo:** 100 s.

---

## 6. Bloque C · De retail a financiación · **dueña: AD** (3 láminas · 7 min)

> **AD.** Este bloque es el que convierte un ejercicio de retail en una conversación
> con ellos. Y hay que decirlo con una advertencia al frente: **no conozco su
> operación**. Lo que traigo no es conocimiento de su negocio, es una afirmación sobre
> modelado de datos que es cierta para cualquier cartera de crédito. Si me equivoco en
> su caso, que me corrijan: la conversación ya vale.

### Lámina 8 — La figura cambia: de evento a contrato vivo

| Campo | Contenido |
|---|---|
| **Título de acción** | «Un pedido es un evento que se cierra; un crédito es un contrato que vive años y cambia de estado: eso cambia el modelo, no solo los nombres» |
| **Mensaje único** | La arquitectura que construí sirve; el **modelo dimensional** necesita dos tipos de hecho más. |
| **Cuerpo** | Dos líneas de tiempo enfrentadas. Arriba, retail: `pedido → entrega → fin`. Abajo, financiación: `originación → desembolso → N cuotas → mora → reestructuración → prepago o castigo → recuperación`, con el saldo cambiando bajo la línea. |
| **Lo que se conserva** | Las cinco garantías del caso no dependen del dominio: contrato de archivo, cuarentena con la fila original, idempotencia por hash, conciliación al grano y compuerta de publicación. |
| **Lo que no basta** | Un único hecho transaccional. Un crédito no se describe con el evento que lo originó. |
| **Anticipa** | «¿Entonces tu trabajo no nos sirve?» → sirve la **plataforma**; el modelo se amplía, y en la siguiente lámina está cómo |
| **Tiempo** | 2,5 min |
| **Trampa** | Inventar detalles de su operación. Habla de clases de problema, no de sus sistemas. |

### Lámina 9 — Los tres tipos de hecho que exige una cartera

| Campo | Contenido |
|---|---|
| **Título de acción** | «Una cartera necesita tres granos simultáneos, y hoy el modelo solo tiene uno» |
| **Cuerpo** | Tabla de tres filas con el tipo de hecho, su grano, la pregunta que responde y su equivalente en lo ya construido. |

| Tipo de hecho (Kimball) | Grano | Pregunta que responde | En el caso hoy |
|---|---|---|---|
| **Transaccional** | Un movimiento: desembolso, cuota, pago, nota | «¿Qué pasó y cuándo?» | `fact_pedido`, `fact_pago` — **existe** |
| **Snapshot periódico** | Un contrato × un cierre (día o mes) | «¿Cuál era el saldo, la mora y la calificación al cierre de marzo?» | **no existe**; es lo que falta para cartera |
| **Snapshot acumulado** | Un contrato, con hitos que se van rellenando | «¿Cuánto tarda de solicitud a desembolso, y dónde se atasca?» | **no existe**; es el embudo de originación |

**AD, lo técnico que debe decirse en voz alta.** El snapshot periódico **no** se
reconstruye sumando movimientos: hay que materializarlo, porque los ajustes
retroactivos reescribirían el pasado. Es la tabla más grande del almacén —contratos ×
cierres— y la que obliga a particionar por fecha de cierre y a decidir retención.
Además, la dimensión del contrato necesita **SCD tipo 2**: una reestructuración cambia
plazo, tasa y cuota, y si se sobrescribe, los informes históricos se vuelven falsos
sin fallar.

**Lo que ya está resuelto y se traslada tal cual:** la idempotencia por `row_hash`
funciona igual sobre un snapshot; la cuarentena con la fila original es más valiosa
aún cuando el registro es regulatorio; y la compuerta de conciliación es exactamente
lo que impide publicar un cierre de cartera descuadrado.

**Tiempo:** 2,5 min.

### Lámina 10 — La verdad a una fecha

| Campo | Contenido |
|---|---|
| **Título de acción** | «"¿Cuál era la mora en marzo?" tiene dos respuestas correctas, y el almacén debe saber cuál está dando» |
| **Mensaje único** | En cartera, el pasado cambia. Decidir cómo se registra ese cambio es una decisión de arquitectura, no de reporte. |
| **Cuerpo** | Un ejemplo, no un concepto. Marzo cierra con una obligación en mora. En abril entra un pago con fecha valor de marzo. Dos respuestas: *«la mora de marzo fue X»* (lo que sabíamos entonces, el cierre publicado y reportado) y *«la mora de marzo fue Y»* (lo que sabemos hoy, ya corregido). **Las dos son correctas; mezclarlas no.** |
| **Técnico** | Se resuelve con dos marcas de tiempo por fila: cuándo ocurrió el hecho y cuándo lo supo el sistema. El cierre publicado se congela y se versiona; las correcciones posteriores se registran como ajustes con su fecha de conocimiento, nunca sobrescribiendo. Es la misma disciplina del proyecto —no borrar, aislar y versionar— aplicada al eje temporal. |
| **Puente con lo construido** | El caso ya tiene la mitad: Bronze es inmutable y versionado por sha256, y `publicacion_actual` congela qué corrida es la vigente. Lo que falta es la segunda marca de tiempo en los hechos. |
| **Anticipa** | «¿Eso no complica todo?» → complica el modelo y **simplifica** las auditorías; sin eso, una diferencia con un reporte regulatorio no se puede explicar |
| **Tiempo** | 2 min |

> **FO, interviene aquí.** Esa tabla de snapshot periódico es la que va a dominar la
> factura: contratos × cierres diarios crece rápido. Antes de construirla hay que
> decidir si el cierre es diario o mensual, y cuánta historia se conserva en caliente.
> Es una decisión de **costo** disfrazada de decisión de modelo. Va en la lámina 22.

---

## 7. Bloque D · Arquitectura general (4 láminas · 8 min)

### Lámina 11 — Una definición, cuatro dialectos
**Título:** «La definición de venta vive en un solo sitio y se replica a cuatro
dialectos de SQL y a DAX; cambiarla en uno solo rompe una prueba».
**Cuerpo:** `config.py` en el centro, radios a T-SQL, DuckDB, Fabric SQL, Databricks
SQL y `medidas.dax`. Sobre cada radio, la prueba que lo vigila.
**Técnico:** `ESTADO_VENTA = "ENTREGADO"`, rango 2025-01-01 a 2026-09-30, venta neta =
`valor_bruto − descuento` atribuida a `fecha_pedido`.
**Tiempo:** 2 min.

### Lámina 12 — Medallion, con una obligación por capa
**Título:** «Cada capa tiene una sola obligación, y por eso se puede auditar por
separado».
**Técnico:** **Bronze** copia cruda en Parquet, todo texto, versionada por sha256;
prohíbe tipar. **Silver** tipa y aplica reglas; lee siempre de Bronze, nunca del CSV;
prohíbe inventar valores. **Gold** agrega al grano día/canal/categoría y se recalcula
**solo** para los días tocados; prohíbe acumular.

> **AD.** Añade una frase que suele faltar: *«Bronze no es un volcado, es un
> **contrato de evidencia**»*. Si mañana el origen cambia o desaparece, Bronze permite
> reconstruir y, sobre todo, **demostrar** qué llegó. En un negocio regulado eso deja
> de ser higiene y pasa a ser requisito.

**Tiempo:** 2 min.

### Lámina 13 — Dos motores, una sola verdad
**Título:** «El mismo diseño corre en DuckDB y en Spark/Delta, y 24 pruebas comparan
sus resultados fila a fila».
**Técnico:** local pandas + DuckDB, corre con `pip install`. Nube PySpark + Delta,
notebook **generado** desde el código (`build_notebook.py`), nunca editado a mano; la
CI falla si se desincronizan. Las pruebas comparan cuarentena por regla, filas
válidas, `row_hash` y la estrella completa, con **modo ANSI de Spark activado**, que es
el más estricto.
**Anticipa:** «¿Por qué DuckDB y no Spark?» → el caso cabe en memoria; Spark aquí sería
coste sin beneficio, y la paridad garantiza el salto cuando el volumen lo justifique.
**Tiempo:** 2 min.

### Lámina 14 — El contrato de consumo
**Título:** «Power BI no consulta el ETL: consulta un modelo estrella con claves
estables que no se renumeran entre cargas».
**Técnico:** las dimensiones solo **crecen**; una clave emitida nunca cambia, porque un
informe guardado contra `canal_key = 3` seguiría apuntando a 3. Hay una prueba
dedicada. El calendario cubre **años completos** porque `DATEADD` lo exige. Cliente `0`
= DESCONOCIDO, para no perder venta por un hueco en la dimensión.
**Tiempo:** 2 min.

---

## 8. Bloque E · Arquitectura detallada · **dueño: IF** (6 láminas · 17 min)

> **IF.** Cada lámina resuelve **un modo de fallo concreto**. No empieces por la
> solución: enuncia el fallo y deja que la solución parezca inevitable. Y una regla
> mía: si en algún momento suena a folleto de producto, lo has perdido.

### Lámina 15 — Fallo 1: el archivo cambió y nadie se enteró
**Título:** «Un CSV con la cabecera cambiada detiene la corrida antes de tocar Bronze:
sus filas ya no significan lo que el proceso cree».
**Técnico:** UTF-8 con BOM permitido, cabecera única y no vacía, columnas requeridas,
ancho constante. Columnas **extra** no fallan: se conservan en Bronze y se reportan.
Cabecera válida sin filas es admisible; deciden las compuertas. Los mensajes de error
**nunca** incluyen valores de las filas.
**Decisión:** un archivo inválido invalida el **archivo**, no la fila; por eso bloquea
en vez de ir a cuarentena.
**Tiempo:** 2,5 min.

### Lámina 16 — Fallo 2: reprocesar duplica, o pierde
**Título:** «Ejecutar dos veces la misma carga inserta cero filas: la idempotencia es
una propiedad verificada, no una intención».
**Técnico:** `row_hash` sobre la fila cruda; `hash_negocio` para el mismo hecho con
distinto id, con desempate determinista —gana el que ya está en Silver, si no el de
menor id—; watermark sobre `fecha_carga` menos 3 días; y la excepción que importa: los
pagos en cuarentena por `PAGO_HUERFANO` o `PEDIDO_EN_CUARENTENA` se releen **siempre**,
fuera de ventana. Verificado comparando el **hash sha256 de las tablas de hechos**
entre dos cargas.
**Anticipa:** «¿Eso es CDC?» → **no**; es incremental en escritura, no en extracción.
Dilo tú antes.
**Tiempo:** 3 min.

### Lámina 17 — Fallo 3: se publica una cifra que no cuadra
**Título:** «La conciliación compara Silver contra Gold fila a fila, no solo el total:
dos errores que se compensan no pasan».
**Técnico:** `EXCEPT ALL` en los dos sentidos al grano día/canal/categoría. Cuatro
umbrales **vacíos por defecto a propósito** —fracción de cuarentena, mínimo de pedidos,
venta esperada con tolerancia, frescura—: inventar un umbral sin acordarlo sería
fabricar un SLA. Si salta, `PublicacionBloqueada`, la transacción revierte y
`publicacion_actual` sigue apuntando a la carga anterior.
**Tiempo:** 2,5 min.

### Lámina 18 — Fallo 4: el proceso muere a mitad, en la nube

| Campo | Contenido |
|---|---|
| **Título de acción** | «Delta no tiene transacción entre tablas; en vez de fingirla, el consumidor solo ve el run que superó las compuertas» |
| **Mensaje único** | **Tu mejor lámina.** Demuestra que entiendes la diferencia entre plataformas, no solo la sintaxis. |
| **Cuerpo** | Dos mitades. **DuckDB**: una transacción abarca Silver, cuarentena, incidencias, watermark, Gold, estrella y publicación. **Delta**: atomicidad solo por tabla → hechos escritos con `run_id`; conciliación; y solo entonces se mueve el puntero `publicacion_actual`, que es **una sola escritura**. Los consumidores leen vistas `v_fact_*` filtradas por el run publicado. |
| **Coste honesto** | Las tablas de hechos **retienen** filas de runs no publicados hasta su purga. Cada cuánto se purgan es una decisión de retención que no he tomado. |

> **IF, el matiz que vale la pregunta.** Hay una salida que conviene conocer y que
> cambia la recomendación de plataforma: **Fabric Warehouse sí soporta transacciones
> multi-tabla en T-SQL**. Si el destino fuera Warehouse y no Lakehouse, el patrón del
> puntero sobraría y se usaría una transacción real, como en local. Lo digo marcado
> como **a verificar en el destino**: no lo he ejecutado. Pero es exactamente el tipo
> de decisión que distingue elegir plataforma de elegir logo.

**Anticipa:** «¿Lo ejecutaste en Fabric?» → **No.** `MERGE`, `DELETE` y
`DESCRIBE HISTORY` están escritos con sintaxis estándar y no se han corrido. Está
probado el **cálculo**, no la plataforma. Los 12 escenarios de validación están en
`docs/08_traslado_delta.md`.
**Tiempo:** 3,5 min. **Trampa:** cualquier matiz que suene a «pero debería funcionar».

### Lámina 19 — Gobierno: quién ve qué, y cómo se demuestra

| Campo | Contenido |
|---|---|
| **Título de acción** | «En un negocio regulado, el permiso no es una casilla: es una columna enmascarada, un filtro de fila y un registro de quién consultó qué» |
| **Cuerpo** | Tres niveles, de grueso a fino, con el mecanismo de cada uno. |

**IF, el detalle técnico por plataforma.**

| Nivel | En Databricks (Unity Catalog) | En Fabric |
|---|---|---|
| Acceso al objeto | `USE CATALOG` → `USE SCHEMA` → `SELECT`, concedido en el *securable* más estrecho que funcione; propiedad con `ALTER … OWNER TO` | Permisos de workspace y de elemento; OneLake con control por ruta |
| Fila y columna | **Row filters** y **column masks** sobre la tabla; vistas dinámicas con `current_user()` e `is_account_group_member()` | Seguridad a nivel de fila en el modelo semántico y en el SQL endpoint |
| Evidencia | `system.access.audit` (quién, qué, cuándo), `system.access.table_lineage` (linaje incluso a nivel de columna) | Registro de actividad y linaje del workspace |

**Por qué importa aquí.** El dato del caso ya trae documentos de identidad y
descripciones escritas por clientes. El proyecto toma dos decisiones en esa línea que
se trasladan tal cual: al clasificador **solo se le envía el texto**, nunca el id de
cliente o de pedido —con una prueba que lo verifica—, y los mensajes de error nunca
incluyen valores de las filas ni la excepción original, porque puede traer texto o
credenciales. Enmascarar en el almacén es el paso que falta y es nativo de la
plataforma; no hay que construirlo.

**AD añade:** el linaje a nivel de columna no es un lujo. El día que alguien pregunte
*«¿de dónde sale este número del informe regulatorio?»*, la respuesta tiene que ser una
consulta, no una reunión.

**Tiempo:** 3 min.

### Lámina 20 — Fallo 5: la IA decide sin que nadie lo apruebe
**Título:** «Una etiqueta propuesta por un modelo y una decidida por una persona no
comparten columna: no hay camino en el código para publicar la primera como validada».
**Técnico:** importación por lote **versionado**, con validación de taxonomía (17 tipos
+ `otro`) y de **procedencia**: un lote `REVISADA` exige origen humano, dos anotadores
y motivo. Asociación por hash del texto normalizado, no por `id_ticket`: 2.125 tickets
contienen solo 34 descripciones distintas. Evaluación con **intervalo de Wilson**,
matriz de confusión y **errores críticos por consecuencia**.
**Anticipa:** «¿Qué exactitud tiene?» → 0,560 con IC 95 % 0,423–0,688 sobre muestra
**sintética** de n = 50; con ese intervalo **no se puede afirmar** que supere a las
reglas.
**Tiempo:** 2,5 min.

---

## 9. Bloque F · Plataforma y costo (2 láminas · 7 min)

### Lámina 21 — Fabric o Databricks: la decisión técnica · **dueño: IF**

| Campo | Contenido |
|---|---|
| **Título de acción** | «La elección no es de producto: es de modelo de consumo, de motor de publicación y de dónde está hoy el equipo» |
| **Mensaje único** | Hay una hipótesis preferida y está condicionada; no es una preferencia personal. |
| **Cuerpo** | Tabla de criterios con el veredicto por criterio, no un ganador global. |

| Criterio | Fabric | Databricks | Peso aquí |
|---|---|---|---|
| Base instalada de Power BI | Integración nativa; el modelo semántico lee Delta directamente sin refresco de importación | Conexión soportada, pero el tablero vive fuera | **Alto** si ya hay +30 informes |
| Publicación transaccional | **Warehouse soporta transacción multi-tabla** (T-SQL): el patrón del puntero sobraría | Delta: atomicidad por tabla; se resuelve con `run_id` + puntero, que es lo implementado | **Alto**: define cuánto código sobra |
| Ingeniería de datos a escala | Spark gestionado dentro de la capacidad | Más maduro: serverless por defecto, Unity Catalog, Lakeflow | **Medio** al volumen actual |
| Gobierno fino | Permisos de workspace y OneLake | Unity Catalog: *row filters*, *column masks*, linaje por columna, `system.access.audit` | **Alto** en negocio regulado |
| Modelo de costo | Capacidad reservada (F-SKU, Unidades de Capacidad) | Consumo medido (DBU) + nube subyacente | **Alto**: ver lámina 22 |
| Curva del equipo | T-SQL y Power BI, cerca de un equipo BI | Python/Spark y conceptos de plataforma | **Alto**: es riesgo de adopción, no de tecnología |

**IF, la recomendación tal y como se dice.** *«Mi hipótesis preferida es Fabric, y está
condicionada a dos cosas: que la base de Power BI sea grande y que el equipo venga de
SQL. Si el peso cae en gobierno fino y en ingeniería a escala, la respuesta es
Databricks. Lo que no haría es decidirlo en una lámina: se decide con un piloto de los
informes prioritarios midiendo operación, conciliación y costo. El código ya está
escrito para los dos destinos.»*

**IF, el hallazgo que da credibilidad al bloque.** Audité mi propio notebook contra
las restricciones de **Databricks serverless** y encontré un bloqueador real: usa
`.cache()` en cuatro puntos, y serverless no lo admite. Hay más: tampoco admite
`sparkContext`, RDD, `spark.conf.set` de memoria, montajes DBFS ni vistas temporales
globales. Mi notebook sí cumple el resto —usa rutas `/Volumes/…` y nombres de tres
partes—, pero esos cuatro `.cache()` hay que quitarlos, y conviene reemplazarlos por
una materialización explícita en una tabla de staging, porque además el origen del
`MERGE` lee la misma tabla que escribe. **Es un hallazgo abierto, no corregido.**
Decirlo en el deck vale más que esconderlo: demuestra que el código se audita contra
la plataforma real y no contra una idea de ella.

**Anticipa:** «¿Cuál elegirías?» → la respuesta de arriba, con las dos condiciones.
**Tiempo:** 3,5 min. **Trampa:** declarar un ganador global. No lo hay.

### Lámina 22 — FinOps: el costo es una decisión de arquitectura · **dueña: FO**

| Campo | Contenido |
|---|---|
| **Título de acción** | «Los dos modelos de costo son estructuralmente distintos: uno se paga esté o no usándose, el otro solo cuando corre» |
| **Mensaje único** | Elegir plataforma es elegir cómo se comporta la factura cuando el uso cambia. |
| **Cuerpo** | Dos curvas: costo contra uso. Capacidad = escalón plano. Consumo = pendiente. El punto donde se cruzan es la decisión. |

**FO, el modelo, sin cifras inventadas.**

| | Capacidad reservada (Fabric, F-SKU) | Consumo medido (Databricks, DBU) |
|---|---|---|
| Qué se paga | Unidades de Capacidad reservadas por hora, se usen o no | Unidades de consumo por trabajo ejecutado, más la nube subyacente |
| Costo en reposo | **Alto**: la capacidad corre aunque nadie consulte | **Cercano a cero** si nada se ejecuta |
| Pico de demanda | Se suaviza y, si se excede, se **limita** (*throttling*) | Escala y **la factura escala con él** |
| Palanca principal | **Pausar la capacidad** fuera de horario (dev y test) | Elegir bien el modo de ejecución y no sobredimensionar |
| Predecibilidad | Alta: factura plana | Media: requiere presupuesto y alertas |

**Las cinco palancas concretas, no genéricas.**

1. **Pausar capacidad en entornos que no son producción.** Es la palanca de mayor
   efecto y la que más se olvida: una capacidad de desarrollo encendida el fin de
   semana cuesta lo mismo que una en uso.
2. **Modo de ejecución por carga.** En Databricks, un trabajo por lotes nocturno sin
   compromiso de latencia va en **`STANDARD`**: arranca en minutos y cuesta menos.
   **`PERFORMANCE_OPTIMIZED`** se reserva para lo que tiene un plazo real o alguien
   esperando. Este ETL es nocturno: **`STANDARD`**. Decidirlo por costumbre es pagar
   de más todas las noches.
3. **Etiquetar todo lo que se ejecuta.** Sin etiquetas no hay reparto por área y la
   conversación de costos se vuelve una opinión. Con etiquetas, `system.billing.usage`
   responde cuánto consumió cada carga, cada equipo y cada mes, en SQL.
4. **Licenciamiento de consumo de informes.** A partir de cierto tamaño de capacidad
   (F64), quienes solo **leen** informes dejan de necesitar licencia individual. Si
   hay muchos lectores, ese umbral puede invertir la comparación entre plataformas.
   **Cifra a pedir, no a suponer**: cuántos lectores y cuántos autores.
5. **Retención y grano del snapshot de cartera.** La tabla de snapshot periódico
   —contratos × cierres— es la que más crece. Que el cierre sea diario o mensual, y
   cuánta historia queda en caliente, es la decisión que más mueve el almacenamiento
   y el cómputo de los informes. **Es una decisión de modelo con factura.**

**FO, lo que no voy a hacer en esta lámina.** No pongo un precio. Las tarifas cambian,
dependen de región y de compromiso contractual, y una cifra desactualizada en un deck
destruye la credibilidad del resto. Lo que llevo es el **modelo** y las palancas; el
número sale de un piloto de dos semanas midiendo consumo real. Y una advertencia de
método: el costo de una plataforma de datos rara vez está en el cómputo del ETL —este
corre en minutos—; está en los **informes interactivos** y en el **entorno encendido
sin usarse**.

**Unit economics que sí propongo medir desde el día uno**, porque son los que hacen la
conversación concreta: costo por carga diaria, costo por informe activo al mes, y
costo por mil consultas al modelo semántico.

**Anticipa:** «¿Cuánto nos va a costar?» → *«El modelo, hoy; el número, al final de un
piloto de dos semanas con estas tres métricas. Darte una cifra ahora sería inventarla.»*
**Tiempo:** 3,5 min.

---

## 10. Bloque G · Cierre (2 láminas · 4 min)

### Lámina 23 — La lámina roja
**Título:** «Lo que no ejecuté, dicho antes de que me lo pregunten».
**Verificado:** 175 pruebas locales; 24 con PySpark real; carga completa del caso
reproducida; segunda carga sin cambios en los hechos; recálculo independiente con
pandas conciliado; CI en GitHub Actions; 102 páginas de PDF auditadas.
**Escrito y no ejecutado:** T-SQL y DDL en SQL Server; medidas DAX en Power BI;
`MERGE`/`DELETE` de Delta en Fabric o Databricks; transporte SMTP del reporte.
**Hallazgo abierto:** cuatro `.cache()` incompatibles con Databricks serverless
(lámina 21).
**Tiempo:** 2 min. **Trampa:** pedir perdón. Es el criterio con el que trabajas.

### Lámina 24 — Qué necesito de ustedes
**Título:** «Noventa días para una cifra en producción; el camino crítico son seis
decisiones, no seis desarrollos».
**Cuerpo:** línea 30/60/90 arriba; abajo, las decisiones con dueño: precisión
monetaria y devoluciones · contrato de fuente (qué significa que una fila deje de
venir) · umbrales, RPO y RTO · destinatarios y horario del reporte · entorno de prueba
con presupuesto acotado · revisión humana de 34 etiquetas.
**Y las tres de este panel:** grano y retención del snapshot de cartera (AD) ·
plataforma destino para el piloto (IF) · las tres métricas de *unit economics* (FO).
**Técnico:** cada decisión ya tiene su punto de entrada en el código **como parámetro,
no como supuesto escondido**. Por eso 90 días es creíble.
**Tiempo:** 2 min.

---

## 11. Bloque H · Apéndice técnico (18 láminas, no proyectadas)

| # | Lámina | Se abre cuando preguntan | Dueño |
|---|---|---|---|
| A1 | Los 4 dialectos de SQL lado a lado | «¿Es el mismo SQL de verdad?» | EM |
| A2 | Meses sin ventas y el calendario completo | «¿Y si un mes no tiene filas?» | AD |
| A3 | Catálogo de las 15 reglas con su tratamiento | «¿Qué más detectaste?» | AD |
| A4 | Parseo monetario exacto: enteros, sin pasar por `double` | «¿Y los decimales?» | AD |
| A5 | Medidas DAX y el período comparable | «¿Cómo comparas ene–sep contra ene–sep?» | AD |
| A6 | Optimización: el CAST en la columna indexada | «¿Cómo optimizarías esa consulta?» | IF |
| A7 | Ablación: 7,28 s → 0,06 s quitando solo el CAST | «¿Lo mediste?» | IF |
| A8 | Notebook Delta: las 13 celdas | «Enséñame el notebook» | IF |
| A9 | Los 12 escenarios de validación cloud (E04) | «¿Cómo sabrías que funciona?» | IF |
| A10 | Restricciones de serverless y la auditoría del código | «¿Corre en serverless?» | IF |
| A11 | Unity Catalog: *row filters*, *column masks*, linaje | «¿Cómo controlan el acceso?» | IF |
| A12 | Modelo de snapshot de cartera y SCD tipo 2 | «¿Cómo modelarías nuestra cartera?» | AD |
| A13 | Corrección retroactiva y cierre congelado | «¿Y si llega un pago con fecha vieja?» | AD |
| A14 | CI: dos jobs, acciones fijadas por SHA | «¿Cómo evitas regresiones?» | IF |
| A15 | Recuperación: lock, respaldo en frío, restauración | «¿Y si se corrompe la base?» | IF |
| A16 | Palancas de costo y cómo se miden | «¿Dónde se nos va la plata?» | FO |
| A17 | Reparto de costo por área con `system.billing.usage` | «¿Quién paga qué?» | FO |
| A18 | Revisión del PR: los 8 bloqueantes | «¿Cómo revisas código de tu equipo?» | EM |

---

## 12. Dónde el panel no se puso de acuerdo

Un deck honesto deja ver sus tensiones. Si preguntan, estas son reales:

| Tensión | Postura A | Postura B | Cómo se resuelve |
|---|---|---|---|
| **Plataforma** | **IF**: Fabric, por la base de Power BI y porque Warehouse da transacción multi-tabla | **FO**: Databricks, porque el consumo medido evita pagar capacidad en reposo mientras el uso es bajo | Piloto de dos semanas midiendo consumo real; la decisión es de datos, no de opinión |
| **Grano del snapshot** | **AD**: diario, porque la mora se mide por días de atraso | **FO**: mensual, y diario solo para la cartera activa | Decisión de negocio con costo: pregunta para la lámina 24 |
| **Profundidad del deck** | **AD/IF**: hacen falta las 24 | **EM**: 18 bastaban para vender | Se resolvió en 24, con la ruta de 10 minutos marcada por si recortan |

---

## 13. Cómo se comporta el deck en vivo

- **Primeros 30 segundos:** da la conclusión. Si te interrumpen en el minuto 2, ya
  dijiste lo importante.
- **Transiciones habladas:** *«Eso es lo que dicen los datos. Ahora, cómo se garantiza
  que digan lo mismo mañana.»*
- **La lámina 8 es la que les habla a ellos.** Si la pasas rápido, el deck se queda en
  retail.
- **La lámina 18 es el examen técnico.** Si entienden que resolviste una diferencia
  real entre plataformas, el puesto se decide ahí.
- **La lámina 22 es la que recuerda el patrocinador.** Nadie firma una arquitectura sin
  saber cómo se comporta la factura.
- **Cambio en vivo:** `python scripts/ensayar_cambio.py` añade el canal MARKETPLACE
  sobre datos y base temporales, recalcula y verifica un incremento exacto de 90.000
  sin tocar los originales. Enséñalo **corriendo**, no en una lámina.
- **Si no sabes algo:** *«No lo verifiqué. Para afirmarlo necesitaría X.»* Es el
  criterio que defiende todo el deck.
- **Cierre:** vuelve a la lámina 2.

---

## 14. Lista de verificación antes de presentar

- [ ] Los 24 títulos de acción, leídos seguidos, cuentan el argumento sin el cuerpo
- [ ] Ninguna lámina tiene dos mensajes
- [ ] Toda cifra lleva archivo, tabla y fecha de corrida al pie
- [ ] Ninguna cifra de precio de plataforma: solo el modelo y las palancas *(FO)*
- [ ] Ningún verbo en pasado sobre algo que no se ejecutó *(IF)*
- [ ] La lámina 8 no afirma nada sobre su operación que no sea una pregunta *(AD)*
- [ ] La lámina 23 está escrita antes que las demás
- [ ] Las tres rutas (10/30/50 min) marcadas en las notas del presentador
- [ ] El ensayo en vivo corre en una terminal ya abierta y probada
- [ ] Cada lámina del apéndice tiene su pregunta disparadora anotada

---

### Fuentes

Cifras del caso: corrida del **1 de noviembre de 2026** sobre `data/warehouse.duckdb`
(`gold_venta_neta_diaria`, `cuarentena`, `silver_pedidos`, `silver_tickets`), más
`docs/ESTADO_IMPLEMENTACION.md`, `docs/02_catalogo_calidad.md`,
`docs/07_clasificacion_ia.md` y `docs/08_traslado_delta.md`.

Guía de plataforma: restricciones de Databricks serverless, modos de ejecución
`STANDARD` y `PERFORMANCE_OPTIMIZED`, etiquetado de trabajos, modelo de privilegios de
Unity Catalog (`USE CATALOG` → `USE SCHEMA` → `SELECT`), *row filters*, *column masks*
y tablas de sistema (`system.billing.usage`, `system.access.audit`,
`system.access.table_lineage`), tomadas de las guías oficiales vigentes de Databricks.
Las capacidades de Fabric citadas —transacción multi-tabla en Warehouse, modelo de
capacidad, umbral de licenciamiento— están marcadas como **a verificar en el destino**:
no se han ejecutado en este proyecto.

Nada en este storyline afirma una ejecución que el repositorio no respalde.
