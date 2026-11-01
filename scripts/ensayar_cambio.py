"""A18: ensayo aislado de un canal nuevo, sin editar fuentes ni base del caso."""
from pathlib import Path
import tempfile
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/shared'),str(ROOT)]
from tests.conftest import datos_base, escribir_csvs
from andina_etl.pipeline import ejecutar
from andina_etl.rules import CANALES
import duckdb


def ensayar():
    anterior=dict(CANALES)
    try:
        with tempfile.TemporaryDirectory(prefix='andina-ensayo-') as tmp:
            tmp=Path(tmp);raw=tmp/'raw';db=tmp/'wh.duckdb';d=datos_base()
            d['pedidos'].append(dict(d['pedidos'][0],id_pedido='P099',canal='MARKETPLACE',fecha_pedido='2025-01-11 10:00:00'))
            escribir_csvs(raw,d);ejecutar(raw,db)
            with duckdb.connect(str(db),read_only=True) as c:
                antes=c.execute('SELECT sum(venta_neta) FROM gold_venta_neta_diaria').fetchone()[0]
            CANALES['MARKETPLACE']='MARKETPLACE'
            ejecutar(raw,db,recalcular_gold=True)
            with duckdb.connect(str(db),read_only=True) as c:
                despues=c.execute('SELECT sum(venta_neta) FROM gold_venta_neta_diaria').fetchone()[0]
                nuevo=c.execute("SELECT count(*) FROM gold.dim_canal WHERE canal='MARKETPLACE'").fetchone()[0]
            assert despues-antes==90000 and nuevo==1
            return {'antes':antes,'despues':despues,'diferencia_esperada':90000,'fuentes_originales_modificadas':False}
    finally:
        CANALES.clear();CANALES.update(anterior)


if __name__=='__main__':print(ensayar())
