import React from "react";
import ReactDOM from "react-dom/client";
import axios from "axios";
import { Toaster } from "react-hot-toast";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";

import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Los errores 4xx (401, 403, 404...) no se resuelven reintentando.
      retry: (failureCount, error) => {
        if (axios.isAxiosError(error) && error.response && error.response.status < 500) {
          return false;
        }
        return failureCount < 2;
      },
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 3000,

            style: {
              borderRadius: "12px",
              background: "#111827",
              color: "#fff",
            },

            success: {
              style: {
                background: "#16a34a",
              },
            },

            error: {
              style: {
                background: "#dc2626",
              },
            },
          }}
        />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
