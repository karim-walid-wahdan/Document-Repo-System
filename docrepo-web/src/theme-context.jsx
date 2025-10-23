import { createContext, useContext, useEffect, useMemo, useState } from "react";

const ThemeModeCtx = createContext({ mode: "light", toggle: () => {} });

export function useThemeMode() { return useContext(ThemeModeCtx); }

export function ThemeModeProvider({ children }) {
  const [mode, setMode] = useState(() => localStorage.getItem("theme-mode") || "light");
  useEffect(() => { localStorage.setItem("theme-mode", mode); }, [mode]);
  const value = useMemo(() => ({ mode, toggle: () => setMode(m => (m === "light" ? "dark" : "light")) }), [mode]);
  return <ThemeModeCtx.Provider value={value}>{children}</ThemeModeCtx.Provider>;
}
