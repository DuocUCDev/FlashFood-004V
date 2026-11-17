"""Configuración .ini y persistencia MySQL.

Las pruebas de MySQL necesitan un servidor real y solo corren si se indica cuál usar:

    FLASHFOOD_TEST_MYSQL_HOST=127.0.0.1 FLASHFOOD_TEST_MYSQL_CONTRASENA=flashfood \\
        python -m unittest discover -s tests -v

Variables: FLASHFOOD_TEST_MYSQL_HOST, _PUERTO (3306), _USUARIO (root), _CONTRASENA (vacía).
Trabajan en bases propias (flashfood_test y flashfood_test_vacia) y nunca tocan `flashfood`.
"""

import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flashfood.configuracion import Configuracion, ConfiguracionMySQL, guardar_configuracion, leer_configuracion
from flashfood.controladores.controlador import Controlador
from flashfood.modelo.errores import PersistenciaError, ReglaNegocioError
from flashfood.modelo.pago import PagoEfectivo, PagoTarjeta
from flashfood.modelo.pedido import EstadoPedido
from flashfood.modelo.sistema import FlashFood
from flashfood.persistencia.fabrica import crear_repositorio
from flashfood.persistencia.repositorio_json import RepositorioJSON
from flashfood.persistencia.repositorio_mysql import RepositorioMySQL

RAIZ = Path(__file__).resolve().parents[1]
BASE_PRUEBAS = "flashfood_test"
BASE_VACIA = "flashfood_test_vacia"


def servidor_de_pruebas() -> ConfiguracionMySQL | None:
    host = os.environ.get("FLASHFOOD_TEST_MYSQL_HOST")
    if not host:
        return None
    return ConfiguracionMySQL(
        host,
        int(os.environ.get("FLASHFOOD_TEST_MYSQL_PUERTO", "3306")),
        os.environ.get("FLASHFOOD_TEST_MYSQL_USUARIO", "root"),
        os.environ.get("FLASHFOOD_TEST_MYSQL_CONTRASENA", ""),
        BASE_PRUEBAS,
    )


def sentencias(nombre_script: str) -> list[str]:
    """Separa un script de database/ en sentencias y lo apunta a la base de pruebas."""
    lineas = [
        linea
        for linea in (RAIZ / "database" / nombre_script).read_text(encoding="utf-8").splitlines()
        if not linea.strip().startswith("--")
    ]
    texto = "\n".join(lineas)
    texto = texto.replace("CREATE DATABASE IF NOT EXISTS flashfood", f"CREATE DATABASE IF NOT EXISTS {BASE_PRUEBAS}")
    texto = texto.replace("USE flashfood;", f"USE {BASE_PRUEBAS};")
    # Si el script cambia y el reemplazo no calza, se detiene antes de tocar la base real.
    if re.search(r"\bflashfood\b", texto) or f"USE {BASE_PRUEBAS};" not in texto:
        raise AssertionError(f"{nombre_script} no quedó apuntando a {BASE_PRUEBAS}")
    return [parte.strip() for parte in texto.split(";") if parte.strip()]


def estado(sistema: FlashFood) -> dict:
    return {
        "productos": [item.a_diccionario() for item in sistema.listar_productos()],
        "clientes": [item.a_diccionario() for item in sistema.listar_clientes()],
        "repartidores": [item.a_diccionario() for item in sistema.listar_repartidores()],
        "pedidos": [item.a_diccionario() for item in sistema.listar_pedidos()],
        "operacion": (sistema.hora_punta, sistema.lluvia),
    }


