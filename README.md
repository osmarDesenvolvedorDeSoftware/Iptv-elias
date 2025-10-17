# IPTV Elias — Plataforma de Gestão de Conteúdo

Este repositório concentra duas frentes principais:

1. **Backend Django existente**, responsável pelas rotinas atuais do sistema IPTV.
2. **Nova interface SPA (React + TypeScript)** em construção dentro de `ui/`, que substituirá gradualmente os templates Argon.

As fases 1A, 1B, 1C e 1D do plano de migração já foram concluídas: a estrutura base da aplicação React (layouts, roteamento, tema), a camada de dados mockada e as páginas funcionais (Login, Importação, Bouquets, Logs e Configurações) estão prontas para evoluir o restante do painel.

## Estrutura atual

```
ui/
└── src/
    ├── App.tsx
    ├── components/
    │   ├── ImportCard.tsx
    │   ├── LogModal.tsx
    │   └── ToastContainer.tsx
    ├── data/
    │   ├── adapters/
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
- `components/ToastContainer.tsx`: container fixo para alertas disparados pelas ações simuladas.
- `MockAdapter.ts`: carrega fixtures JSON com delay aleatório para simular chamadas HTTP.
- `services/`: funções assíncronas (auth, importador, bouquets, logs, config) que encapsulam as leituras dos mocks.
- `types.ts`: contratos TypeScript compartilhados pelas camadas de dados.
- `AppLayout.tsx` / `AuthLayout.tsx`: cascas principais para rotas autenticadas e públicas.
- `providers/`: contextos compartilhados (`ThemeProvider`, `AuthProvider`, `ToastProvider`).
- `routes.tsx`: mapa de rotas da SPA com páginas reais para Bouquets, Logs e Configurações.
- `routes/Login.tsx`: tela real de autenticação mockada com alerta de erro e spinner no botão.
- `routes/Importacao.tsx`: página real exibindo cards de importações de filmes e séries.
- `routes/Bouquets.tsx`: dual-list com filtros de catálogo e persistência simulada.
- `routes/Logs.tsx`: tabela paginada com filtros e modal de detalhe do log.
- `routes/Config.tsx`: formulários tabulados com validação básica e alerta de reinício.

## 🎬 Páginas Login e Importação

- **/login** — utiliza o `authService.login()` para carregar o usuário mockado (`operador@tenant.com`) e valida a senha `admin123`. Durante o envio do formulário, o botão exibe spinner e fica desabilitado; credenciais incorretas rendem um `alert` vermelho. Ao sucesso, o token falso é salvo no `AuthProvider` e o usuário é redirecionado para `/importacao`. O layout fullscreen mantém o botão de alternância de tema funcionando.
- **/importacao** — consome `importerService.getImports('filmes' | 'series')` para preencher dois cards (Filmes e Séries) lado a lado. Cada card apresenta badge de status, barra de progresso quando um job está em execução, tabela com os cinco últimos históricos e botões de ação. “Rodar agora” chama `importerService.runImport(tipo)`, cria um job simulado e exibe toast de sucesso; “Ver log” e “Configurar” disparam toasts informativos. Estados de carregamento, erro e ausência de dados são tratados com spinners, alerts e mensagens amigáveis.
- **Toasts globais** — o `ToastProvider` combinado ao `ToastContainer` (posicionado no `AppLayout`) exibe feedback para as ações mockadas, harmonizando com o tema claro/escuro.

## 📋 Bouquets, Logs e Configurações

- **/bouquets** — consome `bouquetService.getBouquets()` para montar uma dual-list com filtros de busca e tipo. Movimentações individuais, totais e reordenação simples mantêm o estado local até o mock `saveBouquet()` ser chamado, exibindo toast global de sucesso.
- **/logs** — usa `logService.getLogs()` para popular filtros e tabela responsiva. O botão “Ver detalhes” abre `LogModal`, que consulta `logService.getLogDetail(id)` sob demanda e trata estados de loading, erro e vazio.
- **/configuracoes** — carrega `configService.getConfig()` e distribui os campos em abas (Importador, TMDb, Notificações). A validação básica destaca campos obrigatórios e, ao salvar, `saveConfig()` pode sinalizar a necessidade de reiniciar workers via `alert-warning` persistente.
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

## Progresso das fases

- [x] Fase 1A – Estrutura base do SPA (layouts, roteamento, tema).
- [x] Fase 1B – Camada de Mocks e Serviços.
- [x] Fase 1C – Páginas Login e Importação.
- [x] Fase 1D – Bouquets, Logs e Configurações com mocks.
- [ ] Fase 2 – Integração API real.
- [ ] Fase 3 – Hardening.
