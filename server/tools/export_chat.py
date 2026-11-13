#!/usr/bin/env python3
"""Claude Code 대화 기록(jsonl) → 사람이 읽는 Markdown.
   사용자 말과 Claude 답만 남기고 도구 출력·시스템 메시지는 뺀다. 이메일·토큰은 가린다."""
import json, re, sys, datetime

src, out = sys.argv[1], sys.argv[2]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TOKEN = re.compile(r"(gh[opsu]_[A-Za-z0-9]{10,}|sk-[A-Za-z0-9]{10,})")
TAGS = re.compile(r"<(system-reminder|command-[a-z]+|local-command-[a-z]+|antml:[a-z_]+|task-notification|ide_[a-z_]+)[^>]*>.*?</\1>", re.S)

def clean(t):
    t = TAGS.sub("", t)
    t = EMAIL.sub("(이메일 가림)", t)
    t = TOKEN.sub("(토큰 가림)", t)
    return t.strip()

seen, rows = set(), []
for line in open(src, encoding="utf-8"):
    try: d = json.loads(line)
    except Exception: continue
    if d.get("type") not in ("user", "assistant") or d.get("isMeta") or d.get("isCompactSummary") or d.get("isSidechain"):
        continue
    u = d.get("uuid")
    if u in seen: continue
    seen.add(u)
    msg = d.get("message", {})
    c = msg.get("content")
    parts = []
    if isinstance(c, str):
        parts.append(c)
    elif isinstance(c, list):
        for b in c:
            if b.get("type") == "text": parts.append(b.get("text", ""))
            elif b.get("type") == "image" and d["type"] == "user": parts.append("[이미지 첨부]")
            elif b.get("type") == "tool_result": parts = None; break
    if not parts: continue
    text = clean("\n".join(parts))
    if not text or text.startswith("This session is being continued") or text.startswith("[Request interrupted"):
        continue
    if "<task-notification>" in text: continue
    rows.append((d.get("timestamp", ""), d["type"], text))

with open(out, "w", encoding="utf-8") as f:
    f.write("# 별빛 서버 제작 대화 기록\n\n사용자와 Claude가 주고받은 말만 시간 순서대로 모았어요. 도구 실행 결과와 시스템 메시지는 뺐고, 이메일·토큰 같은 개인정보는 가렸어요.\n\n")
    day = None
    for ts, who, text in rows:
        try: t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(datetime.timezone(datetime.timedelta(hours=9)))
        except Exception: t = None
        if t and t.date() != day:
            day = t.date(); f.write(f"\n## {day.isoformat()}\n\n")
        hm = t.strftime("%H:%M") if t else ""
        if who == "user":
            f.write(f"### 🧑 사용자 · {hm}\n\n" + "\n".join("> " + l if l else ">" for l in text.splitlines()) + "\n\n")
        else:
            f.write(f"**Claude · {hm}**\n\n{text}\n\n")
print(len(rows), "개 메시지")
