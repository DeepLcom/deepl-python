#!/usr/bin/env bash

# Usage: ./license_checker.sh source_code_pattern
# Example: ./license_checker.sh '*.py'
# This will search all .py files, ignoring anything not tracked in your git tree

git ls-files -z $1 | xargs -0 -I{} sh -c 'RES=$(head -n 3 "{}" | grep "Copyright 20[0-9][0-9] DeepL SE (https://www.deepl.com)"); if [ ! "${RES}" ] ; then echo "Lacking copyright header in" "{}" ; fi'
