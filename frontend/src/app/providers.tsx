import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';

type AccessRole = 'admin' | 'visitor';
type ThemeMode = 'dark' | 'light';

interface AuthState {
  role: AccessRole;
  passcode: string;
}

interface AuthContextValue {
  auth: AuthState | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  theme: ThemeMode;
  login: (role: AccessRole, passcode: string) => void;
  logout: () => void;
  setTheme: (theme: ThemeMode) => void;
}

export const AUTH_STORAGE_KEY = 'openlistmedia:auth';
export const THEME_STORAGE_KEY = 'openlistmedia:theme';
export const AUTH_EXPIRED_EVENT = 'openlistmedia:auth-expired';

const AuthContext = createContext<AuthContextValue | null>(null);

// eslint-disable-next-line react-refresh/only-export-components
export function readStoredAuth(): AuthState | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<AuthState>;
    if (!parsed.role || !parsed.passcode) {
      return null;
    }
    if (parsed.role !== 'admin' && parsed.role !== 'visitor') {
      return null;
    }
    return {
      role: parsed.role,
      passcode: String(parsed.passcode),
    };
  } catch {
    return null;
  }
}

function readStoredTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'dark';
  }
  const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (raw === 'light' || raw === 'dark') {
    return raw;
  }
  if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

export function AppProviders({ children }: PropsWithChildren) {
  const [auth, setAuth] = useState<AuthState | null>(() => readStoredAuth());
  const [theme, setTheme] = useState<ThemeMode>(() => readStoredTheme());

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    if (!auth) {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
  }, [auth]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    window.document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    function onStorage(event: StorageEvent) {
      if (event.key === AUTH_STORAGE_KEY) {
        setAuth(readStoredAuth());
      }
      if (event.key === THEME_STORAGE_KEY) {
        const next = event.newValue;
        if (next === 'light' || next === 'dark') {
          setTheme(next);
        }
      }
    }
    function onAuthExpired() {
      setAuth(null);
    }
    window.addEventListener('storage', onStorage);
    window.addEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener(AUTH_EXPIRED_EVENT, onAuthExpired);
    };
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }
    const query = window.matchMedia('(prefers-color-scheme: light)');
    function onChange(event: MediaQueryListEvent) {
      const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (stored === 'light' || stored === 'dark') {
        return;
      }
      setTheme(event.matches ? 'light' : 'dark');
    }
    query.addEventListener('change', onChange);
    return () => {
      query.removeEventListener('change', onChange);
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      auth,
      isAuthenticated: Boolean(auth),
      isAdmin: auth?.role === 'admin',
      theme,
      login: (role, passcode) => setAuth({ role, passcode }),
      logout: () => setAuth(null),
      setTheme,
    }),
    [auth, theme],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AppProviders');
  }
  return context;
}
