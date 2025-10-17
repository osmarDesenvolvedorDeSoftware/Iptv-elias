# IPTV Elias — Plataforma de Gestão de Conteúdo

Este repositório concentra duas frentes principais:

1. **Backend Django existente**, responsável pelas rotinas atuais do sistema IPTV.
2. **Nova interface SPA (React + TypeScript)** em construção dentro de `ui/`, que substituirá gradualmente os templates Argon.

As fases 1A e 1B do plano de migração já foram concluídas: a estrutura base da aplicação React (layouts, roteamento, tema) está pronta e agora contamos com uma camada de dados mockada para desenvolvimento offline.

## Estrutura atual

-```
ui/
└── src/
    ├── App.tsx
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
    │   └── ThemeProvider.tsx
    ├── routes.tsx
    └── routes/
        ├── BouquetsPlaceholder.tsx
        ├── ConfiguracoesPlaceholder.tsx
        ├── DashboardPlaceholder.tsx
        ├── ImportacaoPlaceholder.tsx
        ├── LoginPlaceholder.tsx
        └── RelatoriosPlaceholder.tsx
```

- `App.tsx`: inicializa o roteamento e aplica o `ThemeProvider`.
- `MockAdapter.ts`: carrega fixtures JSON com delay aleatório para simular chamadas HTTP.
- `services/`: funções assíncronas (auth, importador, bouquets, logs, config) que encapsulam as leituras dos mocks.
- `types.ts`: contratos TypeScript compartilhados pelas camadas de dados.
- `AppLayout.tsx` / `AuthLayout.tsx`: cascas principais para rotas autenticadas e públicas.
- `ThemeProvider.tsx`: contexto de tema claro/escuro com persistência em `localStorage`.
- `routes.tsx`: mapa de rotas com placeholders para cada página planejada.

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
- [ ] Fase 1C – Páginas Importação e Login.
- [ ] Fase 2 – Bouquets.
- [ ] Fase 3 – Logs/Relatórios.
- [ ] Fase 4 – Configurações.
- [ ] Fase 5 – Integração API real.
- [ ] Fase 6 – Hardening.