def recorrido(sistema: FlashFood) -> None:
    """El mismo guion para cualquier repositorio: catálogo, pedidos en varios estados y una baja."""
    sistema.definir_condiciones(hora_punta=True, lluvia=True)
    comida = sistema.registrar_producto("Comida", "Hamburguesa", 6500, 10, "Sándwich")
    bebida = sistema.registrar_producto("Bebida", "Bebida cola", 1500, 8, 350)
    sobrante = sistema.registrar_producto("Comida", "Ñoquis", 4000, 3, "Pastas")
    cliente = sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central 123", False)
    vip = sistema.registrar_cliente("Andrés Rojas", "+56922222222", "Los Aromos 45", True)
    repartidor = sistema.registrar_repartidor("Diego Muñoz", "Bicicleta")
    entregado = sistema.crear_pedido(vip.id)
    sistema.agregar_producto(entregado.id, comida.id, 2)
    sistema.agregar_producto(entregado.id, bebida.id, 1)
    sistema.pagar(entregado.id, PagoEfectivo(20000))
    sistema.preparar(entregado.id)
    sistema.asignar_repartidor(entregado.id, repartidor.id)
    sistema.despachar(entregado.id)
    sistema.entregar(entregado.id)
    cancelado = sistema.crear_pedido(cliente.id)
    sistema.agregar_producto(cancelado.id, comida.id, 3)
    sistema.pagar(cancelado.id, PagoTarjeta())
    sistema.cancelar(cancelado.id)
    abierto = sistema.crear_pedido(cliente.id)
    sistema.agregar_producto(abierto.id, bebida.id, 4)
    sistema.agregar_producto(abierto.id, comida.id, 1)
    sistema.quitar_producto(abierto.id, comida.id)
    sistema.editar_cliente(cliente.id, "Camila Soto P.", "+56911111111", "Av. Central 456", True)
    sistema.eliminar_producto(sobrante.id)


class ConfiguracionTests(unittest.TestCase):
    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._temporal.name)
        self.ruta = self.carpeta / "config.ini"

    def tearDown(self):
        self._temporal.cleanup()

    def test_sin_archivo_trabaja_con_json(self):
        configuracion = leer_configuracion(self.ruta)
        self.assertEqual(configuracion.motor, "json")
        self.assertEqual(configuracion.mysql.puerto, 3306)
        self.assertIsInstance(crear_repositorio(configuracion, self.carpeta), RepositorioJSON)

    def test_guarda_y_recupera_la_conexion(self):
        original = Configuracion("mysql", ConfiguracionMySQL("db.local", 3307, "ana", "c%la ve;=#1", "tienda"))
        guardar_configuracion(self.ruta, original)
        self.assertEqual(leer_configuracion(self.ruta), original)
        self.assertEqual(stat.S_IMODE(self.ruta.stat().st_mode) & 0o077, 0)
        self.assertNotIn("c%la", repr(original))

    def test_el_ejemplo_del_repositorio_es_valido(self):
        configuracion = leer_configuracion(RAIZ / "config.example.ini")
        self.assertEqual(configuracion, Configuracion())

    def test_rechaza_valores_invalidos(self):
        for motor in ("", "sqlite", "MYSQL "):
            with self.assertRaises(ReglaNegocioError):
                Configuracion(motor)
        for puerto in (0, 70000, "3306", True):
            with self.assertRaises(ReglaNegocioError):
                ConfiguracionMySQL(puerto=puerto)
        with self.assertRaises(ReglaNegocioError):
            ConfiguracionMySQL(host="  ")
        with self.assertRaises(ReglaNegocioError):
            ConfiguracionMySQL(contrasena=" clave ")
        for contenido in ("[persistencia]\nmotor = oracle\n", "[mysql]\npuerto = abc\n", "sin secciones"):
            self.ruta.write_text(contenido, encoding="utf-8")
            with self.assertRaises(PersistenciaError):
                leer_configuracion(self.ruta)

    def test_configuracion_danada_abre_con_json_y_avisa(self):
        self.ruta.write_text("[persistencia]\nmotor = oracle\n", encoding="utf-8")
        controlador = Controlador(self.carpeta)
        self.assertEqual(controlador.motor_activo, "json")
        self.assertIn("config.ini", controlador.advertencia)

    def test_mysql_apagado_abre_con_json_y_avisa(self):
        guardar_configuracion(self.ruta, Configuracion("mysql", ConfiguracionMySQL("127.0.0.1", 1, "nadie", "", "nada")))
        controlador = Controlador(self.carpeta)
        self.assertEqual(controlador.motor_activo, "json")
        self.assertEqual(controlador.configuracion.motor, "mysql")
        self.assertIn("No se pudo conectar a MySQL en 127.0.0.1:1", controlador.advertencia)
        controlador.registrar_cliente("Ana", "+56911112222", "Calle 1", False)
        self.assertTrue((self.carpeta / "clientes.json").exists())

    def test_aplicar_configuracion_invalida_no_cambia_nada(self):
        controlador = Controlador(self.carpeta)
        with self.assertRaises(ReglaNegocioError):
            controlador.aplicar_configuracion("mysql", "127.0.0.1", "abc", "root", "", "flashfood")
        with self.assertRaises(ReglaNegocioError):
            controlador.aplicar_configuracion("sqlite", "127.0.0.1", "3306", "root", "", "flashfood")
        with self.assertRaises(PersistenciaError):
            controlador.aplicar_configuracion("mysql", "127.0.0.1", "1", "root", "", "flashfood")
        self.assertFalse(self.ruta.exists())
        self.assertEqual(controlador.motor_activo, "json")
        controlador.aplicar_configuracion("json", "db.local", "3307", "ana", "clave", "tienda")
        self.assertEqual(leer_configuracion(self.ruta).mysql.host, "db.local")


