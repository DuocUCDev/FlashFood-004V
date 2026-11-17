"""Lectura y escritura en MySQL, con el mismo contrato que el repositorio JSON.

Las tablas se crean con database/01_esquema.sql. Aquí solo hay SQL: las reglas viven en el modelo.
"""

from contextlib import contextmanager

from flashfood.configuracion import ConfiguracionMySQL
from flashfood.modelo.errores import PersistenciaError
from flashfood.persistencia.repositorio import Repositorio

try:
    import mysql.connector as conector
except ImportError:  # el conector solo hace falta si se usa MySQL
    conector = None

_TABLAS = (
    "productos",
    "clientes",
    "repartidores",
    "pedidos",
    "detalles_pedido",
    "historial_pedido",
    "pagos",
    "operacion",
)
_COLUMNAS = {
    "productos": ("id", "tipo", "nombre", "precio", "stock", "categoria", "mililitros"),
    "clientes": ("id", "nombre", "telefono", "direccion", "es_vip"),
    "repartidores": ("id", "nombre", "vehiculo"),
    "pedidos": (
        "id",
        "cliente_id",
        "repartidor_id",
        "es_vip",
        "hora_punta",
        "lluvia",
        "estado",
        "stock_descontado",
        "stock_restituido",
    ),
}
_SIN_CONEXION = {2002, 2003, 2005, 2006, 2013, 2055}
_ACCESO_DENEGADO = 1045
_SIN_BASE = {1044, 1049}
_SIN_TABLA = 1146
_REFERENCIA = {1451, 1452}
_DATO_EXCEDIDO = {1264, 1406}
# Los borrados van al final y de hijos a padres, para respetar las llaves foráneas.
_ORDEN_DE_BORRADO = ("pedidos", "repartidores", "clientes", "productos")


