# Roadmap de ejecución

> Versión con más profundidad conceptual (por qué el orden recomendado es ese, el
> razonamiento de costo detrás de cada palanca, dependencias explicadas y qué hacer si
> el tiempo disponible no encaja en los tres escenarios de abajo):
> [roadmap_detallada.md](roadmap_detallada.md).

**Corte:** 1 de noviembre de 2026. Este es el documento maestro: **qué falta, en qué
orden y qué cierra cada cosa**. El detalle paso a paso vive en un documento por
herramienta.

| Herramienta | Documento | Tiempo | Cierra |
|---|---|---|---|
| Databricks | [plataforma/databricks.md](plataforma/databricks.md) | 8 h | E04, E04b, parte de E05 |
| Microsoft Fabric | [plataforma/fabric.md](plataforma/fabric.md) | 6 h | E04 y la prueba de transacción |
| **Power BI** | [plataforma/powerbi.md](plataforma/powerbi.md) | **3 h** | **E03** |
| SQL Server | [plataforma/sqlserver.md](plataforma/sqlserver.md) | 5 h | E01, E02 |

Todo lo que podía hacerse sin credenciales está hecho (IA-R01 a IA-R05). Lo que queda
necesita tus cuentas.

---

## 1. Punto de partida

**Los datos del caso son ficticios**, así que se cargan los CSV de `data/original/` tal
cual y **las cifras de referencia aplican en todas las plataformas**:

| Comprobación | Valor |
|---|---|
| Clientes válidos | 6.040 (6.000 personas) |
| Pedidos válidos | 19.270 de 19.734 leídos |
| Pagos válidos | 20.124 de 20.883 leídos |
| Filas Gold | 7.925 · 636 días |
| Tickets | 2.125 |
| **Venta neta** | **COP 14.177.333.600** · 16.855 pedidos entregados |

Si una plataforma da otro número, **es un hallazgo**, no un ajuste.

### Lo único que detecté roto

