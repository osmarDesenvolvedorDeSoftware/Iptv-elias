# IPTV Elias — Plataforma de Gestão de Conteúdo

[![Deploy IPTV UI](https://github.com/SEU_ORG/Iptv-elias/actions/workflows/deploy.yml/badge.svg)](https://github.com/SEU_ORG/Iptv-elias/actions/workflows/deploy.yml)

Este repositório concentra duas frentes principais:

1. **Backend Django existente**, responsável pelas rotinas atuais do sistema IPTV.
2. **Nova interface SPA (React + TypeScript)** em construção dentro de `ui/`, que substituirá gradualmente os templates Argon.

As fases 1A, 1B, 1C e 1D do plano de migração já foram concluídas: a estrutura base da aplicação React (layouts, roteamento, tema), a camada de dados mockada e as páginas funcionais (Login, Importação, Bouquets, Logs e Configurações) estão prontas para evoluir o restante do painel.

## 📁 Estrutura do projeto

```
Iptv-elias/
├── backend/
├── ui/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   └── .env
├── dist/
└── ecosystem.config.js
```

- O frontend React fica isolado em `ui/` para evitar conflito com o backend Flask e facilitar deploys independentes.
- O build otimizado sempre é gerado em `dist/` na raiz para que Nginx, PM2 ou outros servidores estáticos consigam servir os arquivos sem depender da pasta `ui/`.
- O backend, workers e demais serviços continuam agrupados dentro de `backend/`.

## ⚙️ Onde rodar os comandos do frontend

Todos os comandos do Vite/React devem ser executados **dentro da pasta `ui/`**:

```bash
cd ui
npm install      # instala dependências declaradas em ui/package.json
npm run dev      # desenvolvimento (http://localhost:5173)
npm run build    # gera artefatos otimizados em ../dist
npm run preview  # servidor estático apontando para ../dist
```

O arquivo `ui/vite.config.ts` já define `root: __dirname` (ou seja, `ui/`) e `build.outDir: resolve(projectRoot, 'dist')`. Assim o Vite reconhece automaticamente `ui/src/` e `ui/public/` como diretórios padrão e despeja o build na raiz do projeto.

## 🌱 Variáveis de ambiente do frontend

O Vite lê variáveis do arquivo `ui/.env`. Para apontar o frontend ao backend Flask padrão (porta 5000), crie ou edite o arquivo com:

```ini
# ui/.env
VITE_API_BASE_URL=http://<ip>:5000
```

Outras variáveis (como `VITE_USE_MOCK`) continuam disponíveis; consulte `ui/.env.example` para a lista completa. Durante o build o Vite também aceita valores exportados via shell (`export VITE_API_BASE_URL=...`).

## 📦 Build e publicação do frontend

O comando `npm run build` (executado dentro de `ui/`) cria a pasta `dist/` na raiz do repositório (`/root/Iptv-elias/dist`). Esse diretório pode ser servido de duas maneiras principais:

1. **PM2 + `npm run preview`** – indicado para staging. Execute `pm2 start ecosystem.config.js` e use o processo `iptv-frontend` descrito abaixo.
2. **Nginx (ou outro servidor estático)** – aponte o `root` do site para `/root/Iptv-elias/dist` após rodar o build. O `vite.config.ts` já produz caminhos relativos (`base: './'`), então basta expor o diretório.

Sempre que o backend for atualizado, gere um novo build (`cd ui && npm run build`) antes de publicar.

## 🧭 PM2 (sem Docker)

O arquivo `ecosystem.config.js` controla os processos do backend e do frontend. O trecho abaixo mostra apenas os apps necessários, todos com logs padronizados:

```js
const path = require('path');

const projectRoot = path.resolve(__dirname);
const backendDir = path.join(projectRoot, 'backend');
const frontendDir = path.join(projectRoot, 'ui');
const pythonBin = path.join(backendDir, 'venv', 'bin', 'python3');
const envFile = path.join(backendDir, '.env');

const backendLogsDir = '/var/log/iptv-backend';
const frontendLogsDir = '/var/log/iptv-ui';

module.exports = {
  apps: [
    {
      name: 'iptv-backend',
      cwd: backendDir,
      script: pythonBin,
      args: ['-m', 'app'],
      interpreter: 'none',
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      out_file: path.join(backendLogsDir, 'backend.out.log'),
      error_file: path.join(backendLogsDir, 'backend.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'iptv-worker',
      cwd: backendDir,
      script: pythonBin,
      args: ['-m', 'app.worker'],
      interpreter: 'none',
      env_file: envFile,
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        PYTHONUNBUFFERED: '1',
      },
      out_file: path.join(backendLogsDir, 'worker.out.log'),
      error_file: path.join(backendLogsDir, 'worker.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name: 'iptv-frontend',
      cwd: frontendDir,
      script: 'npm',
      args: 'run dev',
      interpreter: 'none',
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'development',
      },
      out_file: path.join(frontendLogsDir, 'frontend.out.log'),
      error_file: path.join(frontendLogsDir, 'frontend.err.log'),
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
```

- Ajuste permissões antes de iniciar: `sudo mkdir -p /var/log/iptv-backend /var/log/iptv-ui && sudo chown $(whoami) /var/log/iptv-*`.
- Em produção, troque `npm run dev` por um servidor estático (Nginx/PM2 com `serve`) apontando para `dist/`.

## ℹ️ Por que organizar assim?

1. **Frontend dentro de `ui/`** – mantém o projeto React isolado do backend Flask, evitando conflitos de dependências e facilitando a manutenção por equipes distintas.
2. **Vite rodando na pasta do código-fonte** – o Vite espera encontrar `src/`, `public/` e os arquivos de configuração no diretório raiz do frontend. Executá-lo fora disso (na raiz do repositório) exige hacks e gera confusão com `.env`.
3. **Build em `dist/` na raiz** – permite publicar backend e frontend no mesmo servidor. O Nginx pode servir `dist/` enquanto o Gunicorn/PM2 atende a API Flask em paralelo, mantendo tudo dentro de `/root/Iptv-elias`.

## 💾 Bancos de dados do painel

- O `SQLALCHEMY_DATABASE_URI` configura **apenas o banco local do painel**, usado para armazenar usuários, preferências e históricos internos.
- As credenciais do XUI informadas na tela de configurações são validadas sob demanda com uma conexão temporária. Quando o teste passa, o URI remoto é salvo no cadastro do usuário para que os jobs de sincronização consultem diretamente o banco XUI.
- Assim, o banco local continua isolado para o painel, enquanto o banco remoto do XUI só é acessado durante testes ou sincronizações.


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
   - Modo mock: `cd ui && VITE_USE_MOCK=true npm run dev` (ou, já dentro de `ui/`, `VITE_USE_MOCK=true npm run dev -- --mock`).
   - Modo real: `cd ui && npm run dev` com `.env.local` apontando para o backend HTTP.
 - Em produção, defina `VITE_API_BASE_URL` e mantenha `VITE_USE_MOCK=false` para que todos os services utilizem o `ApiAdapter`.

## 🚀 Deploy Automatizado

- O workflow **Deploy IPTV UI** executa lint (`eslint`), build (`npm run build` dentro de `ui/`) e publica automaticamente o conteúdo de `dist/` no branch `gh-pages` a cada push em `main`.
- Para publicar na **Vercel**, cadastre os segredos `VERCEL_TOKEN`, `VERCEL_ORG_ID` e `VERCEL_PROJECT_ID`; o mesmo workflow detecta os valores e executa `vercel deploy` após o build.
- Deploy manual: acione **Actions → Deploy IPTV UI → Run workflow**, escolha o destino (`auto`, `gh-pages`, `vercel` ou `both`) e confirme. Útil para hotfixes ou rollback imediato.
- Relatórios completos e instruções de fallback estão disponíveis em [`docs/DEPLOY_PLAYBOOK.md`](docs/DEPLOY_PLAYBOOK.md).

## 📦 Build & QA

1. **Instale dependências e gere o build otimizado**
   ```bash
   cd ui
   npm install
   npm run build
   ```
   Os artefatos ficam em `dist/` na raiz do repositório. Use `npm run preview` (a partir de `ui/`) para validar o build com o servidor estático do Vite.

2. **Alternar entre mocks e API real**
   - Centralize as variáveis em `ui/.env` (ou `.env.local`, `.env.production` etc.).
   - Defina `VITE_USE_MOCK=true` para desenvolvimento off-line e `false` em produção.
   - Rode `npm run dev` sempre a partir de `ui/` para garantir que o Vite encontre o `.env` correto.

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
