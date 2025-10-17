import {
  PropsWithChildren,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

type ThemeMode = 'light' | 'dark';

type ThemeContextValue = {
  mode: ThemeMode;
  toggle: () => void;
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);
const STORAGE_KEY = 'iptv-theme';

function readStoredTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light';
  }

  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'dark' ? 'dark' : 'light';
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<ThemeMode>(() => readStoredTheme());

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.document.body.dataset.theme = mode;
    window.localStorage.setItem(STORAGE_KEY, mode);
  }, [mode]);

  const toggle = useCallback(() => {
    setMode((current) => (current === 'light' ? 'dark' : 'light'));
  }, []);

  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error('useTheme deve ser usado dentro de ThemeProvider');
  }

  return context;
}
