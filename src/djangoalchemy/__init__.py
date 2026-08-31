"""Django-style ORM query API on top of SQLAlchemy.

Examples:
    >>> import djangoalchemy as orm
    >>> orm.configure(session_provider=get_db_session)
    >>> Employee.objects.filter(city__icontains="lon").order_by("-salary")[:10]
"""

from .lookups import LOOKUP_MAP, conditions
from .manager import Manager
from .model import DjangoModel, bind, configure
from .queryset import QuerySet, DoesNotExist, MultipleObjectsReturned

__version__ = "0.1.0"

__all__ = [
    "Manager",
    "QuerySet",
    "DjangoModel",
    "configure",
    "bind",
    "conditions",
    "LOOKUP_MAP",
    "DoesNotExist",
    "MultipleObjectsReturned",
    "__version__",
]
