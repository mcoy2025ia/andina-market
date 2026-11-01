# Prompt para que una IA te guíe en la ejecución de los pendientes

Este prompt funciona en un chat nuevo, sin ningún contexto previo. La IA no ve tu equipo ni los datos: tú ejecutas los comandos y le pegas las salidas.

## Qué adjuntar en el chat nuevo

1. **`docs/PENDIENTES_EJECUCION.md`** (obligatorio). Trae el contexto completo del caso, las definiciones, el mapa del repositorio y los pendientes con sus pasos y criterios de cierre.
2. **El enunciado**, `enunciado/Prueba_Tecnica_Lider_Datos.md` (opcional, solo si quieres que la IA revise la prueba contra el enunciado).

**No adjuntes** los CSV de `data/original/` (tienen nombres y documentos de personas) ni `.env.local` (tiene una clave).

---

## Prompt (cópialo tal cual en el chat nuevo)

```
Te voy a pedir ayuda para ejecutar, yo mismo, los pendientes de una prueba técnica de datos. Lo que sigue es todo lo que necesitas saber; el documento adjunto (PENDIENTES_EJECUCION.md) tiene el detalle.

CONTEXTO RESUMIDO
- Es una prueba técnica de selección para Líder Técnico de Datos, BI y Automatización, de la empresa ficticia Andina Market (tecnología, hogar, moda y mercado; página web, app y tiendas físicas).
- La prueba tiene tres partes: (1) SQL, ETL incremental e idempotente con cuarentena, DAX y optimización de una consulta; (2) arquitectura a 12 meses, recomendación entre Microsoft Fabric y Databricks, y plan de 90 días; (3) revisión de un pull request y dos situaciones de liderazgo.
- Hay un repositorio llamado andina-market en C:\Users\USUARIO\Documents\Finanzauto\andina-market. Se trabaja en Windows, con Git Bash y PowerShell.
- Venta neta = valor bruto menos descuento, solo pedidos entregados (ENTREGADO), atribuida a la fecha del pedido. Rango válido: 1-ene-2025 a 30-sep-2026.
- Arquitectura: Bronze (copia cruda), Silver (limpia, con cuarentena para lo inválido), Gold (venta neta diaria). El ETL local usa DuckDB; la versión Spark usa Delta.
- Yo NO te comparto los datos (contienen datos personales). No los necesitas: te paso las salidas de los comandos.

CIFRAS DE REFERENCIA (si una salida no coincide, no la fuerces: documenta la diferencia y pregúntame)
- Clientes válidos 6.040; pedidos válidos 19.270; pagos válidos 20.124; filas de Gold 7.925.
- Venta neta total 14.177.333.600 COP; pedidos entregados 16.855.
- Consulta mensual por canal: 63 filas (3 canales por 21 meses).
- Recompra 2026 a 1, 3 y 6 meses: 26,1 %, 49,2 % y 57,1 %.
- Medida DAX de enero 2026: 948.592.900; de septiembre 2026: 795.114.800.
- Pruebas: con Python 3.12, 85 pasan y 2 se omiten; con Python 3.11 y PySpark, 89 pasan y 1 se omite.

PENDIENTES (el detalle de cada uno está en el documento adjunto)
- P01 Pruebas de paridad Spark frente a DuckDB (Python 3.11, guardar salida).
- P02 Pruebas de Spark SQL (requiere HADOOP_HOME con winutils en Windows, o WSL/Linux).
- P03 T-SQL de venta neta y recompra en SQL Server (necesita P04 antes).
- P04 DDL del modelo en SQL Server.
- P05 Medidas DAX en Power BI Desktop (faltan las tablas fact_pedido y dim_fecha; se construyen desde Silver).
- P06 Notebook Delta en Fabric (prueba gratuita).
- P07 Notebook en Databricks (prueba o edición gratuita).
- P08 Medición de la optimización en SQL Server.
- P09 Política de retención del proveedor de IA (DeepSeek).
- P10 Revisión humana de las 34 etiquetas de tickets.
- P11 Muestra de tickets reales etiquetada por personas (anonimizada).
- P12 Definición de venta neta firmada por finanzas y comercial.
- P13 Fecha de entrega: 21 de octubre frente a 31 de octubre; confirmar prórroga.
- P14 Licencias de Power BI Pro bajo F64 y cotizaciones de Fabric y Databricks.
- P15 Revisión visual de la presentación HTML en escritorio y teléfono.
- P16 Reporte de ventas contra SQL Server real (usuario de solo lectura).
- P17 Rotación urgente de credenciales expuestas (clave de DeepSeek y contraseña del pull request).
- P18 Umbrales de cuarentena (necesita 30 días de cargas reales; hoy no existen).
- P19 Guardar las salidas de las ejecuciones declaradas.
- P20 Cifra mensual de APP.
- P21 Comparar TIENDA de jun-sep 2025 contra jun-sep 2026 (recomendado).

REGLAS (no las rompas)
1. Nunca me pidas una contraseña, clave de API, cadena de conexión ni token. Si aparece uno en una salida que te pego, detente, dime que hay que rotarlo y escribe [REDACTADO] en lugar del valor.
2. Trabaja un pendiente a la vez, en este orden sugerido: P17, P13, P01, P19, P02, P04, P03, P16, P05, P06, P07, P08, P20, P21, P10, P12, P18, P14, P15, P11, P09.
3. Antes de cada paso dime qué voy a ejecutar, por qué, y qué salida debo pegarte. Un comando por vez.
4. No propongas cambios al código de src/ ni de tests/ salvo que yo lo pida. Si algo no cuadra, primero diagnostica y pregúntame.
5. Si un comando falla, pídeme la salida completa del error antes de sugerir una solución.
6. Si un pendiente requiere una decisión de negocio, una persona o una cuenta que yo no tenga, márcalo BLOQUEADO y pasa al siguiente.
7. No des por confirmado nada que no viste en una salida. Si no tienes la salida, dilo.

EVIDENCIA
Al terminar cada pendiente, escribe el contenido de docs/evidencia/PXX/resultado.md con este formato, para que yo lo guarde:

# PXX · nombre
- Fecha:
- Entorno (sistema, versiones de Python, Java, SQL Server, Power BI, etc.):
- Qué se ejecutó (comandos o pasos):
- Cifra de referencia esperada:
- Cifra obtenida:
- Estado: CONFIRMADO / DIFERENCIA / NO CONFIRMADO / BLOQUEADO
- Archivos de salida que debo adjuntar:
- Observaciones:

FORMA DE TRABAJAR
- Respuestas cortas, en orden, sin rodeos.
- Si necesitas ver una captura de pantalla, pídela.

Empecemos. Confirma en dos líneas que entendiste el caso y los pendientes, y dime cuál es el primer paso de P17 (rotación de credenciales, urgente). No ejecutes nada hasta que yo confirme.
```

---

## Para ti

- Si la IA olvida una regla, recuérdasela: "Revisa las reglas del prompt y corrige".
- No pegues claves ni contraseñas en el chat. Si una salida las muestra, redáctalas antes de copiarlas.
- Guarda las salidas en `docs/evidencia/PXX/`. Cuando tengas la evidencia de un pendiente, avísame y actualizo la presentación.
