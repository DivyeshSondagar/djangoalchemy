"""Django-style aggregate expressions for ``annotate()``."""

from __future__ import annotations

from sqlalchemy import func


class Aggregate:
    """Base class for an aggregate expression used in ``annotate()``.

    Subclasses map to a SQL function applied to a model column.
    """

    sql_name: str | None = None

    def __init__(self, field: str, distinct: bool = False):
        self.field = field
        self.distinct = distinct

    def expression(self, model: type):
        column = getattr(model, self.field)
        target = column.distinct() if self.distinct else column
        return getattr(func, self.sql_name)(target)


class Sum(Aggregate):
    sql_name = "sum"


class Count(Aggregate):
    sql_name = "count"


class Avg(Aggregate):
    sql_name = "avg"


class Min(Aggregate):
    sql_name = "min"


class Max(Aggregate):
    sql_name = "max"
