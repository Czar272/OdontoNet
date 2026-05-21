/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from "react";

import api from "../services/api";
import toast from "react-hot-toast";

interface AuthContextType {
  token: string | null;
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState(localStorage.getItem("token"));

  async function login(email: string, password: string) {
    try {
      const response = await api.post("/auth/login", {
        email,
        password,
      });

      const token = response.data.access_token;

      localStorage.setItem("token", token);

      setToken(token);

      toast.success("Login Successful");

      return true;
    } catch (error) {
      console.error(error);

      toast.error("Credenciales Invalidas");

      return false;
    }
  }

  function logout() {
    localStorage.removeItem("token");

    setToken(null);
  }

  return (
    <AuthContext.Provider
      value={{
        token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
