"""Ablación del experimento: qué parte de la consulta original causa la lentitud.

Quita de la consulta original primero el CAST del cruce con tickets y luego las funciones sobre
la fecha, y mide cada variante con índices sobre los mismos datos sintéticos de SQLite.
Uso: python sqlserver/optimizacion/ablacion_cast.py [pedidos]   (por defecto 100000)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experimento_optimizacion as e  # noqa: E402

p = dict(anio=e.ANIO, mes=e.MES, ini=e.INI, fin=e.FIN)
SIN_CAST = e.ORIGINAL.replace("CAST(t.id_cliente AS VARCHAR(20)) = CAST(c.id_cliente AS VARCHAR(20))",
                              "t.id_cliente = c.id_cliente")
assert SIN_CAST != e.ORIGINAL
SIN_CAST_NI_FECHA = SIN_CAST.replace("""AND CAST(strftime('%Y', p.fecha_pedido) AS INT) = :anio
           AND CAST(strftime('%m', p.fecha_pedido) AS INT) = :mes""", "AND p.fecha_pedido >= :ini AND p.fecha_pedido < :fin")
assert SIN_CAST_NI_FECHA != SIN_CAST

n = int(sys.argv[1]) if len(sys.argv) > 1 else 100_000
con = e.crear(n)
for ddl in e.INDICES:
    con.execute(ddl)
con.execute("ANALYZE")
resultados = {}
for nombre, sql in [("original con índices", e.ORIGINAL), ("sin CAST", SIN_CAST),
                    ("sin CAST ni YEAR/MONTH", SIN_CAST_NI_FECHA), ("reescrita", e.REESCRITA)]:
    t = time.perf_counter()
    filas = con.execute(sql, p).fetchall()
    resultados[nombre] = sorted(filas)
    print(f"{n:>8} {nombre:25} {time.perf_counter() - t:7.2f} s  filas={len(filas)}")
print("resultados iguales entre variantes:", len({str(v) for v in resultados.values()}) == 1)
