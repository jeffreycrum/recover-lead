import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@/providers/clerk-provider";
import { QueryProvider } from "@/providers/query-provider";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ClerkProvider>
        <QueryProvider>
          <App />
        </QueryProvider>
      </ClerkProvider>
    </BrowserRouter>
  </React.StrictMode>
);
