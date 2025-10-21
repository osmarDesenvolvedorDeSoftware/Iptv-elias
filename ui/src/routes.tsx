import { ComponentType, LazyExoticComponent, lazy } from 'react';

const HomeRedirect = lazy(() => import('./routes/Home'));
const UserDashboardPage = lazy(() => import('./routes/UserDashboard'));
const AdminDashboardPage = lazy(() => import('./routes/AdminDashboard'));
const ImportacaoPage = lazy(() => import('./routes/Importacao'));
const BouquetsPage = lazy(() => import('./routes/Bouquets'));
const LogsPage = lazy(() => import('./routes/Logs'));
const ConfiguracoesPage = lazy(() => import('./routes/Config'));
const TenantsPage = lazy(() => import('./routes/Tenants'));

const LoginPage = lazy(() => import('./routes/Login'));
const RegisterPage = lazy(() => import('./routes/Register'));

type Role = 'admin' | 'user';

export type RouteConfig = {
  path: string;
  element: LazyExoticComponent<ComponentType> | ComponentType;
  roles?: Role[];
};

export const appRoutes: RouteConfig[] = [
  { path: '/', element: HomeRedirect },
  { path: '/dashboard', element: UserDashboardPage, roles: ['user'] },
  { path: '/admin/dashboard', element: AdminDashboardPage, roles: ['admin'] },
  { path: '/importacao', element: ImportacaoPage, roles: ['admin'] },
  { path: '/bouquets', element: BouquetsPage, roles: ['admin'] },
  { path: '/logs', element: LogsPage },
  { path: '/configuracoes', element: ConfiguracoesPage, roles: ['admin'] },
  { path: '/tenants', element: TenantsPage, roles: ['admin'] },
];

export const authRoutes: RouteConfig[] = [
  { path: '/login', element: LoginPage },
  { path: '/register', element: RegisterPage },
];
