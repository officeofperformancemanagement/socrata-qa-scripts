#!/bin/sh -e

wget https://github.com/officeofperformancemanagement/chattadata-exports/archive/refs/heads/main.zip -O chattadata-exports.zip

unzip -j -o chattadata-exports.zip "chattadata-exports-*/data/*" -d ./data/

cd ./data

unzip -j "*.zip"

rm *.zip

cd ..

rm chattadata-exports.zip
