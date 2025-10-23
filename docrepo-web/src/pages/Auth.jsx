import { useEffect, useMemo, useState } from "react";
import {
  Box, Paper, Tabs, Tab, Stack, TextField, Button, Typography, Alert,
  InputAdornment, IconButton, MenuItem, Select, FormControl, InputLabel,
  CircularProgress, Divider, Avatar
} from "@mui/material";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";
import PersonOutline from "@mui/icons-material/PersonOutline";
import { useNavigate } from "react-router-dom";

import { login, register } from "../api/auth";
import { getDepartments, getRolesByDepartment } from "../api/org";

function FancyBackground({ children }) {
  // subtle gradient background
  return (
    <Box sx={{
      minHeight: "100vh",
      p: 2,
      bgcolor: "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)",
      background: "radial-gradient(ellipse at top, #213e5a, #0f2027)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}>
      {children}
    </Box>
  );
}

export default function Auth() {
  const [tab, setTab] = useState(0); // 0=login, 1=signup
  return (
    <FancyBackground>
      <Paper elevation={8} sx={{
        width: 920,
        maxWidth: "95vw",
        borderRadius: 3,
        overflow: "hidden",
        display: "grid",
        gridTemplateColumns: { xs: "1fr", md: "1.2fr 1fr" },
      }}>
        {/* left: form area */}
        <Box sx={{ p: { xs: 3, md: 5 }}}>
          <Stack spacing={3}>
            <Stack direction="row" spacing={1} alignItems="center">
              <Avatar sx={{ bgcolor: "primary.main" }}><PersonOutline /></Avatar>
              <Typography variant="h5" fontWeight={700}>Welcome to DocRepo</Typography>
            </Stack>
            <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ ".MuiTabs-flexContainer": { gap: 2 } }}>
              <Tab label="Sign in" />
              <Tab label="Create account" />
            </Tabs>
            <Divider />
            {tab === 0 ? <LoginForm /> : <SignupForm onSignedUp={() => setTab(0)} />}
          </Stack>
        </Box>

        {/* right: brand panel */}
        <Box sx={{
          display: { xs: "none", md: "flex" },
          alignItems: "center",
          justifyContent: "center",
          p: 5,
          color: "#fff",
          bgcolor: "linear-gradient(135deg, #1e3c72, #2a5298)",
          background: "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)",
        }}>
          <Stack spacing={2} sx={{ maxWidth: 320 }}>
            <Typography variant="h4" fontWeight={800}>Store. Search. Share.</Typography>
            <Typography variant="body1" sx={{ opacity: 0.9 }}>
              Versioned document storage with department-based permissions.
              Upload securely, find instantly, and control who sees what.
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
              Powered by FastAPI · Postgres · Redis · S3
            </Typography>
          </Stack>
        </Box>
      </Paper>
    </FancyBackground>
  );
}

function LoginForm() {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null); setBusy(true);
    try {
      await login(email.trim(), pw);
      nav("/documents");
    } catch (e) {
      setErr(e?.response?.data?.detail || "Sign-in failed");
    } finally { setBusy(false); }
  }

  return (
    <form onSubmit={onSubmit}>
      <Stack spacing={2}>
        {err && <Alert severity="error">{err}</Alert>}
        <TextField label="Email" type="email" value={email}
          onChange={e => setEmail(e.target.value)} required autoFocus />
        <TextField
          label="Password"
          type={show ? "text" : "password"}
          value={pw}
          onChange={e => setPw(e.target.value)}
          required
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => setShow(s => !s)} edge="end" aria-label="toggle password">
                  {show ? <VisibilityOff/> : <Visibility/>}
                </IconButton>
              </InputAdornment>
            )
          }}
        />
        <Button variant="contained" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </Button>
      </Stack>
    </form>
  );
}

