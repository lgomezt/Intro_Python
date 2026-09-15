import ast
import contextlib
import io
import json
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (
    ROOT
    / "Introducción al Análisis de Datos en Python"
    / "Clase 6. Costo Computacional"
    / "Costo Computacional y Pensamiento Algorítmico (Nueva Versión).ipynb"
)


def cargar_notebook():
    with NOTEBOOK.open(encoding="utf-8") as archivo:
        return json.load(archivo)


def codigo_con_tag(notebook, tag):
    return [
        "".join(celda["source"])
        for celda in notebook["cells"]
        if celda["cell_type"] == "code"
        and tag in celda.get("metadata", {}).get("tags", [])
    ]


def ejecutar_tags(*tags):
    notebook = cargar_notebook()
    espacio = {}
    salida = io.StringIO()

    with contextlib.redirect_stdout(salida):
        for celda in notebook["cells"]:
            if celda["cell_type"] != "code":
                continue
            tags_celda = celda.get("metadata", {}).get("tags", [])
            if any(tag in tags_celda for tag in tags):
                exec("".join(celda["source"]), espacio)

    return espacio


class NotebookCostoComputacionalTest(unittest.TestCase):
    def assert_tags_present(self, *tags):
        notebook = cargar_notebook()
        for tag in tags:
            self.assertTrue(codigo_con_tag(notebook, tag), f"Falta la celda: {tag}")

    def test_todas_las_celdas_de_codigo_compilan(self):
        notebook = cargar_notebook()

        for indice, celda in enumerate(notebook["cells"]):
            if celda["cell_type"] == "code":
                compile("".join(celda["source"]), f"celda_{indice}", "exec")

    def test_celdas_para_escribir_juntos_son_cortas(self):
        notebook = cargar_notebook()
        celdas = codigo_con_tag(notebook, "escribir-juntos")

        self.assertGreaterEqual(len(celdas), 5)
        for codigo in celdas:
            lineas = [linea for linea in codigo.splitlines() if linea.strip()]
            self.assertLessEqual(len(lineas), 16, codigo)

    def test_busqueda_se_mide_con_codigo_directo(self):
        notebook = cargar_notebook()
        codigo = "\n".join(codigo_con_tag(notebook, "busqueda-cedula"))

        self.assertIn("cedulas_lista = list(range(1_000_000))", codigo)
        self.assertIn("cedula_buscada in cedulas_lista", codigo)
        self.assertIn("cedula_buscada in cedulas_set", codigo)
        self.assertGreaterEqual(codigo.count("time.perf_counter()"), 4)

    def test_vectorizacion_empieza_con_un_hospital_y_coincide_con_el_loop(self):
        self.assert_tags_present(
            "imports", "datos-hogares", "distancia-loop", "distancia-vectorizada"
        )
        espacio = ejecutar_tags(
            "imports",
            "datos-hogares",
            "distancia-loop",
            "distancia-vectorizada",
        )

        np.testing.assert_allclose(
            espacio["distancias_loop"], espacio["distancias_numpy"]
        )
        self.assertEqual(espacio["hogares"].shape, (10_000, 2))

    def test_los_dos_algoritmos_encuentran_los_mismos_duplicados(self):
        self.assert_tags_present("imports", "duplicados")
        espacio = ejecutar_tags("imports", "duplicados")
        cedulas = [101, 204, 305, 101, 999, 204, 204]

        esperado = {101, 204}
        self.assertEqual(espacio["duplicados_fuerza_bruta"](cedulas), esperado)
        self.assertEqual(espacio["duplicados_hash"](cedulas), esperado)

    def test_batched_asignacion_coincide_con_matriz_completa(self):
        self.assert_tags_present(
            "imports",
            "datos-hogares",
            "tres-hospitales",
            "batching",
        )
        espacio = ejecutar_tags(
            "imports",
            "datos-hogares",
            "tres-hospitales",
            "batching",
        )

        np.testing.assert_array_equal(
            espacio["hospital_por_lotes"], espacio["hospital_mas_cercano"]
        )
        np.testing.assert_allclose(
            espacio["distancia_por_lotes"], espacio["distancia_mas_cercana"]
        )

    def test_dynamic_programming_valora_la_put_sin_funciones_auxiliares(self):
        self.assert_tags_present("imports", "opcion-americana")
        espacio = ejecutar_tags("imports", "opcion-americana")

        self.assertAlmostEqual(espacio["valor_put_americana"], 8.7436, places=3)
        self.assertGreaterEqual(
            espacio["valor_put_americana"],
            max(espacio["K"] - espacio["S0"], 0),
        )

        codigo = "\n".join(codigo_con_tag(cargar_notebook(), "opcion-americana"))
        arbol = ast.parse(codigo)
        self.assertFalse(any(isinstance(nodo, ast.FunctionDef) for nodo in ast.walk(arbol)))

    def test_sliding_window_reproduce_los_promedios_recalculados(self):
        self.assert_tags_present("imports", "sliding-window")
        espacio = ejecutar_tags("imports", "sliding-window")

        esperado = [101.0, 102.6666666667, 104.6666666667, 106.6666666667]
        np.testing.assert_allclose(espacio["promedios_recalculados"], esperado)
        np.testing.assert_allclose(espacio["promedios_sliding"], esperado)

    def test_el_bono_termina_en_una_celda_vacia(self):
        notebook = cargar_notebook()
        ultima = notebook["cells"][-1]

        self.assertEqual(ultima["cell_type"], "code")
        self.assertIn("bono-climbing-stairs", ultima["metadata"].get("tags", []))
        self.assertEqual("".join(ultima["source"]).strip(), "")


if __name__ == "__main__":
    unittest.main()
