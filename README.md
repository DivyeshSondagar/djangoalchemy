# djangoalchemy

**Django-style ORM query API, built on top of SQLAlchemy.**

Write Django-flavoured, chainable queries against your existing SQLAlchemy models:

```python
Employee.objects.filter(city__icontains="lon", salary__gte=70_000).order_by("-salary")[:10]
```

`djangoalchemy` is a thin adapter. Your models, migrations, engines, and sessions stay
100% SQLAlchemy — only the *query syntax* gets the Django treatment.

---

## Features

- **Django lookups** — `field__icontains`, `salary__gte`, `name__in`, `city__isnull`, and 15 more
- **Chainable, lazy, immutable querysets** — SQL is emitted only on evaluation
- **Slicing** — `qs[10:20]` becomes `OFFSET 10 LIMIT 10`
- **Projection** — `values` (dicts), `values_list` (tuples, scalars, namedtuples)
- **Eager loading** — `select_related` (JOIN) and `prefetch_related` (separate query) for `relationship()`s
- **Aggregation** — `annotate` with `Sum`, `Count`, `Avg`, `Min`, `Max`, grouped via `values()`
- **Write shortcuts** — `.create()`, `.update()`, `.delete()` with auto-commit
- **Session-agnostic** — works with any session provider (FastAPI dependency, request context, manual)
- **Drop-in** — attach `.objects` to models on *any* existing declarative base
- **Type-hinted** (`py.typed`) and tested against SQLite

## Installation

```bash
pip install djangoalchemy
```

Requires Python ≥ 3.10 and SQLAlchemy ≥ 2.0.

## Quickstart

### 1. Define models — unchanged SQLAlchemy

```python
from sqlalchemy import Column, Float, Integer, String
from djangoalchemy import DjangoModel

class Employee(DjangoModel):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    salary = Column(Float)
    city = Column(String(100), nullable=True)
```

Already have a `Base`? No problem — `djangoalchemy` attaches to any declarative base.

### 2. Attach the manager

```python
import djangoalchemy as orm

# provider: any zero-arg callable returning a SQLAlchemy Session,
# or a Session itself.
orm.configure(session_provider=get_db_session, base=Base)
```

For a single model:

```python
orm.bind(Employee, get_db_session)
```

### 3. Query

```python
# Fetching
Employee.objects.all()                          # list of all rows
Employee.objects.first()                        # first row or None
Employee.objects.get(id=42)                     # DoesNotExist / MultipleObjectsReturned

# Filtering
Employee.objects.filter(city="London")
Employee.objects.filter(name__icontains="lon")
Employee.objects.exclude(salary__lt=50_000)

# Ordering / pagination
Employee.objects.order_by("-salary")            # descending
Employee.objects.order_by("city", "-id")        # multiple keys
Employee.objects.filter(...)[1:11]              # slice = offset/limit

# Evaluation
Employee.objects.filter(city="London").count()
Employee.objects.filter(name="Zoey").exists()

# Projection
Employee.objects.values("id", "name")                    # -> [{"id": 1, "name": "Zoey"}, ...]
Employee.objects.values_list("name", flat=True)          # -> ["Zoey", "Zoe", ...]
Employee.objects.values_list("id", "name", named=True)   # -> [EmployeeRow(id=1, name="Zoey"), ...]

# Eager loading (see "Relations & aggregation")
Employee.objects.select_related("company")               # JOIN (many-to-one)
Company.objects.prefetch_related("employees")            # separate query (one-to-many)

# Writes (commit automatically)
emp = Employee.objects.create(name="Zoey", salary=90_000, city="London")
Employee.objects.filter(city="Paris").update(salary=70_000)
Employee.objects.filter(city="Paris").delete()
```

## Lookups reference

