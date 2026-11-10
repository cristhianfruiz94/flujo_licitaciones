"""Pruebas del prototipo. Ejecutar con:  python -m unittest discover -s tests -v"""
import tempfile
import unittest
from pathlib import Path

from prototipo import config
from prototipo.etapa_01_correo import leer_correos_demo, parsear_correo
from prototipo.etapa_03_unspsc import descargar_html, identificar_unspsc
from prototipo.etapa_04_registro import MatrizOportunidades
from prototipo.etapa_05_experiencia import cargar_rup, texto_corrupto
from prototipo.etapa_06_evaluacion import MotorReglas, analisis_geografico, parsear_respuesta_ia
from prototipo.pipeline import main


class TestParserCorreo(unittest.TestCase):
    def setUp(self):
        self.correos = {c["_origen"]: parsear_correo(c) for c in leer_correos_demo()}
        self.c1 = self.correos["01_SA-ACU-014-2026.eml"]

    def test_campos_principales(self):
        self.assertEqual(self.c1["numeroProceso"], "SA-ACU-014-2026")
        self.assertIn("ACUEDUCTO", self.c1["entidad"])
        self.assertEqual(self.c1["valor"], "450.000.000")
        self.assertEqual((self.c1["departamento"], self.c1["municipio"]), ("Valle del Cauca", "Cali"))
        self.assertIn("detalle-contrato", self.c1["enlaceProceso"])

    def test_cronograma_y_documentos(self):
        eventos = [e["evento"] for e in self.c1["cronograma"]]
        self.assertIn("Fecha y Hora de Cierre del Proceso", eventos)
        tipos = {d["tipo"] for d in self.c1["documentosClasificados"]}
        self.assertIn("Estudios Previos", tipos)

    def test_valor_no_informado(self):
        self.assertEqual(self.correos["04_SI-PTO-022-2026.eml"]["valor"], "")


class TestUNSPSC(unittest.TestCase):
    def test_extrae_principal_y_secundarios(self):
        u = identificar_unspsc(descargar_html("", "SA-ACU-014-2026"))
        self.assertTrue(u["Clase"].startswith("72103300"))
        self.assertEqual([s["codigo"] for s in u["unspsc_secundarios"]], ["72103300", "47101500"])
        self.assertEqual(u["idContrato"], "SA-ACU-014-2026")


class TestMotorReglas(unittest.TestCase):
    m = MotorReglas()

    def test_geografia_por_linea(self):
        cali = analisis_geografico("Valle del Cauca : Cali")
        otro = analisis_geografico("Nariño : Pasto")
        self.assertEqual(self.m.score_geografia(cali, 1), 100)
        self.assertEqual(self.m.score_geografia(otro, 1), 30)
        self.assertEqual(self.m.score_geografia(otro, 2), 85)

    def test_presupuesto(self):
        geo = analisis_geografico("Cundinamarca : Chía")
        self.assertIsNone(self.m.score_presupuesto(0, geo, 1))
        self.assertEqual(self.m.score_presupuesto(50e6, geo, 1), 80)
        self.assertEqual(self.m.score_presupuesto(600e6, geo, 1), 100)
        self.assertEqual(self.m.score_presupuesto(15e6, analisis_geografico("Valle del Cauca : Palmira"), 1), 85)

    def test_filtro_negativo(self):
        fit, _, neg = self.m.fit_objeto("Mantenimiento del parque automotor y repuestos automotrices")
        self.assertTrue(neg)
        self.assertLessEqual(fit, 15)

    def test_linea_2(self):
        self.assertEqual(self.m.linea_negocio("Suministro de mangueras y boquillas para alcantarillado"), 2)
        self.assertEqual(self.m.linea_negocio("Limpieza de redes de alcantarillado"), 1)

    def test_frecuencia_unspsc(self):
        rup, _ = cargar_rup()
        self.assertEqual(self.m.score_frecuencia("72103300 | 47101500", rup)[0], 100)
        self.assertEqual(self.m.score_frecuencia("40142000 | 27111700", rup)[0], 85)
        self.assertEqual(self.m.score_frecuencia("99999999", rup)[0], 20)

    def test_pesos_suman_uno(self):
        self.assertAlmostEqual(sum(config.PESOS_CON_PRESUPUESTO.values()), 1.0)
        self.assertAlmostEqual(sum(config.PESOS_SIN_PRESUPUESTO.values()), 1.0)

    def test_decision(self):
        self.assertEqual(MotorReglas.decidir(85), "PARTICIPAR")
        self.assertEqual(MotorReglas.decidir(84), "REVISIÓN MANUAL")
        self.assertEqual(MotorReglas.decidir(59), "NO PARTICIPAR")


class TestParserIA(unittest.TestCase):
    def test_fences_y_texto_extra(self):
        self.assertEqual(parsear_respuesta_ia('```json\n{"match_final": 90}\n```')["match_final"], 90)
        self.assertEqual(parsear_respuesta_ia('Resultado: {"match_final": 70} fin')["match_final"], 70)
        self.assertTrue(parsear_respuesta_ia("sin json")["parse_error"])

    def test_rup_corrupto(self):
        self.assertTrue(texto_corrupto(""))
        self.assertTrue(texto_corrupto("�" * 100))


class TestPipeline(unittest.TestCase):
    def test_extremo_a_extremo(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = config.SALIDA
            config.SALIDA = Path(tmp)
            try:
                resultados = main([])
                por_codigo = {r["codigo"]: r for r in resultados}
                self.assertTrue(por_codigo["SA-ACU-014-2026"]["alerta"])
                self.assertFalse(por_codigo["LP-GOB-009-2026"]["alerta"])
                self.assertEqual(por_codigo["LP-GOB-009-2026"]["evaluacion"]["decision"], "NO PARTICIPAR")
                filas = MatrizOportunidades(Path(tmp) / "Oportunidades_Licitacion.xlsx").filas()
                self.assertEqual(len(filas), 4)  # upsert: una fila por proceso
                self.assertTrue(all("match_final" in f for f in filas))
            finally:
                config.SALIDA = original


if __name__ == "__main__":
    unittest.main()
