import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Stack, LinearProgress, Alert, Button,
  Table, TableHead, TableRow, TableCell, TableBody,
  FormControl, Select, MenuItem, InputLabel, Typography
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ShieldIcon from "@mui/icons-material/Shield";

const PERM_LEVELS = ["owner","edit","view"];

export default function PermissionsDialog({ open, onClose, loadData, saveData }) {
  // loadData: () => Promise<{ departments, rows }>
  // saveData: (rows) => Promise<void>
  const [departments, setDepartments] = useState([]);
  const [rows, setRows] = useState([]); // [{department_id, level}]
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    async function run() {
      setBusy(true); setError("");
      try {
        const { departments: deps, rows: r } = await loadData();
        if (!alive) return;
        setDepartments(deps || []);
        setRows(r || []);
      } catch (e) {
        setError(e?.message || "Failed to load permissions.");
      } finally { if (alive) setBusy(false); }
    }
    if (open) run();
    return () => { alive = false; };
  }, [open, loadData]);

  function upsert(depId, level) {
    setRows((prev) => {
      const copy = prev.filter((r) => r.department_id !== depId);
      if (level) copy.push({ department_id: depId, level });
      return copy;
    });
  }

  async function save() {
    setSaving(true); setError("");
    try {
      await saveData(rows);
      onClose();
    } catch (e) {
      setError(e?.message || "Failed to save permissions.");
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
                Set access per department. <b>owner</b> can manage ACL; <b>edit</b> can add versions & edit metadata; <b>view</b> can read.
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
                              {PERM_LEVELS.map((lv) => (
                                <MenuItem key={lv} value={lv}>{lv}</MenuItem>
                              ))}
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
        <Button onClick={save} disabled={saving || busy} variant="contained" startIcon={<ShieldIcon />}>
          Save
        </Button>
      </DialogActions>
    </Dialog>
  );
}
