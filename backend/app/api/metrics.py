from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from ..services.metrics import get_dashboard_metrics
from .utils import tenant_from_request

bp = Blueprint("metrics", __name__)


@bp.get("/metrics/dashboard")
@jwt_required()
def dashboard_metrics():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = get_dashboard_metrics(tenant_id)
    return jsonify(payload), HTTPStatus.OK
