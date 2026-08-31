import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import djangoalchemy as orm

from .models import Base, Company, Employee


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    orm.bind(Employee, db)
    orm.bind(Company, db)
    yield db
    db.close()
    Base.metadata.drop_all(engine)
