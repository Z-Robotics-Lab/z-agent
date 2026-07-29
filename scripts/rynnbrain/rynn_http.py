# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""RynnBrain 服务器的 HTTP 边车（纯 stdlib，无第三方依赖）.

给 z-agent 等只有 httpx 的客户端用（见 zeno/perception/rynnbrain.py）；可选的
ws+msgpack 老客户端（LIBERO demo / ab_compare）由 server.py 另开线程并存。

  POST /infer   JSON {"image": <base64 jpeg>, "text": str, "think": bool} -> {"reply": str}
  GET  /health  -> {"ok": true, "model": <name>}

错误语义：请求解析/解码失败 -> 400 {"error": ...}；推理失败 -> 500 {"error": ...}

本文件从桌面测试目录 rynnbrain_test/rynn_http.py 收编进仓（原件不动不删）。
"""
import base64
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image

HTTP_PORT = 8786


def start_http_server(infer_fn, model_name, port=HTTP_PORT):
    """在后台 daemon 线程起 HTTP 服务并返回 server 对象.

    绑定端口是同步发生的（ThreadingHTTPServer 构造即 bind）：端口被占用会在此处
    抛错，让调用方尽早失败（生产态由 systemd Restart=on-failure 兜住）。

    infer_fn(image: PIL.Image, text: str, think: bool) -> str 必须自带线程安全
    （调用方用一把锁包住模型推理，ws 与 http 两条路共享同一把锁）.
    """

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # 不刷终端
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True, "model": model_name})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/infer":
                self._send(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length))
                image = Image.open(io.BytesIO(base64.b64decode(req["image"]))).convert("RGB")
                text = req["text"]
                think = bool(req.get("think", False))
            except Exception as exc:  # noqa: BLE001 - 请求侧错误一律 400
                self._send(400, {"error": f"bad request: {exc}"})
                return
            try:
                reply = infer_fn(image, text, think)
            except Exception as exc:  # noqa: BLE001 - 推理侧错误 500
                self._send(500, {"error": f"inference failed: {exc}"})
                return
            self._send(200, {"reply": reply})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"rynnbrain http: listening on http://127.0.0.1:{port}", flush=True)
    return server
