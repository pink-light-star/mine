#!/bin/zsh
# 더블클릭하면 별빛 서버를 켭니다.
#  1) 외부 접속용 playit 프로그램을 백그라운드로 켜고
#  2) 마인크래프트 서버를 이 창에서 실행합니다. (이 창에 명령어 입력 가능)
# 끄려면 이 창에 stop 을 입력하세요. 창을 그냥 닫으면 저장이 안 될 수 있어요.
cd "$(dirname "$0")"

if pgrep -f "paper.jar" >/dev/null; then
  echo "서버가 이미 켜져 있어요. (두 번 켜면 오류가 나요)"
  echo
  read -k 1 "?아무 키나 누르면 창이 닫혀요..."
  exit 0
fi

# playit (다른 와이파이 친구 접속용)
PLAYIT=tools/playit/playit-macos-universal/playitd
if [ -x "$PLAYIT" ] && [ -f tools/playit/playit.secret ]; then
  if pgrep -f "playitd --secret-path" >/dev/null; then
    echo "playit: 이미 켜져 있어요."
  else
    nohup "$PLAYIT" --secret-path tools/playit/playit.secret \
      --socket-path "$PWD/tools/playit/playitd.sock" -l "$PWD/tools/playit/playitd.log" >/dev/null 2>&1 &
    echo "playit: 켰어요. (외부 주소: impairment-unhinge.tun.ply.gg)"
  fi
else
  echo "playit: 설정이 없어서 건너뛰어요. (같은 와이파이에서만 접속 가능)"
fi

echo "마인크래프트 서버를 켜는 중... (30초쯤 걸려요)"
echo "끌 때는 이 창에 stop 을 입력하세요."
echo "--------------------------------------------------"
./start.sh
echo
echo "서버가 꺼졌어요."
read -k 1 "?아무 키나 누르면 창이 닫혀요..."
