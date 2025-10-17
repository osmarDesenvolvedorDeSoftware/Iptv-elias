# IPTV Elias — Plataforma de Gestão de Conteúdo

Este repositório concentra duas frentes principais:

1. **Backend Django existente**, responsável pelas rotinas atuais do sistema IPTV.
2. **Nova interface SPA (React + TypeScript)** em construção dentro de `ui/`, que substituirá gradualmente os templates Argon.

A fase 1A do plano de migração adiciona apenas a estrutura base da aplicação React, com roteamento, layouts e provedor de tema. Nenhum asset ou mock foi incluído neste estágio inicial.

## Estrutura atual

```
ui/
└── src/
    ├── App.tsx
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
- `AppLayout.tsx`: define a casca principal com navbar e sidebar.
- `AuthLayout.tsx`: casca enxuta para telas de autenticação.
- `ThemeProvider.tsx`: contexto de tema claro/escuro com persistência em `localStorage`.
- `routes.tsx`: mapa de rotas com placeholders para cada página planejada.

## Próximos passos

Consulte `docs/iptv-ui-plan.md` para o plano completo de implementação das fases subsequentes (mocks, componentes e integração com API real).
