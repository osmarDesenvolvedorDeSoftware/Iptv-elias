# Plano de Implantação do Frontend IPTV

## 1. Inventário do layout existente

### Estruturas globais
- **Layout base** (`layouts/base.html`): inclui sidenav vertical fixo, navbar superior com busca, dropdowns e área de usuário, além do contêiner principal para conteúdo. 【F:apps/templates/layouts/base.html†L16-L63】【F:apps/templates/includes/navigation.html†L1-L199】【F:apps/templates/includes/sidenav.html†L1-L103】
- **Layout fullscreen** (`layouts/base-fullscreen.html`, usado no login): remove sidenav e mantém somente cabeçalho de página centralizado. (Assumido a partir da herança em `accounts/login.html`; não há acesso direto, mas padrão Argon Dashboard). **Suposição:** estrutura semelhante ao base, porém sem sidebar.

### Componentes reutilizáveis
- **Cards estatísticos** (`card card-stats`), com ícones circulares e métricas rápidas, adequados a KPIs do dashboard. 【F:apps/templates/home/index.html†L31-L119】
- **Cards padrão com cabeçalho** (`card`, `card-header`, `card-body`) usados para gráficos e listas. 【F:apps/templates/home/index.html†L128-L159】
- **Tabela responsiva** (`table align-items-center table-flush`) com cabeçalho claro, ordenação visual, avatares e ações em dropdown – base para listagens (logs, filas). 【F:apps/templates/home/tables.html†L30-L160】
- **Breadcrumb e header de página** com título, ações à direita e contextualização. 【F:apps/templates/home/index.html†L10-L29】
- **Formulário de login** com campos com ícones embutidos e botão primário. 【F:apps/templates/accounts/login.html†L33-L61】
- **Navbar superior** com campo de busca, toggler mobile e dropdowns – pode ser adaptado para notificações de jobs. 【F:apps/templates/includes/navigation.html†L1-L189】
- **Sidebar vertical** com ícones e estado ativo – base para navegação principal. 【F:apps/templates/includes/sidenav.html†L1-L103】
- **Dropdowns dentro de listas** (ex.: ações por item nas tabelas) reutilizáveis para menus contextuais. 【F:apps/templates/home/tables.html†L99-L110】
- **Progress bars** e badges para indicar status e progresso. 【F:apps/templates/home/tables.html†L68-L105】【F:apps/templates/home/index.html†L137-L149】
- **Avatares/ícones em listas** – adaptáveis para pôsteres de filmes/séries. 【F:apps/templates/home/tables.html†L55-L86】

### Componentes a compor
- **Dual-list**: o template não traz componente pronto. Será criado com duas `card` + `list-group`/`table` simples, botões (`btn btn-outline-*`) entre as listas e suporte a teclado (setas, espaço). **Suposição:** uso de Bootstrap `list-group` com atributos ARIA `aria-labelledby`, `aria-live` para feedback.
- **Toasts/alerts**: Bootstrap 4 inclui `toast` e `alert`. Usaremos `alert` inline e `toast` customizado com container fixo. **Suposição:** adicionar container `position-fixed` no canto superior direito.
- **Skeleton/loaders**: utilizar classes `spinner-border`/`spinner-grow` do Bootstrap e placeholders com `bg-secondary` translúcido para skeleton cards. **Suposição:** criar componente `<SkeletonCard>` reutilizável.
- **Modal**: apesar de não existir markup específico, Bootstrap fornece comportamento; criaremos modal padrão para detalhes de logs.
- **Toggle dark/light**: inexistente nativamente; será implementado com botão no navbar, aplicando classe `theme-dark` à `<body>` e persistindo em `localStorage`.

### Mapeamento páginas → componentes
- **Login**: layout fullscreen, card de formulário do login existente, adicionar mensagens de erro com `alert` vermelho. 【F:apps/templates/accounts/login.html†L10-L72】
- **Dashboard**: header com breadcrumb, quatro cards estatísticos, cards extras para últimas execuções (tabela compacta) e erros recentes (lista). 【F:apps/templates/home/index.html†L10-L159】【F:apps/templates/home/tables.html†L30-L110】
- **Importação**: página com título central “Importação” no header, dois cards lado a lado (utilizar `row` + `col-xl-6`) com tabela histórica e estado atual; botões `btn` para ações e `badge`/`progress` para status.
- **Bouquets**: duas cards com listas (`list-group` ou `table` leve), coluna central para botões mover (> , >>, <, <<), barra de busca com input e `input-group` (navbar-search adaptado). Feedback via `toast`.
- **Relatórios/Logs**: card com filtros (inputs inline) e tabela paginada; ação “ver detalhes” abre modal Bootstrap.
- **Configurações**: cards contendo formulários com `form-group`, tooltips (`data-toggle="tooltip"`). Aviso de reinício usando `alert` dentro do card.

