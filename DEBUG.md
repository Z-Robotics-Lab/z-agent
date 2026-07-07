# DEBUG — go2w REPL 2026-07-06 实测:相对移动 unmatched + navigate "not a skill" 自相矛盾

## OBSERVE
- 复现路径:`zeno --world go2w`,VGG decompose 路径。
- 错误 1(原文):`no strategy matched for 'unmatched' (executor_type='fallback'; valid: ['explore','navigate','pick'])` — 指令 "往前走几米"。
- 错误 2(原文):`strategy 'navigate' is not a skill in this world (valid: ['explore','navigate','pick'])` — 同回合第二步;valid 列表自己就包含 navigate。
- go2w 世界仅有绝对坐标 go2w_navigate(x,y);无相对移动技能。

## HYPOTHESIZE
| # | hypothesis | category | evidence |
|---|-----------|----------|----------|
| H1 | go2w 的部分 DecomposeVocab 经 as_kwargs() 把 strategies=frozenset()(非 None)注入 GoalDecomposer,把 KNOWN_STRATEGIES 与 prompt 策略清单清空 → 模型只能编 bare 名,全部被 clear → invalid | config/seam | worlds/base.py as_kwargs 无条件传全字段;goal_decomposer.__init__ 用 `is not None` 判定 |
| H2 | "往前走几米" 在关键词梯子(walk/forward/前进)与 registry alias(走到/导航/去…)都不命中 → fallback unmatched | missing route | strategy_selector.py 梯子关键词;go2w skill aliases |
| H3 | 报错 valid 列表来自 executor._valid_strategy_set()(registry 裸名),而验证接受的是 `<name>_skill` 后缀名 → 两个命名空间不一致,产生自相矛盾报错并在 replan 时反向教坏模型 | naming split-brain | goal_executor._invalid_strategy_error vs goal_decomposer KNOWN_STRATEGIES 推导 |
| H4 | navigate 技能签名 execute(context=None, **kw) 不符合内核 skill.execute(params, context) 约定 | latent bug | goal_executor._execute_skill:1140 与 skill_wrapper:191 均为双位置参数 |

## EXPERIMENT
- H1:离线构造 go2w vocab + GoalDecomposer(带 registry)→ KNOWN_STRATEGIES == [],prompt 的 KNOWN_STRATEGIES/VERIFY_FUNCTIONS/Example 块全空。→ H1 CONFIRMED
- H2:阅读 selector 梯子 + SkillRegistry.match(前缀匹配);"往前走几米" 无任何命中。→ H2 CONFIRMED
- H3:selector cleared 路由 valid_strategies=_registered_skill_names()=裸名 {explore,navigate,pick};decomposer 只认 *_skill(且此处为空集)。→ H3 CONFIRMED
- H4:`Go2WNavigateSkill().execute({"x":1,"y":2}, None)` → TypeError: takes from 1 to 2 positional arguments but 3 were given。→ H4 CONFIRMED

## CONCLUDE
- 根因(一句话):go2w 注入的半配置 vocab 把 decomposer 的策略词汇清空,叠加 strategy↔skill 两侧命名空间(`X_skill` vs 裸名)不一致与 navigate 技能签名不符内核约定,导致相对移动无路由、navigate 解析自相矛盾。
- 修复:
  1. zeno/vcli/worlds/go2w.py — decompose_vocab() 注入完整词汇(strategies/descriptions/params help/verify 签名/示例);新增 move_relative 技能(distance+direction,运行时读 /pose 含 yaw 换算 waypoint);修 navigate execute 签名为 (params, context, **kw);persona 教相对移动。
  2. zeno/vcli/cognitive/goal_decomposer.py — 裸名归一化:`X` ∉ KNOWN 但 `X_skill` ∈ KNOWN 时归一化为 `X_skill`,不再 clear。
  3. zeno/vcli/engine.py preflight — 校验 vocab `strategies` 集(原先只查 strategy_descriptions 的 key);机器人世界 registry 非空却教零策略 → 启动时 warning。
- 回归测试:tests/vcli/test_go2w_vocab_strategy_seam.py(vocab 宣称的每个 strategy 必须解析到本世界技能 + 裸名归一化 + move_relative 行为 + navigate 签名)。
- 验证命令:`.venv/bin/python -m pytest tests/vcli/test_go2w_vocab_strategy_seam.py tests/vcli/test_world_go2w_firstclass.py -q` + tests/vcli world/vgg 子集。
