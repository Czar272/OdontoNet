import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster } from "react-hot-toast";

import App from "./App";

import "./index.css";
import { AuthProvider } from "./context/AuthContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <React.StrictMode>
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
    </React.StrictMode>
  </QueryClientProvider>,
);
