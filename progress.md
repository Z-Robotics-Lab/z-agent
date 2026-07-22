# Zeno — progress

更新：2026-07-22。fork 自 upstream R715 (12f3e15)。集成分支 **hw-go2w-real**；本轮在其上开
**hw-go2w-real-vision**（未 push/未动 main）：RynnBrain 视觉感知接入。

## Works（已验证 / 单测 GREEN）
- **RynnBrain 感知轮（本轮）**：ac74ffa(RED)→GREEN。真机世界长出眼睛——本地 RynnBrain 具身 VLM
  （GPU 工作站服务，模型选择在其 start_rynn.sh 里）经 JSON 边车 http://127.0.0.1:8786 接入：
  ①`zeno/perception/rynnbrain.py`：RynnBrainClient（httpx 现有依赖、零新库；`read_env("RYNNBRAIN_URL")`
  ZENO_ 优先；坐标解析 parse_boxes/parse_points 为纯函数，[0,1000] 归一化；PIL 懒导入，JPEG q85/长边 640；
  仅 transport 错误重试 1 次，4xx 不重试）。
  ②`go2w_real_perception.py` 两只读技能（native LIVE 路径经 wrap_skills 可见——category 工具对 native
  不可见，故必须是 SKILL）：`find_object(description)`→画面侧别(左/中/右)+水平偏角(度,左正,D435i
  HFOV≈69°)+框；`scene_query(question)`→思考模式问答。取帧用 get_camera_image()（None-honest，
  黑帧兜底永不喂 VLM）；帧龄>2s 在结果里警告。诚实失败梯：no_base/bad_params/camera_failed/
  no_vlm(recovery_hints 指向 start_rynn.sh)/object_not_found(教改用真实外观措辞)。
  ③接线：embodiment 持单客户端（services['rynn']+base.rynn_client 双缝）；vocab 三集合同步
  （strategies/descriptions/params_help，set 全等测试通过）；capabilities.md Vision 段改为真实能力
  （感知=决策输入，验收仍 at()/moved()/turned()，无 'look skill' 字样）。
  ④措辞雷全部避开：MOTOR_KEYWORDS 七词不进 effects/description（wrap 后 is_read_only+
  is_concurrency_safe，有测试钉死）；技能名避开 native 特判 navigate/detect。
- **CEO 门裁决（owner 2026-07-22 批准本轮计划即过门）**：新跨进程接口=RynnBrain JSON 边车
  http://127.0.0.1:8786（POST /infer{image b64,text,think}→{reply}，GET /health）；**零新依赖**
  （httpx/numpy 现有，Pillow 在 [perception] tier）。服务端边车在 Learning_based_model 仓（用户侧），
  与 ws://8782 同进程共存、共享推理锁；NUC 部署设 ZENO_RYNNBRAIN_URL=http://<工作站IP>:8786。
- **测试**：`test_world_go2w_real_perception.py` 21/21 全绿（解析纯函数/方位数学 cx=750→右-17.25°/
  三条诚实失败/思考透传/只读判定/接线/能力卡）。回归：tests/vcli -k go2w_real = 363 pass/3 fail——
  3 个全是既存环境性 viz_3d（本工作站无 ~/go2w-nuc，干净树复现相同失败，非本轮引入）；
  vocab/seam/lifecycle/verify_vocab_integrity 子集 97/97 全绿。
- **E2E 冒烟（本轮新做）**：真 PNG 帧(448²)→JPEG 编码(≤640)→真 HTTP 往返(协议同款假模型)→解析→
  方位(+13.7° 左)→教学文案，全链 PASS。

## CEO 现场验收清单（真机，owner+E-stop 在手 — 本轮未做）
① 工作站重启 start_rynn.sh（拾取 8786 边车），`curl http://127.0.0.1:8786/health` 应回 {"ok":true}。
② NUC 上 export ZENO_RYNNBRAIN_URL=http://<工作站IP>:8786；d435i.service 在流。
③ `zeno('看看金属碗在哪')`→find_object 报侧别+偏角；`zeno('桌上有什么')`→scene_query 思考问答。
④ 组合链：find_object→turn 对准→靠近→at()/turned() 里程计判绿（感知永不自证）。
⑤ 上一轮遗留：/clean 全流程 + /place_markers 3D 标签现场验收仍待执行。

## Next
1. 真机执行上述清单（本轮 hermetic 21/21 + E2E 冒烟，硬件闭环未做）。
2. native 错配修复轮（独立分支）：native 通用提示教 at_position 但本世界 deny 之（真谓词 at）、
   native 丢世界 navigate 技能——感知教学在 native 靠技能 description 已覆盖，但整体错配待修。
3. 深度融合阶段2：订 depth 话题→像素+深度→map 米制目标（bearing 伺服先跑通再上）。
4. few-shot 预算：REAL_DECOMPOSE_EXAMPLES 6000 上限已满（5816/6000），感知 few-shot 主动省略
   （descriptions+params_help 已承载教学）；若 legacy 分解实测不足再议腾挪。

## Failed / 教训
- **全量 `tests/vcli/` 在 4090 工作站被 OOM kill**（sim 栈导入 + 共存 Rynn/ROS 服务；团队基线机不同）
  ——本轮以定向子集 + 干净树对照代替全量；勿在本机跑全量，分块跑。
- **例子预算是硬闸**：三个测试钉 ≤6000 字符，append-only 纪律下新 few-shot 挤不进——先写紧凑版仍超,
  最终省略并注释原因。
- 既存环境性失败（勿追）：viz_3d ×3（本机无 ~/go2w-nuc）+ 上轮记录的 playground/PIL/mujoco 族。

## 关键背景
- go2w=Isaac 数字孪生(HTTP 桥 127.0.0.1:8042)；go2w_real=真机(ROS_DOMAIN_ID=20,
  ~/Z-Navigation-Stack)。同 CLI，sim↔real 对称；verify 唯真值=/state_estimation(无 /gt)；测仅经
  `scripts/run-tests`。预建图：`~/maps/zeno_office/`。nav.sh/map_color_publisher 在 go2w-nuc 兄弟仓。
- 感知：RynnBrain 服务=用户侧 Learning_based_model/rynnbrain_test（start_rynn.sh 唯一入口，
  ws:8782+http:8786 双协议同进程）；z-agent 侧只做 httpx 客户端+两只读技能，感知永不进 verify。
