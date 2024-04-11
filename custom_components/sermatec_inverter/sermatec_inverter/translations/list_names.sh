#!/bin/bash

grep "name" protocol-en.json | sed 's/^[ \t]*"name": //' | sed 's/,$//' | sort | uniq | awk '{print $0 ";" $0}'