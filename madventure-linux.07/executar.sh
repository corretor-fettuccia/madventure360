#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"
if ! python3 -c 'import tkinter, PIL, cv2, numpy' 2>/dev/null; then
  echo 'Dependências ausentes. Instale tkinter e as bibliotecas Python:'
  echo 'sudo apt install python3-tk python3-venv'
  echo 'python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'
  if [[ -x .venv/bin/python ]]; then exec .venv/bin/python main.py; fi
  exit 1
fi
exec python3 main.py
