#!/bin/bash

scriptDir=$(cd "$(dirname "$0")" && pwd)

# export PYTHONPATH=$scriptDir
# export VIRTUAL_ENV=$scriptDir/.venv

export DANGEROUSLY_OMIT_AUTH=true
npx @modelcontextprotocol/inspector uv run server.py