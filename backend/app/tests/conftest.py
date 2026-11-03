import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.session import Base, get_db
from app.main import app
from app.database.init_db import init_db
from app.core.security import create_access_token
from app.models.enums import UserRole
from app.models.user import User

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    init_db(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def override_db():
    def _get_test_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def superadmin_headers(db_session):
    user = db_session.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def orgadmin_headers(db_session):
    user = db_session.query(User).filter(User.role == UserRole.ORG_ADMIN).first()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def branchmanager_headers(db_session):
    user = db_session.query(User).filter(User.role == UserRole.BRANCH_MANAGER).first()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def agent_headers(db_session):
    user = db_session.query(User).filter(User.role == UserRole.DELIVERY_AGENT).first()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def customer_headers(db_session):
    user = db_session.query(User).filter(User.role == UserRole.CUSTOMER).first()
    token = create_access_token(subject=user.id, role=user.role.value)
    return {"Authorization": f"Bearer {token}"}
