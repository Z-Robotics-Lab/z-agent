# Zeno — progress

更新：2026-07-15。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-real**（未 push/未动 main）。
叙事在 commit message 里；本文件只留当前状态。

## Works（已验证 / 单测 GREEN）
- **CLI UI 立体化：braille 加载进度条 + 精简圆点树（本轮，设计工作流 w378ob0re + owner 定稿）**。
  纯显示层（turn_render.py），非 CEO 门槛。v1 三态箭头条(`●━→▶┄→○`)被 owner 否("箭头/方块圆圈不好看、
  没进度条感")，改 AskUserQuestion 出 5 套真实渲染让其拍板→选定：① **状态机=braille 加载条 + N/5 计数**：
  `⣿⣿⣿⣿⣿⣿⣀⣀⣀⣀⣀⣀⣀⣀⣀  执行 3/5`——统一 braille 字形(⣿ 已填/⣀ 未填,15 格=5 阶段×3)按 阶段/5 比例填充,
  只显当前阶段名 + 诚实 N/5(固定 5 阶段机,非伪百分比);sink 每进新阶段重发,scrollback 里填充向右推进;
  `完成 5/5` 转绿;分支(恢复/让位)用 reached_rank **冻结**计数在最后真实阶段、绝不假进(挂琥珀 `⑂`)。
  ② **behavior tree=精简圆点**：`├─ ● name` 挂 ⌂ 主干(去掉旧 `◇ Tool·` 杂讯)、状态 ✓/×/… 右对齐到固定列
  成清单(CJK 宽度用 rich cell_len,长名优雅溢出)、`│  └ verify …` 深一层缩进为工具子节点;流式恒 `├─`
  (append-only 不知末 child,诚实开放),final_lines 才闭合末节点 `└─`。诚实:只画已发生节点、无伪造未来/
  百分比/时长(守 Inv-1)。测:owner 定新设计→更新旧钉死字形(▶/◇Tool·/5阶段名/→)的断言到 braille+● 契约;
  120 显示测 GREEN(含 .venv 全依赖);4 场景(顺利/失败恢复/操作员让位/超长)真实渲染肉眼验收。真机 sink 待现场。
- **routed 导航不再让 agent 重规划**：routed stall 不 abort 而 RE-NUDGE far_planner（park+重发 /goal_point），
  同一次调用继续开；只有 overall timeout(120s)/操作员/far_reach 到达才结束，MAX_RENUDGE=8 兜底。navigate_to
  信 far_planner /far_reach_goal_status（到达=里程计 OR far_reach 且里程计 1m 内，绝不 far_reach 单独，守 Inv-1）。
- **框架结论=押注 native**（工作流 wv23zizqc）；VGG 保留休眠不复活其分解器。
- **Fix B（bag 实锤）**：navigate_to 发 /goal_point 让 far_planner 独占 /way_point（单写者），修掉 park 适得其反
  的零位移冻住。无 far_planner 回退直发 /way_point。RViz far_planner 4 display 并入 vehicle_simulator.rviz。
- **地标实时重读 + 模糊匹配**：refresh_marks_from_disk 每次调用前重读 places.json；_resolve_mark 精确→大小写无关
  →无歧义子串，多候选拒绝并列（Inv-1）；RealListPlacesSkill 答"能去哪"。`run-tests -k go2w_real`=352 pass。
- **电量% + 电压上状态栏**：unitree_control.py 转发 lowstate bms → /battery_state（035abfb，owner 批）；zeno
  订阅显示 `电量 NN%`（无源/陈旧→不显示，绝不编数）。**真机需 colcon build + nav 重启生效，待验。**
- **/clean 双确认清空地点**（INTEGRATOR 复核过）：clear_places 原子备份+清空，home 从 start_pose.txt 自动复原。

## Next
1. **真机验收本轮 UI**：重启 zeno 跑一圈（站起/去地标/回home/失败恢复），眼看状态条填充 + 树轨是否更易读立体。
2. **电量真机验证**：`colcon build --packages-select unitree_webrtc_ros` + `nav stop && nav start zeno_office`；
   看状态栏 `电量 NN%`；首帧 `lowstate keys=…` log 确认电压字段名，不对则按真机字段微调 _on_lowstate。
3. operator RViz-goal detection 已 GREEN，真机闭环待现场。map-color-publisher.service 需 NUC 重启拾新代码。

## Failed / 教训
- **既存环境性失败（勿追）**：tests/vcli 少数（playground/go2_perception/level66/go2_courtyard）+ unit/vcli 缺
  PIL/cv2/mujoco + hardware sim 计时 flake + sim-env collect error。裸环境缺 prompt_toolkit/cv2 → 经
  `scripts/run-tests`（.venv）跑显示测才有依赖。
- **真机丝滑天花板=导航栈地形**（obstacleHeightThre=0.1m，95% 零长度局部路径）=CEO 门槛；agent 侧只能去掉
  重规划、去不掉障碍处物理停顿。
- **结构债（既存上游单体）**：native_loop/engine/cli/goal_decomposer >800 行硬上限；go2w_real 620+。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042)；go2w_real=真机(ROS_DOMAIN_ID=20, ~/Z-Navigation-Stack)。同 CLI，
  sim↔real 对称；verify 唯真值=/state_estimation；测仅经 `scripts/run-tests`。预建图 `~/maps/zeno_office/`
  (places.json 命名点，start_pose.txt 首行=home)。nav.sh/map_color_publisher 在 go2w-nuc 兄弟仓（独立提交）。
- **现场跑 sink 模式**（持久 composer，从不调 render_lines）——UI 改动的可见性必须走 sink 流式路径验证。