class RepositorioMySQL(Repositorio):
    def __init__(self, configuracion: ConfiguracionMySQL):
        super().__init__()
        if conector is None:
            raise PersistenciaError(
                "Falta el conector de MySQL. Instálalo con: python -m pip install mysql-connector-python"
            )
        self._configuracion = configuracion
        self._conexion = None
        # Último estado conocido de cada colección: permite escribir solo lo que cambió.
        self._guardado: dict[str, dict[str, dict]] = {}
        self._pendiente: dict[str, dict[str, dict]] = {}
        self._por_eliminar: dict[str, list[str]] = {}

    @property
    def descripcion(self) -> str:
        c = self._configuracion
        return f"MySQL ({c.usuario}@{c.host}:{c.puerto}/{c.base_datos})"

    def probar(self) -> str:
        """Comprueba la conexión y que existan las tablas. Devuelve la versión del servidor."""
        with self._cursor() as cursor:
            for tabla in _TABLAS:
                cursor.execute(f"SELECT 1 FROM {tabla} LIMIT 1")
                cursor.fetchall()
            cursor.execute("SELECT VERSION() AS version")
            return str(cursor.fetchone()["version"])

    @contextmanager
    def transaccion(self):
        """Una sola conexión para todo el bloque: se confirma completo o no se guarda nada."""
        if self._conexion is not None:
            yield self
            return
        conexion = self._conectar()
        self._conexion = conexion
        self._pendiente = {}
        self._por_eliminar = {}
        try:
            yield self
            self._eliminar_pendientes(conexion)
            conexion.commit()
            self._guardado.update(self._pendiente)
        except conector.Error as error:
            self._deshacer(conexion)
            raise self._traducir(error) from error
        except BaseException:
            self._deshacer(conexion)
            raise
        finally:
            self._conexion = None
            self._pendiente = {}
            self._por_eliminar = {}
            self._cerrar(conexion)

    def cargar_lista(self, nombre: str) -> list:
        lectores = {
            "productos": self._leer_productos,
            "clientes": self._leer_clientes,
            "repartidores": self._leer_repartidores,
            "pedidos": self._leer_pedidos,
        }
        if nombre not in lectores:
            raise PersistenciaError(f"MySQL no tiene una colección llamada {nombre}")
        with self._cursor() as cursor:
            datos = lectores[nombre](cursor)
            self._pendiente[nombre] = {item["id"]: item for item in datos}
        return [self._copia(item) for item in datos]

    def recordar(self, nombre: str, datos: list) -> None:
        """Solo se comparan (y se pueden borrar) las filas que el modelo aceptó; las omitidas no se tocan."""
        aceptados = {item["id"]: self._copia(item) for item in datos}
        if self._conexion is None:
            self._guardado[nombre] = aceptados
        else:
            self._pendiente[nombre] = aceptados

    def cargar_objeto(self, nombre: str) -> dict:
        if nombre != "operacion":
            raise PersistenciaError(f"MySQL no tiene un objeto llamado {nombre}")
        with self._cursor() as cursor:
            cursor.execute("SELECT hora_punta, lluvia FROM operacion WHERE id = 1")
            fila = cursor.fetchone()
        if fila is None:
            return {}
        return {"hora_punta": bool(fila["hora_punta"]), "lluvia": bool(fila["lluvia"])}

    def guardar(self, nombre: str, datos: list | dict) -> None:
        with self._cursor() as cursor:
            if nombre == "operacion":
                cursor.execute(
                    "INSERT INTO operacion (id, hora_punta, lluvia) VALUES (1, %s, %s) "
                    "ON DUPLICATE KEY UPDATE hora_punta = VALUES(hora_punta), lluvia = VALUES(lluvia)",
                    (int(datos.get("hora_punta") is True), int(datos.get("lluvia") is True)),
                )
                return
            if nombre not in _COLUMNAS:
                raise PersistenciaError(f"MySQL no tiene una colección llamada {nombre}")
            actual = {item["id"]: self._copia(item) for item in datos}
            previo = self._pendiente.get(nombre, self._guardado.get(nombre, {}))
            eliminados = [clave for clave in previo if clave not in actual]
            cambiados = [item for clave, item in actual.items() if previo.get(clave) != item]
            self._por_eliminar[nombre] = eliminados
            if cambiados:
                self._escribir(cursor, nombre, cambiados)
                if nombre == "pedidos":
                    self._escribir_partes_de_pedidos(cursor, cambiados)
            self._pendiente[nombre] = actual

    # --- lectura -------------------------------------------------------------

    def _leer_productos(self, cursor) -> list[dict]:
        cursor.execute(
            "SELECT id, tipo, nombre, precio, stock, categoria, mililitros FROM productos ORDER BY creado_en, id"
        )
        productos = []
        for fila in cursor.fetchall():
            producto = {clave: fila[clave] for clave in ("id", "tipo", "nombre", "precio", "stock")}
            if fila["tipo"] == "bebida":
                producto["mililitros"] = fila["mililitros"]
            else:
                producto["categoria"] = fila["categoria"]
            productos.append(producto)
        return productos

    def _leer_clientes(self, cursor) -> list[dict]:
        cursor.execute("SELECT id, nombre, telefono, direccion, es_vip FROM clientes ORDER BY creado_en, id")
        return [{**fila, "es_vip": bool(fila["es_vip"])} for fila in cursor.fetchall()]

    def _leer_repartidores(self, cursor) -> list[dict]:
        cursor.execute("SELECT id, nombre, vehiculo FROM repartidores ORDER BY creado_en, id")
        return [dict(fila) for fila in cursor.fetchall()]

    def _leer_pedidos(self, cursor) -> list[dict]:
        cursor.execute(
            "SELECT id, cliente_id, repartidor_id, es_vip, hora_punta, lluvia, estado, "
            "stock_descontado, stock_restituido FROM pedidos ORDER BY creado_en, id"
        )
        pedidos = {}
        for fila in cursor.fetchall():
            pedidos[fila["id"]] = {
                "id": fila["id"],
                "cliente_id": fila["cliente_id"],
                "es_vip": bool(fila["es_vip"]),
                "hora_punta": bool(fila["hora_punta"]),
                "lluvia": bool(fila["lluvia"]),
                "estado": fila["estado"],
                "historial": [],
                "repartidor_id": fila["repartidor_id"],
                "stock_descontado": bool(fila["stock_descontado"]),
                "stock_restituido": bool(fila["stock_restituido"]),
                "pago": None,
                "detalles": [],
            }
        cursor.execute(
            "SELECT pedido_id, producto_id, nombre, precio_unitario, cantidad "
            "FROM detalles_pedido ORDER BY pedido_id, linea"
        )
        for fila in cursor.fetchall():
            pedido_id = fila.pop("pedido_id")
            pedidos[pedido_id]["detalles"].append(fila)
        cursor.execute("SELECT pedido_id, estado FROM historial_pedido ORDER BY pedido_id, orden")
        for fila in cursor.fetchall():
            pedidos[fila["pedido_id"]]["historial"].append(fila["estado"])
        cursor.execute("SELECT pedido_id, aprobado, referencia, medio, mensaje FROM pagos")
        for fila in cursor.fetchall():
            pedido_id = fila.pop("pedido_id")
            pedidos[pedido_id]["pago"] = {**fila, "aprobado": bool(fila["aprobado"])}
        return list(pedidos.values())

    # --- escritura -----------------------------------------------------------

    def _eliminar_pendientes(self, conexion) -> None:
        cursor = conexion.cursor()
        try:
            for tabla in _ORDEN_DE_BORRADO:
                claves = self._por_eliminar.get(tabla)
                if not claves:
                    continue
                marcas = ", ".join(["%s"] * len(claves))
                # Las líneas, el historial y el pago de un pedido se borran en cascada.
                cursor.execute(f"DELETE FROM {tabla} WHERE id IN ({marcas})", tuple(claves))
        finally:
            cursor.close()

    def _escribir(self, cursor, tabla: str, registros: list[dict]) -> None:
        columnas = _COLUMNAS[tabla]
        marcas = ", ".join(["%s"] * len(columnas))
        actualiza = ", ".join(f"{columna} = VALUES({columna})" for columna in columnas[1:])
        sentencia = (
            f"INSERT INTO {tabla} ({', '.join(columnas)}) VALUES ({marcas}) "
            f"ON DUPLICATE KEY UPDATE {actualiza}"
        )
        for registro in registros:
            cursor.execute(sentencia, tuple(self._valor(registro.get(columna)) for columna in columnas))

    def _escribir_partes_de_pedidos(self, cursor, pedidos: list[dict]) -> None:
        for pedido in pedidos:
            clave = (pedido["id"],)
            cursor.execute("DELETE FROM detalles_pedido WHERE pedido_id = %s", clave)
            cursor.execute("DELETE FROM historial_pedido WHERE pedido_id = %s", clave)
            cursor.execute("DELETE FROM pagos WHERE pedido_id = %s", clave)
            for linea, detalle in enumerate(pedido["detalles"], start=1):
                cursor.execute(
                    "INSERT INTO detalles_pedido (pedido_id, linea, producto_id, nombre, precio_unitario, cantidad) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        pedido["id"],
                        linea,
                        detalle["producto_id"],
                        detalle["nombre"],
                        detalle["precio_unitario"],
                        detalle["cantidad"],
                    ),
                )
            for orden, estado in enumerate(pedido["historial"], start=1):
                cursor.execute(
                    "INSERT INTO historial_pedido (pedido_id, orden, estado) VALUES (%s, %s, %s)",
                    (pedido["id"], orden, estado),
                )
            pago = pedido["pago"]
            if pago is not None:
                cursor.execute(
                    "INSERT INTO pagos (pedido_id, aprobado, referencia, medio, mensaje) VALUES (%s, %s, %s, %s, %s)",
                    (pedido["id"], int(pago["aprobado"]), pago["referencia"], pago["medio"], pago["mensaje"]),
                )

    # --- conexión ------------------------------------------------------------

    @contextmanager
    def _cursor(self):
        """Entrega un cursor. Fuera de una transacción abre una propia y la confirma al terminar."""
        if self._conexion is None:
            with self.transaccion():
                with self._cursor() as cursor:
                    yield cursor
            return
        cursor = self._conexion.cursor(dictionary=True)
        try:
            yield cursor
        finally:
            try:
                cursor.close()
            except conector.Error:
                pass

    def _conectar(self):
        c = self._configuracion
        try:
            return conector.connect(
                host=c.host,
                port=c.puerto,
                user=c.usuario,
                password=c.contrasena,
                database=c.base_datos,
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
                connection_timeout=5,
                autocommit=False,
            )
        except conector.Error as error:
            raise self._traducir(error) from error

    def _traducir(self, error) -> PersistenciaError:
        c = self._configuracion
        codigo = getattr(error, "errno", None)
        if codigo in _SIN_CONEXION:
            mensaje = (
                f"No se pudo conectar a MySQL en {c.host}:{c.puerto}. "
                "Revisa que el servidor esté encendido y los datos de Configuración."
            )
        elif codigo == _ACCESO_DENEGADO:
            mensaje = f"MySQL rechazó al usuario {c.usuario}. Revisa el usuario y la contraseña."
        elif codigo in _SIN_BASE:
            mensaje = (
                f"La base de datos {c.base_datos} no existe o el usuario {c.usuario} no tiene acceso. "
                "Créala con database/01_esquema.sql."
            )
        elif codigo == _SIN_TABLA:
            mensaje = f"A la base de datos {c.base_datos} le faltan tablas. Ejecuta database/01_esquema.sql."
        elif codigo in _DATO_EXCEDIDO:
            mensaje = (
                "MySQL rechazó el dato porque supera el largo o el valor máximo de su columna. "
                f"Detalle: {getattr(error, 'msg', None) or error}"
            )
        elif codigo in _REFERENCIA:
            mensaje = "MySQL rechazó el cambio: el registro está relacionado con otros datos."
        else:
            mensaje = f"Error de MySQL: {getattr(error, 'msg', None) or error}"
        return PersistenciaError(mensaje)

    @staticmethod
    def _deshacer(conexion) -> None:
        try:
            conexion.rollback()
        except Exception:
            pass

    @staticmethod
    def _cerrar(conexion) -> None:
        try:
            conexion.close()
        except Exception:
            pass

    @staticmethod
    def _valor(valor):
        return int(valor) if isinstance(valor, bool) else valor

    @staticmethod
    def _copia(registro: dict) -> dict:
        copia = dict(registro)
        for clave in ("detalles", "historial"):
            if clave in copia:
                copia[clave] = [dict(item) if isinstance(item, dict) else item for item in copia[clave]]
        if isinstance(copia.get("pago"), dict):
            copia["pago"] = dict(copia["pago"])
        return copia
