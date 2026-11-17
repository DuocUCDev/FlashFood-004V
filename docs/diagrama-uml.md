# Diagrama de clases

```mermaid
classDiagram
    class Producto {
        <<abstract>>
        +id
        +nombre
        +precio
        +stock
        +detalle
        +descontar(cantidad)
        +reponer(cantidad)
        +actualizar_especifico(extra)*
    }
    class Comida
    class Bebida
    Producto <|-- Comida
    Producto <|-- Bebida

    class MetodoPago {
        <<abstract>>
        +nombre
        +procesar(monto) ResultadoPago*
        +anular(resultado)
    }
    class PagoTarjeta
    class PagoEfectivo
    class PagoBilletera
    class PagoTransferencia
    MetodoPago <|-- PagoTarjeta
    MetodoPago <|-- PagoEfectivo
    MetodoPago <|-- PagoBilletera
    MetodoPago <|-- PagoTransferencia

    class Cliente
    class Repartidor
    class DetallePedido
    class Pedido {
        +detalles
        +subtotal
        +descuento
        +costo_despacho
        +total
        +cobrar(metodo)
        +confirmar_pago(resultado)
        +cancelar()
    }
    class EstadoPedido
    Pedido o-- DetallePedido
    Pedido --> Cliente
    Pedido --> Repartidor
    Pedido --> EstadoPedido
    Pedido --> ResultadoPago
    DetallePedido --> Producto

    class FlashFood
    class Repositorio {
        <<abstract>>
        +descripcion
        +cargar_lista(nombre)*
        +cargar_objeto(nombre)*
        +guardar(nombre, datos)*
        +transaccion()
    }
    class RepositorioJSON
    class RepositorioMySQL
    class Configuracion {
        +motor
        +mysql
    }
    Repositorio <|-- RepositorioJSON
    Repositorio <|-- RepositorioMySQL
    class Controlador
    class Aplicacion
    FlashFood o-- Producto
    FlashFood o-- Cliente
    FlashFood o-- Pedido
    FlashFood o-- Repartidor
    FlashFood --> Repositorio
    Controlador --> FlashFood
    Controlador --> Configuracion
    Aplicacion --> Controlador
```

`PagoTransferencia` entra por el mismo contrato `MetodoPago`. `FlashFood.pagar` no tiene una rama por cada medio: recibe el objeto y el pedido llama a `procesar`.

`FlashFood` solo conoce el contrato `Repositorio`. `crear_repositorio` (en `persistencia/fabrica.py`) entrega `RepositorioJSON` o `RepositorioMySQL` según `config.ini`, y el resto del sistema no cambia.

## Modelo de datos en MySQL

```mermaid
erDiagram
    clientes ||--o{ pedidos : realiza
    repartidores |o--o{ pedidos : entrega
    pedidos ||--|{ historial_pedido : recorre
    pedidos ||--o{ detalles_pedido : contiene
    pedidos ||--o| pagos : confirma
    productos ||--o{ detalles_pedido : aparece_en
```

`productos` guarda comida y bebida en una sola tabla (`tipo`, `categoria`, `mililitros`). `operacion` tiene una sola fila con hora punta y lluvia. El detalle está en `database/01_esquema.sql`.
