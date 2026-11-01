# Parte 1, punto 4: medidas DAX

## Supuestos del modelo
- `fact_pedido` (grano: un pedido) se relaciona con `dim_fecha` por `fecha_key`, muchos a uno, y esa relación usa **fecha_pedido** (decisión de negocio ya tomada).
- `dim_fecha[fecha]` está marcada como tabla de fechas y cubre días continuos. Sin eso, `DATEADD` falla o devuelve resultados erróneos.
- Los pedidos en cuarentena (por ejemplo, los 20 con fecha de 2027) no llegan a Gold, así que el modelo no los ve.

## Las medidas y por qué están escritas así
**Venta Neta.** Suma `valor_bruto - descuento` fila a fila (`SUMX`) y filtra `estado = "ENTREGADO"` dentro de `CALCULATE`. Los pedidos devueltos y cancelados no cuentan. El filtro está en la medida y no solo en la columna `venta_neta` de la tabla de hechos, para que la regla de negocio sea visible y no dependa de que el ETL haya puesto en 0 los demás estados.

**Pedidos Entregados.** `COUNTROWS` sobre `fact_pedido` con el mismo filtro. Como el grano es un pedido por fila, no hace falta `DISTINCTCOUNT`.

**Ticket Promedio.** `DIVIDE([Venta Neta], [Pedidos Entregados])`. Usa `DIVIDE` y no `/` para devolver vacío en vez de error cuando no hay pedidos. Decisión documentada: el ticket se calcula solo sobre pedidos entregados, para que numerador y denominador midan lo mismo.

**Venta Neta Mismo Mes Año Anterior.** `DATEADD(dim_fecha[fecha], -1, YEAR)` desplaza el contexto de fechas un año atrás. Con un mes seleccionado compara con el mismo mes del año anterior; con un trimestre o un año, con el mismo trimestre o año anterior. Antes de desplazar se quedan solo las fechas con datos (columna calculada `dim_fecha[tiene_datos]`, verdadera hasta el último día con pedidos): sin ese límite, con el año 2026 seleccionado la tabla de fechas (que cubre años completos) compararía 9 meses de 2026 contra los 12 de 2025 y la variación saldría +20,2 % en vez de +98,9 %.

**Variación vs Mismo Mes Año Anterior.** `(actual - previo) / previo`, con variables (`VAR`) para evaluar cada medida una sola vez. Si no existe el período previo devuelve **vacío**, no 0 %: un 0 % diría que no hubo cambio cuando en realidad no hay con qué comparar.

## Lo que hay que decir sobre los datos
- Los datos van de enero de 2025 a septiembre de 2026, así que la variación anual **solo existe de enero a septiembre de 2026**. En 2025 las medidas devuelven vacío, y es lo correcto.
- Esa variación sale muy alta (de +738 % en enero a +23 % en septiembre de 2026) porque la base de 2025 es muy baja: la venta mensual arranca en 113 millones en enero de 2025 y supera los 900 millones en diciembre. La cifra es correcta, pero no significa crecimiento sostenido: desde diciembre de 2025 la venta mensual se mueve entre 780 y 950 millones sin tendencia clara.

## Valores esperados para comprobar en Power BI
(Calculados con SQL sobre Silver; en Power BI deben coincidir.)

| Mes | Venta neta | Pedidos entregados | Ticket promedio | Venta mismo mes año anterior | Variación |
|---|---|---:|---:|---:|---:|
| 2026-01 | 948.592.900 | 1.085 | 874.279 | 113.198.600 | +737,99 % |
| 2026-02 | 822.651.100 | 982 | 837.730 | 213.279.700 | +285,71 % |
| 2026-03 | 926.711.300 | 1.048 | 884.267 | 320.529.800 | +189,12 % |
| 2026-06 | 864.946.200 | 1.013 | 853.846 | 455.631.200 | +89,83 % |
| 2026-09 | 795.114.800 | 901 | 882.480 | 648.367.500 | +22,63 % |
| Año 2026 (ene–sep) | 7.739.061.400 | | | 3.891.305.400 (2025 ene–sep) | +98,88 % |

Con el año 2026 seleccionado, si la medida no limitara las fechas, el año anterior sería 2025 completo (6.438.272.200) y la variación +20,2 %.

Total de venta neta de todo el período: 14.177.333.600 (16.855 pedidos entregados de 19.270 válidos).

## Qué no se probó
No se ejecutó Power BI ni Fabric: las medidas están revisadas contra el modelo de Gold, no probadas en un motor DAX.

## Actualización de integración
El ETL local ahora construye gold.fact_pedido y dimensiones; existe un cargador preparado para SQL Server. Esto no cambia el estado de DAX: requiere validación de motor E03. Ver ESTADO_IMPLEMENTACION.md.
