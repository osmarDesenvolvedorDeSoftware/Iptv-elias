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

Antes de autenticar, verifique o endpoint público de health check:

```bash
curl -s http://localhost:8000/health
```

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

7. Métricas consolidadas para o dashboard:

```bash
curl -s http://localhost:8000/metrics/dashboard \
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
- Jobs de importação consultam a API TMDb (filmes e séries), registram progresso real e persistem resumo por item em `job_logs`.
- Logs estruturados em JSON e CORS habilitado conforme variável `CORS_ORIGINS`.

## ✅ Fase Final – Auditoria e Compatibilidade

- Scripts legados integrados (`filmes.py`, `series.py`, `padronizar_urls.py`) com fluxos convertidos para API + Celery.
- Banco compatível com colunas antigas (`source_tag` e `source_tag_filmes`).
- Importadores e lógica de TMDb 100% web e automatizados.
- Execução assíncrona via Celery com logs estruturados em JSON (substitui os prints da CLI).

## 📌 Auditoria de Paridade Legado x Novo (2024)

- **Importação de Filmes**: lê playlists M3U/Xtream, deduplica por URL completa, normaliza `stream_source` como lista JSON e preenche `source_tag_filmes` com domínio:porta. Metadados TMDb são persistidos em `streams.movie_properties` e o catálogo/bouquet de filmes é atualizado automaticamente.
- **Importação de Séries**: identifica a série por `(title_base, source_tag)`, reaproveitando registros existentes ou promovendo tags vazias, grava episódios em `streams`/`streams_episodes` e mantém `streams_series.source_tag` derivado do domínio dominante. Bouquets e flags de conteúdo adulto seguem a heurística legada.
- **Padronização de URLs**: novos campos `streams.primary_url`, `streams.source_tag_filmes` e `streams_series.source_tag` garantem a deduplicação por URL e a disponibilidade dos metadados legados; normalização de listas e containers ocorre durante a importação.
- **Logs e Observabilidade**: `job_logs` recebem eventos item a item com origem (arquivo/API), domínio, status (`inserted`, `duplicate`, `ignored`, `error`) e marcadores de conteúdo adulto, exibidos diretamente na tela de Logs.
- **Bouquets e Catálogo**: inserções atualizam `BouquetItem` com IDs `f_<stream_id>` e `s_<series_id>`, preservando catálogos e bouquets “Filmes”, “Séries” e “Adultos”.

### Ajustes desta auditoria

- Criação das tabelas `streams`, `streams_series` e `streams_episodes` com migração `0005_streams_and_series`, além dos modelos ORM correspondentes.
- Reescrita das tarefas Celery para aplicar todas as regras de deduplicação, enriquecimento TMDb, preenchimento de tags e roteamento automático para bouquets/Adultos.
- Substituição do catálogo baseado em logs por consultas diretas aos novos cadastros, mantendo o cache e as seleções existentes.
- Inclusão de playlists M3U de exemplo (`backend/app/data/samples/*.m3u`) e variáveis `LEGACY_MOVIES_M3U`/`LEGACY_SERIES_M3U` para apontar arquivos reais.

### Como visualizar no front

- **Importação**: acione `/importacoes/filmes` ou `/importacoes/series` pela tela *Importação* do SPA para acompanhar progresso, deduplicação e logs JSON.
- **Bouquets**: consulte a tela *Bouquets* (endpoint `/bouquets`) para verificar o catálogo unificado, inclusive marcação de adulto e tags de origem preenchidas automaticamente.
- **Logs detalhados**: utilize a tela *Logs* (endpoints `/logs` e `/logs/<id>`) para inspecionar os registros ricos por item, com domínio e status.
