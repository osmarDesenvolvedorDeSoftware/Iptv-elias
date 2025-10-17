# Backend IPTV - Fase B1A

Backend mínimo viável em Flask para atender ao front IPTV.

## Requisitos

- Docker e Docker Compose

## Configuração

1. Copie `.env.example` para `.env` na pasta `backend/` e ajuste os valores se necessário.
2. Execute as migrações iniciais com Alembic após subir os containers.

```bash
cd backend
cp .env.example .env
python -m pip install -r requirements.txt  # opcional para executar localmente
```

## Execução com Docker Compose

```bash
cd backend
docker-compose up -d --build
```

O serviço HTTP ficará disponível em `http://localhost:8000`.

## Migrações

Criação da migração inicial:

```bash
cd backend
alembic revision --autogenerate -m "init"
```

Aplicação da migração:

```bash
docker-compose exec api alembic upgrade head
```

## Testes manuais via `curl`

1. Login para obter token:

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@tenant.com","password":"admin123"}'
```

2. Disparar importação dummy:

```bash
curl -s -X POST http://localhost:8000/importacoes/filmes/run \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"
```

3. Consultar status do job:

```bash
curl -s http://localhost:8000/jobs/<jobId>/status \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"
```

## Estrutura de pastas

```
backend/
  app/
    api/
    config.py
    extensions.py
    models/
    services/
    tasks/
  migrations/
  requirements.txt
  docker-compose.yml
  wsgi.py
```

## Notas

- A autenticação utiliza JWT (Flask-JWT-Extended) com tokens de acesso e refresh.
- Multi-tenant: todas as rotas protegidas exigem o cabeçalho `X-Tenant-ID`, validado contra o tenant do usuário autenticado.
- Jobs de importação são processados em fila Celery com Redis, atualizando progresso dummy em 10 passos.
- Logs estruturados em JSON e CORS habilitado conforme variável `CORS_ORIGINS`.
