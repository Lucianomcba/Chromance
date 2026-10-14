#!/bin/bash
set -e

cd "$(dirname "$0")"
make run_tests "$@"
