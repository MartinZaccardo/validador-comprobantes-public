"""
Excepciones de dominio del proyecto.

No importan FastAPI ni HTTP — los handlers en handlers.py son los únicos
responsables de traducir estas excepciones a respuestas HTTP.
"""


class ValidacionNoEncontrada(Exception):
    pass


class EstadoNoReverificable(Exception):
    def __init__(self, estado_actual: str) -> None:
        self.estado_actual = estado_actual


class ErrorSubidaImagen(Exception):
    pass
