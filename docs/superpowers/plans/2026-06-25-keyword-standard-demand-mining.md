# 需求词标准驱动挖掘 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Excel 中 7 款重点游戏的 240 个专属需求词及 39 个通用词变成采集、雷达和需求分析共用的确定性标准。

**Architecture:** 使用版本化 JSON 保存业务词表，Python 词库模块负责加载、游戏隔离、固定别名和最长词优先匹配。雷达只接受标准词命中，模型仅总结已命中的标准方向；采集配置由游戏名与分级标准词生成。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy Async、unittest、React/TypeScript、openpyxl（仅生成词库快照）。

---

### Task 1: 版本化词库与匹配器

**Files:**
- Create: `backend/app/data/demand_keywords.json`
- Create: `backend/app/services/demand_keyword_rules.py`
- Create: `backend/scripts/export_demand_keywords.py`
- Create: `backend/tests/test_demand_keyword_rules.py`

- [ ] 写失败测试：断言加载 7 款重点游戏、240 个专属词和 39 个通用词；重点游戏隔离；非重点游戏仅通用词；固定别名归一。
- [ ] 运行 `python -m unittest tests.test_demand_keyword_rules -v`，确认模块不存在或断言失败。
- [ ] 从 Excel 导出版本化 JSON，并实现 `rules_for_game()`、`match_demand_keywords()`、`canonical_game_name()`。
- [ ] 实现通用表达固定扩展及游戏专属别名，采用规范化后的最长别名优先，不使用编辑距离。
- [ ] 运行词库测试并提交 `Add standard demand keyword library`。

### Task 2: 规则词驱动雷达分级

**Files:**
- Modify: `backend/app/services/radar.py`
- Modify: `backend/app/services/radar_runner.py`
- Modify: `backend/app/services/radar_model.py`
- Create: `backend/tests/test_keyword_radar.py`

- [ ] 写失败测试：一级首次重要；二级首次观察、第二条独立证据重要；三级近 7 天重要、明确节点紧急、旧内容不提醒；一文多词；跨游戏隔离。
- [ ] 运行 `python -m unittest tests.test_keyword_radar -v`，确认当前行为不符合规则。
- [ ] 在规则扫描中仅根据 `match_demand_keywords()` 生成标准需求线索，签名使用游戏 ID 与标准词。
- [ ] 将标准词、优先级、类别、命中别名和证据数写入评分/互动详情；重复内容不增加独立证据。
- [ ] 禁止模型 findings 创建未命中标准词的新线索；模型审阅仅处理已命中标准词内容。
- [ ] 运行雷达相关测试并提交 `Drive radar with standard demand keywords`。

### Task 3: 标准词驱动采集

**Files:**
- Modify: `backend/app/services/data_adapter.py`
- Create: `backend/tests/test_keyword_collection.py`

- [ ] 写失败测试：重点游戏搜索词来自当前游戏一级/二级/三级词与通用词；非重点游戏仅通用词；组合词包含游戏名；不复制关联其他游戏。
- [ ] 运行 `python -m unittest tests.test_keyword_collection -v`，确认当前探索仅使用游戏名称。
- [ ] 新增分级采集关键词生成函数：一级优先、二级低频、三级近 7 天高频，所有标准词与游戏名组合。
- [ ] 保留纯游戏名探索用于覆盖，但只有标准词命中内容进入雷达。
- [ ] 运行采集测试并提交 `Collect content by standard demand keywords`。

### Task 4: 展示与历史基线

**Files:**
- Modify: `backend/app/services/radar_runner.py`
- Modify: `frontend/src/components/RadarPanel.tsx`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/styles/index.css`

- [ ] 在历史回填中建立标准词概念基线，不提醒历史一级/二级词，仅允许最近 7 天三级热点提醒。
- [ ] 雷达卡片从 scores/engagement 展示标准词优先级、类别、命中表达和独立证据数。
- [ ] 运行前端 `npm run build` 和后端相关测试。
- [ ] 提交 `Show standard keyword evidence in radar`。

### Task 5: 全量验证

**Files:**
- No production changes expected.

- [ ] 运行 `python -m unittest discover -s tests -p 'test_*.py' -v`。
- [ ] 运行 `python -m compileall -q app`。
- [ ] 运行 `npm run build`。
- [ ] 运行 `git diff --check`，确认工作区干净。
- [ ] 检查 `deepseek-v4-pro` 仅做总结，不存在自由创建标准外需求的路径。

