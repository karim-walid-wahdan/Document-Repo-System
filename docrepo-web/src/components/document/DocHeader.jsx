import { Box, Stack, Typography, Paper, Button, Tooltip, Divider } from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import EditIcon from "@mui/icons-material/Edit";
import AddIcon from "@mui/icons-material/Add";
import ShieldIcon from "@mui/icons-material/Shield";
import DeleteIcon from "@mui/icons-material/Delete";
import VisibilityChip from "./VisibilityChip";
import { useTheme } from "@mui/material/styles";

export default function DocHeader({
  details,
  onDownload,
  onEdit,
  onNewVersion,
  onPermissions,
  onDelete,
}) {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const bg = isDark
    ? "linear-gradient(135deg, rgba(14,165,233,.10), rgba(124,58,237,.10))"
    : "linear-gradient(135deg, rgba(25,118,210,.08), rgba(123,31,162,.08))";

  const canEdit = !!details?.perms?.can_edit;
  const canModify = !!details?.perms?.can_modify;

  return (
    <Paper sx={{ p: { xs: 2, md: 3 }, borderRadius: 3, background: bg, border: (t) => `1px solid ${t.palette.divider}` }}>
      <Stack direction="row" alignItems="flex-start" spacing={2} justifyContent="space-between">
        <Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h5" fontWeight={800}>{details.doc.title}</Typography>
            <VisibilityChip value={details.doc.visibility} />
          </Stack>
          <Typography variant="body2" color="text.secondary" sx={{ mt: .5 }}>
            Updated: {new Date(details.doc.updated_at).toLocaleString()}
          </Typography>
        </Box>

        <Stack direction="row" spacing={1}>
          <Tooltip title="Download latest">
            <span><Button onClick={onDownload} variant="outlined" startIcon={<DownloadIcon />}>Download</Button></span>
          </Tooltip>
          <Tooltip title={canEdit ? "Edit metadata" : "No edit access"}>
            <span><Button onClick={onEdit} variant="outlined" startIcon={<EditIcon />} disabled={!canEdit}>Edit</Button></span>
          </Tooltip>
          <Tooltip title={canEdit ? "Upload new version" : "No edit access"}>
            <span><Button onClick={onNewVersion} variant="outlined" startIcon={<AddIcon />} disabled={!canEdit}>New Version</Button></span>
          </Tooltip>
          <Tooltip title="Manage permissions (owner/admin)">
            <span><Button onClick={onPermissions} variant="outlined" startIcon={<ShieldIcon />}>Permissions</Button></span>
          </Tooltip>
          <Tooltip title={canModify ? "Delete document" : "No delete access"}>
            <span><Button onClick={onDelete} color="error" variant="contained" startIcon={<DeleteIcon />} disabled={!canModify}>Delete</Button></span>
          </Tooltip>
        </Stack>
      </Stack>
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle2" sx={{ mb: .5 }}>Description</Typography>
      <Typography variant="body1">{details.doc.description || "—"}</Typography>
    </Paper>
  );
}
