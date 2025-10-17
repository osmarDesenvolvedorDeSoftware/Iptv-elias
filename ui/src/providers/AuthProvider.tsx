import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { configureAuthHandlers, isMockEnabled } from '../data/adapters/ApiAdapter';
import { authMockCredentials, refresh as refreshTokens } from '../data/services/authService';
import { AuthLoginResponse, User } from '../data/types';

interface StoredSession {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  user: User;
}

interface AuthContextValue {
  accessToken: string | null;
  refreshToken: string | null;
  tenantId: string | null;
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setSession: (payload: AuthLoginResponse) => void;
  clearSession: () => void;
  refresh: () => Promise<boolean>;
  logout: () => void;
  mockCredentials?: typeof authMockCredentials;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = 'iptv-auth';
const REFRESH_THRESHOLD_MS = 30_000;

function readStoredSession(): StoredSession | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<StoredSession>;

    if (!parsed || !parsed.accessToken || !parsed.refreshToken || !parsed.user) {
      return null;
    }

    const expiresAt = Number(parsed.expiresAt);

    if (!Number.isFinite(expiresAt)) {
      return null;
    }

    return {
      accessToken: parsed.accessToken,
      refreshToken: parsed.refreshToken,
      expiresAt,
      user: parsed.user,
    };
  } catch (error) {
    console.warn('Falha ao ler sessão persistida', error);
    return null;
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const persist = useCallback((value: StoredSession | null) => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      if (!value) {
        window.localStorage.removeItem(STORAGE_KEY);
      } else {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
      }
    } catch (error) {
      console.warn('Falha ao persistir sessão', error);
    }
  }, []);

  const applySession = useCallback(
    (payload: AuthLoginResponse) => {
      const expiresAt = Date.now() + payload.expiresInSec * 1000;
      const nextSession: StoredSession = {
        accessToken: payload.token,
        refreshToken: payload.refreshToken,
        expiresAt,
        user: payload.user,
      };

      setSession(nextSession);
      persist(nextSession);
      setIsLoading(false);
    },
    [persist],
  );

  const clearSession = useCallback(() => {
    setSession(null);
    persist(null);
    setIsLoading(false);
  }, [persist]);

  const refresh = useCallback(async () => {
    const refreshToken = session?.refreshToken;

    if (!refreshToken) {
      clearSession();
      return false;
    }

    try {
      const response = await refreshTokens(refreshToken);
      applySession(response);
      return true;
    } catch (error) {
      console.warn('Falha ao renovar sessão', error);
      clearSession();
      return false;
    }
  }, [applySession, clearSession, session?.refreshToken]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const stored = readStoredSession();

      if (!stored) {
        if (!cancelled) {
          setIsLoading(false);
        }
        return;
      }

      if (!cancelled) {
        setSession(stored);
      }

      const timeUntilExpiry = stored.expiresAt - Date.now();

      if (isMockEnabled || timeUntilExpiry > REFRESH_THRESHOLD_MS) {
        if (!cancelled) {
          setIsLoading(false);
        }
        return;
      }

      try {
        const response = await refreshTokens(stored.refreshToken);
        if (!cancelled) {
          applySession(response);
        }
      } catch (error) {
        console.warn('Falha ao restaurar sessão, limpando estado', error);
        if (!cancelled) {
          clearSession();
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    bootstrap();

    return () => {
      cancelled = true;
    };
  }, [applySession, clearSession]);

  useEffect(() => {
    if (!session || isMockEnabled) {
      return undefined;
    }

    const now = Date.now();
    const msUntilExpiry = session.expiresAt - now;

    if (msUntilExpiry <= 0) {
      void refresh();
      return undefined;
    }

    const msBeforeRefresh = Math.max(msUntilExpiry - REFRESH_THRESHOLD_MS, 5_000);
    const timeoutId = window.setTimeout(() => {
      void refresh();
    }, msBeforeRefresh);

    return () => window.clearTimeout(timeoutId);
  }, [refresh, session]);

  useEffect(() => {
    configureAuthHandlers(
      session
        ? {
            getAccessToken: () => session.accessToken,
            getTenantId: () => session.user.tenantId,
            refresh,
            onAuthFailure: clearSession,
          }
        : null,
    );
  }, [clearSession, refresh, session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      accessToken: session?.accessToken ?? null,
      refreshToken: session?.refreshToken ?? null,
      tenantId: session?.user.tenantId ?? null,
      user: session?.user ?? null,
      isAuthenticated: Boolean(session?.accessToken),
      isLoading,
      setSession: applySession,
      clearSession,
      refresh,
      logout: clearSession,
      mockCredentials: isMockEnabled ? authMockCredentials : undefined,
    }),
    [applySession, clearSession, isLoading, refresh, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error('useAuth deve ser usado dentro de AuthProvider');
  }

  return context;
}
