import os
import sys
from datetime import datetime
from pathlib import Path
from http import HTTPStatus

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from flask_jwt_extended import create_access_token
from sqlalchemy.exc import OperationalError

from app import create_app
from app.extensions import db
from app.models import Job, JobStatus, Tenant, User
from werkzeug.security import generate_password_hash


def test_dashboard_handles_missing_last_sync_column(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'admin_dashboard.db'}")

    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        tenant = Tenant(id="tenant-demo", name="Tenant Demo")
        user = User(
            tenant_id="tenant-demo",
            name="Admin",
            email="admin@example.com",
            password_hash=generate_password_hash("secret123"),
            role="admin",
        )
        db.session.add_all([tenant, user])
        db.session.commit()

        original_execute = db.session.execute

        def fake_execute(statement, params=None, execution_options=None):
            statement_text = str(statement)
            if (
                "max(" in statement_text
                and "user_configs" in statement_text
                and "last_sync" in statement_text
            ):
                raise OperationalError(
                    statement_text,
                    params,
                    Exception("no such column: user_configs.last_sync"),
                )
            return original_execute(
                statement, params=params, execution_options=execution_options
            )

        monkeypatch.setattr(db.session, "execute", fake_execute)

        with app.test_client() as client:
            with app.test_request_context():
                token = create_access_token(identity=f"{user.id}:{user.tenant_id}")

            response = client.get(
                "/admin/dashboard",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": user.tenant_id,
                },
            )

        assert response.status_code == HTTPStatus.OK
        assert response.json["stats"]["lastSync"] is None

        db.session.remove()


def test_dashboard_orders_recent_errors_with_nulls_last(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'admin_dashboard_ordering.db'}")

    app = create_app()

    with app.app_context():
        db.drop_all()
        db.create_all()

        tenant = Tenant(id="tenant-demo", name="Tenant Demo")
        user = User(
            tenant_id="tenant-demo",
            name="Admin",
            email="admin@example.com",
            password_hash=generate_password_hash("secret123"),
            role="admin",
        )
        db.session.add_all([tenant, user])
        db.session.commit()

        finished_job = Job(
            tenant_id=tenant.id,
            user_id=user.id,
            type="import",
            status=JobStatus.FAILED,
            finished_at=datetime.utcnow(),
        )
        pending_job = Job(
            tenant_id=tenant.id,
            user_id=user.id,
            type="sync",
            status=JobStatus.FAILED,
            finished_at=None,
        )
        db.session.add_all([finished_job, pending_job])
        db.session.commit()

        with app.test_client() as client:
            with app.test_request_context():
                token = create_access_token(identity=f"{user.id}:{user.tenant_id}")

            response = client.get(
                "/admin/dashboard",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": user.tenant_id,
                },
            )

        assert response.status_code == HTTPStatus.OK
        payload = response.json["recentErrors"]
        assert [item["id"] for item in payload[:2]] == [finished_job.id, pending_job.id]

        db.session.remove()
