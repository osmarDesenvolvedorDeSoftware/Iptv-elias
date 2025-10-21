from __future__ import annotations

from http import HTTPStatus
import mysql.connector
from flask import Blueprint, g, jsonify, request
from mysql.connector import Error as MySQLError

from ..models import User
from ..services.m3u_parser import parse_m3u_link
from ..services.user_configs import get_user_config, parse_mysql_uri, update_user_config
from .utils import auth_required, json_error

bp = Blueprint("account", __name__, url_prefix="/account")


@bp.get("/config")
@auth_required
def get_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)
    return jsonify(config.to_dict()), HTTPStatus.OK


@bp.put("/config")
@auth_required
def put_config():
    user: User = g.current_user  # type: ignore[assignment]
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    link_payload = payload.get("link_m3u") or payload.get("linkM3u") or payload.get("link")
    if isinstance(link_payload, str) and link_payload.strip():
        parsed_from_link = parse_m3u_link(link_payload.strip())
        if not parsed_from_link:
            return json_error("Formato de link M3U inválido", HTTPStatus.BAD_REQUEST)

        payload.update(
            {
                "domain": parsed_from_link["domain"],
                "port": parsed_from_link["port"],
                "username": parsed_from_link["username"],
                "password": parsed_from_link["password"],
            }
        )

    current_config = get_user_config(user)

    domain = payload.get("domain")
    if domain is None:
        domain = current_config.domain
    if isinstance(domain, str):
        domain = domain.strip() or None

    xtream_username = payload.get("username")
    if xtream_username is None:
        xtream_username = current_config.api_username
    if isinstance(xtream_username, str):
        xtream_username = xtream_username.strip() or None

    xtream_password_input = payload.get("password")
    if xtream_password_input is not None:
        xtream_password = str(xtream_password_input).strip()
    else:
        xtream_password = None
    if not xtream_password:
        xtream_password = current_config.api_password

    raw_db_uri = payload.get("xuiDbUri")
    if raw_db_uri is None:
        raw_db_uri = current_config.xui_db_uri

    if raw_db_uri is None:
        db_uri_candidate = None
    elif isinstance(raw_db_uri, str):
        db_uri_candidate = raw_db_uri.strip()
    else:
        db_uri_candidate = str(raw_db_uri).strip()

    if not db_uri_candidate:
        return json_error("Informe a URI do banco XUI para validar a conexão.", HTTPStatus.BAD_REQUEST)

    db_credentials = parse_mysql_uri(db_uri_candidate)
    if not db_credentials:
        return json_error("URI do banco XUI inválida.", HTTPStatus.BAD_REQUEST)

    if not domain or not xtream_username or not xtream_password:
        return json_error("Informe domínio, usuário e senha para validar a conexão.", HTTPStatus.BAD_REQUEST)

    try:
        connection = mysql.connector.connect(
            host=db_credentials["host"],
            port=db_credentials["port"],
            user=db_credentials["username"],
            password=db_credentials["password"],
            database=db_credentials["database"],
            connection_timeout=5,
        )
    except MySQLError as exc:  # pragma: no cover - depends on external resource
        return json_error(
            f"Não foi possível conectar ao banco XUI: {exc}",
            HTTPStatus.BAD_REQUEST,
        )

    connection_ready = False
    try:  # pragma: no cover - depends on external resource
        connection_ready = bool(connection.is_connected())
    finally:
        try:
            connection.close()
        except MySQLError:
            pass

    if not connection_ready:
        return json_error(
            "Não foi possível validar a conexão com o banco XUI.",
            HTTPStatus.BAD_REQUEST,
        )

    payload["xuiDbUri"] = db_credentials["uri"]

    try:
        config, has_base = update_user_config(user, payload)
    except ValueError as exc:
        return json_error(str(exc), HTTPStatus.BAD_REQUEST)

    response = config.to_dict()
    response["connectionReady"] = True
    response["hasBase"] = has_base
    return jsonify(response), HTTPStatus.OK


@bp.post("/parse_m3u")
@auth_required
def parse_m3u():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return json_error("Payload inválido", HTTPStatus.BAD_REQUEST)

    link = payload.get("link") or payload.get("link_m3u") or payload.get("linkM3u")
    if not isinstance(link, str) or not link.strip():
        return json_error("link_m3u obrigatório", HTTPStatus.BAD_REQUEST)

    parsed = parse_m3u_link(link.strip())
    if not parsed:
        return json_error("Formato M3U inválido", HTTPStatus.BAD_REQUEST)

    return jsonify(parsed), HTTPStatus.OK


@bp.post("/config/test")
@auth_required
def test_config():
    user: User = g.current_user  # type: ignore[assignment]
    config = get_user_config(user)

    if not config.domain or not config.api_username or not config.api_password:
        return json_error(
            "Configure domínio, usuário e senha antes de testar a conexão.",
            HTTPStatus.BAD_REQUEST,
        )

    response = config.to_dict()
    response.update({"ok": True, "message": "Configuração básica válida."})
    return jsonify(response), HTTPStatus.OK
