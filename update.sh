#!/bin/bash

git fetch --all
git reset --hard origin/$(git rev-parse --abbrev-ref HEAD)
git clean -fd