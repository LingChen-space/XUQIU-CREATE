"""Phase2: 清理体验服资格/福利 demand + 跑管线从版本/爆料雷达线索生成 demand。"""
import asyncio
import sqlite3
from collections import Counter
from datetime import date

from app.services.demand_keyword_rules import is_experience_server

DB = r"F:/req-gen/XUQIU-CREATE/backend/data/demand_tool.db"

con = sqlite3.connect(DB, timeout=60, isolation_level=None)
con.execute("PRAGMA busy_timeout=60000")
con.row_factory = sqlite3.Row
games = {r["id"]: r["name"] for r in con.execute("select id,name from games")}
xs = [gid for gid, n in games.items() if is_experience_server(n)]
ph = ",".join("?" * len(xs))

before = dict((r[0], r[1]) for r in con.execute(
    f"select tool_type,count(*) from demands where game_id in ({ph}) group by tool_type", xs))
print("清理前 体验服 demand 按type:", before)
deleted = con.execute(
    f"delete from demands where game_id in ({ph}) and tool_type='qualification'", xs).rowcount
print("删除 qualification(资格/福利) 体验服 demand:", deleted)
con.close()


async def main():
    from sqlalchemy import select
    from app.database import async_session
    from app.models.game import Game
    from app.services.llm_pipeline import LLMPipeline

    async with async_session() as session:
        all_games = (await session.execute(select(Game))).scalars().all()
        xs_ids = [g.id for g in all_games if is_experience_server(g.name)]
        print("体验服游戏数:", len(xs_ids))
        pipe = LLMPipeline(session)
        demands = await pipe.run_pipeline(xs_ids, date.today())
        print("生成 demand 数:", len(demands))
        for d in demands[:25]:
            print(f"  [{d.potential_score:.0f}] {d.tool_type} {d.title}")


asyncio.run(main())

con = sqlite3.connect(DB, timeout=60, isolation_level=None)
con.row_factory = sqlite3.Row
after = dict((r[0], r[1]) for r in con.execute(
    f"select tool_type,count(*) from demands where game_id in ({ph}) group by tool_type", xs))
print("清理+生成后 体验服 demand 按type:", after)
rows = con.execute(
    f"select title,tool_type,potential_score from demands where game_id in ({ph}) "
    f"order by potential_score desc limit 15", xs).fetchall()
print("体验服 demand 样本:")
for r in rows:
    print(f"  [{r['potential_score']:.0f}] {r['tool_type']:14s} {r['title']}")
con.close()
