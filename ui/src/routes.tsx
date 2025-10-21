import { ComponentType, LazyExoticComponent, lazy } from 'react';
import { Navigate } from 'react-router-dom';

const HomeRedirect = lazy(() => import('./routes/Home'));
const AccountConfigPage = lazy(() => import('./routes/AccountConfig'));
const AdminDashboardPage = lazy(() => import('./routes/AdminDashboard'));
const AdminAccountsPage = lazy(() => import('./routes/AdminAccounts'));
const ImportsPage = lazy(() => import('./routes/Imports'));
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
  { path: '/dashboard', element: AccountConfigPage, roles: ['user'] },
  { path: '/admin/dashboard', element: AdminDashboardPage, roles: ['admin'] },
  { path: '/admin/accounts', element: AdminAccountsPage, roles: ['admin'] },
  { path: '/importacoes', element: ImportsPage, roles: ['admin'] },
  { path: '/importacao', element: () => <Navigate to="/importacoes" replace />, roles: ['admin'] },
  { path: '/bouquets', element: BouquetsPage, roles: ['admin'] },
  { path: '/logs', element: LogsPage },
  { path: '/configuracoes', element: ConfiguracoesPage, roles: ['admin'] },
  { path: '/tenants', element: TenantsPage, roles: ['admin'] },
];

export const authRoutes: RouteConfig[] = [
  { path: '/login', element: LoginPage },
  { path: '/register', element: RegisterPage },
];
