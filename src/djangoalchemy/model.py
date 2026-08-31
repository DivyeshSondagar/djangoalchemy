"""Model plumbing: the declarative base and manager attachment helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import DeclarativeBase, Session

from .manager import Manager

ModelT = TypeVar("ModelT")


class DjangoModel(DeclarativeBase):
    """Drop-in declarative base.

    Inherit from this, or keep your own ``Base`` and pass it to
    :func:`configure`.
    """


def configure(session_provider: Callable[[], Session] | Session, base: type[DjangoModel] | None = None) -> list[type]:
    """Attach a ``.objects`` manager to every mapped model in the registry.

    Call this AFTER your models are imported/defined. The provider is any
    zero-arg callable returning a SQLAlchemy ``Session``, or a ``Session``.
    Models that already define their own ``objects`` attribute are left alone.

    Returns the list of models that received a manager.
    """
    base = base or DjangoModel
    attached: list[type] = []
    for cls in base.registry._class_registry.values():
        if (
            isinstance(cls, type)
            and hasattr(cls, "__table__")
            and "__module__" in cls.__dict__
            and not hasattr(cls, "objects")
        ):
            cls.objects = Manager(cls, session_provider)
            attached.append(cls)
    return attached


def bind(model: type[ModelT], session_provider: Callable[[], Session] | Session) -> type[ModelT]:
    """Attach a ``.objects`` manager to a single model."""
    model.objects = Manager(model, session_provider)
    return model
