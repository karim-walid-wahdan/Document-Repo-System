import { IconButton, Tooltip } from "@mui/material";
import DarkModeIcon from "@mui/icons-material/DarkMode";
import LightModeIcon from "@mui/icons-material/LightMode";
import { useTheme } from "@mui/material/styles";
import { useThemeMode } from "../theme-context";

export default function ThemeToggle({ edge }) {
  const theme = useTheme();
  const { toggle } = useThemeMode();
  const isDark = theme.palette.mode === "dark";
  return (
    <Tooltip title={isDark ? "Switch to light" : "Switch to dark"}>
      <IconButton color="inherit" onClick={toggle} edge={edge}>
        {isDark ? <LightModeIcon /> : <DarkModeIcon />}
      </IconButton>
    </Tooltip>
  );
}
