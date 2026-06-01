"""
后端接口文件 - 部署在 Vercel 服务器端
作用：接收前端消息 → 调用 DeepSeek API → 流式返回给浏览器
API Key 只存在服务器环境变量中，用户永远看不到
"""

import os
import json
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error


# 从 Vercel 环境变量读取 API Key（不写死在代码里）
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL   = "deepseek-chat"


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """处理跨域预检请求"""
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        """接收前端消息，转发给 DeepSeek，流式返回"""

        # ── 读取请求体 ──────────────────────
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        try:
            data     = json.loads(body)
            messages = data.get("messages", [])
        except Exception:
            self._error(400, "请求格式错误")
            return

        if not API_KEY:
            self._error(500, "服务器未配置 API Key，请联系管理员")
            return

        if not messages:
            self._error(400, "消息不能为空")
            return

        # ── 构造给 DeepSeek 的请求 ──────────
        payload = json.dumps({
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "你是我的小助理，你什么都懂，请用清晰的中文回答问题。"}
            ] + messages,
            "stream": True,
            "tools": [{"type": "web_search"}],
            "stream_options": {"include_usage": True},
            "temperature": 0.7,
            "max_tokens": 2048,
        }).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type":  "application/json",
                "Accept":        "text/event-stream",
            },
            method="POST"
        )

        # ── 转发流式响应给前端 ──────────────
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("X-Accel-Buffering", "no")
                self._set_cors_headers()
                self.end_headers()

                for raw_line in resp:
                    line = raw_line.decode("utf-8").rstrip("\n")
                    if line:
                        self.wfile.write((line + "\n\n").encode("utf-8"))
                        self.wfile.flush()

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            if e.code == 401:
                self._error(401, "API Key 无效")
            elif e.code == 429:
                self._error(429, "请求频率超限，请稍后重试")
            elif e.code == 402:
                self._error(402, "账户余额不足")
            else:
                self._error(500, f"DeepSeek 返回错误：{e.code}")

        except Exception as e:
            self._error(500, f"服务器内部错误：{str(e)}")

    def _set_cors_headers(self):
        """允许所有来源跨域（前端调用必须）"""
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _error(self, code: int, msg: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": msg}, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 关闭默认日志输出

