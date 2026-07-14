# Zeno — progress

更新：2026-07-14。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-real**（未 push/未动 main）。

## Works（已验证 / 单测 GREEN）
- **预建图重定位集成落地（本轮，INTEGRATOR 复核通过）**：z-agent 102f303(RED 32)→a39ad90(GREEN)
  + go2w-nuc 兄弟仓 1ca9ede(3D 彩色地图发布)+d22593f(current_map.txt 握手)。四条缝：
  ①DEFAULT-MAP BRINGUP：`go2w_real_maps.resolve_bringup_map` 显式名>从零/none/''=空跑>
  未指定→env GO2W_DEFAULT_MAP 或内置 zeno_office(PCD 存在时)；argv 附加地图名。
  ②CURRENT-MAP 握手（只读）：`current_map()` 读 nav.sh 写的 `logs/current_map.txt`
  （env GO2W_CURRENT_MAP_FILE 测试可覆盖），none/空/缺失=None。
  ③PERSISTENT PLACES：`save_places`/`load_places`（atomic tmp+rename，
  `~/maps/<map>/places.json`）+ `home_place`(start_pose.txt 首行)；`PoseLedger.load_marks`
  合并注入；mark_place 有活动地图时落盘，否则仅会话内。
  ④3D VIEW SEAM：`open_viz view=3d` 复用既有 OverlayLauncher（空 mode 直跑 view3d.sh），
  dedupe/close_all 照常。
- **复核范围**：diff 审查（世界文件专属，无内核改动；hw_overlay 空-mode 分支纯加法向后兼容）+
  go2w-nuc 侧 nav.sh 握手（stop_all 后/systemd-run 前落笔，预建图缺失被前置校验挡下时不误写）+
  map_color_publisher.py（rclpy 通用 PCD 头解析，QoS RELIABLE+TRANSIENT_LOCAL）—只读复核，未改动。
- **测试**：`bash scripts/run-tests tests/vcli/` = 6 fail/1196 pass/33 skip/1 xfail —— 6 个失败与既存基线
  完全吻合（playground_-family/go2_perception/level66/go2_courtyard，环境性，非本轮引入）。
  `tests/unit/hardware/` = 6 fail/297 pass/63 error —— 与既存基线吻合（sim g1_* + go2w_hw_interrupt
  计时 flake + 63 个 sim-env collect error，均 mujoco 模块缺失/环境性）。**0 个新增失败**。
  `test_world_go2w_real_maps.py` 单独 32/32 全绿。
- **离线冒烟（本轮新做，未跑真 nav.sh/未连硬件）**：①`resolve_bringup_map` 对真实 `~/maps/zeno_office`
  默认解析出 `zeno_office`；`GO2W_DEFAULT_MAP=none`/缺失 PCD 均正确回退空跑。②`save_places`/
  `load_places`/`home_place` 在 tmp 目录往返一致，含从假 start_pose.txt 注入 home。③`current_map()`
  经 env 覆盖对 active/none/missing 三态正确。④`VizOverlaySession.open('3d')` 用假 popen seam
  验证 argv=`['bash', .../view3d.sh]`（无多余空 mode 参数）、dedupe、close_all 均正常，未真启动进程。

## CEO 现场验收清单（真机，owner+E-stop 在手时执行 — 本轮未做，仅代码+离线验证）
① `zeno('启动导航栈')` → 应带图重定位（默认 zeno_office，非从零建图）
② `zeno('记住这里叫充电桩')` → 重启导航栈（`nav.sh stop` 再 `nav.sh start`）→
  `zeno('去充电桩')` 仍应到位（验证 `~/maps/zeno_office/places.json` 持久化生效）
③ `zeno('回home')` → 应到 start_pose.txt 首行位姿（未 mark 过 home 时的内置注入）
④ `zeno('打开3D视图')` → Foxglove 应显示彩色预建地图 + 狗的实时位姿/轨迹（订阅
  `/prior_map_color`，TRANSIENT_LOCAL 迟连接可见）
⑤ 精准进站（goto_place precise=true）复测，确认预建图模式下坐标系稳定不漂移

## Next
1. 真机执行上述五项现场验收（本轮代码+离线验证 GREEN，硬件闭环未做）。
2. map-color-publisher.service 需在 NUC 上 `systemctl --user enable --now` 一次（本轮未装，只读复核）。
3. 内核轮（路由取证）：native direct 姿态技能放行/内建 posture verify；'angle' 抽参。
4. camera 一等 look_skill STRATEGY。

## Failed / 教训
- **既存失败（勿追，全环境性，与本轮无关）**：tests/vcli 6 个
  (playground_-family/go2_perception/native_loop_devworld_pty/level66/go2_courtyard) +
  tests/unit/hardware 6 个 sim g1_* + go2w_hw_interrupt 计时 flake + 63 个 sim-env collect error
  (mujoco 模块缺失)。
- **结构债（既存）**：native_loop/engine/cli/goal_decomposer >800 硬上限(上游单体)；go2w_real 620+。
- **真机 E2E 未验收**：预建图/places 持久化/3D 视图全部只做了 hermetic 单测 + 离线冒烟，
  硬件闭环（CEO 清单①-⑤）待 owner 现场执行。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042)；go2w_real=真机(ROS_DOMAIN_ID=20,
  ~/Z-Navigation-Stack)。同 CLI，sim↔real 对称；verify 唯真值=/state_estimation(无 /gt)；测仅经
  `scripts/run-tests`。预建图：`~/maps/zeno_office/`(zeno_office.pcd 导航 + zeno_office_viz.pcd
  彩色可视化 + start_pose.txt 首行=home + places.json 持久化命名点)。nav.sh 在 go2w-nuc 仓
  （兄弟仓，独立提交）。SLAM prior 只读——纯定位模式。
