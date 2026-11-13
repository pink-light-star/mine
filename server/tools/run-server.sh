#!/bin/zsh
# launchd(자동 실행)가 부르는 서버 실행 스크립트.
# 콘솔 명령은 console.in 에 한 줄씩 쓰면 서버로 들어간다:  echo "say 안녕" >> console.in
cd /Users/test/mincreft
if pgrep -f "paper.jar --nogui" >/dev/null; then
  echo "이미 서버가 실행 중이라 새로 켜지 않아요." >&2
  exit 0
fi
[ -f server.out ] && mv -f server.out server-prev.out
: > console.in
trap 'pkill -P $$ 2>/dev/null' EXIT
./start.sh < <(tail -n0 -F console.in) > server.out 2>&1
