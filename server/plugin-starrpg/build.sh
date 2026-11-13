#!/bin/zsh
# StarRPG 빌드: ./build.sh  → ../plugins/StarRPG.jar
set -e
cd "$(dirname "$0")"
ROOT=..
CP=$(find $ROOT/libraries -name "*.jar" | tr '\n' ':')$ROOT/plugins/VaultUnlocked-2.20.3.jar:$ROOT/plugins/bettermodel-3.6.0-paper.jar:$ROOT/plugins/PlaceholderAPI-2.12.3.jar
rm -rf out && mkdir -p out
$HOME/Library/Java/JavaVirtualMachines/corretto-25/Contents/Home/bin/javac -encoding UTF-8 --release 21 -nowarn -cp "$CP" -d out $(find src -name "*.java")
cp resources/plugin.yml out/
(cd out && jar cf ../StarRPG.jar .)
cp StarRPG.jar $ROOT/plugins/StarRPG.jar
echo "빌드 완료: plugins/StarRPG.jar"
