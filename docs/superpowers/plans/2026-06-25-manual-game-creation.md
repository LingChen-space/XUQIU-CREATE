# 游戏仅手动新增 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 禁止所有运行期同步流程自动创建游戏，同时保留空库首次初始化和游戏管理手动新增能力。

**Architecture:** 外部同步只调用现有游戏匹配逻辑；匹配失败时保留原始记录并增加 `unmatched_games`，不写入正式内容池。删除自动建游戏方法及 `created_games` 状态字段，首次种子初始化和手动游戏 API 不变。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy Async、unittest、React、TypeScript。

---

### Task 1: 锁定外部同步不得创建游戏

**Files:**
- Modify: `backend/tests/test_external_monitor_sync.py`
- Modify: `backend/app/services/external_monitor_sync.py`

- [ ] **Step 1: 将自动建游戏测试改为禁止创建**

把原 `test_sync_creates_external_game_for_unconfigured_monitor_content` 改为：

```python
def test_sync_does_not_create_game_for_unconfigured_monitor_content(self):
    game_name = "新游戏"
    client = FakeTapKbClient(
        contents=[{
            "external_id": "hykb-new-game",
            "platform": KB_FORUM,
            "game_name": game_name,
            "title": f"《{game_name}》地图工具求推荐",
            "url": "https://bbs.3839.com/thread-new-game.htm",
            "raw_feed_type": "hykb",
        }],
        configs=[],
    )

    result = asyncio.run(run_sync(client))

    self.assertEqual(result["contents"]["inserted"], 0)
    self.assertEqual(result["contents"]["unmatched_games"], 1)
    self.assertNotIn(game_name, {game.name for game in asyncio.run(fetch_games())})
```

将标题推断测试改为同样断言不会创建游戏，并确认原始记录仍保留。

- [ ] **Step 2: 运行测试并确认按预期失败**

Run:

```powershell
python -m unittest tests.test_external_monitor_sync.ExternalMonitorSyncTest.test_sync_does_not_create_game_for_unconfigured_monitor_content -v
```

Expected: FAIL，当前实现仍会插入内容并创建游戏。

- [ ] **Step 3: 删除运行期自动建游戏分支**

在 `_sync_contents` 中改为：

```python
game = self._match_game(game_name, title, body, games_by_name, games)
if game is None:
    stats["unmatched_games"] += 1
    continue
```

删除 `_ensure_external_game` 方法，以及仅供该方法使用的 `GameGenre`、`GameStatus`、`default_priority_weight` 等导入。

- [ ] **Step 4: 运行外部同步测试**

Run:

```powershell
python -m unittest tests.test_external_monitor_sync -v
```

Expected: 全部 PASS。

- [ ] **Step 5: 提交外部同步行为修改**

```powershell
git add backend/tests/test_external_monitor_sync.py backend/app/services/external_monitor_sync.py
git commit -m "Disable automatic game creation during sync"
```

### Task 2: 清理废弃状态字段与说明

**Files:**
- Modify: `backend/app/services/external_monitor_sync.py`
- Modify: `backend/app/services/scheduler.py`
- Modify: `frontend/src/types/index.ts`
- Test: `backend/tests/test_external_monitor_sync.py`

- [ ] **Step 1: 添加状态结构回归断言**

在未匹配游戏测试中增加：

```python
self.assertNotIn("created_games", result["contents"])
```

- [ ] **Step 2: 运行测试并确认失败**

Run:

```powershell
python -m unittest tests.test_external_monitor_sync.ExternalMonitorSyncTest.test_sync_does_not_create_game_for_unconfigured_monitor_content -v
```

Expected: FAIL，因为返回结构仍含 `created_games`。

- [ ] **Step 3: 删除废弃字段和注释**

从 `_empty_content_stats()` 删除：

```python
"created_games": 0,
```

从 `TapKbSyncContentStats` 删除：

```typescript
created_games?: number
```

把每日管线注释改为：

```python
# 外部后台内容不依赖本地搜索词配置，仅匹配游戏管理中已有游戏。
```

- [ ] **Step 4: 验证后端测试与前端构建**

Run:

```powershell
python -m unittest tests.test_external_monitor_sync -v
npm run build
```

Expected: 测试和构建全部通过。

- [ ] **Step 5: 提交状态结构清理**

```powershell
git add backend/app/services/external_monitor_sync.py backend/app/services/scheduler.py backend/tests/test_external_monitor_sync.py frontend/src/types/index.ts
git commit -m "Remove automatic game creation status"
```

### Task 3: 验证保留的新增入口

**Files:**
- Modify: `backend/tests/test_external_monitor_sync.py`
- Inspect: `backend/app/main.py`
- Inspect: `backend/app/services/data_adapter.py`
- Inspect: `backend/app/api/games.py`

- [ ] **Step 1: 增加首次空库种子测试**

新增测试，空库调用 `DataAdapter.seed_games()` 后断言创建默认游戏；再次调用断言不重复创建：

```python
async def scenario():
    async with Session() as session:
        adapter = DataAdapter(session)
        first = await adapter.seed_games()
        second = await adapter.seed_games()
        count = (await session.execute(select(func.count()).select_from(Game))).scalar_one()
        return len(first), len(second), count

first, second, count = asyncio.run(scenario())
self.assertGreater(first, 0)
self.assertEqual(second, 0)
self.assertEqual(count, first)
```

- [ ] **Step 2: 增加手动 API 新增测试**

直接调用 `create_game`，确认返回游戏且数据库中存在：

```python
result = await create_game(
    GameCreate(name="手动新增测试游戏", genre="其他", status="运营中"),
    db=session,
)
self.assertEqual(result.name, "手动新增测试游戏")
```

- [ ] **Step 3: 运行新增测试**

Run:

```powershell
python -m unittest tests.test_external_monitor_sync tests.test_games -v
```

Expected: PASS；若项目没有 `test_games.py`，在新文件中实现该测试。

- [ ] **Step 4: 提交入口回归测试**

```powershell
git add backend/tests/test_external_monitor_sync.py backend/tests/test_games.py
git commit -m "Test manual and initial game creation"
```

### Task 4: 全量验收

**Files:**
- No production changes expected.

- [ ] **Step 1: 后端全量测试**

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
```

Expected: 全部 PASS。

- [ ] **Step 2: 后端编译检查**

```powershell
python -m compileall -q app
```

Expected: exit code 0。

- [ ] **Step 3: 前端生产构建**

```powershell
npm run build
```

Expected: TypeScript 和 Vite 构建成功。

- [ ] **Step 4: 检查残留自动建游戏代码**

```powershell
rg -n "created_games|_ensure_external_game|自动创建新游戏|同步自动创建" backend/app frontend/src
```

Expected: 无运行期自动创建相关命中。

- [ ] **Step 5: 检查工作区**

```powershell
git diff --check
git status --short
```

Expected: 无未提交改动。

