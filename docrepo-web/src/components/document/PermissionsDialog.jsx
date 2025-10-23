import { useEffect, useMemo, useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Stack, LinearProgress, Alert, Typography, Table, TableHead, TableRow, TableCell, TableBody, FormControl, InputLabel, Select, MenuItem, Button } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ShieldIcon from "@mui/icons-material/Shield";
import { listDepartments } from "../../api/departments";

const LEVELS = ["owner", "edit", "view"];

export default function PermissionsDialog({ open, onClose, load, save }) {
  // props:
  //  - load(): Promise<{departments:[], rows:[]}>
  //  - save(rows): Promise<void>
  const [departments, setDepartments] = useState([]);
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    async function refresh() {
      setBusy(true); setError("");
      try {
        const deps = await listDepartments();
        const { rows: perms } = await load();
        if (!alive) return;
        setDepartments(deps);
        setRows(perms || []);
      } catch (e) {
        setError(e?.response?.data?.detail || "Failed to load permissions.");
      } finally { if (alive) setBusy(false); }
    }
    if (open) refresh();
    return () => { alive = false; };
  }, [open, load]);

  function upsert(depId, level) {
    setRows((prev) => {
      const copy = prev.filter((r) => r.department_id !== depId);
      if (level) copy.push({ department_id: depId, level });
      return copy;
    });
  }

  async function onSave() {
    setSaving(true); setError("");
    try {
      await save(rows);
      onClose();
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to save.");
    } finally { setSaving(false); }
  }

  return (
    <Dialog open={open} onClose={saving ? undefined : onClose} maxWidth="md" fullWidth>
      <DialogTitle>Permissions</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          {error && <Alert severity="error" onClose={() => setError("")}>{error}</Alert>}
          {busy && <LinearProgress />}
          {!busy && (
            <>
              <Typography variant="body2" color="text.secondary">
                Set access per department. <b>owner</b> can manage ACL; <b>edit</b> can upload & edit; <b>view</b> can read.
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Department</TableCell>
                    <TableCell>Location</TableCell>
                    <TableCell width={220}>Level</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {departments.map((d) => {
                    const cur = rows.find((r) => r.department_id === d.department_id)?.level || "";
                    return (
                      <TableRow key={d.department_id} hover>
                        <TableCell>{d.name}</TableCell>
                        <TableCell>{d.location}</TableCell>
                        <TableCell>
                          <FormControl fullWidth size="small">
                            <InputLabel id={`lvl-${d.department_id}`}>Level</InputLabel>
                            <Select
                              labelId={`lvl-${d.department_id}`}
                              value={cur}
                              label="Level"
                              onChange={(e) => upsert(d.department_id, e.target.value)}
                            >
                              <MenuItem value=""><em>none</em></MenuItem>
                              {LEVELS.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
                            </Select>
                          </FormControl>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={saving} startIcon={<CloseIcon />}>Close</Button>
        <Button onClick={onSave} disabled={saving || busy} variant="contained" startIcon={<ShieldIcon />}>Save</Button>
      </DialogActions>
    </Dialog>
  );
}