@unittest.skipUnless(servidor_de_pruebas(), "Define FLASHFOOD_TEST_MYSQL_HOST para probar contra MySQL")
class MySQLTests(unittest.TestCase):
    def setUp(self):
        import mysql.connector

        self.mysql = servidor_de_pruebas()
        self.conexion = mysql.connector.connect(
            host=self.mysql.host,
            port=self.mysql.puerto,
            user=self.mysql.usuario,
            password=self.mysql.contrasena,
            charset="utf8mb4",
            autocommit=True,
        )
        self.ejecutar(*sentencias("01_esquema.sql"))
        self._temporal = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._temporal.name)

    def tearDown(self):
        self.ejecutar(f"DROP DATABASE IF EXISTS {BASE_PRUEBAS}", f"DROP DATABASE IF EXISTS {BASE_VACIA}")
        self.conexion.close()
        self._temporal.cleanup()

    def ejecutar(self, *lista: str) -> None:
        cursor = self.conexion.cursor()
        for sentencia in lista:
            cursor.execute(sentencia)
        cursor.close()

    def consultar(self, sentencia: str) -> list[tuple]:
        cursor = self.conexion.cursor()
        cursor.execute(f"USE {BASE_PRUEBAS}")
        cursor.execute(sentencia)
        filas = cursor.fetchall()
        cursor.close()
        return filas

    def nuevo_sistema(self) -> FlashFood:
        return FlashFood(RepositorioMySQL(self.mysql))

    def test_datos_de_ejemplo_cargan_completos(self):
        self.ejecutar(*sentencias("02_datos_ejemplo.sql"))
        sistema = self.nuevo_sistema()
        self.assertEqual(sistema.advertencias, ())
        self.assertEqual(len(sistema.listar_productos()), 7)
        self.assertEqual(len(sistema.listar_clientes()), 4)
        self.assertTrue(sistema.hora_punta)
        self.assertFalse(sistema.lluvia)
        self.assertEqual(
            sorted(pedido.estado.value for pedido in sistema.listar_pedidos()),
            sorted(item.value for item in EstadoPedido),
        )
        totales = {pedido.id: pedido.total for pedido in sistema.listar_pedidos()}
        self.assertEqual(
            totales,
            {
                "ped-0001": 18500,
                "ped-0002": 10060,
                "ped-0003": 12100,
                "ped-0004": 10600,
                "ped-0005": 9000,
                "ped-0006": 5880,
            },
        )
        self.assertEqual(sistema.obtener_producto("prod-cola").detalle, "350 ml")
        self.assertEqual(sistema.obtener_producto("prod-hamburguesa").detalle, "Sándwich")
        self.assertEqual(sistema.stock_disponible("prod-papas"), 38)
        self.assertFalse(sistema.obtener_repartidor("rep-diego").disponible)
        self.assertTrue(sistema.obtener_repartidor("rep-marta").disponible)
        self.assertEqual(sistema.obtener_pedido("ped-0002").pago.mensaje, "Pago en efectivo aprobado. Vuelto: $940")

    def test_mysql_y_json_guardan_lo_mismo(self):
        en_mysql = self.nuevo_sistema()
        recorrido(en_mysql)
        en_json = FlashFood(RepositorioJSON(self.carpeta))
        recorrido(en_json)

        def sin_ids(datos: dict) -> str:
            texto = repr(datos)
            for sistema in (en_mysql, en_json):
                for grupo in ("productos", "clientes", "repartidores", "pedidos"):
                    for posicion, item in enumerate(estado(sistema)[grupo]):
                        texto = texto.replace(item["id"], f"{grupo}-{posicion}")
                    for pedido in estado(sistema)["pedidos"]:
                        if pedido["pago"]:
                            texto = texto.replace(pedido["pago"]["referencia"], "REF")
            return texto

        recargado = self.nuevo_sistema()
        self.assertEqual(recargado.advertencias, ())
        self.assertEqual(estado(recargado), estado(en_mysql))
        self.assertEqual(sin_ids(estado(recargado)), sin_ids(estado(FlashFood(RepositorioJSON(self.carpeta)))))
        self.assertEqual(len(recargado.listar_pedidos()), 3)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM productos"), [(2,)])
        self.assertEqual(self.consultar("SELECT nombre, es_vip FROM clientes ORDER BY creado_en LIMIT 1"), [("Camila Soto P.", 1)])
        self.assertEqual(self.consultar("SELECT hora_punta, lluvia FROM operacion"), [(1, 1)])

    def test_recarga_sin_volver_a_descontar(self):
        sistema = self.nuevo_sistema()
        comida = sistema.registrar_producto("Comida", "Hamburguesa", 6500, 10, "Sándwich")
        cliente = sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central 123", False)
        repartidor = sistema.registrar_repartidor("Diego Muñoz", "Bicicleta")
        pedido = sistema.crear_pedido(cliente.id)
        sistema.agregar_producto(pedido.id, comida.id, 2)
        sistema.pagar(pedido.id, PagoTarjeta())
        sistema.preparar(pedido.id)
        sistema.asignar_repartidor(pedido.id, repartidor.id)
        recuperado = self.nuevo_sistema()
        self.assertEqual(recuperado.obtener_pedido(pedido.id).estado, EstadoPedido.EN_PREPARACION)
        self.assertEqual(recuperado.obtener_producto(comida.id).stock, 8)
        self.assertFalse(recuperado.obtener_repartidor(repartidor.id).disponible)
        with self.assertRaises(ReglaNegocioError):
            recuperado.pagar(pedido.id, PagoTarjeta())
        self.assertEqual(self.consultar("SELECT stock FROM productos"), [(8,)])
        self.assertEqual(
            self.consultar("SELECT estado FROM historial_pedido ORDER BY orden"),
            [("CREADO",), ("PAGADO",), ("EN_PREPARACION",)],
        )

    def test_un_guardado_que_falla_no_deja_nada_a_medias(self):
        import mysql.connector

        repositorio = RepositorioMySQL(self.mysql)
        sistema = FlashFood(repositorio)
        comida = sistema.registrar_producto("Comida", "Hamburguesa", 6500, 10, "Sándwich")
        cliente = sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central 123", False)
        pedido = sistema.crear_pedido(cliente.id)
        sistema.agregar_producto(pedido.id, comida.id, 2)
        # El guardado falla después de haber escrito el stock y el pedido, justo antes de las líneas y el pago.
        corte = mysql.connector.Error(msg="corte simulado", errno=2013)
        with patch.object(repositorio, "_escribir_partes_de_pedidos", side_effect=corte):
            with self.assertRaises(PersistenciaError) as contexto:
                sistema.pagar(pedido.id, PagoTarjeta())
        self.assertIn("No se pudo conectar", str(contexto.exception))
        self.assertEqual(self.consultar("SELECT stock FROM productos"), [(10,)])
        self.assertEqual(self.consultar("SELECT estado FROM pedidos"), [("CREADO",)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pagos"), [(0,)])
        # La memoria vuelve a lo guardado: el pedido sigue creado y el stock intacto.
        self.assertEqual(sistema.obtener_pedido(pedido.id).estado, EstadoPedido.CREADO)
        self.assertEqual(sistema.obtener_producto(comida.id).stock, 10)
        # La aplicación sigue trabajando y el pago, al repetirlo, se guarda completo.
        sistema.registrar_repartidor("Diego Muñoz", "Bicicleta")
        sistema.pagar(pedido.id, PagoTarjeta())
        self.assertEqual(self.consultar("SELECT stock FROM productos"), [(8,)])
        self.assertEqual(self.consultar("SELECT estado FROM pedidos"), [("PAGADO",)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pagos"), [(1,)])
        self.assertEqual(estado(self.nuevo_sistema()), estado(sistema))

    def test_si_tampoco_se_puede_releer_la_memoria_no_se_vacia(self):
        sistema = self.nuevo_sistema()
        sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central 123", False)
        self.ejecutar(f"DROP TABLE {BASE_PRUEBAS}.pagos")
        with self.assertRaises(PersistenciaError) as contexto:
            sistema.cargar()
        self.assertIn("01_esquema.sql", str(contexto.exception))
        self.assertEqual(len(sistema.listar_clientes()), 1)

    def test_un_dato_que_mysql_rechaza_no_bloquea_lo_que_sigue(self):
        sistema = self.nuevo_sistema()
        with self.assertRaises(PersistenciaError) as contexto:
            sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central " + "9" * 250, False)
        self.assertIn("supera el largo", str(contexto.exception))
        self.assertEqual(sistema.listar_clientes(), ())
        with self.assertRaises(PersistenciaError):
            sistema.registrar_producto("Comida", "Hamburguesa", 6500, 5_000_000_000, "Sándwich")
        sistema.registrar_repartidor("Diego Muñoz", "Bicicleta")
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM clientes"), [(0,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM productos"), [(0,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM repartidores"), [(1,)])

    def test_borra_un_producto_y_su_linea_en_el_mismo_guardado(self):
        repositorio = RepositorioMySQL(self.mysql)
        producto = {"id": "prod-1", "tipo": "comida", "nombre": "Pizza", "precio": 5000, "stock": 3, "categoria": "Horno"}
        cliente = {"id": "cli-1", "nombre": "Ana", "telefono": "+56911112222", "direccion": "Calle 1", "es_vip": False}
        pedido = {
            "id": "ped-1",
            "cliente_id": "cli-1",
            "es_vip": False,
            "hora_punta": False,
            "lluvia": False,
            "estado": "CREADO",
            "historial": ["CREADO"],
            "repartidor_id": None,
            "stock_descontado": False,
            "stock_restituido": False,
            "pago": None,
            "detalles": [{"producto_id": "prod-1", "nombre": "Pizza", "precio_unitario": 5000, "cantidad": 1}],
        }
        with repositorio.transaccion():
            repositorio.guardar("productos", [producto])
            repositorio.guardar("clientes", [cliente])
            repositorio.guardar("pedidos", [pedido])
        # El producto se guarda antes que los pedidos: su borrado debe esperar a que la línea ya no exista.
        with repositorio.transaccion():
            repositorio.guardar("productos", [])
            repositorio.guardar("pedidos", [{**pedido, "detalles": []}])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM productos"), [(0,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM detalles_pedido"), [(0,)])
        with repositorio.transaccion():
            repositorio.guardar("pedidos", [])
            repositorio.guardar("clientes", [])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pedidos"), [(0,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM clientes"), [(0,)])

    def test_una_fila_invalida_se_omite_sin_borrarla_ni_bloquear(self):
        self.ejecutar(*sentencias("02_datos_ejemplo.sql"))
        self.ejecutar(
            f"UPDATE {BASE_PRUEBAS}.clientes SET telefono = '555' WHERE id = 'cli-matias'",
            f"UPDATE {BASE_PRUEBAS}.pedidos SET stock_restituido = 1 WHERE id = 'ped-0003'",
        )
        sistema = self.nuevo_sistema()
        self.assertEqual(len(sistema.advertencias), 2)
        self.assertEqual(len(sistema.listar_clientes()), 3)
        self.assertEqual(len(sistema.listar_pedidos()), 5)
        sistema.definir_condiciones(hora_punta=False, lluvia=True)
        sistema.registrar_repartidor("Luis Soto", "Moto")
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM clientes"), [(4,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pedidos"), [(6,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM pagos"), [(5,)])
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM repartidores"), [(4,)])

    def test_solo_escribe_lo_que_cambio(self):
        sistema = self.nuevo_sistema()
        sistema.registrar_cliente("Camila Soto", "+56911111111", "Av. Central 123", False)
        otro = sistema.registrar_cliente("Andrés Rojas", "+56922222222", "Los Aromos 45", True)
        # Un cambio hecho por fuera en un registro que la aplicación no toca debe sobrevivir.
        self.ejecutar(f"UPDATE {BASE_PRUEBAS}.clientes SET direccion = 'Editada por fuera' WHERE nombre = 'Camila Soto'")
        sistema.editar_cliente(otro.id, "Andrés Rojas", "+56922222222", "Los Aromos 99", True)
        self.assertEqual(
            self.consultar("SELECT direccion FROM clientes ORDER BY creado_en"),
            [("Editada por fuera",), ("Los Aromos 99",)],
        )
        sistema.eliminar_cliente(otro.id)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM clientes"), [(1,)])

    def test_errores_de_conexion_se_explican(self):
        casos = (
            (ConfiguracionMySQL(self.mysql.host, 1, "root", "", BASE_PRUEBAS), "No se pudo conectar"),
            (
                ConfiguracionMySQL(self.mysql.host, self.mysql.puerto, self.mysql.usuario, "mala-clave", BASE_PRUEBAS),
                "Revisa el usuario y la contraseña",
            ),
            (
                ConfiguracionMySQL(
                    self.mysql.host, self.mysql.puerto, self.mysql.usuario, self.mysql.contrasena, "no_existe_ff"
                ),
                "no existe",
            ),
        )
        for configuracion, esperado in casos:
            with self.assertRaises(PersistenciaError) as contexto:
                RepositorioMySQL(configuracion).probar()
            self.assertIn(esperado, str(contexto.exception))
        self.ejecutar(f"CREATE DATABASE IF NOT EXISTS {BASE_VACIA}")
        vacia = ConfiguracionMySQL(
            self.mysql.host, self.mysql.puerto, self.mysql.usuario, self.mysql.contrasena, BASE_VACIA
        )
        with self.assertRaises(PersistenciaError) as contexto:
            FlashFood(RepositorioMySQL(vacia))
        self.assertIn("faltan tablas", str(contexto.exception))
        self.assertTrue(RepositorioMySQL(self.mysql).probar())

    def test_el_controlador_cambia_de_json_a_mysql_y_vuelve(self):
        self.ejecutar(*sentencias("02_datos_ejemplo.sql"))
        controlador = Controlador(self.carpeta)
        controlador.registrar_cliente("Solo en JSON", "+56911112222", "Calle 1", False)
        datos = (self.mysql.host, str(self.mysql.puerto), self.mysql.usuario, self.mysql.contrasena, BASE_PRUEBAS)
        self.assertTrue(controlador.probar_mysql(*datos))
        controlador.aplicar_configuracion("mysql", *datos)
        self.assertEqual(controlador.motor_activo, "mysql")
        self.assertIn(BASE_PRUEBAS, controlador.origen_datos)
        self.assertEqual(len(controlador.listar_clientes()), 4)
        controlador.registrar_cliente("Solo en MySQL", "+56933334444", "Calle 2", True)
        self.assertEqual(self.consultar("SELECT COUNT(*) FROM clientes WHERE nombre = 'Solo en MySQL'"), [(1,)])
        # Al abrir de nuevo, la aplicación recuerda MySQL.
        otro = Controlador(self.carpeta)
        self.assertEqual(otro.motor_activo, "mysql")
        self.assertEqual(len(otro.listar_clientes()), 5)
        otro.aplicar_configuracion("json", *datos)
        self.assertEqual([cliente.nombre for cliente in otro.listar_clientes()], ["Solo en JSON"])
        self.assertEqual(leer_configuracion(self.carpeta / "config.ini").motor, "json")


if __name__ == "__main__":
    unittest.main()
