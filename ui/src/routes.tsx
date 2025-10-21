import { ComponentType, LazyExoticComponent, lazy } from 'react';

const DashboardPage = lazy(() => import('./routes/Dashboard'));
const ImportacaoPage = lazy(() => import('./routes/Importacao'));
const BouquetsPage = lazy(() => import('./routes/Bouquets'));
const LogsPage = lazy(() => import('./routes/Logs'));
const ConfiguracoesPage = lazy(() => import('./routes/Config'));
const TenantsPage = lazy(() => import('./routes/Tenants'));

const LoginPage = lazy(() => import('./routes/Login'));

export type RouteConfig = {
  path: string;
  element: LazyExoticComponent<ComponentType> | ComponentType;
};

export const appRoutes: RouteConfig[] = [
  { path: '/', element: DashboardPage },
  { path: '/tenants', element: TenantsPage },
  { path: '/importacao', element: ImportacaoPage },
  { path: '/bouquets', element: BouquetsPage },
  { path: '/logs', element: LogsPage },
  { path: '/configuracoes', element: ConfiguracoesPage },
];

export const authRoutes: RouteConfig[] = [{ path: '/login', element: LoginPage }];
