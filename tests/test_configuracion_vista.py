"""Pantalla de configuración de la persistencia, sin servidor MySQL."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


class ConfiguracionVistaTests(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk

            sonda = tk.Tk()
            sonda.withdraw()
            sonda.destroy()
        except Exception as error:
            self.skipTest(f"Tk no disponible: {error}")
        self._temporal = tempfile.TemporaryDirectory()
        self.ruta_ini = Path(self._temporal.name) / "config.ini"
        from flashfood.controladores.controlador import Controlador
        from flashfood.vista.aplicacion import Aplicacion
        import flashfood.vista.comun as comun
        import flashfood.vista.configuracion as configuracion

        self.errores_comun = comun.mostrar_error = MagicMock()
        self.informar = configuracion.informar = MagicMock()
        self.errores = configuracion.mostrar_error = MagicMock()
        self.controlador = Controlador(self._temporal.name)
        self.app = Aplicacion(self.controlador)
        self.app.withdraw()
        self.app.update_idletasks()
        self.app._botones_nav["configuracion"].invoke()
        self.pantalla = self.app._pantallas["configuracion"]

    def tearDown(self):
        self.app.destroy()
        self._temporal.cleanup()

    def _estados_campos(self) -> set[str]:
        return {str(campo.cget("state")) for campo in self.pantalla._campos}

    def _usar_mysql(self, host: str, puerto: str) -> None:
        self.pantalla.motor.set("mysql")
        self.pantalla.mostrar_campos()
        self.pantalla.host.set(host)
        self.pantalla.puerto.set(puerto)

    def test_arranca_con_json_y_campos_deshabilitados(self):
        self.assertIs(self.app._actual, self.pantalla)
        self.assertEqual(self.pantalla.motor.get(), "json")
        self.assertEqual(self._estados_campos(), {"disabled"})
        self.assertEqual(str(self.pantalla.boton_probar.cget("state")), "disabled")
        self.assertIn("En uso: JSON", self.pantalla.estado.cget("text"))

    def test_elegir_mysql_habilita_campos(self):
        self.pantalla.motor.set("mysql")
        self.pantalla.mostrar_campos()
        self.assertEqual(self._estados_campos(), {"normal"})
        self.assertEqual(str(self.pantalla.boton_probar.cget("state")), "normal")

    def test_guardar_json_escribe_config(self):
        self.assertFalse(self.ruta_ini.exists())
        self.pantalla.guardar()
        self.errores_comun.assert_not_called()
        self.informar.assert_called_once()
        self.assertTrue(self.ruta_ini.exists())
        self.assertIn("motor = json", self.ruta_ini.read_text(encoding="utf-8"))
        self.assertEqual(self.controlador.motor_activo, "json")

    def test_puerto_invalido_no_cambia_nada(self):
        self._usar_mysql("127.0.0.1", "abc")
        self.pantalla.guardar()
        self.errores_comun.assert_called_once()
        self.informar.assert_not_called()
        self.assertFalse(self.ruta_ini.exists())
        self.assertEqual(self.controlador.motor_activo, "json")

    def test_servidor_inalcanzable_no_cambia_nada(self):
        self.pantalla.guardar()
        contenido = self.ruta_ini.read_text(encoding="utf-8")
        self.informar.reset_mock()
        self._usar_mysql("127.0.0.1", "1")
        self.pantalla.guardar()
        self.errores_comun.assert_called_once()
        self.informar.assert_not_called()
        self.assertEqual(self.ruta_ini.read_text(encoding="utf-8"), contenido)
        self.assertEqual(self.controlador.motor_activo, "json")


if __name__ == "__main__":
    unittest.main()
