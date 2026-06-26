"""TapProxySync 端到端验证：临时配置 → 同步 → 验证入库+去重 → 清理。"""
import asyncio
import sqlite3
import uuid

DB = r"F:/req-gen/XUQIU-CREATE/backend/data/demand_tool.db"


def db():
    c = sqlite3.connect(DB, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=60000")
    return c


# 1. 插临时配置
con = db()
g = con.execute("select id,name from games where name like '%三角洲行动体验服%' limit 1").fetchone()
if g is None:
    g = con.execute("select id,name from games limit 1").fetchone()
game_id, game_name = g["id"], g["name"]
cfg_id = str(uuid.uuid4())
con.execute(
    "insert into platform_search_configs(id,game_id,platform,keywords,enabled,crawl_count,source_key) "
    "values(?,?,?,?,?,?,?)",
    (cfg_id, game_id, "taptap", "531928", 1, 10, "tap_proxy"),
)
con.close()
print(f"[1] 临时配置: taptap group=531928 -> {game_name} ({game_id})")


async def run_sync():
    from app.database import async_session
    from app.services.tap_proxy_sync import TapProxySyncService
    async with async_session() as session:
        return await TapProxySyncService(session).sync()


print("[2] sync1:", asyncio.run(run_sync()))

con = db()
cnt = con.execute("select count(*) from platform_contents where source_id like 'tap_proxy:%'").fetchone()[0]
print(f"[3] 入库 tap_proxy 内容: {cnt}")
for r in con.execute(
    "select title,url,view_count,like_count,published_at from platform_contents where source_id like 'tap_proxy:%' limit 5"
):
    print(f"    v{r['view_count']} l{r['like_count']} | {(r['title'] or '')[:36]} | {r['url']}")
con.close()

print("[4] sync2(去重):", asyncio.run(run_sync()))

# 5. 清理
con = db()
con.execute("PRAGMA foreign_keys=ON")
del_cnt = con.execute("delete from platform_contents where source_id like 'tap_proxy:%'").rowcount
con.execute("delete from platform_search_configs where id=?", (cfg_id,))
con.close()
print(f"[5] 清理: 删 {del_cnt} 条 tap_proxy 内容 + 临时配置")
