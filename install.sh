#!/usr/bin/bash
version=0.3.4
poetry build
sudo pip install --force-reinstall dist/radiacode-${version}-py3-none-any.whl