## 2. Arquitetura front → mocks → futura API ✅

### Camadas propostas
1. **UI (React-like em Vanilla/Framework escolhido)**
   - Roteador do template (Django atualmente) será substituído por SPA ou mantido com rotas server-rendered; para o plano consideramos SPA moderna.
   - Estrutura: `src/ui/pages` (Login, Dashboard, Importacao, Bouquets, Logs, Config), `src/ui/components` (CardStats, ImportJobList, BouquetDualList, LogTable, ConfigForm, ThemeToggle, ToastContainer).
   - Sistema de tema: contexto `ThemeProvider` com persistência via `localStorage` (chave `iptv-theme`), toggles na navbar.
   - Breadcrumbs e layout wrappers (`AppLayout`, `AuthLayout`) reutilizam markup Argon.

2. **Estado/Store**
   - Store simples com Zustand/Redux-lite ou Context + Reducer. Mantém sessão (`auth`), jobs correntes (`jobs`), bouquets (`bouquets`), logs (`logs`), configurações (`settings`).
   - Query layer com SWR/React Query-like wrappers para cache e revalidação via polling (jobs).
   - Erros globais mapeados para `toast.error`, com fallback `alert` em tela.

3. **Data layer (services)**
   - Pasta `src/data` com contratos tipados (`types.ts`) e services (`importerService`, `bouquetService`, `logService`, `configService`, `authService`).
   - **Adapters**:
     - `MockAdapter`: lê fixtures estáticos (`src/data/mocks/*.json`), simula delays, atualiza estado em memória para operações (POST/PUT).
     - `ApiAdapter`: wrapper sobre `fetch`/`axios` com headers (JWT, tenant-id), tratamento de erros HTTP, e reuso de contratos.
   - Módulo `JobPollingService` que usa `getJobStatus(jobId)` e aciona updates até `finished/failed`.

### Estratégia de erros
- Responses com erro → normalizar em objeto `{ message, code?, details? }`.
- UI exibe toast no canto superior direito, e componentes críticos mostram mensagem inline com opção de retry.
- 401/403 → redirecionar para Login, limpar estado; usar interceptador do adapter.
- Falhas de salvamento (bouquet/config) → manter diffs em memória para retry manual.

### Contratos de dados (JSON)

#### Autenticação
- **POST `/auth/login` → 200**
```json
{
  "token": "<jwt>",
  "refreshToken": "<jwt-refresh>",
  "expiresInSec": 3600,
  "user": {
    "id": 42,
    "name": "Operador Demo",
    "email": "operador@tenant.com",
    "role": "operator",
    "tenantId": "tenant-123"
  }
}
```
- **401** → `{ "error": "invalid_credentials" }`

#### Importações (Filmes/Séries)
- **GET `/importacoes/{tipo}`** (`tipo=filmes|series`)
```json
{
  "items": [
    {
      "id": 123,
      "startedAt": "2025-10-17T12:30:00Z",
      "finishedAt": "2025-10-17T12:33:05Z",
      "status": "finished",
      "inserted": 120,
      "updated": 35,
      "ignored": 10,
      "errors": 2,
      "durationSec": 185,
      "trigger": "manual",
      "user": "admin@tenant.com"
    },
    {
      "id": 124,
      "startedAt": "2025-10-17T13:00:00Z",
      "status": "running",
      "progress": 0.42,
      "etaSec": 210,
      "trigger": "schedule",
      "user": "scheduler"
    }
  ],
  "page": 1,
  "pageSize": 20,
  "total": 83
}
```
- **POST `/importacoes/{tipo}/run` → 202**
```json
{ "jobId": 130, "status": "queued" }
```
- **GET `/jobs/{id}/status`**
```json
{ "id": 130, "status": "running", "progress": 0.58, "etaSec": 90 }
```
- **GET `/importacoes/{tipo}/fila`** (fila de jobs pendentes)
```json
{
  "queued": [
    { "jobId": 131, "enqueuedAt": "2025-10-17T14:10:00Z", "source": "cron", "priority": 5 }
  ]
}
```

