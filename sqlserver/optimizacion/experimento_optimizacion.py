"""Experimento: efecto de las correcciones de la consulta del punto 5 sobre datos sintéticos.

Usa SQLite (biblioteca estándar) porque, a diferencia de DuckDB, NO reescribe subconsultas
correlacionadas: las ejecuta fila a fila, como hace el plan que describe la prueba. Sirve para
mostrar la FORMA del problema (crecimiento cuadrático sin índices, plano con índices); los tiempos
absolutos de SQL Server serán otros y no se midieron aquí.

Uso:  python sqlserver/optimizacion/experimento_optimizacion.py
"""
import random
import sqlite3
import time
from datetime import datetime, timedelta

ANIO, MES = 2026, 9
INI, FIN = "2026-09-01", "2026-10-01"

ORIGINAL = """
SELECT c.id_cliente,
       (SELECT SUM(p.valor_bruto - p.descuento) FROM pedidos p
         WHERE p.id_cliente = c.id_cliente
           AND CAST(strftime('%Y', p.fecha_pedido) AS INT) = :anio
           AND CAST(strftime('%m', p.fecha_pedido) AS INT) = :mes) AS venta_mes,
       (SELECT t.canal FROM tickets_soporte t
         WHERE CAST(t.id_cliente AS VARCHAR(20)) = CAST(c.id_cliente AS VARCHAR(20))
         ORDER BY t.fecha_creacion DESC LIMIT 1) AS ultimo_canal_soporte
  FROM clientes c
 WHERE c.id_cliente IN (SELECT DISTINCT id_cliente FROM pedidos WHERE estado = 'DEVUELTO')
 ORDER BY venta_mes DESC
"""

REESCRITA = """
WITH venta AS (
    SELECT id_cliente, SUM(valor_bruto - descuento) AS venta_mes
      FROM pedidos
     WHERE fecha_pedido >= :ini AND fecha_pedido < :fin
     GROUP BY id_cliente
)
SELECT c.id_cliente, v.venta_mes,
       (SELECT t.canal FROM tickets_soporte t
         WHERE t.id_cliente = c.id_cliente
         ORDER BY t.fecha_creacion DESC LIMIT 1) AS ultimo_canal_soporte
  FROM clientes c
  LEFT JOIN venta v ON v.id_cliente = c.id_cliente
 WHERE EXISTS (SELECT 1 FROM pedidos p WHERE p.id_cliente = c.id_cliente AND p.estado = 'DEVUELTO')
 ORDER BY v.venta_mes DESC
"""

INDICES = [
    "CREATE INDEX ix_ped_cliente ON pedidos (id_cliente)",
    "CREATE INDEX ix_ped_fecha ON pedidos (fecha_pedido, id_cliente, valor_bruto, descuento)",
    "CREATE INDEX ix_ped_estado ON pedidos (estado, id_cliente)",
    "CREATE INDEX ix_tk_cliente ON tickets_soporte (id_cliente, fecha_creacion DESC, canal)",
]


def crear(n_pedidos, semilla=7):
    rnd = random.Random(semilla)
    n_cli = max(n_pedidos // 10, 10)
    ids = [f"CL{i:07d}" for i in range(n_cli)]
    con = sqlite3.connect(":memory:")
    con.executescript("""
        CREATE TABLE clientes (id_cliente VARCHAR(9) PRIMARY KEY);
        CREATE TABLE pedidos (id_pedido INTEGER PRIMARY KEY, id_cliente VARCHAR(9), fecha_pedido TEXT,
                              valor_bruto INTEGER, descuento INTEGER, estado VARCHAR(10));
        CREATE TABLE tickets_soporte (id_ticket INTEGER PRIMARY KEY, id_cliente VARCHAR(9),
                                      fecha_creacion TEXT, canal VARCHAR(10));""")
    con.executemany("INSERT INTO clientes VALUES (?)", [(i,) for i in ids])
    base = datetime(2025, 1, 1)
    estados = ["ENTREGADO"] * 85 + ["DEVUELTO"] * 8 + ["CANCELADO"] * 7
    filas = []
    for k in range(n_pedidos):
        f = base + timedelta(seconds=rnd.randrange(0, 21 * 30 * 86400))
        bruto = rnd.randrange(50_000, 3_000_000)
        filas.append((k, rnd.choice(ids), f.strftime("%Y-%m-%d %H:%M:%S"), bruto, bruto // 20, rnd.choice(estados)))
    con.executemany("INSERT INTO pedidos VALUES (?,?,?,?,?,?)", filas)
    canales = ["Chat", "WhatsApp", "Email", "Teléfono"]
    tk = []
    for k in range(n_pedidos // 5):
        f = base + timedelta(seconds=rnd.randrange(0, 21 * 30 * 86400))
        tk.append((k, rnd.choice(ids), f.strftime("%Y-%m-%d %H:%M:%S"), rnd.choice(canales)))
    con.executemany("INSERT INTO tickets_soporte VALUES (?,?,?,?)", tk)
    con.commit()
    return con


def medir(con, sql, params):
    t = time.perf_counter()
    filas = con.execute(sql, params).fetchall()
    return time.perf_counter() - t, filas


def main():
    p = dict(anio=ANIO, mes=MES, ini=INI, fin=FIN)
    print("Tiempos en segundos (SQLite, datos sintéticos). '-' = no se ejecutó por tardar demasiado.\n")
    print(f"{'pedidos':>10} {'original sin índices':>22} {'original + índices':>20} {'reescrita + índices':>21}  igual")
    for n in (4_000, 8_000, 16_000, 32_000, 500_000, 2_000_000):
        con = crear(n)
        t_o = "-"
        if n <= 32_000:
            t, r_o = medir(con, ORIGINAL, p)
            t_o = f"{t:.2f}"
        for ddl in INDICES:
            con.execute(ddl)
        con.execute("ANALYZE")
        t_oi = "-"
        r_oi = None
        if n <= 500_000:
            t, r_oi = medir(con, ORIGINAL, p)
            t_oi = f"{t:.2f}"
        t_r, r_r = medir(con, REESCRITA, p)
        igual = "-"
        if r_oi is not None:
            ordenar = lambda rs: sorted(rs, key=lambda x: x[0])
            igual = "sí" if ordenar(r_oi) == ordenar(r_r) else "NO"
        print(f"{n:>10,} {t_o:>22} {t_oi:>20} {t_r:>21.2f}  {igual}")
        con.close()


if __name__ == "__main__":
    main()
