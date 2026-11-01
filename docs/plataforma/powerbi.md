# Power BI y DAX · paso a paso

**Qué vas a lograr aquí:** instalar las cinco medidas DAX en un motor real y
verificarlas contra siete valores calculados en SQL. Cierra **E03**.

**Tiempo total:** 3 h. **Prioridad: la más alta de todo el roadmap.**

> **Por qué es el bloque más rentable.** Hoy el proyecto dice literalmente *«las medidas
> están revisadas contra el modelo de Gold, no probadas en un motor DAX»*. Es la
> afirmación más débil que queda, se pregunta siempre, y cerrarla cuesta tres horas.
> Después podrás decir: «ejecutadas y verificadas contra siete valores».

**Prerrequisito:** una de las dos rutas.
- **Ruta A (recomendada):** [FAB-09](fabric.md#fab-09--modelo-semántico-direct-lake) hecho → ya tienes el modelo.
- **Ruta B:** Power BI Desktop conectado a Databricks o a los datos locales.

---

## PBI-01 · Conectar el modelo ⏱️ 30 min

### Ruta A · Desde Fabric (Direct Lake)

1. En el workspace de Fabric, abre `andina_modelo`.
2. **Crear informe** → se abre Power BI con el modelo ya conectado.
3. No hay que importar nada: Direct Lake lee las tablas Delta directamente.

### Ruta B · Power BI Desktop contra Databricks

1. Power BI Desktop → **Obtener datos → Azure Databricks**.
2. **Server hostname:** `dbc-ebd35512-279a.cloud.databricks.com`
   **HTTP Path:** el de tu SQL warehouse (UI → SQL Warehouses → tu warehouse →
   *Connection details*).
3. Modo **Import** (para este volumen va bien).
4. Selecciona: `gold_fact_pedido`, `gold_fact_venta_neta_diaria`, `gold_dim_fecha`,
   `gold_dim_canal`, `gold_dim_categoria`, `gold_dim_cliente`.

**✅ Debe salir:** las seis tablas cargadas. `gold_fact_pedido` con **19.270 filas**.

**📎 Evidencia:** `evidencia/powerbi/01_conexion.png`.

---

## PBI-02 · Crear las relaciones ⏱️ 20 min

**Pasos.** Vista **Modelo** (icono del diagrama a la izquierda). Arrastra campo sobre
campo:

| Desde | Hacia | Cardinalidad | Filtro cruzado |
|---|---|---|---|
| `gold_fact_pedido[fecha_key]` | `gold_dim_fecha[fecha_key]` | Varios a uno (*:1) | Simple |
| `gold_fact_pedido[canal_key]` | `gold_dim_canal[canal_key]` | Varios a uno | Simple |
| `gold_fact_pedido[categoria_key]` | `gold_dim_categoria[categoria_key]` | Varios a uno | Simple |
| `gold_fact_pedido[cliente_key]` | `gold_dim_cliente[cliente_key]` | Varios a uno | Simple |

**✅ Debe salir:** un esquema en estrella con `gold_dim_fecha` conectada al hecho, y las
cuatro relaciones **activas** (línea continua, no punteada).

**❌ Si Power BI propone relaciones automáticas raras** (por ejemplo entre dos
dimensiones): bórralas. En un esquema en estrella las dimensiones **no** se relacionan
entre sí.

**📎 Evidencia:** `evidencia/powerbi/02_relaciones.png`.

---

## PBI-03 · Marcar la tabla de fechas ⏱️ 10 min 🔴

**No te saltes este paso.** Sin él, `DATEADD` falla o devuelve resultados erróneos, y
las dos últimas medidas no funcionarán.

**Pasos**

1. Vista **Datos** → selecciona la tabla `gold_dim_fecha`.
2. Pestaña **Herramientas de tabla** → **Marcar como tabla de fechas**.
3. Columna de fecha: **`fecha`** (la de tipo fecha, no `fecha_key`).
4. Acepta la validación.

**✅ Debe salir:** el icono de calendario junto a `gold_dim_fecha` en el panel de campos.

**❌ Si la validación falla** diciendo que hay huecos o duplicados: el calendario del ETL
cubre años completos sin huecos, así que revisa que cargaste `gold_dim_fecha` entera y
no una vista filtrada.

**📎 Evidencia:** `evidencia/powerbi/03_tabla_fechas.png`.

---

## PBI-04 · Crear la columna calculada `tiene_datos` ⏱️ 10 min 🔴

**Por qué.** El calendario cubre años completos porque `DATEADD` lo exige, pero los
datos terminan el **30 de septiembre de 2026**. Sin este límite, con el año 2026
seleccionado se compararían 9 meses de 2026 contra los **12** de 2025 y la variación
saldría **+20,2 %** en vez de **+98,9 %**.

**Pasos.** Selecciona `gold_dim_fecha` → **Nueva columna**:

```dax
tiene_datos =
gold_dim_fecha[fecha_key] <= MAX ( gold_fact_pedido[fecha_key] )
```

**✅ Debe salir:** una columna booleana, `True` hasta 2026-09-30 y `False` después.
Compruébalo poniéndola en una tabla junto a `fecha`.

**📎 Evidencia:** `evidencia/powerbi/04_tiene_datos.png`.

---

## PBI-05 · Instalar las cinco medidas ⏱️ 20 min

El original está en `fabric/semantic_model/medidas.dax`. **Ojo:** ahí las tablas se
llaman `fact_pedido` y `dim_fecha`; si en tu modelo son `gold_fact_pedido` y
`gold_dim_fecha`, usa esta versión ya adaptada.

Crea cada una con **Nueva medida**:

```dax
Venta Neta =
CALCULATE (
    SUMX ( gold_fact_pedido, gold_fact_pedido[valor_bruto] - gold_fact_pedido[descuento] ),
    gold_fact_pedido[estado] = "ENTREGADO"
)
```

```dax
Pedidos Entregados =
CALCULATE ( COUNTROWS ( gold_fact_pedido ), gold_fact_pedido[estado] = "ENTREGADO" )
```

```dax
Ticket Promedio =
DIVIDE ( [Venta Neta], [Pedidos Entregados] )
```

```dax
Venta Neta Mismo Mes Año Anterior =
CALCULATE (
    [Venta Neta],
    CALCULATETABLE ( DATEADD ( gold_dim_fecha[fecha], -1, YEAR ), gold_dim_fecha[tiene_datos] = TRUE () )
)
```

```dax
Variación vs Mismo Mes Año Anterior =
VAR actual = [Venta Neta]
VAR previo = [Venta Neta Mismo Mes Año Anterior]
RETURN
    IF ( NOT ISBLANK ( previo ), DIVIDE ( actual - previo, previo ) )
```

Luego dale formato **Porcentaje, 2 decimales** a la última.

**✅ Debe salir:** las cinco medidas sin errores de sintaxis.

**❌ Si una da error de columna no encontrada:** revisa el prefijo `gold_` en los nombres
de tabla.

**📎 Evidencia:** `evidencia/powerbi/05_medidas.png` con el panel de medidas.

---

## PBI-06 · Verificar contra los siete valores ⏱️ 45 min ⭐

**Esta es la tarea que cierra E03.** Los valores salen del cálculo equivalente en SQL
sobre Silver; en Power BI **deben coincidir**.

**Pasos**

1. Inserta una **Matriz**.
2. Filas: `gold_dim_fecha[anio_mes]`.
3. Valores: `Venta Neta`, `Pedidos Entregados`, `Ticket Promedio`,
   `Venta Neta Mismo Mes Año Anterior`, `Variación vs Mismo Mes Año Anterior`.
4. Compara contra esta tabla:

| Mes | Venta Neta | Pedidos | Ticket | Año anterior | Variación |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 948.592.900 | 1.085 | 874.279 | 113.198.600 | +737,99 % |
| 2026-02 | 822.651.100 | 982 | 837.730 | 213.279.700 | +285,71 % |
| 2026-03 | 926.711.300 | 1.048 | 884.267 | 320.529.800 | +189,12 % |
| 2026-06 | 864.946.200 | 1.013 | 853.846 | 455.631.200 | +89,83 % |
| 2026-09 | 795.114.800 | 901 | 882.480 | 648.367.500 | +22,63 % |

5. **Total del período** (quita el desglose por mes):

| Medida | Esperado |
|---|---:|
| Venta Neta | **14.177.333.600** |
| Pedidos Entregados | **16.855** |

**✅ Debe salir:** los siete valores exactos. Si uno falla, es un hallazgo real y hay que
reportarlo, no ajustarlo.

**📎 Evidencia:** `evidencia/powerbi/06_matriz.png` con la matriz completa visible.

---

## PBI-07 · Las cuatro pruebas de borde ⏱️ 30 min

Estas son las que de verdad validan el diseño de las medidas, no solo que sumen.

### Prueba 1 · Año 2025 → variación vacía
**Haz:** filtra `anio = 2025`.
**✅ Debe salir:** `Variación` **en blanco**, no `0 %`.
**Por qué:** un 0 % diría que no hubo cambio; la verdad es que no hay con qué comparar.
Los datos empiezan en enero de 2025.

### Prueba 2 · Año 2026 completo → +98,88 % 🔴
**Haz:** filtra `anio = 2026` sin desglose por mes.
**✅ Debe salir:** Venta Neta `7.739.061.400`, año anterior `3.891.305.400`,
variación **+98,88 %**.
**❌ Si sale +20,2 %:** la columna `tiene_datos` no está aplicada en la medida. Vuelve a
PBI-04 y revisa el `CALCULATETABLE` de PBI-05. **Esta es la prueba que más falla.**

### Prueba 3 · Mes sin ventas en un canal
**Haz:** filtra un canal y busca un mes sin ventas.
**✅ Debe salir:** el mes aparece con **cero**, no desaparece de la matriz.

### Prueba 4 · Filtro por canal
**Haz:** segmentación por `gold_dim_canal[canal]`, elige `APP`.
**✅ Debe salir:** las cinco medidas responden. Venta Neta total de APP:
**6.061.702.800** (42,8 % del total). WEB: `4.606.783.900`. TIENDA: `3.508.846.900`.

**📎 Evidencia:** una captura por prueba →
`evidencia/powerbi/07_prueba1.png` … `07_prueba4.png`.

---

## PBI-08 · Informe mínimo ⏱️ 20 min *(opcional)*

1. Gráfico de líneas: eje `anio_mes`, valor `Venta Neta`, leyenda `canal`.
2. Tarjetas: `Venta Neta`, `Pedidos Entregados`, `Ticket Promedio`.
3. Segmentación por `anio` y por `canal`.

**✅ Debe salir:** la línea de TIENDA cayendo entre junio y septiembre de 2026 y la de
APP subiendo. Es el hallazgo de negocio, visible.

**📎 Evidencia:** `evidencia/powerbi/08_informe.png`.

---

## PBI-09 · Conexión de solo lectura ⏱️ 20 min *(opcional)*

**Por qué.** El PR revisado en la parte 3 usaba un usuario `admin` con contraseña en el
código. Demostrar lo contrario cierra el círculo.

1. Crea o usa un usuario con permisos **solo de lectura** sobre el esquema Gold.
2. Reconfigura la conexión del modelo con ese usuario.
3. Refresca.

**✅ Debe salir:** el informe funciona igual.
**⚠️ No publiques la cadena de conexión** en ninguna captura ni archivo.

**📎 Evidencia:** `evidencia/powerbi/09_lectura.png` con las credenciales tapadas.

---

## Lista de cierre

| Tarea | Hecho | Evidencia | Cierra |
|---|---|---|---|
| PBI-01 Conexión | ☐ | `01_conexion.png` | — |
| PBI-02 Relaciones | ☐ | `02_relaciones.png` | — |
| PBI-03 Tabla de fechas | ☐ | `03_tabla_fechas.png` | 🔴 requisito de `DATEADD` |
| PBI-04 `tiene_datos` | ☐ | `04_tiene_datos.png` | 🔴 requisito del período comparable |
| PBI-05 Cinco medidas | ☐ | `05_medidas.png` | — |
| PBI-06 Siete valores | ☐ | `06_matriz.png` | **E03** |
| PBI-07 Pruebas de borde | ☐ | `07_prueba*.png` | **E03** |
| PBI-08 Informe | ☐ | `08_informe.png` | — |
| PBI-09 Solo lectura | ☐ | `09_lectura.png` | higiene |

**Cuando termines PBI-06 y PBI-07, avísame.** Cambio en todos los documentos «DAX
escrito y revisado» por «DAX ejecutado y verificado contra siete valores y cuatro
pruebas de borde», con fecha y motor.
