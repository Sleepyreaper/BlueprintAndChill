#!/usr/bin/env bash
set -euo pipefail

uvicorn blueprintandchill.main:app --host 0.0.0.0 --port 8000 --reload
