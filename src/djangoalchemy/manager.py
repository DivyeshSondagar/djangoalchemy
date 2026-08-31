"""The ``objects`` manager: the entry point attached to every model."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.orm import Session

from .queryset import QuerySet

ModelT = TypeVar("ModelT")
SessionProvider = Callable[[], Session] | Session


class Manager:
    """Attached to a model as ``Model.objects`` (or any other name).

    Resolves the SQLAlchemy session from the configured ``session_provider``
    on every call, so it works with request-scoped sessions (e.g. FastAPI
    dependencies) without holding a session itself.
    """

    def __init__(self, model: type[ModelT], session_provider: SessionProvider):
        self.model = model
        self._session_provider = session_provider

    def _session(self) -> Session:
        provider = self._session_provider
        return provider() if callable(provider) else provider

    def get_queryset(self) -> QuerySet:
        return QuerySet(self._session(), self.model)

    def all(self) -> QuerySet:
        return self.get_queryset()

    def filter(self, **kwargs) -> QuerySet:
        return self.get_queryset().filter(**kwargs)

    def exclude(self, **kwargs) -> QuerySet:
        return self.get_queryset().exclude(**kwargs)

    def get(self, **kwargs) -> ModelT:
        return self.get_queryset().get(**kwargs)

    def first(self, **kwargs) -> ModelT | None:
        return self.get_queryset().filter(**kwargs).first()

    def values(self, *fields) -> QuerySet:
        return self.get_queryset().values(*fields)

    def count(self, **kwargs) -> int:
        return self.get_queryset().filter(**kwargs).count()

    def exists(self, **kwargs) -> bool:
        return self.get_queryset().filter(**kwargs).exists()

    def create(self, **kwargs) -> ModelT:
        return self.get_queryset().create(**kwargs)

    def __getattr__(self, name):
        # Django-style delegation: any unhandled method is forwarded to the queryset.
        return getattr(self.get_queryset(), name)
