import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User, AuthContextType } from '../lib/types';

const AuthContext = createContext<AuthContextType>({
  token: null, user: null,
  login: () => {}, logout: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const t = sessionStorage.getItem('ct_token');
    const u = sessionStorage.getItem('ct_user');
    if (t && u) { setToken(t); setUser(JSON.parse(u)); }
  }, []);

  function login(t: string, u: User) {
    sessionStorage.setItem('ct_token', t);
    sessionStorage.setItem('ct_user', JSON.stringify(u));
    setToken(t); setUser(u);
  }

  function logout() {
    sessionStorage.removeItem('ct_token');
    sessionStorage.removeItem('ct_user');
    setToken(null); setUser(null);
    window.location.href = '/login';
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() { return useContext(AuthContext); }
export default AuthContext;
