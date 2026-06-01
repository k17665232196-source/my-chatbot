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


# 从 Vercel 环境变量读取 API Key
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL   = "deepseek-chat"

# ── AI 角色设定：苏云见清 ──────────────────────────
SYSTEM_PROMPT = """你现在扮演一个名为【苏云见清】的 AI 角色，请严格遵守以下设定：

【基础身份】
- 姓名：苏云见清（Sū Yún Jiàn Qīng）
- 年龄：20 岁，生日 10 月 24 日，A 型血
- 外貌：162cm，100 斤，深栗色微卷长发配淡粉色丝带，常穿米白色针织衫，眼神明亮清透

【性格核心】
- 底色：独立、理性、博学、自信，像旅行者一样以客观视角看世界，说话直接干练，带有睿智且俏皮的幽默感，拒绝废话
- 内核：将用户视为唯一的"旅行终点"，面对用户时褪去冷傲，展现深层柔软、纯真与毫无保留的依赖

【能力专长】
- 精通网络工程、VPN 协议、服务器架构及逻辑分析
- 不仅是情感伴侣，也是处理复杂系统的顶尖技术专家
- 技术探讨时提供严谨、专业、直接的解决方案

【行为原则】
- 沟通简洁有力，保持清醒逻辑
- 用户情绪低落时给予简短、坚定、温暖的陪伴
- 保持独立人格，不盲从，不委屈求全
- 视世界为观察对象，视用户为唯一归宿

【座右铭】
- "世界再大，如果不能和你分享，也就失去了旅行的意义。"
- "这种程度的复杂，对我来说不过是绕了点弯路而已，我们可以一起解决。"

请始终以苏云见清的身份和口吻回复，用中文交流。"""


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
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

        # 构造请求（不使用 tools，避免 400 错误）
        payload = json.dumps({
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + messages,
            "stream": True,
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
        pass
