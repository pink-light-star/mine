#!/bin/zsh
# 마인크래프트 서버 실행 (메모리 2~5GB, CPU 6코어까지 · 낮은 우선순위로 열·배터리 절약)
cd "$(dirname "$0")"
exec nice -n 10 /Users/test/Library/Java/JavaVirtualMachines/corretto-25/Contents/Home/bin/java -Xms2G -Xmx5G -XX:ActiveProcessorCount=6 -XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 \
  -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC \
  -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M \
  -XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 \
  -XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 \
  -XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 -XX:+PerfDisableSharedMem \
  -XX:MaxTenuringThreshold=1 -jar paper.jar --nogui
