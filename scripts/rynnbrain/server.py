#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""RynnBrain 具身-VLM 服务 —— 产品化、仓内自持的入口。

对外提供 z-agent 感知契约（见 zeno/perception/rynnbrain.py）:

    POST http://127.0.0.1:${RYNNBRAIN_HTTP_PORT}/infer
         {"image": <base64 jpeg>, "text": str, "think": bool} -> {"reply": str}
    GET  http://127.0.0.1:${RYNNBRAIN_HTTP_PORT}/health
         -> {"ok": true, "model": <spec>}

跑在专用 venv ~/envs/rynnbrain（torch/transformers/bitsandbytes），**不是** z-agent
的 .venv —— 因此本文件不 import 任何 `zeno` 代码，配置全走环境变量。生产态由
systemd --user 托管（scripts/rynnbrain/install-service.sh 生成 unit）。

配置（全部走环境变量；systemd unit 用 Environment= 设定，可 `systemctl --user edit` 覆盖）:
    RYNNBRAIN_MODEL_SPEC   2b-bf16（默认） | 9b-nf4
    RYNNBRAIN_MODEL_PATH   模型目录（默认按 spec 推导到 ~/models 下）
    RYNNBRAIN_HTTP_PORT    默认 8786（z-agent 契约端口）
    RYNNBRAIN_DEVICE       默认 cuda:0
    RYNNBRAIN_WS_ENABLE    0（默认） | 1 —— 额外开 ws+msgpack 边车（给 LIBERO /
                           ab_compare 等桌面老客户端）；关掉时纯 HTTP 单一职责
    RYNNBRAIN_WS_PORT      默认 8782（仅当 RYNNBRAIN_WS_ENABLE=1 时生效）

模型选择依据：默认 2B bf16 —— 显存 ~4.5GB、定位 ~1s，对共享的 24GB 4090 友好。
9B NF4（int4，显存 ~7.9GB）是即插即用的配置项（RYNNBRAIN_MODEL_SPEC=9b-nf4），
问答更强并支持思考模式。

本文件由桌面测试目录 rynnbrain_test/{rynnbrain_server.py, rynnbrain9b_server.py}
收编、统一并参数化而来（原件不动不删）。
"""
from __future__ import annotations

import os
import threading

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

from rynn_http import start_http_server

# --- spec 表：模型选择是数据，加一个规格是一行改动 -------------------------
SPECS = {
    "2b-bf16": {"default_path": "~/models/RynnBrain1.1-2B", "quant": None},
    "9b-nf4": {"default_path": "~/models/RynnBrain1.1-9B", "quant": "nf4"},
}


def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def load_model(spec, model_path, device):
    """按 spec 加载模型与 processor。2B 直接 bf16；9B 走 bitsandbytes NF4 量化，
    但视觉塔/merger/lm_head 跳过量化保持 bf16（坐标定位依赖视觉塔精度）。"""
    kwargs = dict(dtype=torch.bfloat16, device_map={"": device},
                  attn_implementation="sdpa")
    if SPECS[spec]["quant"] == "nf4":
        from transformers import BitsAndBytesConfig
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            llm_int8_skip_modules=["visual", "vision_tower", "vision_model",
                                   "merger", "lm_head"],
        )
    model = AutoModelForImageTextToText.from_pretrained(model_path, **kwargs)
    processor = AutoProcessor.from_pretrained(model_path)
    return model, processor


def make_infer(model, processor, device):
    """返回一个自带锁、线程安全的 infer_locked(image, text, think)。

    ws 与 http 两条入口共享同一把锁串行化 GPU 推理。think 对不支持思考模式的
    chat_template（如 2B）会在 apply_chat_template 抛 TypeError/ValueError，回退到
    不带 enable_thinking 的调用。"""
    def infer(image, text, think=False):
        messages = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": text},
        ]}]
        try:
            inputs = processor.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors="pt", enable_thinking=think,
            ).to(device)
        except (TypeError, ValueError):
            inputs = processor.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                return_dict=True, return_tensors="pt",
            ).to(device)
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=768 if think else 256,
                                 do_sample=False)
        return processor.decode(out[0][inputs["input_ids"].shape[1]:],
                                skip_special_tokens=True).strip()

    lock = threading.Lock()

    def infer_locked(image, text, think=False):
        with lock:
            return infer(image, text, think)

    return infer_locked


def serve_ws_forever(infer_locked, host, port):
    """老 ws+msgpack 边车（尽力而为；绑定失败只记日志，绝不拖垮 http 契约）.

    wire 协议与桌面原件一致：请求 {"image": <jpeg bytes>, "text", "think"} ->
    {"reply": <text>}（msgpack）."""
    import asyncio
    import io

    import msgpack
    import websockets

    async def handle(ws):
        async for message in ws:
            req = msgpack.unpackb(message, raw=False)
            image = Image.open(io.BytesIO(req["image"])).convert("RGB")
            reply = infer_locked(image, req["text"],
                                 think=bool(req.get("think", False)))
            await ws.send(msgpack.packb({"reply": reply}))

    async def run():
        async with websockets.serve(handle, host, port,
                                    max_size=32 * 1024 * 1024):
            print(f"rynnbrain ws: listening on ws://{host}:{port}", flush=True)
            await asyncio.Future()

    asyncio.run(run())


def main():
    spec = _env("RYNNBRAIN_MODEL_SPEC", "2b-bf16")
    if spec not in SPECS:
        raise SystemExit(f"unknown RYNNBRAIN_MODEL_SPEC={spec!r}; "
                         f"choose one of {sorted(SPECS)}")
    model_path = os.path.expanduser(
        _env("RYNNBRAIN_MODEL_PATH", SPECS[spec]["default_path"]))
    device = _env("RYNNBRAIN_DEVICE", "cuda:0")
    http_port = int(_env("RYNNBRAIN_HTTP_PORT", "8786"))
    ws_enable = _env("RYNNBRAIN_WS_ENABLE", "0") == "1"
    ws_port = int(_env("RYNNBRAIN_WS_PORT", "8782"))

    print(f"rynnbrain server: loading spec={spec} path={model_path} "
          f"device={device}", flush=True)
    model, processor = load_model(spec, model_path, device)
    if device.startswith("cuda"):
        idx = int(device.split(":")[1]) if ":" in device else 0
        vram = torch.cuda.memory_allocated(idx) / 1e9
        print(f"rynnbrain server: model loaded, VRAM {vram:.1f} GB", flush=True)
    else:
        print("rynnbrain server: model loaded", flush=True)

    infer_locked = make_infer(model, processor, device)

    # HTTP 边车（z-agent 契约）—— daemon 线程，永远在。端口被占用会在此同步抛错。
    start_http_server(infer_locked, spec, port=http_port)

    # 老 ws 边车 —— 可选、尽力而为：放 daemon 线程，绑定失败只记日志，主线程照常 park。
    if ws_enable:
        def _ws():
            try:
                serve_ws_forever(infer_locked, "127.0.0.1", ws_port)
            except Exception as exc:  # noqa: BLE001 — ws 是尽力而为
                print(f"rynnbrain ws: disabled ({exc})", flush=True)
        threading.Thread(target=_ws, daemon=True).start()

    ws_note = f", ws://127.0.0.1:{ws_port}" if ws_enable else ""
    print(f"rynnbrain server: ready (http://127.0.0.1:{http_port}{ws_note})",
          flush=True)
    threading.Event().wait()  # 主线程 park；边车在后台线程服务


if __name__ == "__main__":
    main()