#### Bouquets
- **GET `/bouquets`**
```json
{
  "bouquets": [
    { "id": 1, "name": "Ação" },
    { "id": 2, "name": "Favoritos" }
  ],
  "catalog": [
    { "id": "f_101", "type": "movie", "title": "Blade Runner 2049", "year": 2017, "genres": ["Sci-Fi"], "poster": "/media/posters/f_101.jpg" },
    { "id": "s_550", "type": "series", "title": "The Witcher", "seasons": 3, "status": "returning" }
  ],
  "selected": {
    "1": ["f_101"],
    "2": []
  }
}
```
- **POST `/bouquets/{id}`**
```json
{ "ok": true, "updatedAt": "2025-10-17T14:20:00Z" }
```

#### Logs/Relatórios
- **GET `/logs`**
```json
{
  "items": [
    {
      "id": 9001,
      "jobId": 130,
      "type": "filmes",
      "status": "failed",
      "startedAt": "2025-10-16T23:00:00Z",
      "finishedAt": "2025-10-16T23:10:12Z",
      "durationSec": 612,
      "inserted": 0,
      "updated": 0,
      "ignored": 12,
      "errors": 3,
      "errorSummary": "TMDb quota exceeded"
    }
  ],
  "filters": {
    "type": "filmes",
    "status": "failed",
    "dateRange": { "from": "2025-10-10", "to": "2025-10-20" }
  },
  "page": 1,
  "pageSize": 20,
  "total": 5
}
```
- **GET `/logs/{id}`** → `{ "id": 9001, "content": "<texto cru ou json>" }

#### Configurações
- **GET `/config`**
```json
{
  "tmdb": {
    "apiKey": "***",
    "language": "pt-BR",
    "region": "BR"
  },
  "importer": {
    "movieDelayMs": 250,
    "seriesDelayMs": 500,
    "maxParallelJobs": 2,
    "defaultCategories": ["Ação", "Drama"],
    "useImageCache": true
  },
  "notifications": {
    "emailAlerts": true,
    "webhookUrl": null
  }
}
```
-
## ✅ Fase Final – Auditoria e Compatibilidade

- Scripts legados integrados (`filmes.py`, `series.py`, `padronizar_urls.py`).
- Banco compatível com colunas antigas (`source_tag` e `source_tag_filmes`).
- Importadores e lógica de TMDb 100% web e automatizados.
- Execução assíncrona via Celery com logs estruturados em JSON, substituindo os prints da CLI.

## ✅ Fase 2 – Integração com API real

### Ambiente de Integração com API Real
- `ApiAdapter` centraliza as chamadas HTTP usando `fetch`, lendo `VITE_API_BASE_URL` para compor os endpoints.
- Cabeçalhos `Authorization: Bearer <token>` e `X-Tenant-ID` são enviados automaticamente a partir da sessão ativa no `AuthProvider`.
- Em modo desenvolvimento (`import.meta.env.DEV`), o adapter realiza logs simples em `console.info`/`console.error` para depuração.
- Erros são normalizados como `{ message, code?, details?, status? }`, garantindo mensagens amigáveis para a UI.

### Alternância entre API real e mocks
- Defina `VITE_USE_MOCK=true` no ambiente (ex.: `.env.local`) para utilizar apenas os JSONs de `MockAdapter`.
- Com `VITE_USE_MOCK=false`, todos os services (`authService`, `importerService`, `bouquetService`, `logService`, `configService`) passam a usar o `ApiAdapter` e os endpoints HTTP reais definidos acima.
- A flag pode ser alternada em tempo de build/execução local (ex.: `VITE_USE_MOCK=true npm run dev` para mock vs `npm run dev` em modo real com `.env.local` configurado).

### Autenticação JWT e multi-tenant
- Login (`POST /auth/login`) retorna `token`, `refreshToken`, `expiresInSec` e `user`. O `AuthProvider` persiste `accessToken`, `refreshToken`, `tenantId` e `expiresAt` em `localStorage`.
- O contexto expõe `refresh()` e agenda renovações automáticas antes da expiração (`expiresInSec - 30s`). 401 acionam `refresh()` via `ApiAdapter`; falhas limpam a sessão e redirecionam para `/login`.
- `logout` remove tokens e credenciais, reencaminhando o usuário para a rota pública. O tenant ativo (`user.tenantId`) alimenta o cabeçalho `X-Tenant-ID` nas requisições.
- **POST `/config`** → `{ "ok": true, "requiresWorkerRestart": true }

