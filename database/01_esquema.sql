-- FlashFood — Operación 13:00
-- Esquema de la base de datos para la persistencia MySQL.
--
-- Uso con XAMPP (MySQL iniciado): importar este archivo y luego 02_datos_ejemplo.sql
-- desde phpMyAdmin (pestaña Importar), o por terminal:
--   mysql -u root < database/01_esquema.sql
--   mysql -u root < database/02_datos_ejemplo.sql
--
-- ATENCIÓN: este script borra y vuelve a crear las tablas de FlashFood.
-- Probado con MariaDB 10.4 (XAMPP). También funciona en MySQL 8.0.16+.

CREATE DATABASE IF NOT EXISTS flashfood
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE flashfood;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS historial_pedido;
DROP TABLE IF EXISTS detalles_pedido;
DROP TABLE IF EXISTS pagos;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS repartidores;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS operacion;
SET FOREIGN_KEY_CHECKS = 1;

-- Catálogo. Comida usa `categoria`; Bebida usa `mililitros` (herencia en una sola tabla).
CREATE TABLE productos (
  id          VARCHAR(40)  NOT NULL,
  tipo        ENUM('comida', 'bebida') NOT NULL,
  nombre      VARCHAR(120) NOT NULL,
  precio      INT UNSIGNED NOT NULL,
  stock       INT UNSIGNED NOT NULL DEFAULT 0,
  categoria   VARCHAR(80)  NULL,
  mililitros  INT UNSIGNED NULL,
  creado_en   DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  CONSTRAINT chk_productos_precio CHECK (precio > 0),
  CONSTRAINT chk_productos_tipo CHECK (
    (tipo = 'comida' AND categoria IS NOT NULL AND mililitros IS NULL)
    OR (tipo = 'bebida' AND mililitros IS NOT NULL AND mililitros > 0 AND categoria IS NULL)
  )
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

CREATE TABLE clientes (
  id         VARCHAR(40)  NOT NULL,
  nombre     VARCHAR(120) NOT NULL,
  telefono   VARCHAR(30)  NOT NULL,
  direccion  VARCHAR(200) NOT NULL,
  es_vip     TINYINT(1)   NOT NULL DEFAULT 0,
  creado_en  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- La disponibilidad del repartidor no se guarda: se deduce de sus pedidos activos.
CREATE TABLE repartidores (
  id         VARCHAR(40)  NOT NULL,
  nombre     VARCHAR(120) NOT NULL,
  vehiculo   VARCHAR(60)  NOT NULL,
  creado_en  DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- es_vip, hora_punta y lluvia quedan congelados al crear el pedido.
CREATE TABLE pedidos (
  id                VARCHAR(40) NOT NULL,
  cliente_id        VARCHAR(40) NOT NULL,
  repartidor_id     VARCHAR(40) NULL,
  es_vip            TINYINT(1)  NOT NULL DEFAULT 0,
  hora_punta        TINYINT(1)  NOT NULL DEFAULT 0,
  lluvia            TINYINT(1)  NOT NULL DEFAULT 0,
  estado            ENUM('CREADO', 'PAGADO', 'EN_PREPARACION', 'EN_CAMINO', 'ENTREGADO', 'CANCELADO')
                    NOT NULL DEFAULT 'CREADO',
  stock_descontado  TINYINT(1)  NOT NULL DEFAULT 0,
  stock_restituido  TINYINT(1)  NOT NULL DEFAULT 0,
  creado_en         DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  KEY idx_pedidos_cliente (cliente_id),
  KEY idx_pedidos_repartidor (repartidor_id),
  KEY idx_pedidos_estado (estado),
  CONSTRAINT fk_pedidos_cliente FOREIGN KEY (cliente_id) REFERENCES clientes (id),
  CONSTRAINT fk_pedidos_repartidor FOREIGN KEY (repartidor_id) REFERENCES repartidores (id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Líneas del pedido. Nombre y precio quedan congelados al agregar el producto.
CREATE TABLE detalles_pedido (
  pedido_id        VARCHAR(40)       NOT NULL,
  linea            SMALLINT UNSIGNED NOT NULL,
  producto_id      VARCHAR(40)       NOT NULL,
  nombre           VARCHAR(120)      NOT NULL,
  precio_unitario  INT UNSIGNED      NOT NULL,
  cantidad         INT UNSIGNED      NOT NULL,
  PRIMARY KEY (pedido_id, linea),
  UNIQUE KEY uq_detalles_producto (pedido_id, producto_id),
  KEY idx_detalles_producto (producto_id),
  CONSTRAINT fk_detalles_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE,
  CONSTRAINT fk_detalles_producto FOREIGN KEY (producto_id) REFERENCES productos (id),
  CONSTRAINT chk_detalles_precio CHECK (precio_unitario > 0),
  CONSTRAINT chk_detalles_cantidad CHECK (cantidad > 0)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Recorrido de estados de cada pedido, en orden.
CREATE TABLE historial_pedido (
  pedido_id  VARCHAR(40)       NOT NULL,
  orden      SMALLINT UNSIGNED NOT NULL,
  estado     ENUM('CREADO', 'PAGADO', 'EN_PREPARACION', 'EN_CAMINO', 'ENTREGADO', 'CANCELADO') NOT NULL,
  PRIMARY KEY (pedido_id, orden),
  CONSTRAINT fk_historial_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Pago confirmado del pedido (0 o 1 por pedido).
CREATE TABLE pagos (
  pedido_id   VARCHAR(40)  NOT NULL,
  aprobado    TINYINT(1)   NOT NULL,
  referencia  VARCHAR(80)  NOT NULL DEFAULT '',
  medio       VARCHAR(40)  NOT NULL,
  mensaje     VARCHAR(255) NOT NULL DEFAULT '',
  PRIMARY KEY (pedido_id),
  CONSTRAINT fk_pagos_pedido FOREIGN KEY (pedido_id) REFERENCES pedidos (id) ON DELETE CASCADE
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

-- Condiciones del despacho. Una sola fila (id = 1).
CREATE TABLE operacion (
  id          TINYINT UNSIGNED NOT NULL DEFAULT 1,
  hora_punta  TINYINT(1)       NOT NULL DEFAULT 0,
  lluvia      TINYINT(1)       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  CONSTRAINT chk_operacion_unica CHECK (id = 1)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_unicode_ci;

INSERT INTO operacion (id, hora_punta, lluvia) VALUES (1, 0, 0);
