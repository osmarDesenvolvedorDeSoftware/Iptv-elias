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

## 2. Arquitetura front → mocks → futura API

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
- Inventariar e extrair componentes Argon (navbar, sidenav, cards, tabelas) para `AppLayout`.
- Implementar roteamento SPA (React Router ou equivalente) para Login, Dashboard, Importação, Bouquets, Logs, Config.
- Criar `ThemeProvider` com toggle persistido (`localStorage`).
- Criar `MockAdapter` com fixtures para autenticação, importações, bouquets, logs, configurações; conectar páginas à camada de dados mock.
- Construir página Importação com dois cards independentes (Filmes, Séries) respeitando regras.
- Implementar estados básicos (loading spinner, vazio, erro) para cada bloco.

### Fase 2 — Bouquets
- Desenvolver componente DualList acessível (teclado, ARIA) com busca e filtros.
- Integrar com `MockAdapter` para carregar catálogo, atualizar seleção e persistir em memória.
- Implementar toasts para sucesso/erro, loading overlay no botão `Salvar`.

### Fase 3 — Logs/Relatórios
- Construir filtros reutilizando inputs Argon.
- Implementar tabela paginada com dados mock, incluindo badges de status.
- Criar modal Bootstrap para detalhe de log; conectar ao serviço `logService.getLog(id)`.

### Fase 4 — Configurações
- Montar formulários com validação (campos obrigatórios, formatos) e tooltips de ajuda.
- Mostrar aviso de reinício quando API retornar `requiresWorkerRestart`.
- Suporte a desfazer alterações (reset para dados carregados).

### Fase 5 — Integração API real
- Implementar `ApiAdapter` com `fetch`/`axios`, interceptadores para JWT e tenant.
- Substituir mocks por chamadas reais, mantendo contratos documentados.
- Adicionar refresh de token e tratamento de rate-limit (mostrar badge/alerta).

### Fase 6 — Hardening
- Revisar acessibilidade (atalhos teclado na dual-list, labels, contraste, aria-live para toasts).
- Adicionar testes básicos (unitários para services, testes de integração/UI com Cypress/Playwright mockado).
- Otimizar performance (lazy load de páginas, memorização de listas grandes, compressão de imagens).

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

