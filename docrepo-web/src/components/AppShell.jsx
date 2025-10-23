import { useState } from "react";
import {
  AppBar, Toolbar, Typography, Button, Box, IconButton,
  Drawer, List, ListItemButton, ListItemIcon, ListItemText, Divider
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import SearchIcon from "@mui/icons-material/Search";
import UploadIcon from "@mui/icons-material/UploadFile";
import LocalFireIcon from "@mui/icons-material/LocalFireDepartment";
import LogoutIcon from "@mui/icons-material/Logout";
import HomeIcon from "@mui/icons-material/Home";
import ThemeToggle from "./ThemeToggle";
import { useLocation, useNavigate } from "react-router-dom";
import { logout } from "../api/auth";

const navItems = [
  { label: "Home", to: "/documents", icon: <HomeIcon /> },
  { label: "Upload", to: "/upload", icon: <UploadIcon /> },
  { label: "Hot Docs", to: "/hot", icon: <LocalFireIcon /> }, // if you add later
];

export default function AppShell({ children }) {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const go = (to) => { setOpen(false); nav(to); };

  async function handleLogout() {
    await logout();
    nav("/login", { replace: true });
  }

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <AppBar position="sticky" elevation={1}>
        <Toolbar>
          <IconButton color="inherit" onClick={() => setOpen(true)} sx={{ mr: 1 }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 800, letterSpacing: .2 }}>
            DocRepo
          </Typography>
          <Button color="inherit" startIcon={<SearchIcon />} onClick={() => go("/documents")}>Search</Button>
          <Button color="inherit" startIcon={<UploadIcon />} onClick={() => go("/upload")}>Upload</Button>
          <ThemeToggle />
          <Button color="inherit" startIcon={<LogoutIcon />} onClick={handleLogout}>Logout</Button>
        </Toolbar>
      </AppBar>

      <Drawer anchor="left" open={open} onClose={() => setOpen(false)}>
        <Box sx={{ width: 260 }} role="presentation">
          <Typography variant="h6" sx={{ px: 2, py: 2, fontWeight: 700 }}>Navigation</Typography>
          <Divider />
          <List>
            {navItems.map((it) => (
              <ListItemButton key={it.to} selected={loc.pathname === it.to} onClick={() => go(it.to)}>
                <ListItemIcon>{it.icon}</ListItemIcon>
                <ListItemText primary={it.label} />
              </ListItemButton>
            ))}
          </List>
          <Divider />
          <List>
            <ListItemButton onClick={handleLogout}>
              <ListItemIcon><LogoutIcon /></ListItemIcon>
              <ListItemText primary="Logout" />
            </ListItemButton>
          </List>
        </Box>
      </Drawer>

      <Box sx={{ p: { xs: 2, md: 3 } }}>{children}</Box>
    </Box>
  );
}
