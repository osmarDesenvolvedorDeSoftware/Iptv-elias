# Guia de Uso do IPTV Elias

O IPTV Elias é um painel administrativo completo para catálogos IPTV. Ele combina uma API Flask, tarefas assíncronas no Celery, Redis e um painel React. A arquitetura foi pensada desde o início para multitenancy: cada tenant possui banco XUI próprio, credenciais Xtream isoladas e configuração de importação independente.

---

## 1. Preparar o ambiente

1. **Pré-requisitos:** Docker, Docker Compose, Node.js 20+, npm 10+.
2. **Configurar variáveis do backend:**
   ```bash
   cd backend
   cp .env.example .env
   ```
   O arquivo `.env` define apenas parâmetros globais (JWT, Redis, banco da API, etc.). As integrações com o XUI não ficam mais no `.env`.
3. **Subir os serviços:**
   ```bash
   docker compose up -d --build
   ```
   Isso cria os containers `api`, `worker`, `db` (MySQL multitenant) e `redis`.
4. **Instalar dependências do painel:**
   ```bash
   cd ..
   npm install
   ```
5. **Executar o painel:**
   ```bash
   npm run dev
   ```
   A interface React estará em `http://localhost:5173`, enquanto a API fica em `http://localhost:8000`.

---

## 2. Acessar o painel

A migração inicial cria um usuário administrador padrão:

- **E-mail:** `admin@tenant.com`
- **Senha:** `admin123`
- **Tenant ID:** `tenant-demo`

Informe o Tenant ID no login. O cabeçalho `X-Tenant-ID` será propagado automaticamente nas chamadas feitas pelo painel.

---

## 3. Criar novos tenants

### 3.1 Pelo painel

1. Acesse o menu **Tenants** na barra lateral.
2. Clique em **Adicionar Tenant**.
3. Preencha os campos:
   - **Tenant ID:** identificador único em minúsculas (letras, números, `-` ou `_`).
   - **Nome:** nome exibido no painel.
   - **URI do banco XUI:** conexão completa (ex.: `mysql+pymysql://user:senha@host:3306/xui`).
   - **Base da API Xtream:** endereço do provedor (ex.: `https://painel.provedor.com`).
   - **Usuário/Senha da API Xtream:** credenciais exclusivas do tenant.
   - **TMDb Key:** chave por tenant (pode ser diferente para cada operação).
   - **Prefixes/ Categorias ignoradas:** listas separadas por vírgula que serão aplicadas a filmes e séries.
4. Salve. O painel cria o tenant, persiste as credenciais no banco e deixa a configuração disponível na aba **Configurações > Integração XUI** para ajustes futuros.

### 3.2 Via API

O mesmo fluxo pode ser automatizado via `POST /tenants` (o proxy pode expor como `/api/tenants`). Exemplo:

```bash
curl -X POST http://localhost:8000/tenants \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-Tenant-ID: tenant-demo" \
  -H "Content-Type: application/json" \
  -d '{
        "id": "tenant-filial-01",
        "name": "Filial 01",
        "integration": {
          "xuiDbUri": "mysql+pymysql://filial:senha@mysql-filial:3306/xui",
          "xtreamBaseUrl": "https://filial.provedor.com",
          "xtreamUsername": "api-filial",
          "xtreamPassword": "senha-super-secreta",
          "tmdbKey": "TMDB_KEY_FILIAL",
          "ignorePrefixes": ["TESTE"],
          "ignoreCategories": ["999"]
        }
      }'
```

A resposta inclui os dados do tenant e a configuração persistida.

> **Importante:** somente usuários do tenant padrão (`DEFAULT_TENANT_ID`) com papel `admin` podem criar novos tenants. Isso garante isolamento administrativo.

---

## 4. Configurar integrações por tenant

Acesse **Configurações > Integração XUI** dentro do tenant desejado:

1. **Banco XUI:** informe ou atualize a URI do banco MySQL do XUI.
2. **API Xtream:** atualize base URL, usuário e senha. A senha só é exibida no momento do envio; o backend guarda um hash seguro.
3. **TMDb:** habilite a opção por tenant, informe a chave e defina idioma/região.
4. **Regras de ignorar:**
   - Prefixos e categorias inseridos aqui são consolidados nas colunas `ignore_prefixes` e `ignore_categories` do banco.
   - Os valores são considerados tanto para filmes quanto para séries.
5. **Bouquets, mapeamento e retentativas:** personalize os IDs e limites usados pela importação.
6. Salve. Toda a configuração fica armazenada em `tenant_integration_configs` e será consumida pelas tasks sem depender de `.env`.

---

## 5. Executar a sincronização completa

1. Vá até **Importação** e escolha **Filmes** ou **Séries**.
2. O backend agenda um job Celery que executa:
   - Normalização automática (`normalize_xui_sources`) para padronizar `stream_source`, `source_tag_filmes` e `streams_series.source_tag` no banco XUI.
   - Importação Xtream → XUI (`run_import`) com TMDb opcional, bouquets e filtros por tenant.
3. Acompanhe o progresso e os logs na própria tela de importação. Cada item é armazenado em `job_logs` e pode ser consultado depois.
4. Para depurar em tempo real, observe o worker:
   ```bash
   docker compose logs -f worker
   ```

Cada execução respeita o `tenant_id` propagado: o worker usa `get_worker_config(tenant_id)` para carregar as credenciais corretas.

---

## 6. Validar resultados no XUI/MySQL

Após a importação:

1. Conecte-se ao banco XUI informado na integração (cada tenant possui uma URI distinta).
2. Verifique as tabelas principais:
   - `streams` (filmes VOD) — deve conter URLs normalizadas e `source_tag_filmes` preenchido.
   - `streams_series` — deve ter `source_tag` populado por série.
   - `streams_episodes` — associa episódios aos streams já criados.
   - `bouquets` — as listas configuradas recebem os IDs importados.
3. Se preferir validar via painel XUI, entre com as mesmas credenciais e confirme os catálogos e bouquets.

---

## 7. Observabilidade e isolamento

- **Isolamento por tenant:** todos os modelos relevantes (`jobs`, `streams`, `bouquets`, `tenant_integration_configs`) possuem coluna `tenant_id`. O cabeçalho `X-Tenant-ID` é verificado em cada requisição e propagado às tasks Celery.
- **Segurança:** o JWT inclui `user_id:tenant_id`. O backend cruza o valor com o cabeçalho e bloqueia acessos cruzados.
- **Logs e métricas:** jobs, logs e métricas são filtrados por tenant. Consulte **Relatórios & Logs** para acompanhar execuções anteriores.

---

## 8. Dicas de operação

- Use `docker compose down -v` para limpar dados de desenvolvimento.
- Ajuste `throttleMs`, `limitItems` e `maxParallel` quando testar importações em ambientes com limites estritos.
- Campos “ignorar prefixos/categorias” aceitam listas. Esses valores são consolidados nas colunas dedicadas e também replicados no JSON de opções para retrocompatibilidade.
- Ao alterar credenciais XUI, o painel informa quando é necessário reiniciar o worker.

Com esses passos é possível criar múltiplos tenants, configurar integrações e operar o catálogo IPTV sem tocar no `.env` após a primeira execução.
