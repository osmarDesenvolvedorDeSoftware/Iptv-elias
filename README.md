# IPTV Elias — Plataforma de Gestão de Conteúdo

[![Deploy IPTV UI](https://github.com/SEU_ORG/Iptv-elias/actions/workflows/deploy.yml/badge.svg)](https://github.com/SEU_ORG/Iptv-elias/actions/workflows/deploy.yml)

Este repositório concentra duas frentes principais:

1. **Backend Django existente**, responsável pelas rotinas atuais do sistema IPTV.
2. **Nova interface SPA (React + TypeScript)** em construção dentro de `ui/`, que substituirá gradualmente os templates Argon.

As fases 1A, 1B, 1C e 1D do plano de migração já foram concluídas: a estrutura base da aplicação React (layouts, roteamento, tema), a camada de dados mockada e as páginas funcionais (Login, Importação, Bouquets, Logs e Configurações) estão prontas para evoluir o restante do painel.

## Estrutura atual

```
ui/
└── src/
    ├── App.tsx
    ├── main.tsx
    ├── components/
    │   ├── DualList.tsx
    │   ├── ImportCard.tsx
    │   ├── LogModal.tsx
    │   └── ToastContainer.tsx
    ├── data/
    │   ├── adapters/
    │   │   ├── ApiAdapter.ts
    │   │   └── MockAdapter.ts
    │   ├── mocks/
    │   │   ├── auth.login.json
    │   │   ├── bouquets.list.json
    │   │   ├── config.get.json
    │   │   ├── importacoes.filmes.json
    │   │   ├── importacoes.run.filmes.json
    │   │   ├── importacoes.run.series.json
    │   │   ├── importacoes.series.json
    │   │   ├── jobs.status.130.json
    │   │   ├── logs.9001.json
    │   │   └── logs.list.json
    │   ├── services/
    │   │   ├── authService.ts
    │   │   ├── bouquetService.ts
    │   │   ├── configService.ts
    │   │   ├── importerService.ts
    │   │   └── logService.ts
    │   └── types.ts
    ├── layouts/
    │   ├── AppLayout.tsx
    │   └── AuthLayout.tsx
    ├── providers/
    │   ├── AuthProvider.tsx
    │   ├── ThemeProvider.tsx
    │   └── ToastProvider.tsx
    ├── styles/
    │   └── app.css
    ├── routes.tsx
    └── routes/
        ├── Bouquets.tsx
        ├── Config.tsx
        ├── DashboardPlaceholder.tsx
        ├── Importacao.tsx
        ├── Login.tsx
        └── Logs.tsx
```

- `App.tsx`: inicializa o roteamento e aplica os provedores globais (tema, autenticação mockada e toasts).
- `components/ImportCard.tsx`: card reutilizável para exibir status e histórico de importações.
- `components/LogModal.tsx`: modal Bootstrap sem dependências externas para exibir o texto completo de um log.
- `components/DualList.tsx`: componente memoizado com acessibilidade de teclado para as listas de bouquets.
- `components/ToastContainer.tsx`: container fixo para alertas disparados pelas ações simuladas.
- `ApiAdapter.ts`: cliente HTTP tipado com `fetch`, headers automáticos (`Authorization`, `X-Tenant-ID`), refresh de token e logs em modo dev.
- `MockAdapter.ts`: carrega fixtures JSON com delay aleatório para simular chamadas HTTP.
- `services/`: funções assíncronas (auth, importador, bouquets, logs, config) que alternam entre mocks e API real via `VITE_USE_MOCK`.
- `types.ts`: contratos TypeScript compartilhados pelas camadas de dados.
- `AppLayout.tsx` / `AuthLayout.tsx`: cascas principais para rotas autenticadas e públicas.
- `providers/`: contextos compartilhados (`ThemeProvider`, `AuthProvider`, `ToastProvider`).
- `routes.tsx`: mapa de rotas da SPA com páginas reais para Bouquets, Logs e Configurações.
- `routes/Login.tsx`: tela real de autenticação mockada com alerta de erro e spinner no botão.
- `routes/Importacao.tsx`: página real exibindo cards de importações de filmes e séries.
- `routes/Bouquets.tsx`: dual-list com filtros de catálogo e persistência simulada, usando componente dedicado e suporte a teclado.
- `routes/Logs.tsx`: tabela paginada com filtros e modal de detalhe do log.
- `routes/Config.tsx`: formulários tabulados com validação básica e alerta de reinício.

## 🎬 Páginas Login e Importação

- **/login** — chama `authService.login()` com e-mail/senha reais (modo API) ou credenciais mock (`operador@tenant.com`/`admin123`). Tokens (`access`, `refresh`) e `tenantId` são persistidos pelo `AuthProvider`, que agenda refresh automático e adiciona os cabeçalhos necessários para as rotas protegidas.
- **/importacao** — consome `importerService.getImports('filmes' | 'series')` para preencher dois cards (Filmes e Séries) lado a lado. Cada card apresenta badge de status, barra de progresso quando um job está em execução, tabela com os cinco últimos históricos e botões de ação. “Rodar agora” chama `importerService.runImport(tipo)`, usa mocks locais ou dispara o endpoint real (`/importacoes/{tipo}/run`) e exibe toast de sucesso; estados de carregamento, erro e ausência de dados seguem tratados com spinners/alerts.
- **Toasts globais** — o `ToastProvider` combinado ao `ToastContainer` (posicionado no `AppLayout`) exibe feedback para as ações mockadas, harmonizando com o tema claro/escuro.

## 📋 Bouquets, Logs e Configurações

- **/bouquets** — consome `bouquetService.getBouquets()` (mock ou API real) para montar a dual-list. Movimentações individuais, totais e reordenação simples mantêm o estado local até `saveBouquet()` confirmar no backend e disparar toast global de sucesso.
- **/logs** — usa `logService.getLogs()` para popular filtros e tabela responsiva. O botão “Ver detalhes” abre `LogModal`, que consulta `logService.getLogDetail(id)` sob demanda e normaliza erros retornados pela API.
- **/configuracoes** — carrega `configService.getConfig()` e distribui os campos em abas (Importador, TMDb, Notificações). A validação destaca campos obrigatórios e `saveConfig()` comunica o backend, sinalizando (quando necessário) o reinício de workers.
- **Feedbacks globais** — o `ToastProvider` continua responsável pelos toasts de ações, garantindo consistência visual entre tema claro/escuro e páginas.

## 📦 Camada de Mocks e Serviços

O frontend pode ser desenvolvido offline utilizando a seguinte cadeia:

1. **MockAdapter** → localiza o arquivo JSON em `ui/src/data/mocks/`, aguarda um delay de 200 a 600 ms e devolve os dados tipados.
2. **Services** → expõem funções assíncronas (`login`, `getImports`, `getBouquets`, `getLogs`, `getConfig`, etc.) prontos para serem consumidos pelos componentes React.
3. **UI** → nas próximas fases, os componentes usarão os services para preencher telas reais, sem depender de API externa.

Exemplo rápido no console do navegador (após carregar a aplicação do diretório `ui/`):

```ts
import { getImports } from './src/data/services/importerService';

getImports('filmes').then((response) => {
  console.table(response.items);
});
```

## Próximos passos

Consulte `docs/iptv-ui-plan.md` para o plano completo de implementação das fases subsequentes (componentes de página, integração com API real, testes, etc.).

## 🔐 Integração com API Real

1. **Configure o ambiente**
   - Copie `ui/.env.example` para `ui/.env.local` e ajuste os valores:
     ```ini
     VITE_API_BASE_URL=https://api.suaempresa.com
     VITE_USE_MOCK=false
     ```
   - `VITE_USE_MOCK=true` força o uso dos JSONs em `ui/src/data/mocks/` sem tocar a API real.

2. **Fluxo de autenticação JWT**
   - `authService.login(email, password)` envia `POST /auth/login` e retorna `{ token, refreshToken, expiresInSec, user }`.
   - O `AuthProvider` persiste os tokens em `localStorage`, injeta os headers `Authorization` e `X-Tenant-ID` e expõe `refresh()` para renovações automáticas (30s antes da expiração ou ao receber 401).
   - `logout` limpa os tokens e força o redirecionamento para `/login`.

3. **Alternar entre modos mock vs. real**
   - Modo mock: `VITE_USE_MOCK=true npm run dev` (ou `npm run dev -- --mock`, garantindo que a flag defina `VITE_USE_MOCK=true`).
   - Modo real: `npm run dev` com `.env.local` apontando para o backend HTTP.
 - Em produção, defina `VITE_API_BASE_URL` e mantenha `VITE_USE_MOCK=false` para que todos os services utilizem o `ApiAdapter`.

## 🚀 Deploy Automatizado

- O workflow **Deploy IPTV UI** executa lint (`eslint . --max-warnings=0`), build (`npm run build`) e publica automaticamente o conteúdo de `dist/` no branch `gh-pages` a cada push em `main`.
- Para publicar na **Vercel**, cadastre os segredos `VERCEL_TOKEN`, `VERCEL_ORG_ID` e `VERCEL_PROJECT_ID`; o mesmo workflow detecta os valores e executa `vercel deploy` após o build.
- Deploy manual: acione **Actions → Deploy IPTV UI → Run workflow**, escolha o destino (`auto`, `gh-pages`, `vercel` ou `both`) e confirme. Útil para hotfixes ou rollback imediato.
- Relatórios completos e instruções de fallback estão disponíveis em [`docs/DEPLOY_PLAYBOOK.md`](docs/DEPLOY_PLAYBOOK.md).

## 📦 Build & QA

1. **Instale dependências e gere o build otimizado**
   ```bash
   npm install
   npm run build
   ```
   Os artefatos ficam em `dist/` (equivalente a `ui/dist` quando acessado a partir da pasta `ui/`). Utilize `npm run preview` para validar com o servidor estático do Vite.

2. **Alternar entre mocks e API real**
   - Crie arquivos `.env.local`, `.env.production` conforme o ambiente.
   - Defina `VITE_USE_MOCK=true` para desenvolvimento off-line e `false` em produção.

3. **Checklist rápido de QA manual**
   - Login autentica e redireciona para Importação.
   - Cards de importação exibem histórico e barras de progresso.
   - Dual-list permite mover, remover e reordenar itens por mouse/teclado.
   - Modal de logs abre com foco preso e fecha com `Esc`.
   - Configurações salvam com toast e alerta de reinício quando necessário.
   - Tema claro/escuro alterna e persiste após recarregar a página.
   - Requisições reais retornam sem erros (verificar console/redes 200).

## Progresso das fases

- [x] Fase 1A – Estrutura base do SPA (layouts, roteamento, tema).
- [x] Fase 1B – Camada de Mocks e Serviços.
- [x] Fase 1C – Páginas Login e Importação.
- [x] Fase 1D – Bouquets, Logs e Configurações com mocks.
- [x] Fase 2 – Integração API real.
- [x] Fase 3 – Hardening & Build.
- [x] Fase 3B – Deploy & CI/CD.
