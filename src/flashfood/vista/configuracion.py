"""Elección de la persistencia: archivos JSON o base de datos MySQL."""

import tkinter as tk
from tkinter import ttk

from flashfood.vista.comun import Pantalla, informar, mostrar_error, titulo


class Configuracion(Pantalla):
    def __init__(self, master, controlador):
        super().__init__(master, controlador)
        titulo(self, "Configuración")
        ttk.Label(
            self,
            text="Elige dónde guarda FlashFood sus datos. El cambio se aplica al instante y queda guardado.",
            wraplength=760,
        ).pack(anchor="w", pady=(0, 8))
        self.estado = ttk.Label(self, justify="left", wraplength=760)
        self.estado.pack(anchor="w", pady=(0, 12))

        persistencia = ttk.LabelFrame(self, text="Persistencia", padding=12)
        persistencia.pack(fill="x", pady=(0, 12))
        self.motor = tk.StringVar(value="json")
        ttk.Radiobutton(
            persistencia,
            text="Archivos JSON (carpeta data/)",
            value="json",
            variable=self.motor,
            command=self.mostrar_campos,
        ).pack(anchor="w")
        ttk.Radiobutton(
            persistencia,
            text="Base de datos MySQL",
            value="mysql",
            variable=self.motor,
            command=self.mostrar_campos,
        ).pack(anchor="w", pady=(6, 0))

        conexion = ttk.LabelFrame(self, text="Conexión MySQL", padding=12)
        conexion.pack(fill="x")
        self.host = tk.StringVar()
        self.puerto = tk.StringVar()
        self.usuario = tk.StringVar()
        self.contrasena = tk.StringVar()
        self.base_datos = tk.StringVar()
        self._campos: list[ttk.Entry] = []
        for fila, texto, variable, oculto in (
            (0, "Servidor", self.host, False),
            (1, "Puerto", self.puerto, False),
            (2, "Usuario", self.usuario, False),
            (3, "Contraseña", self.contrasena, True),
            (4, "Base de datos", self.base_datos, False),
        ):
            ttk.Label(conexion, text=texto).grid(row=fila, column=0, sticky="w", pady=4)
            campo = ttk.Entry(conexion, textvariable=variable, show="•" if oculto else "")
            campo.grid(row=fila, column=1, sticky="ew", padx=(8, 0), pady=4)
            self._campos.append(campo)
        conexion.columnconfigure(1, weight=1)

        acciones = ttk.Frame(self)
        acciones.pack(fill="x", pady=(12, 0))
        self.boton_probar = ttk.Button(acciones, text="Probar conexión", command=self.probar)
        self.boton_guardar = ttk.Button(acciones, text="Guardar y aplicar", command=self.guardar)
        self.boton_deshacer = ttk.Button(acciones, text="Deshacer cambios", command=self.refrescar)
        for boton in (self.boton_probar, self.boton_guardar, self.boton_deshacer):
            boton.pack(side="left", padx=(0, 8))

        ttk.Label(
            self,
            text=(
                "Las tablas se crean con database/01_esquema.sql y los datos de ejemplo con "
                "database/02_datos_ejemplo.sql. La contraseña queda en texto plano en config.ini, "
                "que no se sube al repositorio."
            ),
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(16, 0))
        self.refrescar()

    def refrescar(self) -> None:
        configuracion = self.controlador.configuracion
        self.motor.set(configuracion.motor)
        self.host.set(configuracion.mysql.host)
        self.puerto.set(str(configuracion.mysql.puerto))
        self.usuario.set(configuracion.mysql.usuario)
        self.contrasena.set(configuracion.mysql.contrasena)
        self.base_datos.set(configuracion.mysql.base_datos)
        lineas = [
            f"En uso: {self.controlador.origen_datos}",
            f"Archivo: {self.controlador.archivo_configuracion}",
        ]
        if self.controlador.motor_activo != configuracion.motor:
            lineas.append(
                "Atención: la configuración guardada pide MySQL, pero se está trabajando con JSON "
                "porque no se pudo conectar."
            )
        self.estado.configure(text="\n".join(lineas))
        self.mostrar_campos()

    def mostrar_campos(self) -> None:
        estado = "normal" if self.motor.get() == "mysql" else "disabled"
        for campo in self._campos:
            campo.configure(state=estado)
        self.boton_probar.configure(state=estado)

    def probar(self) -> None:
        if self.motor.get() != "mysql":
            mostrar_error(self.winfo_toplevel(), "Elige Base de datos MySQL para probar la conexión.")
            return
        ok, version = self.ejecutar(
            lambda: self.controlador.probar_mysql(
                self.host.get(),
                self.puerto.get(),
                self.usuario.get(),
                self.contrasena.get(),
                self.base_datos.get(),
            )
        )
        if not ok:
            return
        informar(
            self.winfo_toplevel(),
            "Conexión correcta",
            f"MySQL respondió (versión {version}). Las tablas de FlashFood existen.",
        )

    def guardar(self) -> None:
        ok, _resultado = self.ejecutar(
            lambda: self.controlador.aplicar_configuracion(
                self.motor.get(),
                self.host.get(),
                self.puerto.get(),
                self.usuario.get(),
                self.contrasena.get(),
                self.base_datos.get(),
            )
        )
        if not ok:
            return
        informar(
            self.winfo_toplevel(),
            "Configuración aplicada",
            f"FlashFood ahora trabaja con {self.controlador.origen_datos}.",
        )
        self.refrescar()
