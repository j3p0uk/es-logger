#!/bin/bash -xeu

# Copyright (c) 2018 Cisco Systems, Inc.
# All rights reserved.

export PATH=${PATH}:~/.local/bin
pip install -q --user -r test-requirements.txt

$HOME/.local/bin/tox --workdir /tmp
