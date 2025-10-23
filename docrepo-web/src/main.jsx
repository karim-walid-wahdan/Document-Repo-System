import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { ThemeModeProvider, useThemeMode } from "./theme-context.jsx";
import { makeTheme } from "./theme";


function ThemedApp() {
  const { mode } = useThemeMode();
  const theme = React.useMemo(() => makeTheme(mode), [mode]);
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ThemeProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);
