#!/bin/sh
#
# 1. Run the tests with `tox` (this will set up all the tox envs).
# 2. ./run_benchmarks.sh <env-name> | tee results-<env-name>.out

NAME="$1"
PYTHON="./.tox/$NAME/bin/python"
BENCH_DIR="bench_build/$1"
BENCH_BIN_DIR="$BENCH_DIR/bin"
mkdir -p "bench_build"

rm -rf "$BENCH_DIR"
cp -R "examples/bench" "$BENCH_DIR"

case "$NAME" in
  py32|py33)
    2to3 -w --no-diffs "$BENCH_DIR"
    ;;
esac

echo "-- basic --"
"$PYTHON" "$BENCH_DIR/basic.py" 
echo

echo "-- bigtable --"
"$PYTHON" "$BENCH_DIR/bigtable.py"
echo

echo "-- xpath --"
"$PYTHON" "$BENCH_DIR/xpath.py"
echo
