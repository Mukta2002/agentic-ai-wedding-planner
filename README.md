# Agentic AI Wedding Planner

An intelligent AI-powered wedding planning system that generates:

- Wedding branding (logo, theme, style guide)
- Invitation designs
- Cinematic teaser video prompts
- Hotel recommendations with budget breakdown
- Structured, budget-aware wedding planning state

## Features
- Agentic pipeline (updates propagate automatically)
- Gemini / Imagen / Veo integration
- Budget-aware planning
- CLI entry point via `python app/main.py`

## Local Setup

1) Create and activate a virtual environment

   Windows (PowerShell):
   - `python -m venv .venv`
   - `.\\.venv\\Scripts\\Activate.ps1`

   macOS/Linux (bash/zsh):
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`

2) Install dependencies

   - `pip install -r requirements.txt`

3) Set up environment variables

   - Copy `.env.example` to `.env`:
     - Windows: `copy .env.example .env`
     - macOS/Linux: `cp .env.example .env`
   - Edit `.env` and set your credentials:
     - `GEMINI_API_KEY=your_gemini_api_key_here`

   Notes:
   - You may alternatively set `GOOGLE_API_KEY` or `GOOGLE_APIKEY` for compatibility.
   - `.env` is ignored by Git and must never be committed.

4) Run the app

   - `python app/main.py`

## Environment Variables

- `GEMINI_API_KEY` (required)
  - API key for Google GenAI (Gemini). The app also accepts `GOOGLE_API_KEY` or `GOOGLE_APIKEY`.
- `ENV` (optional)
  - Local environment label, e.g., `dev`.

## Security Notes

- No secrets are hardcoded in the codebase.
- Secrets must be provided via environment variables and optionally a local `.env` file for development.
- The `.gitignore` includes `.env` to prevent accidental commits of credentials.
- If you previously committed a real key, rotate/revoke it in your provider dashboard and scrub it from Git history before pushing public.

