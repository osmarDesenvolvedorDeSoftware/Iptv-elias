from flask import Blueprint, jsonify

from ..services.health import check_system_health


bp = Blueprint("health", __name__)


@bp.get("/health")
def healthcheck():
    return jsonify(check_system_health())
