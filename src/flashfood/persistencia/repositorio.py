"""Contrato común de los repositorios. FlashFood no sabe si guarda en JSON o en MySQL."""

from abc import ABC, abstractmethod
from contextlib import contextmanager


class Repositorio(ABC):
    """Guarda y recupera colecciones por nombre: productos, clientes, repartidores, pedidos y operacion."""

    def __init__(self):
        self.advertencias: list[str] = []

    @property
    @abstractmethod
    def descripcion(self) -> str:
        """Texto visible del origen de los datos."""

    @abstractmethod
    def cargar_lista(self, nombre: str) -> list:
        """Devuelve los registros de una colección como diccionarios."""

    @abstractmethod
    def cargar_objeto(self, nombre: str) -> dict:
        """Devuelve un objeto único (por ejemplo, las condiciones de operación)."""

    @abstractmethod
    def guardar(self, nombre: str, datos: list | dict) -> None:
        """Deja la colección guardada tal como viene en `datos`."""

    def recordar(self, nombre: str, datos: list) -> None:
        """Informa qué registros aceptó el modelo al cargar. Por defecto no hace nada."""
        return None

    @contextmanager
    def transaccion(self):
        """Agrupa varias lecturas o escrituras. Por defecto no hace nada especial."""
        yield self
