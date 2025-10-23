import { useEffect, useState } from "react";
import {
  Stack, Paper, TextField, IconButton, InputAdornment,
  Chip, Table, TableHead, TableBody, TableRow, TableCell,
  Tooltip, CircularProgress, Typography, Box
} from "@mui/material";
import Autocomplete from "@mui/material/Autocomplete";
import { LoadingButton } from "@mui/lab";
import SearchIcon from "@mui/icons-material/Search";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import ShieldIcon from "@mui/icons-material/Shield";

import { useNavigate } from "react-router-dom";

import {
  searchDocumentsAdvanced,
  getPresignedDownload,
  getDocumentDetails,
  deleteDocument,
  addVersion
} from "../api/documents";
import { searchTags } from "../api/tags";
import { resolveUploaderId } from "../api/users";

/* ----------------------------- Search Bar ----------------------------- */
function SearchBar({ onSearch, busy }) {
  const [q, setQ] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tagOptions, setTagOptions] = useState([]);
  const [tags, setTags] = useState([]);
  const [uploaderText, setUploaderText] = useState("");
  // track whether the tags dropdown is open; we won't submit on Enter if open
  const [tagsOpen, setTagsOpen] = useState(false);

  // Tags typeahead (Redis → DB fallback handled by server)
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await searchTags(tagInput, 20);
        if (alive) setTagOptions(data || []);
      } catch {
        if (alive) setTagOptions([]);
      }
    })();
    return () => { alive = false; };
  }, [tagInput]);

  async function run() {
    const uploaderId = await resolveUploaderId(uploaderText);
    onSearch({ q, tags: tags.map((t) => t.name), uploaderId });
  }

  return (
    <Paper
      sx={{
        p: 2,
        borderRadius: 3,
        boxShadow: (t) =>
          t.palette.mode === "dark"
            ? "0 8px 30px rgba(0,0,0,.35)"
            : "0 8px 24px rgba(0,0,0,.08)",
      }}
      // Global Enter handler: works for Title, Tags (when menu closed), and Uploader
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          if (tagsOpen) return;    // don't submit while the tags popup is open
          e.preventDefault();
          run();
        }
      }}
    >
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="stretch">
        {/* Title field with end search icon */}
        <TextField
          fullWidth
          label="Search title (partials OK)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          InputProps={{
            endAdornment: (
              <InputAdornment position="end">
                <IconButton onClick={run} aria-label="search">
                  <SearchIcon />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        {/* Tags multi-select */}
        <Autocomplete
          multiple
          open={tagsOpen}
          onOpen={() => setTagsOpen(true)}
          onClose={() => setTagsOpen(false)}
          sx={{ minWidth: 280 }}
          options={tagOptions}
          value={tags}
          getOptionLabel={(opt) => opt.name}
          filterOptions={(x) => x} // rely on server results
          onChange={(_, val) => setTags(val)}
          onInputChange={(_, val) => setTagInput(val)}
          renderInput={(params) => (
            <TextField {...params} label="Tags" placeholder="type to search…" />
          )}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => (
              <Chip
                key={option.tag_id ?? option.name}
                label={option.name}
                color="primary"
                variant="outlined"
                sx={{ fontWeight: 700 }}
                {...getTagProps({ index })}
              />
            ))
          }
        />

        {/* Uploader (email, id, or 'me') */}
        <TextField
          sx={{ minWidth: 240 }}
          label="Uploader (email, id, or 'me')"
          value={uploaderText}
          onChange={(e) => setUploaderText(e.target.value)}
        />

        {/* Search button (consistent height & style) */}
        <LoadingButton
          onClick={run}
          loading={busy}
          variant="contained"
          disableElevation
          sx={(t) => ({
            height: 56, // matches MUI TextField
            alignSelf: { xs: "stretch", md: "center" },
            borderRadius: 3,
            px: 3,
            fontWeight: 800,
            letterSpacing: 0.4,
            textTransform: "none",
            background:
              t.palette.mode === "dark"
                ? "linear-gradient(90deg, #0ea5e9 0%, #7c3aed 100%)"
                : "linear-gradient(90deg, #1976d2 0%, #7b1fa2 100%)",
            "&:hover": {
              filter: "brightness(1.05)",
              background:
                t.palette.mode === "dark"
                  ? "linear-gradient(90deg, #22d3ee 0%, #8b5cf6 100%)"
                  : "linear-gradient(90deg, #1e88e5 0%, #8e24aa 100%)",
            },
          })}
        >
          Search
        </LoadingButton>
      </Stack>
    </Paper>
  );
}

