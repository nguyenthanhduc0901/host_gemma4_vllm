#!/usr/bin/env bash
set -euo pipefail

echo "== uname =="
uname -a

echo
echo "== lscpu =="
lscpu

echo
echo "== memory =="
free -h

echo
echo "== disk =="
df -h .

echo
echo "== gpu =="
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
else
  echo "nvidia-smi not found"
fi