# Backend IPTV - Fase B1C

Backend mínimo viável em Flask para atender ao front IPTV.

## Requisitos

- Docker e Docker Compose

## Configuração

1. Copie `.env.example` para `.env` na pasta `backend/` e ajuste os valores se necessário.
   - Cadastre uma chave da API [TMDb](https://www.themoviedb.org/) e informe em `TMDB_API_KEY`.
   - Ajuste `TMDB_LANGUAGE`/`TMDB_REGION` caso utilize outra localidade.
   - `DEFAULT_TENANT_ID` define o tenant padrão usado pelos ambientes de desenvolvimento e testes (`tenant-demo`).
2. Execute as migrações (incluindo a expansão de métricas dos jobs) com Alembic após subir os containers.

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

2. Disparar importação real (filmes ou séries):

```bash
curl -s -X POST http://localhost:8000/importacoes/filmes/run \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"
```

Opcionalmente, acione o worker diretamente pela Celery registrando o tenant e o usuário:

```bash
docker-compose exec worker \
  celery -A app.extensions.celery_app call app.tasks.importers.run_import \
  args='["filmes","tenant-demo",1]'
```

3. Consultar status do job:

```bash
curl -s http://localhost:8000/jobs/<jobId>/status \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"
```

4. Listar histórico e logs consolidados:

```bash
curl -s http://localhost:8000/importacoes/filmes \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"

curl -s "http://localhost:8000/logs?type=filmes&status=finished" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"
```

5. Bouquets persistidos e catálogo recente:

```bash
curl -s http://localhost:8000/bouquets \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"

curl -s -X POST http://localhost:8000/bouquets/1 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo" \
  -d '{"items":["f_101","s_550"]}'

curl -s -X POST http://localhost:8000/bouquets \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo" \
  -d '{"name":"Favoritos"}'
```

6. Configurações por tenant com merge de defaults:

```bash
curl -s http://localhost:8000/config \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo"

curl -s -X POST http://localhost:8000/config \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: tenant-demo" \
  -d '{"importer":{"maxParallelJobs":4}}'
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
- Jobs de importação consultam a API TMDb (filmes e séries), registram progresso real e persistem resumo por item em `job_logs`.
- Logs estruturados em JSON e CORS habilitado conforme variável `CORS_ORIGINS`.
