from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..services import bouquets as bouquet_service
from .utils import json_error, tenant_from_request

bp = Blueprint("bouquets", __name__)


@bp.get("/bouquets")
@jwt_required()
def list_bouquets():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    bouquets = [bouquet.to_dict() for bouquet in bouquet_service.list_bouquets(tenant_id)]
    catalog = bouquet_service.get_catalog(tenant_id)
    selected = bouquet_service.get_selections_map(tenant_id)

    return (
        jsonify(
            {
                "bouquets": bouquets,
                "catalog": catalog,
                "selected": selected,
            }
        ),
        HTTPStatus.OK,
    )


@bp.post("/bouquets")
@jwt_required()
def create_bouquet():
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return json_error("Nome do bouquet é obrigatório", HTTPStatus.BAD_REQUEST)

    try:
        bouquet = bouquet_service.create_bouquet(tenant_id, name)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.CONFLICT)

    return jsonify({"id": bouquet.id, "name": bouquet.name}), HTTPStatus.CREATED


@bp.post("/bouquets/<int:bouquet_id>")
@jwt_required()
def update_bouquet(bouquet_id: int):
    tenant_id, error = tenant_from_request()
    if error:
        return error

    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if items is None:
        return json_error("Lista de itens é obrigatória", HTTPStatus.BAD_REQUEST)
    if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
        return json_error("Formato inválido para itens", HTTPStatus.BAD_REQUEST)

    try:
        updated_at = bouquet_service.update_bouquet_items(tenant_id, bouquet_id, items)
    except LookupError as exc:
        return json_error(str(exc), HTTPStatus.NOT_FOUND)

    return jsonify({"ok": True, "updatedAt": updated_at.isoformat() + "Z"}), HTTPStatus.OK
