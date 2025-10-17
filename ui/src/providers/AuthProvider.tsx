import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

import { AuthLoginResponse, User } from '../data/types';

interface AuthContextValue {
  token: string | null;
  user: User | null;
  setSession: (payload: AuthLoginResponse) => void;
  clearSession: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = 'iptv-auth';

function readStoredSession(): { token: string | null; user: User | null } {
  if (typeof window === 'undefined') {
    return { token: null, user: null };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);

    if (!raw) {
      return { token: null, user: null };
    }

    const parsed = JSON.parse(raw) as { token?: string; user?: User };
    return {
      token: parsed.token ?? null,
      user: parsed.user ?? null,
    };
  } catch (error) {
    console.warn('Falha ao ler sessão mockada', error);
    return { token: null, user: null };
  }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const initialSession = readStoredSession();
  const [token, setToken] = useState<string | null>(initialSession.token);
  const [user, setUser] = useState<User | null>(initialSession.user);

  const persist = useCallback((nextToken: string | null, nextUser: User | null) => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ token: nextToken, user: nextUser }),
      );
    } catch (error) {
      console.warn('Falha ao persistir sessão mockada', error);
    }
  }, []);

  const setSession = useCallback(
    (payload: AuthLoginResponse) => {
      setToken(payload.token);
      setUser(payload.user);
      persist(payload.token, payload.user);
    },
    [persist],
  );

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
    persist(null, null);
  }, [persist]);

  const value = useMemo(
    () => ({
      token,
      user,
      setSession,
      clearSession,
    }),
    [clearSession, setSession, token, user],
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
