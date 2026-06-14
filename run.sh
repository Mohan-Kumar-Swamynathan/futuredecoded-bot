#!/bin/bash
set -e
cd "$(dirname "$0")"
export PYTHONPATH=src
python -m futuredecoded.main "$@"
