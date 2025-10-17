from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from ..models import Job
from ..services.jobs import enqueue_import

bp = Blueprint("imports", __name__)

VALID_IMPORT_TYPES = {"filmes", "series"}


def _tenant_from_request():
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        return None, _error("Cabeçalho X-Tenant-ID é obrigatório", HTTPStatus.BAD_REQUEST)
    identity = get_jwt_identity()
    if identity.get("tenant_id") != tenant_id:
        return None, _error("Tenant inválido para o usuário", HTTPStatus.FORBIDDEN)
    return tenant_id, None


def _error(message: str, status: HTTPStatus):
    response = jsonify({"message": message})
    response.status_code = status
    return response


@bp.post("/importacoes/<string:tipo>/run")
@jwt_required()
def run_import(tipo: str):
    if tipo not in VALID_IMPORT_TYPES:
        return _error("Tipo de importação inválido", HTTPStatus.BAD_REQUEST)

    tenant_id, error = _tenant_from_request()
    if error:
        return error

    identity = get_jwt_identity()
    job = enqueue_import(tipo=tipo, tenant_id=tenant_id, user_id=identity["user_id"])

    return (
        jsonify(
            {
                "jobId": job.id,
                "status": job.status,
            }
        ),
        HTTPStatus.ACCEPTED,
    )


@bp.get("/jobs/<int:job_id>/status")
@jwt_required()
def job_status(job_id: int):
    tenant_id, error = _tenant_from_request()
    if error:
        return error

    job = Job.query.filter_by(id=job_id, tenant_id=tenant_id).first()
    if not job:
        return _error("Job não encontrado", HTTPStatus.NOT_FOUND)

    payload = job.to_dict()
    return jsonify(payload), HTTPStatus.OK
