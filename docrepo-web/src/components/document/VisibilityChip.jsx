import React from "react";
import { Chip, MenuItem, Stack, TextField, Typography } from "@mui/material";
import PublicIcon from "@mui/icons-material/Public";
import GroupsIcon from "@mui/icons-material/Groups";
import LockIcon from "@mui/icons-material/Lock";

export const VIS_OPTIONS = [
  { value: "public",     label: "public",     Icon: PublicIcon,  paletteKey: "success"  },
  { value: "internal",   label: "internal",   Icon: GroupsIcon,  paletteKey: "info"     },
  { value: "restricted", label: "restricted", Icon: LockIcon,    paletteKey: "warning"  },
];

export function VisibilityChip({ value }) {
  const opt = VIS_OPTIONS.find(o => o.value === value) || VIS_OPTIONS[1];
  const Ico = opt.Icon;
  return (
    <Chip
      size="small"
      icon={<Ico sx={{ color: (t) => t.palette[opt.paletteKey].main }} />}
      label={opt.label}
      variant="outlined"
      sx={{ fontWeight: 700 }}
    />
  );
}

export function VisibilitySelect({ value, onChange, sx }) {
  return (
    <TextField select label="Visibility" value={value} onChange={(e) => onChange(e.target.value)} sx={{ minWidth: 220, ...sx }}>
      {VIS_OPTIONS.map((opt) => {
        const Ico = opt.Icon;
        return (
          <MenuItem key={opt.value} value={opt.value}>
            <Stack direction="row" alignItems="center" spacing={1}>
              <Ico sx={{ color: (t) => t.palette[opt.paletteKey].main, opacity: .9 }} fontSize="small" />
              <Typography sx={{ textTransform: "capitalize" }}>{opt.label}</Typography>
            </Stack>
          </MenuItem>
        );
      })}
    </TextField>
  );
}
