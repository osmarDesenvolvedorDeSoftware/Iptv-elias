import { ComponentType, LazyExoticComponent, lazy } from 'react';

const DashboardPage = lazy(() => import('./routes/DashboardPlaceholder'));
const ImportacaoPage = lazy(() => import('./routes/Importacao'));
const BouquetsPage = lazy(() => import('./routes/BouquetsPlaceholder'));
const RelatoriosPage = lazy(() => import('./routes/RelatoriosPlaceholder'));
const ConfiguracoesPage = lazy(() => import('./routes/ConfiguracoesPlaceholder'));

const LoginPage = lazy(() => import('./routes/Login'));

export type RouteConfig = {
  path: string;
  element: LazyExoticComponent<ComponentType> | ComponentType;
};

export const appRoutes: RouteConfig[] = [
  { path: '/', element: DashboardPage },
  { path: '/importacao', element: ImportacaoPage },
  { path: '/bouquets', element: BouquetsPage },
  { path: '/relatorios', element: RelatoriosPage },
  { path: '/configuracoes', element: ConfiguracoesPage },
];

export const authRoutes: RouteConfig[] = [{ path: '/login', element: LoginPage }];
