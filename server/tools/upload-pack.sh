#!/bin/zsh
# 리소스팩(BetterModel build.zip)을 catbox.moe에 올리고 StarRPG 설정에 주소를 넣는다.
# 모델을 고친 뒤(/bm reload 후) 다시 실행하세요. 외부 접속자는 새 주소의 팩을 받습니다.
set -e
cd "$(dirname "$0")"
ZIP=plugins/BetterModel/build.zip
[ -f plugins/StarRPG/pack-merged.zip ] && ZIP=plugins/StarRPG/pack-merged.zip   # 무기 모델을 합친 팩
CFG=plugins/StarRPG/config.yml
[ -f "$ZIP" ] || { echo "팩 파일이 없습니다: $ZIP"; exit 1; }
# 사용법: ./upload-pack.sh          → catbox.moe
#         ./upload-pack.sh 0x0      → 0x0.st (catbox가 고장일 때)
HOST=${1:-catbox}
if [ "$HOST" = "0x0" ]; then
  URL=$(curl -s -A "starserver-pack-uploader/1.0" -F "file=@$ZIP;filename=starserver-pack.zip" https://0x0.st | tr -d '[:space:]')
  case "$URL" in https://0x0.st/*.zip) ;; *) echo "업로드 실패: $URL"; exit 1;; esac
else
  URL=$(curl -s -F "reqtype=fileupload" -F "fileToUpload=@$ZIP;filename=starserver-pack.zip" https://catbox.moe/user/api.php)
  case "$URL" in https://files.catbox.moe/*.zip) ;; *) echo "업로드 실패: $URL"; exit 1;; esac
fi
sleep 3
# 올라간 파일이 로컬 파일과 같은지 확인 (해시가 다르면 클라이언트가 팩을 거부함)
L=$(shasum -a 1 "$ZIP" | awk '{print $1}')
R=$(curl -sL "$URL" | shasum -a 1 | awk '{print $1}')
[ "$L" = "$R" ] || { echo "업로드된 파일 해시가 다릅니다 ($L vs $R)"; exit 1; }
sed -i '' "s#^  public-url: .*#  public-url: '$URL'#" "$CFG"
echo "업로드 완료: $URL"
echo "$(date '+%Y-%m-%d %H:%M') $URL" >> tools/pack-uploads.log
