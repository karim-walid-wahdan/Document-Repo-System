import { createTheme } from "@mui/material/styles";

export function makeTheme(mode = "light") {
  const isDark = mode === "dark";

  const primary = isDark ? { main: "#6ee7ff" } : { main: "#1976d2" };   // cyan-ish in dark, indigo in light
  const secondary = isDark ? { main: "#f48fb1" } : { main: "#d81b60" };

  return createTheme({
    palette: {
      mode,
      primary,
      secondary,
      background: isDark
        ? { default: "#0f172a", paper: "#111827" }       // slate / gray-900
        : { default: "#f5f7fb", paper: "#ffffff" },
    },
    shape: { borderRadius: 12 },
    typography: {
      fontFamily: `"Inter", system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif`,
      h5: { fontWeight: 700 },
      subtitle1: { fontWeight: 600 },
    },
    components: {
      MuiAppBar: {
        styleOverrides: {
          root: {
            // subtle gradient for color ✨
            backgroundImage: isDark
              ? "linear-gradient(90deg, #0ea5e9 0%, #7c3aed 100%)"
              : "linear-gradient(90deg, #1976d2 0%, #7b1fa2 100%)",
          },
        },
      },
      MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 600 },
        },
      },
    },
  });
}
