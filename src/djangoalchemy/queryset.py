"""Lazy, immutable queryset that compiles to SQLAlchemy queries."""

from __future__ import annotations

from collections import namedtuple

from sqlalchemy import desc, not_
from sqlalchemy.orm import Session

from .aggregates import Aggregate
from .lookups import conditions
from .relations import joined_option, selectin_option


class DoesNotExist(Exception):
    """Raised by ``get()`` when no row matches the query."""


class MultipleObjectsReturned(Exception):
    """Raised by ``get()`` when more than one row matches the query."""


class QuerySet:
    """A lazy, chainable query builder over a SQLAlchemy session.

    Every chaining method returns a copy, so querysets are safe to reuse.
    The SQL is only emitted when the queryset is evaluated (iteration,
    ``all()``, ``first()``, ``count()``, ``len()``, ``bool()``, ``get()``).
    """

    def __init__(self, session: Session, model: type):
        self._session = session
        self._model = model
        self._filters: list = []
        self._excludes: list = []
        self._ordering: list = []
        self._columns: tuple[str, ...] | None = None
        self._mode: str | None = None
        self._related: list = []
        self._annotations: list = []
        self._offset: int | None = None
        self._limit: int | None = None

    # ------------------------------------------------------------------ chaining
    def filter(self, **kwargs) -> "QuerySet":
        """Narrow the query with ``field=value`` or ``field__lookup=value``."""
        clone = self._clone()
        clone._filters.extend(conditions(self._model, **kwargs))
        return clone

    def exclude(self, **kwargs) -> "QuerySet":
        """Negate the given conditions."""
        clone = self._clone()
        clone._excludes.extend(not_(c) for c in conditions(self._model, **kwargs))
        return clone

    def order_by(self, *fields: str) -> "QuerySet":
        """Order ascending, or descending when prefixed with ``-``."""
        clone = self._clone()
        for field in fields:
            column = getattr(self._model, field[1:] if field.startswith("-") else field)
            clone._ordering.append(desc(column) if field.startswith("-") else column)
        return clone

    def values(self, *fields: str) -> "QuerySet":
        """Select only the given columns; evaluates to a list of dicts."""
        clone = self._clone()
        clone._columns = fields
        clone._mode = "dict"
        return clone

    def values_list(self, *fields: str, flat: bool = False, named: bool = False) -> "QuerySet":
        """Select columns as tuples; ``flat=True`` returns scalars, ``named=True`` namedtuples."""
        if flat and named:
            raise ValueError("flat and named are mutually exclusive")
        if flat and len(fields) != 1:
            raise ValueError("flat=True requires exactly one field")
        clone = self._clone()
        clone._columns = fields
        clone._mode = "flat" if flat else "named" if named else "tuple"
        return clone

    def select_related(self, *paths: str) -> "QuerySet":
        """Eagerly load relationships with a JOIN (use for ``many-to-one``)."""
        clone = self._clone()
        for path in paths:
            clone._related.append(joined_option(self._model, path))
        return clone

    def prefetch_related(self, *paths: str) -> "QuerySet":
        """Eagerly load relationships with a separate query (use for ``one-to-many``)."""
        clone = self._clone()
        for path in paths:
            clone._related.append(selectin_option(self._model, path))
        return clone

    def annotate(self, **annotations) -> "QuerySet":
        """Add aggregate expressions; combine with ``values()`` to group by those columns."""
        clone = self._clone()
        for alias, aggregate in annotations.items():
            if not isinstance(aggregate, Aggregate):
                raise TypeError(
                    f"annotate({alias}=...) expects an Aggregate (Sum, Count, Avg, Min, Max)"
                )
            clone._annotations.append((alias, aggregate))
        return clone

    def offset(self, count: int) -> "QuerySet":
        clone = self._clone()
        clone._offset = count
        return clone

    def limit(self, count: int) -> "QuerySet":
        clone = self._clone()
        clone._limit = count
        return clone

    # -------------------------------------------------------------- evaluation
    def _query(self):
        query = self._session.query(self._model)
        for cond in self._filters:
            query = query.filter(cond)
        for cond in self._excludes:
            query = query.filter(cond)
        for option in self._related:
            query = query.options(option)
        if self._ordering:
            query = query.order_by(*self._ordering)
        if self._offset is not None:
            query = query.offset(self._offset)
        if self._limit is not None:
            query = query.limit(self._limit)
        return query

    def _all(self) -> list:
        if self._annotations:
            return self._annotated()
        query = self._query()
        if self._columns:
            columns = [getattr(self._model, c) for c in self._columns]
            rows = query.with_entities(*columns).all()
            return self._project(rows)
        return query.all()

    def _project(self, rows: list) -> list:
        if self._mode == "flat":
            return [row[0] for row in rows]
        if self._mode == "named":
            row_type = namedtuple(f"{self._model.__name__}Row", self._columns)
            return [row_type(*row) for row in rows]
        if self._mode == "tuple":
            return [tuple(row) for row in rows]
        return [dict(zip(self._columns, row)) for row in rows]

    def _annotated(self) -> list:
        query = self._query()
        if self._columns:
            columns = [getattr(self._model, c) for c in self._columns]
            query = query.with_entities(*columns)
            for alias, aggregate in self._annotations:
                query = query.add_columns(aggregate.expression(self._model).label(alias))
            rows = query.group_by(*columns).all()
            keys = list(self._columns) + [alias for alias, _ in self._annotations]
            if self._mode == "flat":
                return [row[0] for row in rows]
            if self._mode == "named":
                row_type = namedtuple(f"{self._model.__name__}Row", keys)
                return [row_type(*row) for row in rows]
            if self._mode == "tuple":
                return [tuple(row) for row in rows]
            return [dict(zip(keys, row)) for row in rows]
        for alias, aggregate in self._annotations:
            query = query.add_columns(aggregate.expression(self._model).label(alias))
        query = query.group_by(*self._model.__mapper__.primary_key)
        instances = []
        for row in query.all():
            instance = row[0]
            for i, (alias, _aggregate) in enumerate(self._annotations, start=1):
                setattr(instance, alias, row[i])
            instances.append(instance)
        return instances

    def all(self) -> list:
        """Evaluate and return all matching rows."""
        return self._all()

    def first(self):
        """Return the first matching row, or ``None``."""
        rows = self.limit(1)._all()
        return rows[0] if rows else None

    def count(self) -> int:
        """Return the number of matching rows."""
        return self._query().count()

    def exists(self) -> bool:
        """Return whether at least one row matches."""
        return self._query().first() is not None

    def get(self, **kwargs):
        """Return the single matching row.

        Raises :class:`DoesNotExist` or :class:`MultipleObjectsReturned`.
        """
        rows = self.filter(**kwargs)._all()
        if not rows:
            raise DoesNotExist(f"{self._model.__name__} matching query does not exist.")
        if len(rows) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self._model.__name__}."
            )
        return rows[0]

    def create(self, **kwargs):
        """Create a row, commit, refresh and return it."""
        instance = self._model(**kwargs)
        self._session.add(instance)
        self._session.commit()
        self._session.refresh(instance)
        return instance

    def update(self, **values) -> int:
        """Set the given attributes on all matching rows and commit."""
        rows = self._all()
        for row in rows:
            for key, value in values.items():
                setattr(row, key, value)
        self._session.commit()
        return len(rows)

    def delete(self) -> int:
        """Delete all matching rows and commit; returns the row count."""
        rows = self._all()
        for row in rows:
            self._session.delete(row)
        self._session.commit()
        return len(rows)

    # ---------------------------------------------------------------- dunder
    def __getitem__(self, item):
        if isinstance(item, slice):
            start = item.start or 0
            if item.stop is None:
                return self.offset(start)._all()
            return self.offset(start).limit(max(item.stop - start, 0))._all()
        if isinstance(item, int):
            rows = self.offset(item).limit(1)._all()
            if not rows:
                raise IndexError(f"{self._model.__name__} index out of range")
            return rows[0]
        raise TypeError("QuerySet indices must be integers or slices")

    def __iter__(self):
        return iter(self._all())

    def __len__(self) -> int:
        return self.count()

    def __bool__(self) -> bool:
        return self.exists()

    def _clone(self) -> "QuerySet":
        clone = QuerySet(self._session, self._model)
        clone._filters = list(self._filters)
        clone._excludes = list(self._excludes)
        clone._ordering = list(self._ordering)
        clone._columns = self._columns
        clone._mode = self._mode
        clone._related = list(self._related)
        clone._annotations = list(self._annotations)
        clone._offset = self._offset
        clone._limit = self._limit
        return clone
