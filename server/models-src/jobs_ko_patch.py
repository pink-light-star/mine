#!/usr/bin/env python3
"""Jobs Reborn 한국어 메시지 보강: plugins/Jobs/locale/messages_ko.yml 에서 영어로 남은 문구를 한글로 바꾼다."""
import os, re

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "Jobs", "locale", "messages_ko.yml")

T = {
    "general.info.join": "'&e클릭해서 직업 가입'",
    "general.info.leave": "'&c클릭해서 직업 탈퇴'",
    "general.error.job": "'&c선택한 직업이 없거나 가입하지 않은 직업입니다'",
    "command.limit.output.moneytime": "'&e돈 한도 초기화까지 남은 시간: &2%time%'",
    "command.limit.output.moneyLimit": "'&e돈 한도: &2%current%&e/&2%total%'",
    "command.limit.output.exptime": "'&e경험치 한도 초기화까지 남은 시간: &2%time%'",
    "command.limit.output.expLimit": "'&e경험치 한도: &2%current%&e/&2%total%'",
    "command.limit.output.pointstime": "'&e포인트 한도 초기화까지 남은 시간: &2%time%'",
    "command.limit.output.pointsLimit": "'&e포인트 한도: &2%current%&e/&2%total%'",
    "command.limit.output.reachedmoneylimit": "'&4정해진 시간 동안 벌 수 있는 돈 한도에 도달했어요!'",
    "command.limit.output.reachedmoneylimit2": "'&e&2/jobs limit &e로 한도를 확인할 수 있어요'",
    "command.limit.output.reachedmoneylimit3": "'&e이제 버는 돈이 점점 줄어들어요... 그래도 조금은 벌 수 있어요'",
    "command.limit.output.reachedexplimit": "'&4정해진 시간 동안 얻을 수 있는 경험치 한도에 도달했어요!'",
    "command.limit.output.reachedexplimit2": "'&e&2/jobs limit &e로 한도를 확인할 수 있어요'",
    "command.limit.output.reachedpointslimit": "'&4정해진 시간 동안 얻을 수 있는 포인트 한도에 도달했어요!'",
    "command.limit.output.reachedpointslimit2": "'&e&2/jobs limit &e로 한도를 확인할 수 있어요'",
    "command.limit.output.notenabled": "'&e돈 한도가 꺼져 있어요'",
    "command.stats.error.nojob": "'&c먼저 직업에 가입하세요. (&e/jobs browse&c)'",
    "command.stats.output.Level": "'&f%jobname% &7레벨 &f%joblevel%&7: &f%jobxp%&7/&f%jobmaxxp%&7 경험치'",
    "command.stats.output.maxLevel": "'    &2최대 &7레벨 &f%joblevel% &7(&f%jobname%&7)'",
    "command.stats.bossBarOutput": "'%jobname% Lv.%joblevel%: %jobxp%/%jobmaxxp% 경험치%gain%'",
    "command.archive.error.nojob": "'&c저장된 직업이 없어요.'",
    "command.info.help.title": "'&2*** &e직업&2 ***'",
    "command.info.help.penalty": "'&e이 직업은 하는 사람이 너무 많아서 &c[penalty]% &e감소가 있어요.'",
    "command.info.help.bonus": "'&e이 직업은 하는 사람이 적어서 &2[bonus]% &e보너스가 있어요.'",
    "command.info.help.actions": "'&e돈을 버는 행동: &f%actions%'",
    "command.info.help.max": "' - &e최대 레벨:&f '",
    "command.info.help.newMax": "' &e최대 레벨: &f[max]'",
    "command.info.help.levelRange": "' &a(&e%levelFrom% &a~ &e%levelUntil% &a레벨)'",
    "command.info.help.levelFrom": "' &a(&e%levelFrom% &a레벨부터)'",
    "command.info.help.levelUntil": "' &a(&e%levelUntil% &a레벨까지)'",
    "command.info.help.points": "' &6%points%점'",
    "command.info.gui.pickjob": "'&e직업을 골라주세요!'",
    "command.info.gui.jobinfo": "'&e[jobname] 정보'",
    "command.info.gui.actions": "'&e돈을 버는 행동:'",
    "command.info.gui.leftClick": "'&e좌클릭: 자세히 보기'",
    "command.info.gui.middleClick": "'&e휠 클릭: 이 직업 탈퇴'",
    "command.info.gui.qClick": "'&eQ 키: 이 직업 탈퇴'",
    "command.info.gui.rightClick": "'&a우클릭: 이 직업 가입'",
    "command.info.gui.leftSlots": "'&e남은 자리:&f '",
    "command.info.gui.working": "'&2&n이미 하고 있는 직업'",
    "command.info.gui.cantJoin": "'&c이 직업에는 가입할 수 없어요.'",
    "command.info.gui.max": "'&e최대 레벨:&f '",
    "command.join.error.alreadyin": "'&c이미 %jobname% 직업이에요.'",
    "command.join.error.fullslots": "'&c%jobname% 직업에 남은 자리가 없어요.'",
    "command.join.error.maxjobs": "'&c가입할 수 있는 직업 수를 넘었어요.'",
    "command.join.error.rejoin": "'&c아직 다시 가입할 수 없어요. [time] 기다려 주세요'",
    "command.join.rejoin": "'&a클릭해서 다시 가입: '",
    "command.join.success": "'&a%jobname% 직업에 가입했어요!'",
    "command.join.confirm": "'&2클릭하면 &7[jobname] &2직업에 가입해요.'",
    "command.leave.success": "'&e%jobname% 직업을 그만뒀어요.'",
    "command.leave.confirmationNeed": "'&c정말&e [jobname]&c 직업을 그만둘까요? &6[time]초 &c안에 명령어를 한 번 더 입력하면 확정돼요!'",
    "command.leaveall.error.nojobs": "'&c그만둘 직업이 없어요!'",
    "command.leaveall.success": "'&e모든 직업을 그만뒀어요.'",
    "command.leaveall.confirmationNeed": "'&c정말 모든 직업을 그만둘까요? &6[time]초 &c안에 명령어를 한 번 더 입력하면 확정돼요!'",
    "command.browse.help.info": "'가입할 수 있는 직업 목록'",
    "command.browse.error.nojobs": "'&c가입할 수 있는 직업이 없어요.'",
    "command.browse.output.header": "'&e가입할 수 있는 직업:'",
    "command.browse.output.footer": "'&7자세한 정보: &e/jobs info [직업이름]'",
    "command.browse.output.totalWorkers": "' &7하는 사람: &e[amount]명'",
    "command.browse.output.penalty": "' &4감소: &c[amount]%'",
    "command.browse.output.bonus": "' &2보너스: &a[amount]%'",
    "command.browse.output.newHeader": "'&2========== 가입 가능한 직업 [amount]개 =========='",
    "command.browse.output.console.newHeader": "'&2========== 가입 가능한 직업 [amount]개 =========='",
    "command.browse.output.console.totalWorkers": "' &7하는 사람: &e[amount]명'",
    "command.browse.output.console.penalty": "' &4감소: &c[amount]%'",
    "command.browse.output.console.bonus": "' &2보너스: &a[amount]%'",
    "command.browse.output.console.newMax": "' &e최대 레벨: &f[max]'",
    "command.browse.output.newMax": "' &e최대 레벨: &f[max]'",
    "command.browse.output.click": "'&b직업을 클릭하면 자세한 정보를 볼 수 있어요!'",
    "command.browse.output.detailed": "'&b클릭해서 돈 버는 행동 자세히 보기'",
    "command.browse.output.chooseJob": "'&7&n&o이 직업 선택'",
    "command.browse.output.chooseJobHover": "'&7클릭하면 이 직업에 가입해요'",
    "command.quests.error.noquests": "'&c퀘스트가 없어요'",
    "command.quests.status.changed": "'&2퀘스트 상태가 바뀌었어요:&r %status%'",
    "command.quests.status.started": "'&a진행 중'",
    "command.quests.status.stopped": "'&c멈춤'",
    "command.quests.output.completed": "'&2      !완료!&r      '",
    "command.quests.output.skip": "'&7클릭해서 이 퀘스트 넘기기'",
    "command.quests.output.skips": "'&7남은 넘기기: &f[skips]'",
    "command.quests.output.hover": "\"&f[jobName] \\n[desc] \\n&7새 퀘스트까지: [time]\"",
    "command.top.error.nojob": "'&c그런 이름의 직업이 없어요.'",
}

