import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react';

type AccessRole = 'admin' | 'visitor';

interface AuthState {
  role: AccessRole;
  passcode: string;
}

interface AuthContextValue {
  auth: AuthState | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  login: (role: AccessRole, passcode: string) => void;
  logout: () => void;
}

export const AUTH_STORAGE_KEY = 'openlistmedia:auth';

const AuthContext = createContext<AuthContextValue | null>(null);

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

export function AppProviders({ children }: PropsWithChildren) {
  const [auth, setAuth] = useState<AuthState | null>(() => readStoredAuth());

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

  const value = useMemo<AuthContextValue>(
    () => ({
      auth,
      isAuthenticated: Boolean(auth),
      isAdmin: auth?.role === 'admin',
      login: (role, passcode) => setAuth({ role, passcode }),
      logout: () => setAuth(null),
    }),
    [auth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AppProviders');
  }
  return context;
}
