import pytest
from flask import Flask

from app.extensions import db
from app.models import Tenant, TenantIntegrationConfig, User
from app.services import settings as settings_service
from app.services import xui_integration


@pytest.fixture()
def app_context():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="test-secret",
    )

    db.init_app(app)
    ctx = app.app_context()
    ctx.push()

    db.create_all()

    yield app

    db.session.remove()
    db.drop_all()
    ctx.pop()


def _create_tenant_setup():
    tenant = Tenant(id="tenant-test", name="Tenant Test")
    user = User(
        tenant_id=tenant.id,
        name="Test User",
        email="test@example.com",
        password_hash="hash",
    )
    config = TenantIntegrationConfig(tenant_id=tenant.id)

    db.session.add_all([tenant, user, config])
    db.session.commit()

    return tenant, user, config


def _valid_payload():
    return {
        "db_host": "db.example.local",
        "db_port": 3307,
        "db_user": "iptv_user",
        "db_pass": "s3cret",
        "db_name": "xui",
        "api_base_url": "",
        "m3u_link": "",
        "tmdb_key": None,
        "xtream_user": "",
        "xtream_pass": None,
        "use_xtream_api": True,
        "bouquet_normal": None,
        "bouquet_adulto": None,
        "ignored_prefixes": [],
    }


def test_save_settings_synchronizes_mysql_uri(app_context):
    tenant, user, _ = _create_tenant_setup()

    payload = _valid_payload()

    settings_service.save_settings(tenant.id, user.id, payload)

    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant.id).first()

    assert config is not None
    assert (
        config.xui_db_uri
        == "mysql+pymysql://iptv_user:s3cret@db.example.local:3307/xui"
    )


def test_worker_config_refreshes_tenant_uri(app_context):
    tenant, user, config = _create_tenant_setup()

    payload = _valid_payload()
    settings_service.save_settings(tenant.id, user.id, payload)

    config.xui_db_uri = "mysql+pymysql://old_user:old_pass@old-host:3306/legacy"
    db.session.commit()

    worker_payload = xui_integration.get_worker_config(tenant.id, user.id)

    expected_uri = "mysql+pymysql://iptv_user:s3cret@db.example.local:3307/xui"
    assert worker_payload["xui_db_uri"] == expected_uri

    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant.id).first()
    assert config is not None
    assert config.xui_db_uri == expected_uri


def test_successful_test_connection_updates_uri(monkeypatch, app_context):
    tenant, user, config = _create_tenant_setup()

    payload = _valid_payload()
    settings_service.save_settings(tenant.id, user.id, payload)

    config.xui_db_uri = "mysql+pymysql://old_user:old_pass@old-host:3306/legacy"
    db.session.commit()

    captured = {}

    class DummyConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, statement):  # pragma: no cover - não retorna resultado
            return None

    class DummyEngine:
        def __init__(self, url):
            self.url = url

        def connect(self):
            captured["url"] = self.url
            return DummyConnection()

        def dispose(self):
            return None

    def fake_create_engine(url, pool_pre_ping=True):
        return DummyEngine(url)

    monkeypatch.setattr(settings_service, "create_engine", fake_create_engine)

    success, message, meta = settings_service.test_connection(tenant.id, user.id, {})

    assert success is True
    assert "Conexão estabelecida" in message
    assert meta["status"] == "success"

    expected_uri = "mysql+pymysql://iptv_user:s3cret@db.example.local:3307/xui"
    assert captured["url"].render_as_string(hide_password=False) == expected_uri

    config = TenantIntegrationConfig.query.filter_by(tenant_id=tenant.id).first()
    assert config is not None
    assert config.xui_db_uri == expected_uri
