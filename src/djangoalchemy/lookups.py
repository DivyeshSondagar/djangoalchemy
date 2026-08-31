"""Field lookup translators: map Django-style ``field__lookup`` names to SQLAlchemy expressions."""

from __future__ import annotations

from sqlalchemy import ColumnOperators

LOOKUP_MAP = {
    "exact": lambda col, v: col == v,
    "iexact": lambda col, v: col.ilike(v),
    "contains": lambda col, v: col.contains(v),
    "icontains": lambda col, v: col.ilike(f"%{v}%"),
    "startswith": lambda col, v: col.startswith(v),
    "istartswith": lambda col, v: col.ilike(f"{v}%"),
    "endswith": lambda col, v: col.endswith(v),
    "iendswith": lambda col, v: col.ilike(f"%{v}"),
    "gt": lambda col, v: col > v,
    "gte": lambda col, v: col >= v,
    "lt": lambda col, v: col < v,
    "lte": lambda col, v: col <= v,
    "in": lambda col, v: col.in_(v),
    "range": lambda col, v: col.between(v[0], v[1]),
    "isnull": lambda col, v: col.is_(None) if v else col.is_not(None),
}


def conditions(model: type, **kwargs) -> list:
    """Translate ``filter(...)`` kwargs into SQLAlchemy binary expressions.

    Keys may be plain field names (exact match) or ``field__lookup`` pairs.
    Raises ``ValueError`` for unknown fields or lookups.
    """
    result = []
    for key, value in kwargs.items():
        field, lookup = key.rsplit("__", 1) if "__" in key else (key, "exact")
        if lookup not in LOOKUP_MAP:
            raise ValueError(f"Unknown lookup '{lookup}' (available: {sorted(LOOKUP_MAP)})")
        column = getattr(model, field, None)
        if not isinstance(column, ColumnOperators):
            raise ValueError(f"Unknown field '{field}' on {model.__name__}")
        result.append(LOOKUP_MAP[lookup](column, value))
    return result
