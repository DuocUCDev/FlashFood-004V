# FlashFood — Operación 13:00

Aplicación de escritorio para administrar productos, clientes, pedidos, pagos y repartidores de FlashFood. El caso aplica abstracción, encapsulamiento, herencia y polimorfismo, con arquitectura MVC y persistencia en JSON o en MySQL.

## Ejecutar

Requiere Python 3.12 o superior. Desde la carpeta del repositorio:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
flashfood
```

En Windows: `.venv\Scripts\Activate.ps1`.

Sin configuración, la ventana abre los datos de `data/`. Cada operación vuelve a guardar productos, clientes, repartidores, pedidos y las condiciones de despacho.

```bash
python -m unittest discover -s tests -v
flashfood-demo
```

`flashfood-demo` recorre registro, pago rechazado, pago aprobado, preparación, despacho y entrega sin abrir ventanas.

## Persistencia: JSON o MySQL

La aplicación guarda en archivos JSON (por defecto) o en una base de datos MySQL. Ambas opciones cumplen el mismo contrato (`Repositorio`), así que el modelo y las pantallas no cambian.

**1. Crear la base de datos y cargar los datos de ejemplo (XAMPP)**

Abre el panel de XAMPP e inicia **MySQL**. Luego carga los dos scripts, en orden, de una de estas formas:

- **phpMyAdmin** (`http://localhost/phpmyadmin`, con Apache iniciado): pestaña **Importar** → elegir `database/01_esquema.sql` → Continuar. Repetir con `database/02_datos_ejemplo.sql`.
- **Terminal**, desde la carpeta del repositorio:

```bash
# Windows (cmd, no PowerShell)
C:\xampp\mysql\bin\mysql.exe -u root < database\01_esquema.sql
C:\xampp\mysql\bin\mysql.exe -u root < database\02_datos_ejemplo.sql

# macOS
/Applications/XAMPP/xamppfiles/bin/mysql -u root < database/01_esquema.sql
/Applications/XAMPP/xamppfiles/bin/mysql -u root < database/02_datos_ejemplo.sql
```

Si tu `root` tiene contraseña, agrega `-p`.

`01_esquema.sql` crea la base `flashfood` y sus tablas (si ya existen, las borra y las vuelve a crear). `02_datos_ejemplo.sql` deja 7 productos, 4 clientes, 3 repartidores y un pedido en cada estado. Están probados con MariaDB 10.4, el motor que trae XAMPP; también funcionan en MySQL 8.0.16+.

**2. Indicar la conexión**

Desde la aplicación: pantalla **Configuración** → *Base de datos MySQL* → completar servidor, puerto, usuario, contraseña y base de datos (en XAMPP: `127.0.0.1`, `3306`, `root`, sin contraseña, `flashfood`) → **Probar conexión** → **Guardar y aplicar**. El cambio se aplica sin reiniciar.

A mano: copiar `config.example.ini` como `config.ini` y editarlo.

```ini
[persistencia]
motor = mysql          ; json | mysql

[mysql]
host = 127.0.0.1
puerto = 3306
usuario = root
contrasena =
base_datos = flashfood
```

`config.ini` es propio de cada equipo y no se sube al repositorio (la contraseña queda en texto plano). Si MySQL no responde al abrir, la aplicación avisa y trabaja con JSON para que puedas corregir la conexión.

Los datos de JSON y de MySQL son independientes: cambiar de motor no copia registros de uno a otro.

**3. Probar contra MySQL**

Las pruebas de MySQL se saltan si no se indica un servidor. Con el MySQL de XAMPP iniciado (usuario `root` sin contraseña; si tiene, agrega `FLASHFOOD_TEST_MYSQL_CONTRASENA`), usan bases propias (`flashfood_test`) y no tocan `flashfood`:

```bash
FLASHFOOD_TEST_MYSQL_HOST=127.0.0.1 python -m unittest discover -s tests -v
```

## Pantallas

Inicio, Productos, Clientes, Pedidos, Detalle del pedido, Pagos, Repartidores, Seguimiento y Configuración. El menú **Módulos** cambia de pantalla. Las tablas usan `ttk.Treeview` y los avisos usan `messagebox`.

## Estados

```text
CREADO → PAGADO → EN_PREPARACION → EN_CAMINO → ENTREGADO
   └──────────────→ CANCELADO
```

Se puede cancelar en Creado, Pagado y En preparación. En camino y Entregado no se cancelan. El pedido entregado no vuelve a cambiar.

## Reglas

1. No se agrega una cantidad mayor que el stock disponible, contando lo ya comprometido en otros pedidos creados.
2. El stock nunca queda negativo.
3. Un pedido puede tener varias líneas. El precio de cada línea queda congelado al agregarla.
4. El total es subtotal − descuento + despacho. El despacho base es $2.000. En hora punta sube 25%. Con lluvia se suman $1.000. Un cliente VIP tiene 10% de descuento sobre el subtotal.
5. Un pedido no se paga dos veces. Un pago rechazado no confirma la compra ni descuenta inventario.
6. El stock se descuenta solo cuando el pago queda aprobado, y una sola vez. Si ese descuento no puede completarse, el cobro se anula.
7. Cancelar un pedido pagado restituye el stock una sola vez y libera al repartidor si ya estaba asignado.
8. Un repartidor no tiene dos entregas activas. Se asigna con el pedido en preparación y queda libre al entregar o al cancelar.
9. Una operación inválida muestra el error y la aplicación sigue abierta.

## Pilares de POO

| Pilar | Dónde se ve |
| --- | --- |
| Abstracción | `Producto`, `MetodoPago` y `Repositorio` son clases abstractas (`abc`). No se instancian. |
| Encapsulamiento | El estado, el stock y el pago se cambian con métodos. No hay setters públicos. |
| Herencia | `Comida` y `Bebida` especializan `Producto`. `PagoTarjeta`, `PagoEfectivo`, `PagoBilletera` y `PagoTransferencia` especializan `MetodoPago`. |
| Polimorfismo | `Pedido.cobrar` llama a `procesar` sin saber qué medio concreto recibió. `FlashFood.guardar` llama al repositorio sin saber si es JSON o MySQL. |
| Composición | Un `Pedido` contiene varios `DetallePedido`. |

`PagoTransferencia` se agregó implementando `MetodoPago`. Las otras clases de pago no se modifican para aceptarla.

## Estructura

```text
src/flashfood/modelo/          entidades, reglas y FlashFood
src/flashfood/persistencia/    contrato Repositorio, RepositorioJSON, RepositorioMySQL y la fábrica que elige
src/flashfood/configuracion.py lectura y escritura de config.ini
src/flashfood/controladores/   traducción de la interfaz al modelo
src/flashfood/vista/           ventanas Tkinter y ttk
data/                          datos de ejemplo en JSON
database/                      esquema MySQL y datos de ejemplo
config.example.ini             plantilla de la configuración
tests/                         reglas, persistencia (JSON y MySQL) y recorrido de pantallas
```

El modelo no importa Tkinter. Las pantallas no deciden stock, totales ni transiciones.

## Documentación

- [Diagrama de clases](docs/diagrama-uml.md)
- [Guía docente](docs/guia-docente.md)
- [Especificación](FlashFood_Operacion_1300_Requerimientos.md)
