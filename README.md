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
- **Write shortcuts** — `.create()`, `.update()`, `.delete()` with auto-commit
- **Session-agnostic** — works with any session provider (FastAPI dependency, request context, manual)
- **Drop-in** — attach `.objects` to models on *any* existing declarative base
- **Type-hinted** (`py.typed`) and tested against SQLite

## Installation

```bash
pip install djangoalchemy        # from PyPI (once published)
pip install -e /path/to/djangoalchemy   # development
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
Employee.objects.values("id", "name")           # -> [{"id": 1, "name": "Zoey"}, ...]

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
        │         slicing       → offset()/limit()
        ▼
      result: list of model instances (or dicts with .values())
```

- `lookups.py` — maps Django lookup names to SQLAlchemy column operators.
- `queryset.py` — the lazy, immutable, chainable query builder.
- `manager.py` — the `.objects` entry point; delegates unknown methods to the queryset (Django-style).
- `model.py` — `configure()` walks `Base.registry` and attaches a `Manager` to each mapped model.

You can mix Django-style calls and raw SQLAlchemy freely in the same codebase.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

## Publishing to PyPI

The package uses the standard PyPA workflow: a `src/` layout with a single
`pyproject.toml` as the build config, and no `setup.py` needed.

1. **Build the distributions** into `dist/`:

   ```bash
   python -m build
   ```

   This produces `dist/djangoalchemy-<version>.tar.gz` (sdist) and
   `dist/djangoalchemy-<version>-py3-none-any.whl` (wheel).

2. **Verify the artifacts**:

   ```bash
   twine check dist/*
   ```

3. **Upload to Test PyPI first** (recommended):

   ```bash
   twine upload --repository testpypi dist/*
   ```

4. **Publish to PyPI**:

   ```bash
   twine upload dist/*
   ```

You'll need a [PyPI account](https://pypi.org/account/register/) (and a
separate one for Test PyPI). Use an API token via `TWINE_USERNAME=__token__`
and `TWINE_PASSWORD=pypi-...`, or configure `~/.pypirc`.

Then anyone can install it:

```bash
pip install djangoalchemy
```

## Roadmap

- [ ] Relations: `fk__field` filters, `select_related` / `prefetch_related`
- [ ] Aggregates: `sum`, `avg`, `group_by` + `annotate`
- [ ] `Q`-style boolean composition (`&`, `|`)
- [ ] `get_or_create`, `update_or_create`, `bulk_create`
- [ ] Async engine / async session support
- [ ] Custom manager methods per model

## License

MIT
