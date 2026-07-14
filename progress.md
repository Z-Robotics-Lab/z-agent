# Zeno — progress

更新：2026-07-14。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **`/clean` 双确认清空地点落地（本轮，INTEGRATOR 复核通过）**：z-agent 7fc37ee(RED)→3bd43d3(GREEN)
  + go2w-nuc 兄弟仓 6578ad4(3D 视图地点/home 标签)。
  ①`go2w_real_maps.clear_places(map)`：`os.replace(places.json→.bak)` 原子备份+清空（旧 bak 直接覆盖），
  返回删除数；无文件/目录缺失/OSError → 0，从不抛出。home/家 不在 places.json（源自 start_pose.txt），
  清空后经 `home_place()` 自动复原。
  ②`cli.py` `/clean` 处理器：内核不静态 import 世界(Inv-4)——懒加载 map seam；无活动地图/seam 不可用→
  诚实拒绝；预览排除内置 home/家；确认1=精确输入地图名，确认2=y/N(默认N)，任何不匹配/EOF/Ctrl+C→
  “已取消”，未删除任何东西；确认后清盘+清活会话 ledger 的非内置 marks+重载 home/家；已注册进
  SLASH_COMMANDS+/help。
  ③go2w-nuc `map_color_publisher.py` 新增 `/place_markers`(MarkerArray, latched)：每个保存地点蓝球+文字
  标签，内置 home 金球+朝向箭头+标签；每次发布 DELETEALL 打头，id 按名字哈希稳定；5s 内跟随
  places.json/start_pose.txt mtime 变化刷新。3d-map-view.json + connections.md 同步更新。只读复核，未改动。
- **测试**：`bash scripts/run-tests tests/vcli/` = 6 fail/1201 pass/33 skip/1 xfail —— 6 个失败与既存基线
  完全吻合（playground_-family/go2_perception/level66/go2_courtyard，环境性，非本轮引入）。
  `tests/unit/vcli/`(排除 cv2 依赖两个文件) = 5 fail/1171 pass —— 均环境性(缺 PIL/cv2/mujoco 模块)，
  与 /clean 无关。`tests/unit/hardware/` = 15 fail/297 pass/63 error —— 与既存基线吻合(sim
  g1_room/go2w_hw_interrupt/go2w_hw_external_goal 计时 flake + 63 个 sim-env collect error，均
  mujoco/环境性)。**/clean 相关代码 0 个新增失败**：`test_clean_places.py` 11/11 全绿，
  `test_world_go2w_real_maps.py` 37/37 全绿。
- **离线冒烟（本轮新做）**：tmp 目录 `clear_places` 往返验证——备份+清空生效，`home_place` 重载后
  home 座标不受影响（1.0, 2.0, 0.5 存活）；`/clean` 单测已覆盖地图名不匹配/默认N/EOF 全部 abort 路径。

## 并发未完成工作（本轮未动，NEVER-KILL-INFRA——不得干扰）
- 分支上另有一轮并发 RED 提交 `3c46503`(operator RViz-goal detection，仅测试文件)落在 3bd43d3 之后，
  加上工作区未提交的 `zeno/hardware/ros2/go2w_hw.py` 改动（疑似同一 in-progress 轮次的 GREEN 半成品）。
  这不属于本次 /clean 复核范围，本轮完全未触碰、未 stash、未丢弃。`test_world_go2w_real_operator_override.py`
  与 `test_go2w_hw_external_goal.py` 的失败是该未完成特性的 RED 测试，不是 /clean 引入的回归。

## CEO 现场验收清单（真机，owner+E-stop 在手时执行 — 本轮未做，仅代码+离线验证）
① `/clean` 全流程：无预建图时诚实拒绝 → 有预建图时预览 → 打错地图名/回车默认N/Ctrl+D 均安全中止 →
  正确输入+y 后地点清空，`~/maps/<map>/places.json.bak` 生成，home/家 立即可用。
② 3D 视图（Foxglove）实时验证：`/place_markers` 随地点增删/`places.json` mtime 变化 5s 内刷新。
③ `zeno('记住这里叫X')` 后 3D 视图应秒现蓝球+标签“X”。

## Next
1. 真机执行上述 CEO 清单（本轮仅 hermetic 单测 + 离线冒烟，硬件闭环未做）。
2. 关注/协调分支上并发的 operator RViz-goal detection 轮次何时转 GREEN，届时需要重新跑基线对比。
3. map-color-publisher.service 需在 NUC 上重启一次以拾取新代码（若尚未做）。

## Failed / 教训
- **既存失败（勿追，全环境性，与本轮无关）**：tests/vcli 6 个（playground_-family/go2_perception/
  native_loop_devworld_pty/level66/go2_courtyard）+ tests/unit/vcli 5 个（PIL/cv2/mujoco 缺失）+
  tests/unit/hardware sim g1_room/go2w_hw_interrupt 计时 flake + 63 个 sim-env collect error。
- **结构债（既存）**：native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体，cli.py 本轮加法
  未改变超限状态，非本轮引入)；go2w_real 620+。
- **真机 E2E 未验收**：/clean + 3D 地点标签只做了 hermetic 单测 + 离线冒烟，硬件闭环待 owner 现场执行。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042)；go2w_real=真机(ROS_DOMAIN_ID=20,
  ~/Z-Navigation-Stack)。同 CLI，sim↔real 对称；verify 唯真值=/state_estimation(无 /gt)；测仅经
  `scripts/run-tests`。预建图：`~/maps/zeno_office/`(places.json 持久化命名点，start_pose.txt 首行=home)。
  nav.sh/map_color_publisher 在 go2w-nuc 仓（兄弟仓，独立提交）。
