#!/bin/zsh
set -eu
cd "$(dirname "$0")/demo"
exec ./start-demo.command "$@"
