"""Elige el repositorio según la configuración. Es el único lugar que conoce ambos motores."""

from pathlib import Path

from flashfood.configuracion import Configuracion
from flashfood.persistencia.repositorio import Repositorio
from flashfood.persistencia.repositorio_json import RepositorioJSON
from flashfood.persistencia.repositorio_mysql import RepositorioMySQL


def crear_repositorio(configuracion: Configuracion, directorio: str | Path) -> Repositorio:
    if configuracion.motor == "mysql":
        return RepositorioMySQL(configuracion.mysql)
    return RepositorioJSON(directorio)
