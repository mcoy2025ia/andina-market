"""Paridad Spark con datos sintéticos; omisiones hacen fallar este job."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src/shared'),str(ROOT)]
from tests.conftest import escribir_csvs,datos_base
from andina_etl.pipeline import ejecutar


if __name__=='__main__':
    out=ROOT/'.local/ci-spark';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='andina-spark-') as tmp:
        tmp=Path(tmp);raw=tmp/'raw';db=tmp/'warehouse.duckdb'
        escribir_csvs(raw,datos_base());ejecutar(raw,db)
        env=dict(os.environ,ANDINA_TEST_DB=str(db),PYSPARK_PYTHON=sys.executable,
                 PYSPARK_DRIVER_PYTHON=sys.executable,SPARK_LOCAL_IP='127.0.0.1')
        p=subprocess.run([sys.executable,'-m','pytest','tests/test_spark_paridad.py','tests/test_sql_spark.py',
                          'tests/test_spark_extensiones.py',
                          '-q','-ra',f'--junitxml={out/"pytest.xml"}'],cwd=ROOT,env=env,
                         capture_output=True,text=True,encoding='utf-8')
        (out/'pytest.txt').write_text(p.stdout+p.stderr,encoding='utf-8')
        print(p.stdout)
        if p.returncode:raise SystemExit(p.returncode)
        xml=ET.parse(out/'pytest.xml')
        if xml.findall('.//skipped'):raise SystemExit('Spark debe ejecutarse sin omisiones')