| Lookup | Meaning | SQLA equivalent |
|---|---|---|
| `field` / `field__exact` | exact match | `==` |
| `field__iexact` | case-insensitive exact | `ilike(v)` |
| `field__contains` | substring contains | `contains(v)` |
| `field__icontains` | case-insensitive contains | `ilike("%v%")` |
| `field__startswith` / `__istartswith` | prefix | `startswith(v)` / `ilike("v%")` |
| `field__endswith` / `__iendswith` | suffix | `endswith(v)` / `ilike("%v")` |
| `field__gt` / `__gte` / `__lt` / `__lte` | comparisons | `>`, `>=`, `<`, `<=` |
| `field__in` | in a list | `in_(...)` |
| `field__range` | between two values | `between(a, b)` |
| `field__isnull` | `True`/`False` for NULL | `is_(None)` / `is_not(None)` |

Unknown fields or lookups raise a clear `ValueError` immediately.

## Relations & aggregation

### Eager loading

Models use plain SQLAlchemy `relationship()`s:

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

class Company(DjangoModel):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    employees = relationship("Employee", back_populates="company")

class Employee(DjangoModel):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    company_id = Column(Integer, ForeignKey("companies.id"))
    company = relationship("Company", back_populates="employees")
```

```python
# one SQL query with a LEFT JOIN — use for many-to-one (FK) relations
Employee.objects.select_related("company").all()

# separate SELECT ... WHERE fk IN (...) — use for one-to-many / reverse relations
Company.objects.prefetch_related("employees").all()

# nested paths work on both
Employee.objects.select_related("company__ceo")
```

A path segment that isn't a relationship raises a clear `ValueError` immediately.

### Aggregation

```python
from djangoalchemy import Sum, Count, Avg, Min, Max

# On instances — the value is attached to each row (grouped by primary key)
Employee.objects.annotate(total=Sum("salary")).all()      # e.total is set

# Grouped report — values(...) fields become the GROUP BY columns
Employee.objects.values("city").annotate(avg_salary=Avg("salary")).order_by("city")
# -> [{"city": "London", "avg_salary": 105000.0}, {"city": "Paris", "avg_salary": 60000.0}]

# Count supports distinct
Company.objects.annotate(employee_count=Count("employees", distinct=True))
```

Passing anything that isn't an aggregate to `annotate()` raises `TypeError`.

## FastAPI integration

Session comes from the request — no manual plumbing:

```python
# app/db/session.py
from contextvars import ContextVar

_session_context: ContextVar[Session | None] = ContextVar("db_session", default=None)

def get_db():
    db = SessionLocal()
    token = _session_context.set(db)
    try:
        yield db
    finally:
        _session_context.reset(token)
        db.close()

def get_current_session() -> Session:
    db = _session_context.get()
    if db is None:
        raise RuntimeError("No active database session for this request.")
    return db
```

```python
# app/main.py
import djangoalchemy as orm
from app.db.session import Base, get_current_session

orm.configure(get_current_session, base=Base)   # one line; attaches .objects to every model
```

```python
# app/services/employee_service.py
def get_employee_service(params):
    return Employee.objects.filter(
        name=params.name, city=params.city,
    ).order_by("-salary")[:params.page_limit]   # no db plumbing at all
```

## How it works

```
Your model (still a SQLAlchemy model)
        │
        ▼
   .objects ──── Manager
        │         resolves the session from the configured provider
        ▼
    QuerySet ── builds a SQLAlchemy query lazily
        │         filter/exclude → lookups.py → sqlalchemy expressions
        │         order_by      → asc()/desc() on model columns
        │         select_related / prefetch_related → relations.py → joinedload / selectinload
        │         annotate      → aggregates.py → func.sum / func.count / ...
        │         slicing       → offset()/limit()
        ▼
      result: model instances, dicts (.values), tuples (.values_list), or annotated instances
```

- `lookups.py` — maps Django lookup names to SQLAlchemy column operators.
- `queryset.py` — the lazy, immutable, chainable query builder.
- `relations.py` — resolves `fk__fk` paths into `joinedload` / `selectinload` options.
- `aggregates.py` — Django-style `Sum` / `Count` / `Avg` / `Min` / `Max` mapped to SQL functions.
- `manager.py` — the `.objects` entry point; delegates unknown methods to the queryset (Django-style).
- `model.py` — `configure()` walks `Base.registry` and attaches a `Manager` to each mapped model.

You can mix Django-style calls and raw SQLAlchemy freely in the same codebase.

## License

MIT
