import pytest

import djangoalchemy as orm

from .models import Company, Employee


def seed(session):
    Employee.objects.create(name="Zoey", salary=90_000, city="London")
    Employee.objects.create(name="Zoe", salary=60_000, city="Paris")
    Employee.objects.create(name="Ivy", salary=120_000, city="London")


def seed_companies(session):
    acme = Company.objects.create(name="Acme")
    globex = Company.objects.create(name="Globex")
    Employee.objects.create(name="Zoey", salary=90_000, city="London", company=acme)
    Employee.objects.create(name="Zoe", salary=60_000, city="Paris", company=acme)
    Employee.objects.create(name="Ivy", salary=120_000, city="London", company=globex)


class TestCreateAndGet:
    def test_create_commits_and_returns_instance(self, session):
        emp = Employee.objects.create(name="Ava", salary=50_000, city="Berlin")
        assert emp.id is not None
        assert session.query(Employee).count() == 1

    def test_get(self, session):
        seed(session)
        emp = Employee.objects.get(name="Ivy")
        assert emp.salary == 120_000

    def test_get_missing_raises(self, session):
        with pytest.raises(orm.DoesNotExist):
            Employee.objects.get(id=999)

    def test_get_multiple_raises(self, session):
        seed(session)
        with pytest.raises(orm.MultipleObjectsReturned):
            Employee.objects.get(city="London")


class TestFilter:
    def test_exact(self, session):
        seed(session)
        assert Employee.objects.filter(city="London").count() == 2

    def test_icontains(self, session):
        seed(session)
        assert Employee.objects.filter(city__icontains="lon").count() == 2

    def test_iexact(self, session):
        seed(session)
        assert Employee.objects.filter(city__iexact="paris").count() == 1

    def test_comparisons(self, session):
        seed(session)
        assert Employee.objects.filter(salary__gte=90_000).count() == 2
        assert Employee.objects.filter(salary__lt=120_000).count() == 2

    def test_in_and_range(self, session):
        seed(session)
        assert Employee.objects.filter(name__in=["Zoey", "Ivy"]).count() == 2
        assert Employee.objects.filter(salary__range=(50_000, 100_000)).count() == 2

    def test_startswith(self, session):
        seed(session)
        assert Employee.objects.filter(name__startswith="Zo").count() == 2

    def test_isnull(self, session):
        seed(session)
        Employee.objects.create(name="NullCity", salary=1, city=None)
        assert Employee.objects.filter(city__isnull=True).count() == 1
        assert Employee.objects.filter(city__isnull=False).count() == 3

    def test_combined(self, session):
        seed(session)
        assert Employee.objects.filter(city__icontains="l", salary__gte=100_000).count() == 1

    def test_exclude(self, session):
        seed(session)
        assert Employee.objects.exclude(city="Paris").count() == 2

    def test_unknown_field_raises(self, session):
        with pytest.raises(ValueError, match="Unknown field"):
            Employee.objects.filter(bogus=1)

    def test_unknown_lookup_raises(self, session):
        with pytest.raises(ValueError, match="Unknown lookup"):
            Employee.objects.filter(name__nope="x")


class TestOrderingAndSlicing:
    def test_descending(self, session):
        seed(session)
        assert [e.name for e in Employee.objects.order_by("-salary")] == ["Ivy", "Zoey", "Zoe"]

    def test_multiple_keys(self, session):
        seed(session)
        assert [e.name for e in Employee.objects.order_by("city", "-salary")] == ["Ivy", "Zoey", "Zoe"]

    def test_slicing(self, session):
        seed(session)
        ordered = Employee.objects.order_by("salary")
        assert [e.name for e in ordered[:2]] == ["Zoe", "Zoey"]
        assert [e.name for e in ordered[1:3]] == ["Zoey", "Ivy"]
        assert ordered[0].name == "Zoe"

    def test_first(self, session):
        seed(session)
        assert Employee.objects.order_by("salary").first().name == "Zoe"
        assert Employee.objects.filter(city="Berlin").first() is None