#### Multi-tenant context
- Todos os endpoints recebem cabeçalhos `X-Tenant-ID` e `Authorization: Bearer <token>`.
- Respostas devem sempre ser filtradas por tenant.

## 3. Wireframes textuais

### Login
- **Layout:** AuthLayout fullscreen.
- **Header:** logotipo central (opcional), sem navbar.
- **Card central:** título “Entrar”, formulário com campos e botão primário; mensagem de erro exibida em `alert alert-danger` acima do formulário.
- **Links auxiliares:** “Registrar” e “Suporte”.
- **Estados:**
  - *Loading:* botão desabilitado com spinner inline.
  - *Erro credenciais:* alerta vermelho persistente.
  - *Sucesso:* redireciona para Dashboard.

### Dashboard
- **Breadcrumb Header:** título “Dashboard” à esquerda, ações rápidas (botões “Importar Filmes”, “Importar Séries”, “Gerenciar Bouquets”) à direita.
- **Linha 1:** quatro `CardStats` com KPIs (filmes, séries, execuções, erros).
- **Linha 2 (col-xl-8):** card com gráfico/painel “Atividade recente” (pode ser tabela de últimas importações). (Placeholder gráfico do template até conectar dados.)
- **Linha 2 (col-xl-4):** card “Últimos erros” listando logs recentes com `list-group`.
- **Linha 3:** cards para “Próximas execuções agendadas” (lista) e “Status atual dos jobs” (progress bars).
- **Estados:** skeleton cards no carregamento inicial; mensagem “Nenhum dado ainda” com ícone ao ficar vazio; erro exibe `alert` no topo do card.

### Importação
- **Header:** título central “Importação”, breadcrumb `Dashboard / Importação`.
- **Seção principal:** `row` com dois `col-xl-6`.
  - **Card Filmes:**
    - Subtítulo “Filmes”.
    - Bloco superior com status atual (badge + progress). Lista “Fila pendente” (lista simples) e tabela “Histórico recente” (5 itens, link “Ver todos”).
    - Botões: `Rodar agora` (primary), `Ver log` (secondary), `Configurar` (outline).
  - **Card Séries:** espelho do card de filmes, com dados da API de séries.
- **Rodapé opcional:** alert informando limites configurados.
- **Estados:**
  - *Running:* progress bar animada.
  - *Vazio:* mensagem “Nenhuma importação registrada”.
  - *Erro no job:* badge vermelho e tooltip com resumo.

### Bouquets
- **Header:** título “Bouquets”, breadcrumb `Dashboard / Bouquets`.
- **Topo:** dropdown para selecionar bouquet e campo de busca global.
- **Corpo:** três colunas dentro de um card grande:
  - **Coluna esquerda (Disponíveis):** lista com filtros (tabs por tipo filme/série) e resultados com checkbox + título + tags.
  - **Coluna central:** botões verticais `>` `>>` `<` `<<` (cada um `btn btn-outline-primary`) + indicadores de seleção (contador).
  - **Coluna direita (No bouquet):** lista ordenável (drag ou botões “subir/descer”).
- **Rodapé:** botão `Salvar` (primary), `Cancelar` (secondary). Toast de sucesso/erro após salvar.
- **Estados:** spinner ao carregar catálogos; mensagem “Sem resultados” quando filtro vazio; erro exibe `alert` no topo do card.

### Relatórios/Logs
- **Header:** título “Relatórios & Logs”.
- **Filtro:** card pequeno com formulário (data range picker, select status, select tipo). Botão `Aplicar` e `Limpar`.
- **Tabela principal:** reutiliza tabela responsiva com colunas `Início`, `Fim`, `Tipo`, `Status`, `Totais`, `Erros`, `Ações`.
- **Paginação:** `pagination` Bootstrap no footer.
- **Ação “Ver detalhes”:** abre modal com título `Log #ID` e conteúdo em `<pre>` scrollável.
- **Estados:** skeleton para tabela; estado vazio com ilustração; erros com `alert`.

