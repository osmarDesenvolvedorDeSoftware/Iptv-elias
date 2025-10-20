# 📦 Introdução

O IPTV Elias é um sistema completo para gerenciamento de catálogos IPTV. O backend foi desenvolvido em Flask, com tarefas assíncronas orquestradas pelo Celery e filas no Redis, enquanto o painel administrativo foi construído em React. Os dados persistem em um banco MySQL preparado para multitenancy.

A arquitetura é formada por três serviços principais:

- **API**: serviço Flask exposto na porta `8000`, responsável pelos endpoints REST e autenticação JWT.
- **Worker**: processo Celery que executa importações em segundo plano e processa filas Redis.
- **Banco de dados**: instância MySQL isolada por tenant para armazenar catálogo, jobs e configurações.

# ⚙️ Instalação e Configuração

1. **Pré-requisitos**: Docker, Docker Compose, Node.js 20+, npm 10+.
2. **Configurar variáveis de ambiente do backend**:
   ```bash
   cd backend
   cp .env.example .env
   ```
   O arquivo `.env` define, entre outros parâmetros:
   - `TMDB_API_KEY`: chave pessoal obtida no TMDb.
   - `TMDB_LANGUAGE` / `TMDB_REGION`: idioma e região padrão das importações.
   - `DEFAULT_TENANT_ID`: tenant utilizado por padrão (`tenant-demo`).
3. **Subir os serviços com Docker**:
   ```bash
   cd backend
   docker compose up -d --build
   ```
   O `docker-compose.yml` provisiona os serviços `api`, `worker`, `db` e `redis`. As variáveis MySQL configuradas no bloco `environment` determinam o nome do banco (`MYSQL_DATABASE`), usuário (`MYSQL_USER`), senha (`MYSQL_PASSWORD`) e senha do root (`MYSQL_ROOT_PASSWORD`). A porta `3307` é exposta localmente.
4. **Verificar os containers ativos**:
   ```bash
   docker compose ps
   ```
   Espere ver `api`, `worker`, `db` e `redis` com o status `running`.
5. **Checar a API**:
   ```bash
   curl http://localhost:8000/health
   ```
   O endpoint `/health` confirma se o backend está disponível.
6. **Instalar dependências do painel**:
   ```bash
   cd ..  # volte para a raiz do repositório
   npm install
   ```
7. **Executar o painel em modo desenvolvimento**:
   ```bash
   npm run dev
   ```
   O painel ficará acessível em `http://localhost:5173`. Para build de produção, use `npm run build` e sirva os artefatos da pasta `dist/` com seu servidor favorito.

# 🔑 Login Inicial

A instalação inicial já cria um usuário administrador padrão:

- **E-mail**: `admin@tenant.com`
- **Senha**: `admin123`
- **Tenant ID**: `tenant-demo`

Informe o tenant no campo correspondente da tela de login para acessar o painel.

# 🎬 Configurando o TMDb

1. Acesse [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api) e solicite uma API Key (conta gratuita).
2. Com a chave em mãos, abra o painel em `Configurações > TMDb`.
3. Preencha os campos:
   - **API Key**: cole o valor obtido no TMDb.
   - **Linguagem**: define o idioma dos títulos e sinopses (ex.: `pt-BR`).
   - **Região**: direciona resultados a um país específico (ex.: `BR`).
4. Salve. A API passará a usar esses parâmetros em todas as importações.

# 🧾 Importando Filmes e Séries

O fluxo completo funciona assim:

1. O operador dispara uma importação pelo painel.
2. A API recebe a requisição autenticada e registra um job.
3. O Celery worker consome o job via Redis, consulta o TMDb e normaliza os dados.
4. Os dados processados são persistidos no MySQL e ficam disponíveis no painel.

Para testar manualmente via terminal:

```bash
curl -H "Authorization: Bearer <TOKEN>" \
     -H "X-Tenant-ID: tenant-demo" \
     http://localhost:8000/importacoes/filmes
```

Substitua `<TOKEN>` por um JWT válido obtido no login. Enquanto a importação roda, acompanhe os logs do worker:

```bash
docker compose logs -f worker
```

# 💾 Conferindo no Banco

Os dados de catálogo ficam nas tabelas `movies`, `genres` e `series`. Elas refletem, respectivamente, os filmes importados, os gêneros associados e as séries com suas temporadas/episódios. Para inspeccionar:

1. Conecte-se ao MySQL na porta `3307` (host `localhost`).
2. Use um cliente gráfico como DBeaver ou Adminer.
3. Autentique com usuário `iptv`, senha `iptv`, banco `iptv` (ou os valores que você definiu no `docker-compose.yml`).

Cada tenant possui seu próprio schema lógico: ao utilizar múltiplos tenants, os registros são isolados pelo campo `tenant_id`.

# 🧩 Multitenancy (Vários Bancos)

A API identifica o tenant pelo cabeçalho `X-Tenant-ID`. Sempre envie esse header nas requisições autenticadas.

- **Exemplo com outro tenant**:
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" \
       -H "X-Tenant-ID: tenant-loja2" \
       http://localhost:8000/importacoes/filmes
  ```
- **Adicionando um novo tenant**:
  1. Cadastre o tenant via endpoint de administração ou direto no banco (tabela `tenants`).
  2. Crie usuários vinculados ao novo `tenant_id`.
  3. Execute importações usando o mesmo cabeçalho `X-Tenant-ID` para manter os dados isolados.

Cada tenant cria um conjunto separado de registros em `movies`, `genres` e `series`, garantindo isolamento lógico mesmo dentro da mesma instância MySQL.

# 🧠 Dicas de Uso

- **Resetar o sistema**: pare os containers e remova volumes para limpar dados.
  ```bash
  docker compose down -v
  ```
- **Testar o build de produção do painel**:
  ```bash
  npm run build
  npm run preview  # visualização rápida do bundle
  ```
- **Depurar erros comuns**:
  - `Cannot read properties of undefined`: verifique se a API retornou dados esperados e se o tenant foi informado corretamente.
  - `task not registered`: confirme se o worker está em execução e compartilha o mesmo código/versão da API.
  - Falha de conexão com MySQL: cheque as variáveis de ambiente `MYSQL_*` e se a porta `3307` está livre.
  - Importação sem resultados: garanta que a `TMDB_API_KEY` está ativa e que a linguagem/região configuradas são válidas.

# 📚 Créditos

- **Autor**: Osmar F. Cavalcante
- **Projeto**: IPTV Elias
- **Stack**: Flask, Celery, React, Redis, MySQL, Docker