Tu único perfil de Databricks en `.databrickscfg` tiene como **nombre una URL de
notebook pegada** y marca `Valid: NO`. Es la primera tarea
([DBX-01](plataforma/databricks.md#dbx-01--arreglar-el-perfil-del-cli)), 10 minutos.

Lo demás está listo: CLI v1.23.0, Java 17 y Python 3.11 locales.

### Una decisión que sigue siendo tuya

**¿Qué motor T-SQL usas?** No mencionaste tener SQL Server.

| Opción | Sirve para | Límite |
|---|---|---|
| **SQL Server en Docker** ✅ recomendado | E01 y E02 completos | Necesita Docker y ~2 GB de RAM |
| Azure SQL Database | E01 y E02 casi completos | Cobra por hora; hay que apagarla |
| Fabric Warehouse | Ejecutar T-SQL y conectar Power BI | **No sirve para E02**: no es SQL Server, los planes no son comparables |

El documento de SQL Server asume Docker. Si eliges otra, el resto de pasos es igual
salvo la conexión.

---

## 2. El orden importa más que la lista

### Si solo tienes 3 horas

**[Power BI](plataforma/powerbi.md) completo.** Nada más.

Es el bloque de mayor retorno de todo el proyecto: hoy la documentación dice *«las
medidas están revisadas, no probadas en un motor DAX»*, que es la afirmación más débil
que queda y la que más se pregunta. Tres horas la eliminan.

Si no hiciste Fabric antes, usa la Ruta B del documento (Power BI Desktop contra
Databricks o contra los datos locales).

### Si tienes 2 días

| Día | Qué | Cierra |
|---|---|---|
| 1 | [Databricks](plataforma/databricks.md) DBX-01 a DBX-08 | **E04** completo |
| 2 | [Power BI](plataforma/powerbi.md) PBI-01 a PBI-07 | **E03** |

Con esto pasas de «escrito» a «ejecutado» en los dos puntos que más se preguntan.

### Si tienes la semana completa

| Día | Bloque | Tareas | Cierra |
|---|---|---|---|
| **1** | Databricks | DBX-01 → DBX-06 | E04-01 |
| **2** | Databricks | DBX-07 → DBX-08 | E04b, E04 completo |
| **3** | Fabric | FAB-01 → FAB-08 | E04 en Fabric + **la prueba de transacción** |
| **4** | Power BI | FAB-09 → PBI-01 → PBI-08 | **E03** |
| **5** | SQL Server | SQL-01 → SQL-07 | **E01 y E02** |
| **6** | Cierre | DBX-09 a DBX-11, operación, 34 etiquetas | E05 parcial, U05 |

**Por qué Fabric antes que Power BI:** FAB-09 crea el modelo semántico Direct Lake, y
PBI-01 lo usa directamente. Si haces Fabric primero, te ahorras una hora en Power BI.

---

## 3. Dependencias

```
DBX-01 perfil ──► DBX-02..DBX-06 ──► DBX-07 (serverless) ──► DBX-08 (escenarios)
                                                     └──► DBX-09 (bundle) ──► E05

FAB-01 capacidad ──► FAB-02..FAB-05 ──► FAB-07 (escenarios)
                                   ├──► FAB-08 (transacción) ──► lámina 18 del deck
                                   └──► FAB-09 (modelo) ──► PBI-01 (ruta A)

SQL-01 docker ──► SQL-02 DDL ──► SQL-03 carga ──► SQL-04 consultas
                                            └──► SQL-05 volumen ──► SQL-06/07 planes

U05 (34 etiquetas) ──► E06  [bloqueante: sin esto no hay IA validada]
```

**Lo único que bloquea otra cosa es FAB-09 → PBI-01.** El resto es independiente: puedes
hacer los bloques en el orden que te convenga.

---

## 4. Las tres tareas que más valen

Si tuvieras que justificar el tiempo invertido con tres resultados:

### 1. [PBI-06](plataforma/powerbi.md#pbi-06--verificar-contra-los-siete-valores) · Verificar las medidas DAX
Siete valores calculados en SQL que deben coincidir en el motor. Elimina la afirmación
más débil del proyecto. **3 h.**

### 2. [FAB-08](plataforma/fabric.md#fab-08--la-prueba-que-solo-fabric-permite) · ¿Warehouse soporta transacción multi-tabla?
Todo el diseño de publicación del proyecto existe porque Delta **no** la tiene. Si
Warehouse sí, en ese destino el patrón sobraría. Convierte un argumento del deck de
hipótesis en hecho verificado. **45 min.**

### 3. [SQL-07](plataforma/sqlserver.md#sql-07--medir-la-consulta-reescrita) · Medir la optimización con planes reales
Convierte el experimento en SQLite en evidencia del motor que pide el enunciado. **30 min.**

Y la cuarta, que no es técnica pero bloquea todo un bloque:
**[las 34 etiquetas](REVISION_HUMANA_IA.md)** (U05). Dos horas tuyas desbloquean E06.

---

## 5. Lo que no puedo hacer por ti: decisiones

| ID | Decisión | Qué bloquea |
|---|---|---|
| U01 | Fecha y forma de entrega | Portada y fechas de los documentos |
| U02 | ¿Evaluador recibe ZIP o acceso al repositorio? | Instrucciones de revisión |
| U03 | Pesos enteros o centavos; devoluciones; catálogo de categorías | Tipos en Silver, Gold, DDL y DAX **a la vez** |
| U04 | Contrato de fuente: ¿snapshot o incremento? ¿Qué significa una ausencia? | Sin esto no se habilitan bajas |
| **U05** | **Revisar las 34 etiquetas** | **Todo el bloque de IA** |
| U06 | Muestra real de tickets etiquetada por personas | E06 |
| U07 | Destinatarios, canal y horario del reporte | El transporte se niega a enviar sin esto |
| U08 | Umbrales de publicación, frescura, RPO y RTO | Las compuertas están vacías a propósito |
| U09 | Presupuesto del entorno | Límite de consumo |
| U10 | Rotación de credenciales expuestas, si aplica | Higiene |

**U03 y U04 son las caras.** Cambiar la precisión monetaria toca tipos en cinco sitios a
la vez; el contrato de fuente decide si una fila ausente es una baja o un fallo de
extracción. Las demás son de media hora.

### Cómo cerrar U05 ⏱️ 2 h

```bash
# 1. La plantilla ya existe, con las 34 descripciones y la propuesta de la IA
start docs/revision_etiquetas_34.csv
```

Completa `anotador_1`, `anotador_2`, `decision_final`, `motivo` y `particion` en las 34
filas. **Dos anotadores de verdad**; si solo hay una persona, que sea distinta de quien
escribió la propuesta, y anótalo como limitación. **No uses otra IA.**

```bash
# 2. Auditar formato, acuerdo entre anotadores y fugas
python scripts/revision_etiquetas.py auditar docs/revision_etiquetas_34.csv

# 3. Importar (se niega si falta algo) y reconstruir los hechos
python scripts/importar_etiquetas.py revision --db data/warehouse.duckdb \
  --archivo docs/revision_etiquetas_34.csv --version rev-2026-11-XX
python scripts/cargar_datos.py
```

**✅ Debe salir:** `estado: VALIDADO_FORMATO`, sin fugas, y después
`gold.fact_ticket.tipo_caso` poblado con `clasificacion_estado = 'REVISADA'`.

---

## 6. Qué me devuelves

Guarda todo en `docs/evidencia/ejecucion_plataforma/<herramienta>/` con los nombres de
archivo que indica cada documento. Para cada tarea necesito:

1. **Qué ejecutaste** — comando o pasos.
2. **Qué salió** — salida, captura o plan de ejecución.
3. **Si coincidió con lo esperado.** Si no: **el error exacto**, sin resumir.
4. **Contexto** — fecha, plataforma, workspace, región, tipo de cómputo.

**Sin secretos.** Nada de cadenas de conexión, tokens ni contraseñas. Si una captura los
muestra, tápalos antes de guardarla.

### Qué hago yo con eso

- Actualizo `ESTADO_IMPLEMENTACION.md` y `PENDIENTES_ACTUALES.md`.
- Cambio cada «escrito, no ejecutado» por una afirmación con fecha y artefacto.
- Ajusto el deck ([10_storyline_finanzauto.md](10_storyline_finanzauto.md)): la lámina
  roja encoge y la 18 y la 22 se vuelven verificadas.
- Ajusto el simulacro ([11_simulacro_sustentacion.md](11_simulacro_sustentacion.md)):
  las respuestas P33, P43 y P46 cambian de «no lo ejecuté» a la cifra real.
- Si DBX-07 funciona, incorporo la corrección de `.cache()` al generador con sus pruebas.

---

## 7. Control de costo

| Riesgo | Palanca | Dónde |
|---|---|---|
| Capacidad Fabric encendida sin usarse | **Pausarla** al terminar cada sesión | [FAB-11](plataforma/fabric.md#fab-11--pausar-la-capacidad-️-5-min-) |
| Clúster Databricks ocioso | Serverless no cobra en reposo; el clásico sí | [DBX-12](plataforma/databricks.md#dbx-12--apagar-todo-️-5-min) |
| Job programado olvidado | Déjalo en `PAUSED` hasta operarlo de verdad | DBX-09, FAB-10 |
| Contenedor SQL Server corriendo | `docker stop` | SQL-09 |
| No saber en qué se fue | Etiquetar todo y revisar `system.billing.usage` | DBX-11 |

**Regla práctica:** al cerrar cada día, comprueba que no queda nada encendido. Estas
pruebas deberían costar horas de cómputo, no días.

En Databricks, el job va en `performance_target: STANDARD`: es un lote nocturno sin
nadie esperando, arranca en minutos y cuesta menos que `PERFORMANCE_OPTIMIZED`.

---

## 8. Estado: antes y después

| Afirmación | Hoy | Después de |
|---|---|---|
| ETL local verificado | ✅ 175 pruebas | — |
| Paridad Spark | ✅ 24 pruebas | — |
| Notebook Delta ejecutado | ❌ escrito | DBX-06 o FAB-05 |
| MERGE / DELETE / RESTORE | ❌ escrito | DBX-08 o FAB-07 |
| Compatible con serverless | ❌ bloqueador conocido | DBX-07 |
| Medidas DAX | ❌ escritas | **PBI-06 y PBI-07** |
| DDL T-SQL | ❌ escrito | SQL-02 |
| Modelo estrella en SQL Server | ❌ no cargado | SQL-03 |
| Optimización en el motor real | ❌ medida en SQLite | SQL-07 |
| Transporte SMTP | ❌ escrito | depende de U07 |
| Etiquetas validadas | ❌ pendiente | U05 |

**Hoy quedan 8 afirmaciones en «escrito, no ejecutado». Con los días 1 a 5 bajan a 2**
(el transporte y la IA, que dependen de decisiones tuyas, no de ejecución).
