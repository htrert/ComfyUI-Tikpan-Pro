# Tikpan Local Repository Map

This workspace contains the ComfyUI node package plus two standalone web
projects that live beside it locally.

## Repositories

| Local folder | Git remote | Purpose | Tracking rule |
| --- | --- | --- | --- |
| `.` | `https://github.com/htrert/ComfyUI-Tikpan-Pro.git` | ComfyUI custom nodes, docs, tests, node package assets | Tracked by this repository |
| `web_app/` | `https://github.com/htrert/tikpan-web.git` | Flask commercial web backend / site | Standalone repository, ignored by parent |
| `experiments/canvas_model_studio/` | `https://github.com/htrert/tikpan-canvas.git` | Canvas/model studio experiment | Standalone repository, ignored by parent |

## Local-Only Folders

These are intentionally not part of the parent repository:

- `web_app/`: committed and pushed from inside `web_app`.
- `experiments/`: experiment workspaces, including the standalone canvas repo.
- `landing-page/api/node_modules/`, `dist/`, `*.log`, `*.tsbuildinfo`: generated runtime output.
- `chrome-*.png`, `DESIGN.md`, `tools/`: local research screenshots, working notes, and operator scripts.

## Workflow

Use the repository root for ComfyUI node changes:

```powershell
git status -sb
```

Use `web_app/` for Tikpan Web changes:

```powershell
git -C web_app status -sb
git -C web_app push
```

Use `experiments/canvas_model_studio/` for Tikpan Canvas changes:

```powershell
git -C experiments\canvas_model_studio status -sb
```

Do not commit the contents of standalone repositories from the parent
`ComfyUI-Tikpan-Pro` repository. They are kept in place for local convenience
but published through their own remotes.