/* --------------------------- Per-row Actions --------------------------- */
function ActionsCell({ doc, onChanged }) {
  const [perms, setPerms] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const details = await getDocumentDetails(doc.doc_id);
        if (!alive) return;
        setPerms(details.perms);
      } catch {
        // ignore; download still works
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [doc.doc_id]);

  async function doDownload() {
    const url = await getPresignedDownload(doc.doc_id);
    window.location.href = url;
  }

  async function doDelete() {
    if (!window.confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    await deleteDocument(doc.doc_id);
    onChanged?.();
  }

  async function doAddVersion() {
    const inp = document.createElement("input");
    inp.type = "file";
    inp.onchange = async () => {
      const file = inp.files && inp.files[0];
      if (file) {
        await addVersion(doc.doc_id, file);
        onChanged?.();
      }
    };
    inp.click();
  }

  const canEdit = !!perms?.can_edit;
  const canModify = !!perms?.can_modify;

  return (
    <Stack direction="row" spacing={1} justifyContent="flex-end" alignItems="center">
      {loading && <CircularProgress size={18} />}
      <Tooltip title="Download">
        <IconButton onClick={doDownload} size="small"><DownloadIcon /></IconButton>
      </Tooltip>
      <Tooltip title={canEdit ? "Add version" : "No edit access"}>
        <span>
          <IconButton onClick={doAddVersion} size="small" disabled={!canEdit}><AddIcon /></IconButton>
        </span>
      </Tooltip>
      <Tooltip title={canEdit ? "Edit metadata (open details to edit)" : "No edit access"}>
        <span>
          <IconButton size="small" disabled={!canEdit}><EditIcon /></IconButton>
        </span>
      </Tooltip>
      <Tooltip title={canModify ? "Delete" : "No delete access"}>
        <span>
          <IconButton onClick={doDelete} size="small" disabled={!canModify}><DeleteIcon /></IconButton>
        </span>
      </Tooltip>
      {perms?.access_level != null && (
        <Tooltip title={`Access level: ${perms.access_level}`}>
          <ShieldIcon fontSize="small" sx={{ opacity: 0.6 }} />
        </Tooltip>
      )}
    </Stack>
  );
}

/* ------------------------------- Page ------------------------------- */
export default function Search() {
  const navigate = useNavigate(); // for clicking titles → /documents/:id

  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [lastQuery, setLastQuery] = useState({});

  async function runSearch(q) {
    setBusy(true);
    try {
      const data = await searchDocumentsAdvanced(q || {});
      setRows(data);
      setLastQuery(q || {});
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => { runSearch({}); }, []);

  const empty = !busy && rows.length === 0;

  const visibilityChip = (v) => (
    <Chip
      label={v}
      size="small"
      variant="outlined"
      color={v === "public" ? "success" : v === "internal" ? "info" : "warning"}
      sx={{ fontWeight: 700, mr: 1 }}
    />
  );

  return (
    <Stack spacing={2}>
      <SearchBar onSearch={runSearch} busy={busy} />

      <Paper sx={{ overflowX: "auto" }}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Title & Description</TableCell>
              <TableCell>Latest</TableCell>
              <TableCell>Tags</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>

          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.doc.doc_id} hover>
                <TableCell>
                  <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
                    {visibilityChip(r.doc.visibility)}
                    <Box>
                      <Typography
                        variant="subtitle1"
                        fontWeight={800}
                        sx={{ color: "primary.main", cursor: "pointer", textDecoration: "underline" }}
                        onClick={() => navigate(`/documents/${r.doc.doc_id}`)}
                      >
                        {r.doc.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                        {r.doc.description}
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>

                <TableCell width={140}>
                  {r.latest_version ? (
                    <Box>
                      <Typography variant="body2">v{r.latest_version.version_no}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {(r.latest_version.file_size ?? 0).toLocaleString()} bytes
                      </Typography>
                    </Box>
                  ) : (
                    <Typography variant="body2" color="text.secondary">—</Typography>
                  )}
                </TableCell>

                <TableCell width={320}>
                  {(r.tags || []).map((t) => (
                    <Chip
                      key={t}
                      label={t}
                      size="small"
                      color="primary"
                      variant="outlined"
                      sx={{ mr: 0.5, mb: 0.5, fontWeight: 700 }}
                    />
                  ))}
                </TableCell>

                <TableCell width={280} align="right">
                  <ActionsCell doc={r.doc} onChanged={() => runSearch(lastQuery)} />
                </TableCell>
              </TableRow>
            ))}

            {empty && (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 6, color: "text.secondary" }}>
                  No results. Try a different title, tags, or uploader.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>

        {busy && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
            <CircularProgress />
          </Box>
        )}
      </Paper>
    </Stack>
  );
}
