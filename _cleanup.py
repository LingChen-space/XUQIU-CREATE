"""清理跨游戏重复 url 的 content 副本。

同 url 多 game_id 的，保留：标题含某游戏名→该游戏(多个含则 priority 最高)；
都不含→priority 最高的副本游戏。其余 content 删除，并处理指向被删 content 的
clue.evidence_content_ids(移除失效 id；evidence 全空则删该 clue)。
用法: python _cleanup.py          # dry-run，只报告
      python _cleanup.py --apply   # 先在线备份，再执行删除
"""
import sqlite3, json, sys

DB = r"F:/req-gen/XUQIU-CREATE/backend/data/demand_tool.db"
APPLY = "--apply" in sys.argv
con = sqlite3.connect(DB, timeout=30)
con.execute("PRAGMA busy_timeout=30000")
con.row_factory = sqlite3.Row
out = []

if APPLY:
    dst = r"F:/req-gen/XUQIU-CREATE/backend/data/backups/demand_tool.before-cross-game-cleanup.db"
    bck = sqlite3.connect(dst)
    con.backup(bck)
    bck.close()
    out.append(f"[backup] -> {dst}")

games = {r["id"]: {"name": r["name"] or "", "pw": r["priority_weight"] or 0}
         for r in con.execute("select id, name, priority_weight from games")}

dup_urls = [r["url"] for r in con.execute(
    "select url from platform_contents where url is not null and url != '' "
    "group by url having count(distinct game_id) > 1")]
out.append(f"cross-game dup urls: {len(dup_urls)}")


def pick_keep(rows):
    title = rows[0]["title"] or ""
    gids = [r["game_id"] for r in rows]
    matched = [g for g in gids if games.get(g, {}).get("name") and games[g]["name"] in title]
    cands = matched if matched else gids
    cands.sort(key=lambda g: -games.get(g, {}).get("pw", 0))
    return cands[0], bool(matched)


to_delete = []
examples = []
for url in dup_urls:
    rows = list(con.execute("select id, game_id, title from platform_contents where url=?", (url,)))
    keep_gid, by_title = pick_keep(rows)
    for r in rows:
        if r["game_id"] != keep_gid:
            to_delete.append(r["id"])
    if len(examples) < 10:
        keep_name = games.get(keep_gid, {}).get("name", "?")
        all_names = [games.get(r["game_id"], {}).get("name", "?") for r in rows]
        examples.append(f"  keep={keep_name} (by_title={by_title}) title={(rows[0]['title'] or '')[:42]} from={all_names}")

out.append(f"content rows to delete: {len(to_delete)}")
out.append("keep decisions (sample 10):")
out.extend(examples)

del_set = set(to_delete)
clue_update, clue_delete = [], []
for cr in con.execute("select id, evidence_content_ids from radar_clues"):
    ev = json.loads(cr["evidence_content_ids"] or "[]")
    if not ev or not any(e in del_set for e in ev):
        continue
    new_ev = [e for e in ev if e not in del_set]
    if new_ev:
        clue_update.append((cr["id"], json.dumps(new_ev)))
    else:
        clue_delete.append(cr["id"])
out.append(f"clues to update evidence: {len(clue_update)}")
out.append(f"clues to delete (evidence all gone): {len(clue_delete)}")

if DRY := (not APPLY):
    out.append("\n[DRY RUN] no changes. run with --apply to execute (backs up first).")
else:
    con.execute("PRAGMA foreign_keys=ON")
    for i in range(0, len(to_delete), 500):
        chunk = to_delete[i:i + 500]
        ph = ",".join("?" * len(chunk))
        con.execute(f"delete from platform_contents where id in ({ph})", chunk)
    for cid, ev in clue_update:
        con.execute("update radar_clues set evidence_content_ids=? where id=?", (ev, cid))
    for cid in clue_delete:
        con.execute("delete from radar_clues where id=?", (cid,))
    con.commit()
    out.append(f"\n[APPLIED] deleted {len(to_delete)} content, updated {len(clue_update)} clues, deleted {len(clue_delete)} clues")

con.close()
open(r"F:/req-gen/XUQIU-CREATE/_cleanup_report.txt", "w", encoding="utf-8").write("\n".join(out))
print("dup_urls:", len(dup_urls), " del_content:", len(to_delete),
      " clue_update:", len(clue_update), " clue_delete:", len(clue_delete), " applied:", APPLY)