function SignupForm({ onSignedUp }) {
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [show, setShow] = useState(false);

  const [departments, setDepartments] = useState(null);
  const [deptId, setDeptId] = useState("");
  const [roles, setRoles] = useState(null);
  const [roleId, setRoleId] = useState("");

  const [loadingDepts, setLoadingDepts] = useState(true);
  const [loadingRoles, setLoadingRoles] = useState(false);

  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  // load departments (cached in api layer)
  useEffect(() => {
    let alive = true;
    setLoadingDepts(true);
    getDepartments()
      .then(d => { if (alive) setDepartments(d); })
      .catch(() => { if (alive) setDepartments([]); })
      .finally(() => { if (alive) setLoadingDepts(false); });
    return () => { alive = false; };
  }, []);

  // when department changes, load its roles
  useEffect(() => {
    if (!deptId) { setRoles(null); setRoleId(""); return; }
    setLoadingRoles(true);
    getRolesByDepartment(deptId)
      .then(r => setRoles(r))
      .catch(() => setRoles([]))
      .finally(() => setLoadingRoles(false));
  }, [deptId]);

  const deptMenu = useMemo(() => (departments || []).map(d => (
    <MenuItem key={d.department_id} value={d.department_id}>
      {d.name} <Typography component="span" sx={{ ml: 1, opacity: .6 }}>· {d.location}</Typography>
    </MenuItem>
  )), [departments]);

  const roleMenu = useMemo(() => (roles || []).map(r => (
    <MenuItem key={r.role_id} value={r.role_id}>{r.name}</MenuItem>
  )), [roles]);

  async function onSubmit(e) {
    e.preventDefault();
    setErr(null);
    if (!deptId || !roleId) { setErr("Please choose a department and role"); return; }
    setBusy(true);
    try {
      await register(email.trim(), pw, Number(roleId), Number(deptId));
      // backend returns access+refresh; you're now logged in → take user in
      nav("/documents");
      onSignedUp?.();
    } catch (e) {
      setErr(e?.response?.data?.detail || "Sign-up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <Stack spacing={2}>
        {err && <Alert severity="error">{err}</Alert>}
        <TextField label="Email" type="email" value={email}
          onChange={e => setEmail(e.target.value)} required autoFocus />
        <TextField
          label="Password"
          type={show ? "text" : "password"}
          value={pw}
          onChange={e => setPw(e.target.value)}
          helperText="Min 8 characters"
          required
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={() => setShow(s => !s)} edge="end" aria-label="toggle password">
                  {show ? <VisibilityOff/> : <Visibility/>}
                </IconButton>
              </InputAdornment>
            )
          }}
        />

        {/* Department select */}
        <FormControl fullWidth required>
          <InputLabel id="dept-label">Department</InputLabel>
          <Select
            labelId="dept-label" label="Department"
            value={deptId} onChange={e => setDeptId(e.target.value)}
            disabled={loadingDepts}
            renderValue={(v) => {
              const d = (departments || []).find(x => x.department_id === v);
              return d ? `${d.name} · ${d.location}` : "";
            }}
          >
            {loadingDepts
              ? <MenuItem disabled><CircularProgress size={20} sx={{ mr: 1 }}/> Loading…</MenuItem>
              : (deptMenu.length ? deptMenu : <MenuItem disabled>No departments</MenuItem>)
            }
          </Select>
        </FormControl>

        {/* Role select (depends on department) */}
        <FormControl fullWidth required disabled={!deptId || loadingRoles}>
          <InputLabel id="role-label">Role</InputLabel>
          <Select
            labelId="role-label" label="Role"
            value={roleId} onChange={e => setRoleId(e.target.value)}
            renderValue={(v) => {
              const r = (roles || []).find(x => x.role_id === v);
              return r ? r.name : "";
            }}
          >
            {!deptId && <MenuItem disabled>Select a department first</MenuItem>}
            {loadingRoles && <MenuItem disabled><CircularProgress size={20} sx={{ mr: 1 }}/> Loading…</MenuItem>}
            {!loadingRoles && deptId && (roleMenu.length ? roleMenu : <MenuItem disabled>No roles for this department</MenuItem>)}
          </Select>
        </FormControl>

        <Button variant="contained" type="submit" disabled={busy}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </Stack>
    </form>
  );
}
