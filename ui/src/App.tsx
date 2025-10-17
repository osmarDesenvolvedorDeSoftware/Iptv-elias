import { Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layouts/AppLayout';
import { AuthLayout } from './layouts/AuthLayout';
import { AuthProvider } from './providers/AuthProvider';
import { ToastProvider } from './providers/ToastProvider';
import { ThemeProvider } from './providers/ThemeProvider';
import { appRoutes, authRoutes } from './routes';

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense fallback={<div>Carregando...</div>}>
              <Routes>
                <Route element={<AuthLayout />}>
                  {authRoutes.map((route) => (
                    <Route key={route.path} path={route.path} element={<route.element />} />
                  ))}
                </Route>

                <Route element={<AppLayout />}>
                  {appRoutes.map((route) => (
                    <Route key={route.path} path={route.path} element={<route.element />} />
                  ))}
                </Route>
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
