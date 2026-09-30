import React, { createContext, useContext, useState, useEffect } from "react";
import apiClient from "../api/client";

export interface UserProfile {
  id: number;
  name: string;
  email: string;
  role: string;
  permissions: string[];
  authority_id: number | null;
  authority?: {
    id: number;
    name: string;
    authority_type: string;
  };
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (token: string, remember: boolean) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem("pravaah_token") || sessionStorage.getItem("pravaah_token");
  });
  const [loading, setLoading] = useState<boolean>(true);

  const fetchUserProfile = async () => {
    try {
      const res = await apiClient.get<UserProfile>("/auth/me");
      setUser(res.data);
    } catch {
      logout();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token) {
      fetchUserProfile();
    } else {
      setLoading(false);
    }
  }, [token]);

  const login = async (newToken: string, remember: boolean) => {
    if (remember) {
      localStorage.setItem("pravaah_token", newToken);
    } else {
      sessionStorage.setItem("pravaah_token", newToken);
    }
    setToken(newToken);
    await fetchUserProfile();
  };

  const logout = () => {
    localStorage.removeItem("pravaah_token");
    sessionStorage.removeItem("pravaah_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        isAuthenticated: !!token && !!user,
        login,
        logout,
        refreshUser: fetchUserProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
