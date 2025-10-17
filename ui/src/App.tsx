import { Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { AppLayout } from './layouts/AppLayout';
import { AuthLayout } from './layouts/AuthLayout';
import { AuthProvider } from './providers/AuthProvider';
import { ToastProvider } from './providers/ToastProvider';
import { ThemeProvider } from './providers/ThemeProvider';
import { appRoutes, authRoutes } from './routes';
import { ToastContainer } from './components/ToastContainer';

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <BrowserRouter>
            <ToastContainer />
            <Suspense
              fallback={
                <div
                  className="d-flex flex-column align-items-center justify-content-center py-5"
                  role="status"
                  aria-live="polite"
                >
                  <span className="spinner-border text-primary mb-3" aria-hidden="true" />
                  <span className="fw-semibold">Carregando interface…</span>
                </div>
              }
            >
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
