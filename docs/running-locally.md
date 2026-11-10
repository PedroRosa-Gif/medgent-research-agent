# Running the local LLM (Ollama) with Docker

MedGent's default LLM provider is a **local Ollama** server, run as a Docker
container. The provided `docker-compose.yml` (at the repo root) starts the server
and **auto-pulls the model** so there is no manual setup step.

## Prerequisites

- **Docker Desktop** (Windows): install and start it. On Windows it runs on the
  WSL2 backend.
- **Disk & RAM**:
  - Default model `qwen2.5:7b` — ~4.7 GB download, comfortable with ~8 GB free RAM.
  - Lighter alternative `llama3.2:3b` — ~2 GB download, fine on low-RAM machines.
- For the smoke test only: the backend deps (`uv sync` in `backend/`).

## ⚠️ GPU vs CPU — read this first

The `docker-compose.yml` **reserves an NVIDIA GPU** for Ollama. This matters a lot:
a 7B model on CPU takes **minutes per step** (a full run can take ~10 minutes),
while on a GPU each generation is near-instant.

- **You have an NVIDIA GPU** (+ Docker Desktop with the WSL2 NVIDIA driver): it works
  out of the box. Verify Docker can see the GPU:
  ```bash
  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi
  ```
  After `docker compose up`, confirm the model is on the GPU (not CPU):
  ```bash
  docker compose exec ollama ollama ps   # PROCESSOR should read "100% GPU"
  ```
- **You do NOT have an NVIDIA GPU**: `docker compose up` will **fail** trying to
  reserve a device that isn't there. Until the planned `docker-compose.gpu.yml`
  override lands (see `roadmap.md`), comment out the `deploy:` block in
  `docker-compose.yml` to run on CPU — expect it to be slow, and consider the
  lighter `llama3.2:3b` model.

## 1. Start Ollama and pull the model

From the repo root:

```bash
docker compose up -d
```

This starts two services:

- `ollama` — the server, listening on `http://localhost:11434`.
- `ollama-init` — a one-shot container that waits for the server to be healthy,
  pulls the model, then exits.

> ⚠️ The first run **downloads several GB** and may take a while depending on your
> connection. It only happens once — the model is cached in a named Docker volume
> (`ollama_data`).

## 2. Watch the download progress

```bash
docker compose logs -f ollama-init
```

When `ollama-init` exits cleanly, the model is ready. (It's normal for this
container to show as `Exited (0)` afterward — it's a one-shot job.)

## 3. Verify the server and model

```bash
curl http://localhost:11434/api/tags
```

or:

```bash
docker compose exec ollama ollama list
```

You should see your model (e.g. `qwen2.5:7b`) listed.

## 4. Run the smoke test

A manual script exercises the adapter end-to-end (free-form + structured output).
Run it from the `backend/` directory so it uses the backend's virtualenv:

```bash
cd backend
uv run python ../scripts/smoke_ollama.py
```

Expected: it prints roughly `pong` for the first check and a small list of queries
for the structured check, ending with `✓ Ollama smoke test passed.` If it can't
connect, it prints a friendly hint telling you to bring the stack up.

## 5. Switch models

Pick a different model via the `OLLAMA_MODEL` env var — either inline:

```bash
OLLAMA_MODEL=llama3.2:3b docker compose up -d
```

or by creating a root `.env` (copy from `.env.example`):

```dotenv
OLLAMA_MODEL=llama3.2:3b
```

Make the app use the same model too, via `backend/.env` (`OLLAMA_MODEL=...`), so
the smoke test and the agent target the model you actually pulled.

## 6. Stop and clean up

Stop the containers (keeps the downloaded model):

```bash
docker compose down
```

Stop **and delete the model volume** (frees disk, but the model must be
re-downloaded next time):

```bash
docker compose down -v
```

> ⚠️ `down -v` removes the `ollama_data` volume. Only use it when you want to
> reclaim the disk space.

## Reusing an existing Ollama model store

If you already have models from another project, `docker-compose.yml` has commented
examples for pointing at an existing named volume (`external: true`) or bind-mounting
your host's `~/.ollama`. See the comments in that file.

---

## Running the full stack (API + UI)

The smoke test above only checks the LLM. To use MedGent end to end, run three
things. With Ollama already up (steps 1–3), open two more terminals:

**Backend API** (from `backend/`) — serves `http://localhost:8000`:

```bash
uv sync
./serve.ps1                 # Windows PowerShell wrapper (recommended)
# cross-platform equivalent:
#   PYTHONPATH=src uv run uvicorn medgent.adapters.driving.api.app:create_app --factory --port 8000
```

**Frontend** (from `frontend/`) — opens `http://localhost:5173`:

```bash
npm install
npm run dev
```

Then open the Vite URL, type a clinical topic, and hit Research. Vite proxies
`/research`, `/research/stream`, and `/health` to the API on port 8000, so the
browser talks same-origin (no CORS needed in dev).

### CLI instead of the UI

```bash
cd backend
./run.ps1 "efficacy of metformin for type 2 diabetes"
# cross-platform equivalent:
#   PYTHONPATH=src uv run python -m medgent "efficacy of metformin for type 2 diabetes"
```

It streams the agent's steps, prints the report, and saves it to
`backend/reports/<slug>.md`.

## Troubleshooting

- **`POST /research` / the CLI errors with "connection refused" to port 11434** —
  Ollama isn't running. Start Docker Desktop, then `docker compose up -d`.
- **`POST /research` times out in Insomnia/Postman** — expected: the sync endpoint
  blocks for the whole run. Use `GET /research/stream` (or raise the client timeout).
- **The run takes ~10 minutes** — Ollama is on CPU. See the GPU vs CPU section above
  (`ollama ps` should say `100% GPU`).
- **`python -m medgent` → `No module named 'medgent'` (Windows)** — CPython reads
  editable-install `.pth` files with the system code page, not UTF-8, so a home path
  with non-ASCII characters (e.g. `C:\Users\Usuário`) corrupts the path and breaks
  the import. Use the `run.ps1` / `serve.ps1` wrappers, which set `PYTHONPATH=src`
  and sidestep the `.pth` entirely. The manual fallback is to prefix any command
  with `$env:PYTHONPATH="src"` (PowerShell) or `PYTHONPATH=src` (bash). `pytest` is
  unaffected (it uses `pythonpath = ["src"]`).
