#!/usr/bin/env bash
cd ~/Upload-Assistant
source venv/bin/activate
exec python3 upload.py "$@"