### Configurações
- **Header:** título “Configurações”.
- **Layout:** tabs horizontais (ex.: “Importador”, “TMDb”, “Notificações”). Dentro de cada tab, formulário com campos `form-group`, tooltips `data-toggle="tooltip"` para dicas.
- **Aviso:** banner `alert alert-warning` quando `requiresWorkerRestart` for `true` após alteração.
- **Ações:** botões `Salvar` e `Reverter`. Loading spinner ao salvar.
- **Estados:**
  - *Loading:* skeleton para inputs.
  - *Sucesso:* toast “Configurações salvas”.
  - *Erro:* alerta vermelho com mensagens por campo.

## 4. Plano de implementação (fases)

### Fase 1 — Base do front com mocks
- **Fase 1A concluída ✅** — Estrutura inicial do SPA configurada com roteamento, layouts (App/Auth) e provedor de tema persistente.
- **Fase 1B concluída ✅** — Camada de dados mock implementada com `MockAdapter` (delay de 200–600 ms), serviços tipados (auth, importer, bouquets, logs, config) e fixtures JSON seguindo os contratos.
- **Fase 1C concluída ✅** — Telas de Login e Importação entregues utilizando os serviços mockados, com contexto de autenticação, cards de importação, estados (loading/erro/vazio) e toasts para ações simuladas.
- **Fase 1D concluída ✅** — Bouquets, Relatórios e Configurações operando com mocks, dual-list, modal de logs e formulários validados.

### Status atual do Frontend
- ✅ 1A – Estrutura base (layouts, tema e roteamento inicial).
- ✅ 1B – Mocks e serviços tipados.
- ✅ 1C – Login & Importação integrados aos mocks.
- ✅ 1D – Bouquets, Logs e Configurações com navegação completa e feedbacks simulados.
- 🔜 2 – Integração API real.

### Observações técnicas recentes
- Dual-list de bouquets com movimentação individual, total e reordenação simples.
- Modal de logs carregando detalhes on-demand com estados de loading e erro.
- Formulários de configuração com abas, validação básica e alerta de reinício de worker.

### Fase 2 — Integração API real
- Implementar `ApiAdapter` com `fetch`/`axios`, interceptadores para JWT e tenant.
- Substituir mocks por chamadas reais, mantendo contratos documentados.
- Adicionar refresh de token e tratamento de rate-limit (mostrar badge/alerta).

### Fase 3 — Hardening ✅
- Revisar acessibilidade (atalhos teclado na dual-list, labels, contraste, aria-live para toasts).
- Adicionar testes básicos (unitários para services, testes de integração/UI com Cypress/Playwright mockado).
- Otimizar performance (lazy load de páginas, memorização de listas grandes, compressão de imagens).

### Fase 3B – Deploy & CI/CD ✅
- Novo playbook [`docs/DEPLOY_PLAYBOOK.md`](DEPLOY_PLAYBOOK.md) descrevendo build (`npm run build`), publicação estática (Nginx, GitHub Pages, Vercel) e rollback.
- Workflow `deploy.yml` no GitHub Actions executando `npm ci`, lint (`eslint . --max-warnings=0`), build, upload de artefato e publicação em `gh-pages`, com opção automática para Vercel via segredos (`VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`).
- Documentação atualizada (README com badge de status e seção “Deploy Automatizado”) alinhando requisitos de Node 20 LTS / npm 10+ e direcionando a equipe para o playbook.

### Checklist de QA e Build
- [x] Login funcional.
- [x] Importação com cards separados.
- [x] Dual-list operando.
- [x] Logs abrindo modal.
- [x] Configurações com toast + alerta de reinício.
- [x] Tema dark/light persistente.
- [x] API real respondendo sem erros.

## 5. Critérios de aceite
- Página Importação com título central “Importação” e dois cards lado a lado, cada um exibindo somente itens do seu domínio (Filmes ou Séries).
- Dual-list funcional nos Bouquets permitindo mover individualmente ou todos os itens, com botão `Salvar` fornecendo feedback visual (toast) e estados de loading.
- Tema dark/light disponível em todas as páginas, com preferência persistida localmente.
- Inputs, cards e tabelas com espaçamento consistente (sem caixas desproporcionais ou elementos colados).
- Logs acessíveis com tabela paginada e modal de detalhe.
- Contratos de dados documentados e implementados na camada de mocks, prontos para troca por API real.

