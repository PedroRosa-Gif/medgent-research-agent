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
