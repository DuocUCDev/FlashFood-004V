-- FlashFood — Operación 13:00
-- Datos de ejemplo (ficticios). Ejecutar después de 01_esquema.sql.
-- Deja un pedido en cada estado para recorrer todas las pantallas.

USE flashfood;

SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM historial_pedido;
DELETE FROM detalles_pedido;
DELETE FROM pagos;
DELETE FROM pedidos;
DELETE FROM repartidores;
DELETE FROM clientes;
DELETE FROM productos;
DELETE FROM operacion;
SET FOREIGN_KEY_CHECKS = 1;

-- El stock ya considera lo descontado por los pedidos pagados de más abajo.
INSERT INTO productos (id, tipo, nombre, precio, stock, categoria, mililitros, creado_en) VALUES
  ('prod-hamburguesa', 'comida', 'Hamburguesa',       6500, 22, 'Sándwich',       NULL, '2026-11-02 09:00:00'),
  ('prod-papas',       'comida', 'Papas fritas',      2500, 40, 'Acompañamiento', NULL, '2026-11-02 09:01:00'),
  ('prod-completo',    'comida', 'Completo italiano', 3200, 28, 'Sándwich',       NULL, '2026-11-02 09:02:00'),
  ('prod-empanada',    'comida', 'Empanada de pino',  2800, 15, 'Horno',          NULL, '2026-11-02 09:03:00'),
  ('prod-cola',        'bebida', 'Bebida cola',       1500, 46, NULL,             350,  '2026-11-02 09:04:00'),
  ('prod-jugo',        'bebida', 'Jugo natural',      2000, 19, NULL,             400,  '2026-11-02 09:05:00'),
  ('prod-agua',        'bebida', 'Agua mineral',      1200, 35, NULL,             500,  '2026-11-02 09:06:00');

INSERT INTO clientes (id, nombre, telefono, direccion, es_vip, creado_en) VALUES
  ('cli-camila',    'Camila Soto',      '+56911112222', 'Av. Central 123',        0, '2026-11-02 09:10:00'),
  ('cli-andres',    'Andrés Rojas',     '+56933334444', 'Los Aromos 45',          1, '2026-11-02 09:11:00'),
  ('cli-valentina', 'Valentina Muñoz',  '+56955556666', 'Pasaje Las Rosas 780',   0, '2026-11-02 09:12:00'),
  ('cli-matias',    'Matías Fernández', '+56977778888', 'Av. Providencia 2100',   1, '2026-11-02 09:13:00');

INSERT INTO repartidores (id, nombre, vehiculo, creado_en) VALUES
  ('rep-diego', 'Diego Muñoz',  'Bicicleta', '2026-11-02 09:20:00'),
  ('rep-marta', 'Marta López',  'Moto',      '2026-11-02 09:21:00'),
  ('rep-pablo', 'Pablo Vargas', 'Auto',      '2026-11-02 09:22:00');

-- Son las 13:00: hora punta, sin lluvia.
INSERT INTO operacion (id, hora_punta, lluvia) VALUES (1, 1, 0);

INSERT INTO pedidos
  (id, cliente_id, repartidor_id, es_vip, hora_punta, lluvia, estado, stock_descontado, stock_restituido, creado_en)
VALUES
  ('ped-0001', 'cli-camila',    'rep-marta', 0, 1, 0, 'ENTREGADO',      1, 0, '2026-11-16 13:02:00'),
  ('ped-0002', 'cli-andres',    'rep-diego', 1, 1, 0, 'EN_CAMINO',      1, 0, '2026-11-16 13:05:00'),
  ('ped-0003', 'cli-valentina', NULL,        0, 1, 0, 'EN_PREPARACION', 1, 0, '2026-11-16 13:08:00'),
  ('ped-0004', 'cli-matias',    NULL,        1, 1, 0, 'PAGADO',         1, 0, '2026-11-16 13:11:00'),
  ('ped-0005', 'cli-camila',    NULL,        0, 1, 0, 'CREADO',         0, 0, '2026-11-16 13:14:00'),
  ('ped-0006', 'cli-andres',    NULL,        1, 0, 1, 'CANCELADO',      1, 1, '2026-11-16 12:40:00');

INSERT INTO detalles_pedido (pedido_id, linea, producto_id, nombre, precio_unitario, cantidad) VALUES
  ('ped-0001', 1, 'prod-hamburguesa', 'Hamburguesa',       6500, 2),
  ('ped-0001', 2, 'prod-cola',        'Bebida cola',       1500, 2),
  ('ped-0002', 1, 'prod-completo',    'Completo italiano', 3200, 2),
  ('ped-0002', 2, 'prod-jugo',        'Jugo natural',      2000, 1),
  ('ped-0003', 1, 'prod-empanada',    'Empanada de pino',  2800, 3),
  ('ped-0003', 2, 'prod-agua',        'Agua mineral',      1200, 1),
  ('ped-0004', 1, 'prod-hamburguesa', 'Hamburguesa',       6500, 1),
  ('ped-0004', 2, 'prod-papas',       'Papas fritas',      2500, 1),
  ('ped-0005', 1, 'prod-papas',       'Papas fritas',      2500, 2),
  ('ped-0005', 2, 'prod-cola',        'Bebida cola',       1500, 1),
  ('ped-0006', 1, 'prod-completo',    'Completo italiano', 3200, 1);

INSERT INTO historial_pedido (pedido_id, orden, estado) VALUES
  ('ped-0001', 1, 'CREADO'), ('ped-0001', 2, 'PAGADO'), ('ped-0001', 3, 'EN_PREPARACION'),
  ('ped-0001', 4, 'EN_CAMINO'), ('ped-0001', 5, 'ENTREGADO'),
  ('ped-0002', 1, 'CREADO'), ('ped-0002', 2, 'PAGADO'), ('ped-0002', 3, 'EN_PREPARACION'),
  ('ped-0002', 4, 'EN_CAMINO'),
  ('ped-0003', 1, 'CREADO'), ('ped-0003', 2, 'PAGADO'), ('ped-0003', 3, 'EN_PREPARACION'),
  ('ped-0004', 1, 'CREADO'), ('ped-0004', 2, 'PAGADO'),
  ('ped-0005', 1, 'CREADO'),
  ('ped-0006', 1, 'CREADO'), ('ped-0006', 2, 'PAGADO'), ('ped-0006', 3, 'CANCELADO');

-- Totales con hora punta (despacho $2.500) y 10% VIP sobre el subtotal:
--   ped-0001: 16.000 + 2.500 = 18.500
--   ped-0002:  8.400 −   840 + 2.500 = 10.060 (pagó con $11.000)
--   ped-0003:  9.600 + 2.500 = 12.100
--   ped-0004:  9.000 −   900 + 2.500 = 10.600
--   ped-0006:  3.200 −   320 + 3.000 =  5.880 (con lluvia, sin hora punta; cancelado y stock restituido)
INSERT INTO pagos (pedido_id, aprobado, referencia, medio, mensaje) VALUES
  ('ped-0001', 1, 'TAR-9F3A61C2',      'Tarjeta',           'Pago con tarjeta aprobado'),
  ('ped-0002', 1, 'EFE-4B7D20E8',      'Efectivo',          'Pago en efectivo aprobado. Vuelto: $940'),
  ('ped-0003', 1, 'BIL-C15E9A07',      'Billetera digital', 'Pago con billetera aprobado'),
  ('ped-0004', 1, 'TRF-20261116-0042', 'Transferencia',     'Transferencia aprobada'),
  ('ped-0006', 1, 'TAR-2D8840B1',      'Tarjeta',           'Pago con tarjeta aprobado');