ACTIONS = {
    "break": ("블록 캐기", "블록을 캐도 돈을 받지 않아요."), "striplogs": ("나무 껍질 벗기기", "나무 껍질을 벗겨도 돈을 받지 않아요."),
    "tntbreak": ("TNT로 부수기", "TNT로 부숴도 돈을 받지 않아요."), "place": ("블록 놓기", "블록을 놓아도 돈을 받지 않아요."),
    "kill": ("몹 사냥", "몹을 잡아도 돈을 받지 않아요."), "mmkill": ("커스텀 몹 사냥", "커스텀 몹을 잡아도 돈을 받지 않아요."),
    "fish": ("낚시", "낚시로는 돈을 받지 않아요."), "craft": ("제작", "제작으로는 돈을 받지 않아요."),
    "vtrade": ("주민 거래", "주민과 거래해도 돈을 받지 않아요."), "smelt": ("굽기(화로)", "화로로 구워도 돈을 받지 않아요."),
    "brew": ("양조", "양조로는 돈을 받지 않아요."), "enchant": ("마법부여", "마법부여로는 돈을 받지 않아요."),
    "repair": ("수리", "수리로는 돈을 받지 않아요."), "breed": ("번식", "동물을 번식시켜도 돈을 받지 않아요."),
    "tame": ("길들이기", "동물을 길들여도 돈을 받지 않아요."), "dye": ("염색", "염색으로는 돈을 받지 않아요."),
    "shear": ("양털 깎기", "양털을 깎아도 돈을 받지 않아요."), "milk": ("우유 짜기", "우유를 짜도 돈을 받지 않아요."),
    "explore": ("탐험", "탐험으로는 돈을 받지 않아요."), "eat": ("음식 먹기", "음식을 먹어도 돈을 받지 않아요."),
    "collect": ("수확", "수확으로는 돈을 받지 않아요."), "bake": ("요리", "요리로는 돈을 받지 않아요."),
    "bucket": ("양동이 사용", "양동이를 써도 돈을 받지 않아요."), "brush": ("솔질(고고학)", "솔질로는 돈을 받지 않아요."),
    "vax": ("밀랍 칠하기", "밀랍을 칠해도 돈을 받지 않아요."), "customkill": ("플레이어 처치", "플레이어를 잡아도 돈을 받지 않아요."),
}
for k, (name, none) in ACTIONS.items():
    T[f"command.info.output.{k}.info"] = f"'&e{name}'"
    T[f"command.info.output.{k}.none"] = f"'&7%jobname%: {none}'"

lines = open(P, encoding="utf-8").read().split("\n")
out, stack, i, changed = [], [], 0, 0
while i < len(lines):
    l = lines[i]
    m = re.match(r"^(\s*)([^:#\s][^:]*):(\s*)(.*)$", l)
    if m:
        ind = len(m.group(1))
        while stack and stack[-1][0] >= ind:
            stack.pop()
        stack.append((ind, m.group(2)))
        path = ".".join(k for _, k in stack)
        if path in T and m.group(4):
            out.append(f"{m.group(1)}{m.group(2)}: {T[path]}")
            changed += 1
            i += 1
            # 여러 줄로 이어진 값의 나머지 줄 제거
            while i < len(lines) and lines[i].strip() and not re.match(r"^\s*[^:#\s][^:]*:", lines[i]) \
                    and len(lines[i]) - len(lines[i].lstrip()) > ind:
                i += 1
            continue
    out.append(l)
    i += 1
open(P, "w", encoding="utf-8").write("\n".join(out))
print(f"한글로 바꾼 문구: {changed}개")