class TestProjection:
    def test_values(self, session):
        seed(session)
        rows = Employee.objects.values("name", "city").order_by("name").all()
        assert rows == [
            {"name": "Ivy", "city": "London"},
            {"name": "Zoe", "city": "Paris"},
            {"name": "Zoey", "city": "London"},
        ]


class TestValuesList:
    def test_tuples(self, session):
        seed(session)
        rows = Employee.objects.values_list("name", "city").order_by("name").all()
        assert rows == [("Ivy", "London"), ("Zoe", "Paris"), ("Zoey", "London")]

    def test_flat(self, session):
        seed(session)
        names = Employee.objects.values_list("name", flat=True).order_by("name").all()
        assert names == ["Ivy", "Zoe", "Zoey"]

    def test_named(self, session):
        seed(session)
        rows = Employee.objects.values_list("name", "city", named=True).order_by("name").all()
        assert rows[0].name == "Ivy"
        assert rows[0].city == "London"

    def test_flat_requires_single_field(self, session):
        with pytest.raises(ValueError, match="exactly one field"):
            Employee.objects.values_list("name", "city", flat=True)

    def test_flat_and_named_conflict(self, session):
        with pytest.raises(ValueError, match="mutually exclusive"):
            Employee.objects.values_list("name", flat=True, named=True)


class TestRelations:
    def test_select_related(self, session):
        seed_companies(session)
        emps = Employee.objects.select_related("company").order_by("name").all()
        assert [e.company.name for e in emps] == ["Globex", "Acme", "Acme"]

    def test_prefetch_related(self, session):
        seed_companies(session)
        emps = Employee.objects.prefetch_related("company").order_by("name").all()
        assert [e.company.name for e in emps] == ["Globex", "Acme", "Acme"]

    def test_reverse_prefetch(self, session):
        seed_companies(session)
        companies = Company.objects.prefetch_related("employees").order_by("name").all()
        assert [len(c.employees) for c in companies] == [2, 1]

    def test_unknown_relationship_raises(self, session):
        seed_companies(session)
        with pytest.raises(ValueError, match="not a relationship"):
            Employee.objects.select_related("city").all()


class TestAnnotate:
    def test_annotate_instances(self, session):
        seed(session)
        emps = Employee.objects.annotate(twice=orm.Sum("salary")).all()
        assert [e.twice for e in emps] == [90_000, 60_000, 120_000]

    def test_values_annotate_groups(self, session):
        seed(session)
        rows = Employee.objects.values("city").annotate(total=orm.Sum("salary")).order_by("city").all()
        assert rows == [
            {"city": "London", "total": 210_000},
            {"city": "Paris", "total": 60_000},
        ]

    def test_annotate_requires_aggregate(self, session):
        with pytest.raises(TypeError, match="Aggregate"):
            Employee.objects.annotate(x=42).all()


class TestEvaluation:
    def test_count_exists_bool_len_iter(self, session):
        seed(session)
        qs = Employee.objects.filter(city__icontains="l")
        assert qs.count() == 2
        assert qs.exists() is True
        assert bool(qs) is True
        assert len(qs) == 2
        assert [e.name for e in qs] == ["Zoey", "Ivy"]

    def test_queryset_is_lazy_and_immutable(self, session):
        seed(session)
        base = Employee.objects.all()
        narrowed = base.filter(city="Paris")
        assert len(base) == 3
        assert len(narrowed) == 1


class TestWrites:
    def test_update(self, session):
        seed(session)
        updated = Employee.objects.filter(city="London").update(salary=1)
        assert updated == 2
        assert session.query(Employee).filter(Employee.salary == 1).count() == 2

    def test_delete(self, session):
        seed(session)
        deleted = Employee.objects.filter(city="Paris").delete()
        assert deleted == 1
        assert Employee.objects.count() == 2

    def test_manager_delegation(self, session):
        seed(session)
        assert Employee.objects.order_by("salary").first().name == "Zoe"
        assert Employee.objects.values("id").count() == 3