## 6. Riscos e suposições
- **Dependência da API real:** até que exista backend HTTP, todas as interações dependem do `MockAdapter`; divergências futuras de contrato exigirão ajustes rápidos.
- **Multi-tenant e perfis:** simulados via payloads; suposição de que API final fornecerá `tenantId` e `role` no login e aceitará cabeçalho de tenant.
- **Dual-list acessível:** pode demandar biblioteca adicional (ex.: `react-aria`) ou desenvolvimento manual; estimar tempo extra para testes de teclado/leitor de tela.
- **Tema dark/light:** Argon não possui tema escuro completo; será necessário ajustar variáveis SCSS ou adicionar classes customizadas (risco de inconsistência visual).
- **Logs extensos:** exibição de logs grandes no modal pode afetar performance; considerar virtualização ou download separado.
- **Agendamentos em tempo real:** polling frequente pode gerar carga; supõe-se que API suportará endpoints eficientes ou WebSockets (fora do escopo inicial).
- **Pipeline de build e deploy:** mitigado com o workflow `deploy.yml`; monitorar credenciais (tokens Vercel) e permissões de `gh-pages` a cada rotação.
- **Integração contínua:** configurar lint/test/build no CI evita regressões de acessibilidade e performance ao evoluir features.

## 7. Versão 1.1 – próximos passos
- Expandir cobertura de testes automatizados (unitários + Playwright) para rotas principais e componentes críticos.
- Definir monitoramento contínuo (Lighthouse CI, Web Vitals) integrado ao pipeline ou a jobs dedicados.
- Mapear métricas de observabilidade no backend para correlacionar com toasts/alertas e garantir SLA fim-a-fim.

## Backend

### Fase B1A – Infra básica ✅
- API Flask com autenticação JWT (login, refresh, logout) alinhada ao SPA.
- Multi-tenant validado via cabeçalho `X-Tenant-ID` em todas as rotas protegidas.
- Fila Celery + Redis com endpoints `/importacoes/{tipo}/run` e `/jobs/{id}/status` retornando progresso dummy.
- Migração inicial Alembic com tabelas `tenants`, `users`, `jobs`, `job_logs` e seed de tenant demo.

### Fase B1B – Importadores Reais ✅
- Integração com TMDb (filmes e séries) respeitando `TMDB_LANGUAGE`/`TMDB_REGION` e chave configurável por `.env`.
- Jobs Celery criados dinamicamente, registrando métricas completas (`inserted`, `updated`, `ignored`, `errors`, `durationSec`).
- Logs persistidos em JSON por item e resumo final disponível via `/importacoes/{tipo}` e `/logs` com filtros.
- Nova migração `0002_job_metrics` adicionando colunas e índice composto para consultas por tenant/tipo.
- Documentação atualizada com comando Celery e instruções de configuração.

### Fase B1C – Bouquets e Configurações ✅
- Migração `0003_bouquets_and_config` adicionando tabelas `bouquets`, `bouquet_items` e `configurations` com vínculo por tenant.
- Serviço de bouquets entregando catálogo real (últimos itens importados) com cache e seleção persistente por bouquet.
- Serviço de configuração consolidando defaults (`tmdb`, `importer`, `notifications`) e salvando overrides por tenant.
- Endpoints `/bouquets` e `/config` com autenticação JWT + `X-Tenant-ID`, alinhados ao contrato da SPA.
- Documentação e `.env.example` atualizados para refletir a persistência real do backend.

### Fase B2A – Dashboard & Métricas ✅
- Endpoint `/metrics/dashboard` consolidando KPIs (filmes, séries, importações, falhas e última importação) filtrados por tenant.
- Serviço `metrics.get_dashboard_metrics` agregando dados com SQLAlchemy (`func.count`, `func.max`) e formatando timestamps em UTC.

### Fase B2B – Health Check ✅
- Endpoint `/health` público retornando status de banco de dados, Redis e Celery com timestamp em UTC.
- Indicadores de saúde prontos para alimentar o dashboard e monitoramento externo.

### Backend pronto – Release v1.0.0 ✅
- Todas as fases B1A–B2B concluídas; backend considerado estável para o release final v1.0.0.
