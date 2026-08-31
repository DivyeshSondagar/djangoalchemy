"""Relationship path resolution for ``select_related`` / ``prefetch_related``."""

from __future__ import annotations

from sqlalchemy.orm import RelationshipProperty, joinedload, selectinload


def _chain(model: type, path: str) -> list:
    """Resolve a ``fk__fk2`` path to a list of relationship attributes.

    Raises ``ValueError`` if any segment is not a relationship on its model.
    """
    chain = []
    current = model
    for part in path.split("__"):
        attr = getattr(current, part, None)
        prop = getattr(attr, "property", None)
        if not isinstance(prop, RelationshipProperty):
            raise ValueError(f"'{part}' is not a relationship on {current.__name__}")
        chain.append(attr)
        current = prop.mapper.class_
    return chain


def joined_option(model: type, path: str):
    chain = _chain(model, path)
    option = joinedload(chain[0])
    for attr in chain[1:]:
        option = option.joinedload(attr)
    return option


def selectin_option(model: type, path: str):
    chain = _chain(model, path)
    option = selectinload(chain[0])
    for attr in chain[1:]:
        option = option.selectinload(attr)
    return option
