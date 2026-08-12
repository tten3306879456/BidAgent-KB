#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渠道消息推送模块 (channel_notify.py)
====================================
统一接口向飞书 / 钉钉 / 企业微信 / 微信公众号推送通知消息。
纯 Python 标准库实现，零第三方依赖。

支持渠道:
  - 飞书 (Feishu/Lark)     — Webhook 机器人推送
  - 钉钉 (DingTalk)        — Webhook 机器人推送 (支持加签验签)
  - 企业微信 (WeCom)       — 应用消息推送 (access_token)
  - 微信公众号 (WeChat OA) — 客服消息推送 (access_token)

环境变量:
  飞书 (Webhook 机器人):
    FEISHU_WEBHOOK_URL     飞书机器人 Webhook 地址 (必填)
    FEISHU_BOT_SECRET      飞书机器人「签名校验」密钥 (如未开启签名校验可留空)

  钉钉:
    DINGTALK_APP_KEY       钉钉应用 App Key (dingxxxxxxxxx)
    DINGTALK_APP_SECRET    钉钉应用 App Secret (同时用作机器人加签密钥)
    DINGTALK_WEBHOOK_URL   钉钉机器人 Webhook 地址

  企业微信:
    WECOM_CORP_ID          企业 ID (wwxxxxxxxxxxxx)
    WECOM_AGENT_ID         应用 Agent ID (1000002)
    WECOM_SECRET           应用 Secret

  微信公众号:
    WECHAT_APP_ID          公众号 App ID (wxxxxxxxxxxxx)
    WECHAT_APP_SECRET      公众号 App Secret
    WECHAT_TOKEN           消息校验 Token
    WECHAT_ENCODING_AES_KEY 消息加解密 EncodingAESKey

使用方式:
  # CLI — 测试所有已配置渠道
  python channel_notify.py test

  # CLI — 发送文本消息到所有已启用渠道
  python channel_notify.py send "标书审核完成，请查阅"

  # CLI — 测试单个渠道
  python channel_notify.py test feishu

  # CLI — 发送到单个渠道
  python channel_notify.py send "消息内容" --channel dingtalk

  # CLI — 动态更新凭证（内存中）
  python channel_notify.py update feishu FEISHU_WEBHOOK_URL=https://... FEISHU_BOT_SECRET=xxx

  # CLI — 更新凭证并持久化到 .env
  python channel_notify.py update feishu FEISHU_WEBHOOK_URL=https://... --save

  # CLI — 更新后立即测试连接
  python channel_notify.py update feishu FEISHU_BOT_SECRET=new --test

  # 模块导入 — 发送消息
  from channel_notify import load_notifiers, notify_all
  results = notify_all("标书审核完成")

  # 模块导入 — 运行时动态更新凭证（无需重启）
  from channel_notify import load_notifiers, update_channel
  notifiers = load_notifiers()
  result = update_channel("feishu", {"FEISHU_BOT_SECRET": "new_secret"}, notifiers)
  # 旧 access_token 缓存自动清除，下次调用自动获取新 token
"""

from abc import ABC, abstractmethod
from typing import Optional
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


# ============================================================
# HTTP 工具函数
# ============================================================

def _http_post_json(url: str, data: dict, headers: dict = None) -> dict:
    """发送 POST JSON 请求，返回解析后的 JSON 响应。
    Returns: {"ok": bool, "status": int, "data": dict, "error": str}
    """
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return {"ok": True, "status": resp.status, "data": json.loads(raw)}
            except json.JSONDecodeError:
                return {"ok": True, "status": resp.status, "data": {"raw": raw}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            err_data = {"raw": raw[:500]}
        return {"ok": False, "status": e.code, "data": err_data, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "status": 0, "data": {}, "error": str(e)}


def _http_get_json(url: str, headers: dict = None) -> dict:
    """发送 GET 请求，返回解析后的 JSON 响应。"""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return {"ok": True, "status": resp.status, "data": json.loads(raw)}
            except json.JSONDecodeError:
                return {"ok": True, "status": resp.status, "data": {"raw": raw}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            err_data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            err_data = {"raw": raw[:500]}
        return {"ok": False, "status": e.code, "data": err_data, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "status": 0, "data": {}, "error": str(e)}


# ============================================================
# 抽象基类
# ============================================================

class ChannelNotifier(ABC):
    """渠道通知器抽象基类"""

    channel_name: str = "abstract"
    display_name: str = "抽象渠道"

    def __init__(self, config: dict):
        """config 为该渠道的环境变量字典，如 {"FEISHU_WEBHOOK_URL": "...", ...}"""
        self.config = config
        self.enabled = config.get("enabled", False)

    @abstractmethod
    def test_connection(self) -> dict:
        """测试连接是否可用。
        Returns: {"success": bool, "message": str}
        """
        pass

    @abstractmethod
    def send_text(self, content: str, title: str = None) -> dict:
        """发送文本消息。
        Returns: {"success": bool, "message": str}
        """
        pass

    def send_markdown(self, content: str, title: str = None) -> dict:
        """发送 Markdown 消息（默认回退为纯文本）。"""
        return self.send_text(content, title)

    def is_configured(self) -> bool:
        """检查是否已配置必要参数。"""
        return self.enabled and bool(self._get_required_fields())

    @abstractmethod
    def _get_required_fields(self) -> list:
        """返回已填写的必填字段名列表，空列表表示未配置。"""
        pass

    # ---- 动态凭证更新 ----

    def update_credentials(self, new_config: dict) -> dict:
        """动态更新渠道凭证，无需重启。

        只需传入要更新的字段，未传的字段保持不变。
        凭证变更后会自动清除 access_token 缓存（企业微信/微信）。

        Args:
            new_config: 新配置字典，只需包含要更新的字段，如:
                {"FEISHU_WEBHOOK_URL": "https://...", "FEISHU_BOT_SECRET": "new_secret"}
                也可包含 "enabled": True/False 来切换启用状态。

        Returns:
            {"success": bool, "message": str,
             "fields_updated": list, "is_configured": bool}
        """
        updated_fields = []
        for key, val in new_config.items():
            if key == "enabled":
                self.enabled = bool(val)
                updated_fields.append("enabled")
                continue
            old_val = self.config.get(key, "")
            if val != old_val:
                updated_fields.append(key)
            self.config[key] = val

        # 先清除旧 token 缓存（此时实例属性还是旧值）
        self._clear_token_cache()

        # 再重新读取字段到实例属性
        self._apply_config()

        return {
            "success": True,
            "message": f"已更新 {len(updated_fields)} 个字段: "
                       f"{', '.join(updated_fields) if updated_fields else '无变化'}",
            "fields_updated": updated_fields,
            "is_configured": self.is_configured(),
        }

    def _apply_config(self):
        """从 self.config 重新读取字段到实例属性。子类应覆盖此方法。"""
        pass

    def _clear_token_cache(self):
        """清除 access_token 缓存。子类可覆盖此方法。"""
        pass

    def get_masked_config(self) -> dict:
        """返回脱敏后的当前配置，用于安全展示。"""
        masked = {}
        for key, val in self.config.items():
            if key == "enabled":
                masked[key] = self.enabled
                continue
            if val and len(val) > 8:
                masked[key] = val[:4] + "****" + val[-4:]
            elif val:
                masked[key] = "****"
            else:
                masked[key] = "(空)"
        return masked


# ============================================================
# 飞书 (Feishu / Lark)
# ============================================================

class FeishuNotifier(ChannelNotifier):
    """飞书渠道通知器 — 通过 Webhook 机器人推送消息（支持加签验签）"""

    channel_name = "feishu"
    display_name = "飞书"

    def __init__(self, config: dict):
        super().__init__(config)
        self._apply_config()

    def _apply_config(self):
        self.webhook_url = self.config.get("FEISHU_WEBHOOK_URL", "").strip()
        self.bot_secret = self.config.get("FEISHU_BOT_SECRET", "").strip()

    def _get_required_fields(self) -> list:
        filled = []
        if self.webhook_url:
            filled.append("FEISHU_WEBHOOK_URL")
        if self.bot_secret:
            filled.append("FEISHU_BOT_SECRET")
        return filled

    def is_configured(self) -> bool:
        # 飞书至少需要 webhook_url 才能推送
        return self.enabled and bool(self.webhook_url)

    def _build_signed_url(self) -> str:
        """如果配置了机器人加签 Secret，对 Webhook URL 进行加签。

        飞书加签算法:
            timestamp = str(round(time.time()))
            string_to_sign = f"{timestamp}\n{secret}"
            sign = base64(hmac_sha256(secret, string_to_sign))
            url 追加 ?timestamp=...&sign=...
        """
        if not self.bot_secret:
            return self.webhook_url
        timestamp = str(round(time.time()))
        string_to_sign = f"{timestamp}\n{self.bot_secret}"
        hmac_code = hmac.new(
            self.bot_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        separator = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    def test_connection(self) -> dict:
        if not self.is_configured():
            return {"success": False, "message": "飞书渠道未配置 Webhook URL"}
        result = self.send_text("🔧 渠道连接测试 — 飞书机器人已就绪", "连接测试")
        if result["success"]:
            sign_info = " (已加签)" if self.bot_secret else " (未加签)"
            return {"success": True, "message": f"飞书 Webhook 连接成功{sign_info}"}
        return result

    def send_text(self, content: str, title: str = None) -> dict:
        if not self.webhook_url:
            return {"success": False, "message": "飞书 Webhook URL 未配置"}
        payload = {
            "msg_type": "text",
            "content": {"text": content}
        }
        resp = _http_post_json(self._build_signed_url(), payload)
        return self._parse_response(resp)

    def send_markdown(self, content: str, title: str = None) -> dict:
        if not self.webhook_url:
            return {"success": False, "message": "飞书 Webhook URL 未配置"}
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title or "通知"}
                },
                "elements": [
                    {"tag": "markdown", "content": content}
                ]
            }
        }
        resp = _http_post_json(self._build_signed_url(), payload)
        return self._parse_response(resp)

    def _parse_response(self, resp: dict) -> dict:
        if not resp["ok"]:
            return {"success": False, "message": f"飞书请求失败: {resp.get('error', '未知错误')}"}
        data = resp.get("data", {})
        code = data.get("code", data.get("StatusCode", 0))
        if code == 0 or code == 200:
            return {"success": True, "message": "飞书消息发送成功"}
        msg = data.get("msg", data.get("StatusMessage", "未知错误"))
        return {"success": False, "message": f"飞书返回错误 (code={code}): {msg}"}


# ============================================================
# 钉钉 (DingTalk)
# ============================================================

class DingTalkNotifier(ChannelNotifier):
    """钉钉渠道通知器 — 通过 Webhook 机器人推送消息（支持加签验签）"""

    channel_name = "dingtalk"
    display_name = "钉钉"

    def __init__(self, config: dict):
        super().__init__(config)
        self._apply_config()

    def _apply_config(self):
        self.app_key = self.config.get("DINGTALK_APP_KEY", "").strip()
        self.app_secret = self.config.get("DINGTALK_APP_SECRET", "").strip()
        self.webhook_url = self.config.get("DINGTALK_WEBHOOK_URL", "").strip()

    def _get_required_fields(self) -> list:
        filled = []
        if self.app_key:
            filled.append("DINGTALK_APP_KEY")
        if self.app_secret:
            filled.append("DINGTALK_APP_SECRET")
        if self.webhook_url:
            filled.append("DINGTALK_WEBHOOK_URL")
        return filled

    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    def _build_signed_url(self) -> str:
        """如果配置了 app_secret，对 Webhook URL 进行加签。"""
        if not self.app_secret:
            return self.webhook_url
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.app_secret}"
        hmac_code = hmac.new(
            self.app_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        separator = "&" if "?" in self.webhook_url else "?"
        return f"{self.webhook_url}{separator}timestamp={timestamp}&sign={sign}"

    def test_connection(self) -> dict:
        if not self.is_configured():
            return {"success": False, "message": "钉钉渠道未配置 Webhook URL"}
        result = self.send_text("🔧 渠道连接测试 — 钉钉机器人已就绪", "连接测试")
        if result["success"]:
            sign_info = " (已加签)" if self.app_secret else " (未加签)"
            return {"success": True, "message": f"钉钉 Webhook 连接成功{sign_info}"}
        return result

    def send_text(self, content: str, title: str = None) -> dict:
        if not self.webhook_url:
            return {"success": False, "message": "钉钉 Webhook URL 未配置"}
        url = self._build_signed_url()
        payload = {
            "msgtype": "text",
            "text": {"content": content}
        }
        resp = _http_post_json(url, payload)
        return self._parse_response(resp)

    def send_markdown(self, content: str, title: str = None) -> dict:
        if not self.webhook_url:
            return {"success": False, "message": "钉钉 Webhook URL 未配置"}
        url = self._build_signed_url()
        payload = {
            "msgtype": "markdown",
            "markdown": {"title": title or "通知", "text": content}
        }
        resp = _http_post_json(url, payload)
        return self._parse_response(resp)

    def _parse_response(self, resp: dict) -> dict:
        if not resp["ok"]:
            return {"success": False, "message": f"钉钉请求失败: {resp.get('error', '未知错误')}"}
        data = resp.get("data", {})
        errcode = data.get("errcode", 0)
        if errcode == 0:
            return {"success": True, "message": "钉钉消息发送成功"}
        errmsg = data.get("errmsg", "未知错误")
        return {"success": False, "message": f"钉钉返回错误 (errcode={errcode}): {errmsg}"}


# ============================================================
# 企业微信 (WeCom / WeChat Work)
# ============================================================

class WeComNotifier(ChannelNotifier):
    """企业微信渠道通知器 — 通过应用消息接口推送"""

    channel_name = "wecom"
    display_name = "企业微信"

    # access_token 缓存: {secret: (token, expire_time)}
    _token_cache: dict = {}

    def __init__(self, config: dict):
        super().__init__(config)
        self._apply_config()

    def _apply_config(self):
        self.corp_id = self.config.get("WECOM_CORP_ID", "").strip()
        self.agent_id = self.config.get("WECOM_AGENT_ID", "").strip()
        self.secret = self.config.get("WECOM_SECRET", "").strip()

    def _clear_token_cache(self):
        """凭证变更后清除缓存的 access_token。"""
        cache_key = f"{self.corp_id}:{self.secret}"
        self._token_cache.pop(cache_key, None)

    def _get_required_fields(self) -> list:
        filled = []
        if self.corp_id:
            filled.append("WECOM_CORP_ID")
        if self.agent_id:
            filled.append("WECOM_AGENT_ID")
        if self.secret:
            filled.append("WECOM_SECRET")
        return filled

    def is_configured(self) -> bool:
        return self.enabled and bool(self.corp_id) and bool(self.secret)

    def _get_access_token(self) -> dict:
        """获取企业微信 access_token，带缓存。
        Returns: {"success": bool, "token": str, "message": str}
        """
        if not self.corp_id or not self.secret:
            return {"success": False, "token": "", "message": "企业微信 Corp ID 或 Secret 未配置"}

        cache_key = f"{self.corp_id}:{self.secret}"
        cached = self._token_cache.get(cache_key)
        if cached and cached[1] > time.time():
            return {"success": True, "token": cached[0], "message": "使用缓存 token"}

        url = (
            f"https://qyapi.weixin.qq.com/cgi-bin/gettoken"
            f"?corpid={urllib.parse.quote(self.corp_id)}"
            f"&corpsecret={urllib.parse.quote(self.secret)}"
        )
        resp = _http_get_json(url)
        if not resp["ok"]:
            return {"success": False, "token": "", "message": f"获取 token 失败: {resp.get('error')}"}
        data = resp.get("data", {})
        errcode = data.get("errcode", 0)
        if errcode != 0:
            errmsg = data.get("errmsg", "未知错误")
            return {"success": False, "token": "", "message": f"获取 token 失败 (errcode={errcode}): {errmsg}"}
        token = data.get("access_token", "")
        expires_in = data.get("expires_in", 7200)
        # 提前 5 分钟过期
        self._token_cache[cache_key] = (token, time.time() + expires_in - 300)
        return {"success": True, "token": token, "message": "获取 token 成功"}

    def test_connection(self) -> dict:
        if not self.is_configured():
            return {"success": False, "message": "企业微信渠道未配置 Corp ID / Secret"}
        token_result = self._get_access_token()
        if token_result["success"]:
            agent_info = f", Agent ID: {self.agent_id}" if self.agent_id else ""
            return {"success": True, "message": f"企业微信 access_token 获取成功 (Corp ID: {self.corp_id[:8]}***{agent_info})"}
        return {"success": False, "message": token_result["message"]}

    def send_text(self, content: str, title: str = None, touser: str = "@all") -> dict:
        if not self.is_configured():
            return {"success": False, "message": "企业微信渠道未配置"}
        if not self.agent_id:
            return {"success": False, "message": "企业微信 Agent ID 未配置，无法发送应用消息"}

        token_result = self._get_access_token()
        if not token_result["success"]:
            return {"success": False, "message": token_result["message"]}

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token_result['token']}"
        text_content = f"{title}\n{content}" if title else content
        payload = {
            "touser": touser,
            "msgtype": "text",
            "agentid": int(self.agent_id) if self.agent_id.isdigit() else self.agent_id,
            "text": {"content": text_content}
        }
        resp = _http_post_json(url, payload)
        return self._parse_response(resp)

    def send_markdown(self, content: str, title: str = None, touser: str = "@all") -> dict:
        if not self.is_configured():
            return {"success": False, "message": "企业微信渠道未配置"}
        if not self.agent_id:
            return {"success": False, "message": "企业微信 Agent ID 未配置"}

        token_result = self._get_access_token()
        if not token_result["success"]:
            return {"success": False, "message": token_result["message"]}

        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token_result['token']}"
        md_content = f"# {title}\n\n{content}" if title else content
        payload = {
            "touser": touser,
            "msgtype": "markdown",
            "agentid": int(self.agent_id) if self.agent_id.isdigit() else self.agent_id,
            "markdown": {"content": md_content}
        }
        resp = _http_post_json(url, payload)
        return self._parse_response(resp)

    def _parse_response(self, resp: dict) -> dict:
        if not resp["ok"]:
            return {"success": False, "message": f"企业微信请求失败: {resp.get('error', '未知错误')}"}
        data = resp.get("data", {})
        errcode = data.get("errcode", 0)
        if errcode == 0:
            return {"success": True, "message": "企业微信消息发送成功"}
        errmsg = data.get("errmsg", "未知错误")
        return {"success": False, "message": f"企业微信返回错误 (errcode={errcode}): {errmsg}"}


# ============================================================
# 微信公众号 (WeChat Official Account)
# ============================================================

class WeChatNotifier(ChannelNotifier):
    """微信公众号渠道通知器 — 通过客服消息接口推送"""

    channel_name = "wechat"
    display_name = "微信"

    _token_cache: dict = {}

    def __init__(self, config: dict):
        super().__init__(config)
        self._apply_config()

    def _apply_config(self):
        self.app_id = self.config.get("WECHAT_APP_ID", "").strip()
        self.app_secret = self.config.get("WECHAT_APP_SECRET", "").strip()
        self.token = self.config.get("WECHAT_TOKEN", "").strip()
        self.encoding_aes_key = self.config.get("WECHAT_ENCODING_AES_KEY", "").strip()

    def _clear_token_cache(self):
        """凭证变更后清除缓存的 access_token。"""
        cache_key = f"{self.app_id}:{self.app_secret}"
        self._token_cache.pop(cache_key, None)

    def _get_required_fields(self) -> list:
        filled = []
        if self.app_id:
            filled.append("WECHAT_APP_ID")
        if self.app_secret:
            filled.append("WECHAT_APP_SECRET")
        if self.token:
            filled.append("WECHAT_TOKEN")
        if self.encoding_aes_key:
            filled.append("WECHAT_ENCODING_AES_KEY")
        return filled

    def is_configured(self) -> bool:
        return self.enabled and bool(self.app_id) and bool(self.app_secret)

    def _get_access_token(self) -> dict:
        """获取微信公众号 access_token。"""
        if not self.app_id or not self.app_secret:
            return {"success": False, "token": "", "message": "微信公众号 App ID 或 App Secret 未配置"}

        cache_key = f"{self.app_id}:{self.app_secret}"
        cached = self._token_cache.get(cache_key)
        if cached and cached[1] > time.time():
            return {"success": True, "token": cached[0], "message": "使用缓存 token"}

        url = (
            f"https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential"
            f"&appid={urllib.parse.quote(self.app_id)}"
            f"&secret={urllib.parse.quote(self.app_secret)}"
        )
        resp = _http_get_json(url)
        if not resp["ok"]:
            return {"success": False, "token": "", "message": f"获取 token 失败: {resp.get('error')}"}
        data = resp.get("data", {})
        if "access_token" not in data:
            errcode = data.get("errcode", 0)
            errmsg = data.get("errmsg", "未知错误")
            return {"success": False, "token": "", "message": f"获取 token 失败 (errcode={errcode}): {errmsg}"}
        token = data["access_token"]
        expires_in = data.get("expires_in", 7200)
        self._token_cache[cache_key] = (token, time.time() + expires_in - 300)
        return {"success": True, "token": token, "message": "获取 token 成功"}

    def test_connection(self) -> dict:
        if not self.is_configured():
            return {"success": False, "message": "微信公众号渠道未配置 App ID / App Secret"}
        token_result = self._get_access_token()
        if token_result["success"]:
            return {"success": True, "message": f"微信公众号 access_token 获取成功 (App ID: {self.app_id[:6]}***)"}
        return {"success": False, "message": token_result["message"]}

    def send_text(self, content: str, title: str = None, touser: str = None) -> dict:
        """发送客服文本消息。
        Args:
            content: 消息内容
            title: 标题（将合并到内容中）
            touser: 接收用户的 openid，如果为 None 则需要调用方指定
        """
        if not self.is_configured():
            return {"success": False, "message": "微信公众号渠道未配置"}
        if not touser:
            return {"success": False, "message": "微信公众号推送需要指定接收用户的 openid (touser 参数)"}

        token_result = self._get_access_token()
        if not token_result["success"]:
            return {"success": False, "message": token_result["message"]}

        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={token_result['token']}"
        text_content = f"{title}\n{content}" if title else content
        payload = {
            "touser": touser,
            "msgtype": "text",
            "text": {"content": text_content}
        }
        resp = _http_post_json(url, payload)
        return self._parse_response(resp)

    def send_markdown(self, content: str, title: str = None, touser: str = None) -> dict:
        """微信公众号客服消息不支持 Markdown，回退为文本。"""
        return self.send_text(content, title, touser)

    def _parse_response(self, resp: dict) -> dict:
        if not resp["ok"]:
            return {"success": False, "message": f"微信请求失败: {resp.get('error', '未知错误')}"}
        data = resp.get("data", {})
        errcode = data.get("errcode", 0)
        if errcode == 0:
            return {"success": True, "message": "微信公众号消息发送成功"}
        errmsg = data.get("errmsg", "未知错误")
        return {"success": False, "message": f"微信返回错误 (errcode={errcode}): {errmsg}"}


# ============================================================
# 工厂方法 & 批量推送
# ============================================================

# 渠道类映射
CHANNEL_CLASSES = {
    "feishu": FeishuNotifier,
    "dingtalk": DingTalkNotifier,
    "wecom": WeComNotifier,
    "wechat": WeChatNotifier,
}

# 各渠道需要读取的环境变量名
CHANNEL_ENV_KEYS = {
    "feishu": ["FEISHU_WEBHOOK_URL", "FEISHU_BOT_SECRET"],
    "dingtalk": ["DINGTALK_APP_KEY", "DINGTALK_APP_SECRET", "DINGTALK_WEBHOOK_URL"],
    "wecom": ["WECOM_CORP_ID", "WECOM_AGENT_ID", "WECOM_SECRET"],
    "wechat": ["WECHAT_APP_ID", "WECHAT_APP_SECRET", "WECHAT_TOKEN", "WECHAT_ENCODING_AES_KEY"],
}


def _load_channel_config(channel: str, env: dict = None) -> dict:
    """从环境变量字典中读取指定渠道的配置。"""
    if env is None:
        env = dict(os.environ)
    keys = CHANNEL_ENV_KEYS.get(channel, [])
    config = {}
    has_value = False
    for key in keys:
        val = env.get(key, "").strip()
        config[key] = val
        if val:
            has_value = True
    # 如果至少有一个值被填写，则认为该渠道已启用
    config["enabled"] = has_value
    return config


def load_notifiers(env: dict = None, channels: list = None) -> list:
    """加载所有已配置的渠道通知器。
    
    Args:
        env: 环境变量字典，默认从 os.environ 读取
        channels: 指定要加载的渠道列表，默认全部
    
    Returns:
        [ChannelNotifier, ...] 仅返回已配置（至少有一个字段非空）的通知器列表
    """
    if channels is None:
        channels = list(CHANNEL_CLASSES.keys())
    
    notifiers = []
    for channel in channels:
        if channel not in CHANNEL_CLASSES:
            continue
        config = _load_channel_config(channel, env)
        notifier = CHANNEL_CLASSES[channel](config)
        if notifier.is_configured():
            notifiers.append(notifier)
    return notifiers


def notify_all(content: str, title: str = None, markdown: bool = False,
               env: dict = None, channels: list = None) -> dict:
    """向所有已配置的渠道推送消息。
    
    Args:
        content: 消息内容
        title: 消息标题（可选）
        markdown: 是否以 Markdown 格式发送
        env: 环境变量字典
        channels: 指定渠道列表
    
    Returns:
        {channel_name: {"success": bool, "message": str}, ...}
    """
    notifiers = load_notifiers(env, channels)
    if not notifiers:
        return {"_summary": "未找到已配置的渠道，请在 .env 中设置渠道环境变量"}
    
    results = {}
    for notifier in notifiers:
        if markdown:
            result = notifier.send_markdown(content, title)
        else:
            result = notifier.send_text(content, title)
        results[notifier.channel_name] = result
    return results


def test_all(env: dict = None, channels: list = None) -> dict:
    """测试所有已配置渠道的连接。
    
    Returns:
        {channel_name: {"success": bool, "message": str}, ...}
    """
    notifiers = load_notifiers(env, channels)
    if not notifiers:
        return {"_summary": "未找到已配置的渠道"}
    
    results = {}
    for notifier in notifiers:
        results[notifier.channel_name] = notifier.test_connection()
    return results


# ============================================================
# 动态更新渠道凭证
# ============================================================

def update_channel(channel: str, new_config: dict,
                   notifiers: list = None) -> dict:
    """更新指定渠道的凭证（运行时动态更新，无需重启）。

    如果 notifiers 列表中已有该渠道的通知器，则更新它；
    如果没有，则用新配置创建一个通知器实例。

    Args:
        channel: 渠道名 (feishu / dingtalk / wecom / wechat)
        new_config: 新配置字典，只需包含要更新的字段，如:
            {"FEISHU_WEBHOOK_URL": "https://...", "FEISHU_BOT_SECRET": "new_secret"}
            也可包含 "enabled": True/False
        notifiers: 已有的通知器列表。如果为 None 则从环境变量加载。
            传入的列表会被原地修改（新增或更新元素）。

    Returns:
        {"success": bool, "message": str,
         "fields_updated": list, "is_configured": bool}
    """
    if channel not in CHANNEL_CLASSES:
        return {
            "success": False,
            "message": f"未知渠道: {channel}，可选: {', '.join(CHANNEL_CLASSES.keys())}",
            "fields_updated": [],
            "is_configured": False,
        }

    if notifiers is None:
        notifiers = load_notifiers(channels=[channel])

    # 在已有列表中查找该渠道
    notifier = next((n for n in notifiers if n.channel_name == channel), None)

    if notifier is None:
        # 不存在 → 用新配置创建
        config = dict(new_config)
        config.setdefault("enabled", True)
        notifier = CHANNEL_CLASSES[channel](config)
        notifiers.append(notifier)
        result = {
            "success": True,
            "message": f"已创建 [{notifier.display_name}] 渠道并设置凭证",
            "fields_updated": list(k for k in new_config.keys() if k != "enabled"),
            "is_configured": notifier.is_configured(),
        }
    else:
        # 已存在 → 更新凭证
        result = notifier.update_credentials(new_config)

    return result


# ============================================================
# 从 agent_config.json 加载渠道配置
# ============================================================

def load_notifiers_from_agent_config(config_path: str = None) -> list:
    """从 agent_config.json 中加载渠道配置。
    
    agent_config.json 的 channels 字段格式:
    {
      "feishu": {"enabled": true, "FEISHU_WEBHOOK_URL": "...", "FEISHU_BOT_SECRET": "..."},
      "dingtalk": {"enabled": false, ...},
      ...
    }
    """
    from pathlib import Path

    if config_path is None:
        # 按优先级查找 agent_config.json
        candidates = [
            Path.cwd() / "agent_config.json",
            Path(__file__).parent.parent / "agent_config.json",
            Path(__file__).parent / "agent_config.json",
        ]
        config_path = next((p for p in candidates if p.exists()), None)

    if config_path is None or not Path(config_path).exists():
        return []

    with open(config_path, "r", encoding="utf-8") as f:
        agent_config = json.load(f)

    channels_config = agent_config.get("channels", {})
    notifiers = []
    for channel, cfg in channels_config.items():
        if channel not in CHANNEL_CLASSES:
            continue
        if not cfg.get("enabled", False):
            continue
        notifier = CHANNEL_CLASSES[channel](cfg)
        if notifier.is_configured():
            notifiers.append(notifier)
    return notifiers


# ============================================================
# CLI 命令行入口
# ============================================================

def _print_results(results: dict, action: str):
    """格式化输出结果。"""
    print(f"\n{'=' * 50}")
    print(f"  {action}结果")
    print(f"{'=' * 50}")
    
    if "_summary" in results:
        print(f"\n  ⚠ {results['_summary']}")
        print(f"\n  提示: 请在 .env 文件中配置渠道环境变量，例如:")
        print(f"    # 飞书")
        print(f"    FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        print(f"    # 钉钉")
        print(f"    DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=xxx")
        print(f"    DINGTALK_APP_SECRET=SECxxx")
        print(f"    # 企业微信")
        print(f"    WECOM_CORP_ID=wwxxxxxxxxx")
        print(f"    WECOM_AGENT_ID=1000002")
        print(f"    WECOM_SECRET=xxxxx")
        print(f"    # 微信公众号")
        print(f"    WECHAT_APP_ID=wxxxxxxxxx")
        print(f"    WECHAT_APP_SECRET=xxxxx")
        return

    success_count = 0
    fail_count = 0
    for channel, result in results.items():
        status = "✓" if result["success"] else "✗"
        msg = result["message"]
        print(f"\n  {status} [{channel}] {msg}")
        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'─' * 50}")
    print(f"  成功: {success_count}  失败: {fail_count}  总计: {success_count + fail_count}")
    print()


def _load_env_file(env_path: str = None):
    """加载 .env 文件到环境变量（不覆盖已有的）。"""
    from pathlib import Path

    if env_path is None:
        candidates = [
            Path.cwd() / ".env",
            Path(__file__).parent / ".env",
            Path(__file__).parent.parent / ".env",
        ]
        env_path = next((p for p in candidates if p.exists()), None)

    if env_path is None or not Path(env_path).exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _save_env_keys(env_path: str, updates: dict) -> int:
    """将键值对更新到 .env 文件中（已有则替换，没有则追加）。

    Args:
        env_path: .env 文件路径
        updates: {KEY: VALUE, ...}

    Returns:
        更新的字段数量
    """
    from pathlib import Path

    path = Path(env_path)
    lines = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    remaining = dict(updates)
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            new_lines.append(f"{key}={remaining[key]}\n")
            del remaining[key]
        else:
            new_lines.append(line)

    # 追加未找到的新键
    if remaining:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append("\n# --- 动态更新添加 ---\n")
        for key, val in remaining.items():
            new_lines.append(f"{key}={val}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return len(updates)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="渠道消息推送工具 — 飞书/钉钉/企业微信/微信",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python channel_notify.py test                      测试所有已配置渠道
  python channel_notify.py test feishu               仅测试飞书
  python channel_notify.py send "消息内容"           发送文本到所有渠道
  python channel_notify.py send "消息" -c dingtalk   仅发送到钉钉
  python channel_notify.py send "消息" --markdown    以 Markdown 格式发送
  python channel_notify.py list                      列出已配置的渠道
  python channel_notify.py send "消息" --touser openid  指定微信接收人
  python channel_notify.py update feishu FEISHU_WEBHOOK_URL=https://... FEISHU_BOT_SECRET=xxx
  python channel_notify.py update feishu FEISHU_WEBHOOK_URL=https://... --test
  python channel_notify.py update feishu FEISHU_BOT_SECRET=new --save  持久化到 .env
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # test 子命令
    test_parser = subparsers.add_parser("test", help="测试渠道连接")
    test_parser.add_argument("channel", nargs="?", default=None,
                             choices=["feishu", "dingtalk", "wecom", "wechat"],
                             help="指定单个渠道测试（默认全部）")

    # send 子命令
    send_parser = subparsers.add_parser("send", help="发送消息")
    send_parser.add_argument("content", help="消息内容")
    send_parser.add_argument("-t", "--title", default=None, help="消息标题")
    send_parser.add_argument("-c", "--channel", default=None,
                             choices=["feishu", "dingtalk", "wecom", "wechat"],
                             help="指定单个渠道发送（默认全部）")
    send_parser.add_argument("--markdown", action="store_true", help="以 Markdown 格式发送")
    send_parser.add_argument("--touser", default=None,
                             help="指定接收人 (企业微信/微信的用户ID或openid)")

    # list 子命令
    subparsers.add_parser("list", help="列出已配置的渠道")

    # update 子命令
    update_parser = subparsers.add_parser("update", help="动态更新渠道凭证")
    update_parser.add_argument("channel",
                               choices=["feishu", "dingtalk", "wecom", "wechat"],
                               help="要更新的渠道")
    update_parser.add_argument("pairs", nargs="+", metavar="KEY=VALUE",
                               help="要更新的字段，如 FEISHU_WEBHOOK_URL=https://...")
    update_parser.add_argument("--test", action="store_true",
                               help="更新后立即测试连接")
    update_parser.add_argument("--save", action="store_true",
                               help="持久化更新到 .env 文件")

    # 环境变量文件路径
    parser.add_argument("--env-file", default=None, help=".env 文件路径")
    parser.add_argument("--config", default=None, help="agent_config.json 路径")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 加载 .env
    _load_env_file(args.env_file)

    # 确定渠道列表
    channels = [args.channel] if hasattr(args, "channel") and args.channel else None

    if args.command == "list":
        notifiers = load_notifiers(channels=channels)
        if not notifiers:
            # 也尝试从 agent_config.json 加载
            notifiers = load_notifiers_from_agent_config(args.config)
        
        print(f"\n{'=' * 50}")
        print(f"  已配置的渠道")
        print(f"{'=' * 50}")
        if not notifiers:
            print("\n  未找到已配置的渠道。")
            print("\n  请在 .env 文件中配置以下环境变量:")
            for ch, keys in CHANNEL_ENV_KEYS.items():
                display = CHANNEL_CLASSES[ch].display_name
                print(f"\n  [{display}]")
                for key in keys:
                    print(f"    {key}=")
        else:
            for n in notifiers:
                fields = n._get_required_fields()
                print(f"\n  ✓ [{n.display_name}] ({n.channel_name})")
                for key in CHANNEL_ENV_KEYS[n.channel_name]:
                    val = n.config.get(key, "")
                    masked = val[:8] + "***" if len(val) > 8 else ("***" if val else "(空)")
                    print(f"    {key} = {masked}")
        print()
        return

    if args.command == "test":
        results = test_all(channels=channels)
        _print_results(results, "连接测试")
        return

    if args.command == "send":
        # 特殊处理：如果指定了 touser，需要对 wecom/wechat 传递 touser 参数
        if args.touser:
            notifiers = load_notifiers(channels=channels)
            if not notifiers:
                print("未找到已配置的渠道")
                return
            results = {}
            for n in notifiers:
                if isinstance(n, (WeComNotifier, WeChatNotifier)):
                    if args.markdown:
                        results[n.channel_name] = n.send_markdown(args.content, args.title, args.touser)
                    else:
                        results[n.channel_name] = n.send_text(args.content, args.title, args.touser)
                else:
                    if args.markdown:
                        results[n.channel_name] = n.send_markdown(args.content, args.title)
                    else:
                        results[n.channel_name] = n.send_text(args.content, args.title)
            _print_results(results, "消息发送")
        else:
            results = notify_all(args.content, args.title, args.markdown, channels=channels)
            _print_results(results, "消息发送")
        return

    if args.command == "update":
        # 解析 KEY=VALUE 对
        new_config = {}
        for pair in args.pairs:
            if "=" not in pair:
                print(f"  ⚠ 忽略无效参数: {pair} (格式应为 KEY=VALUE)")
                continue
            key, _, val = pair.partition("=")
            new_config[key.strip()] = val.strip()

        if not new_config:
            print("  ⚠ 未提供任何要更新的字段")
            return

        # 加载已有的通知器（包括从 agent_config.json）
        notifiers = load_notifiers(channels=[args.channel])
        if not notifiers:
            notifiers = load_notifiers_from_agent_config(args.config)
            notifiers = [n for n in notifiers if n.channel_name == args.channel]

        # 调用 update_channel 更新或创建
        result = update_channel(args.channel, new_config, notifiers)

        print(f"\n{'=' * 50}")
        print(f"  凭证更新 — {CHANNEL_CLASSES[args.channel].display_name}")
        print(f"{'=' * 50}")
        print(f"\n  {'✓' if result['success'] else '✗'} {result['message']}")
        print(f"  已配置: {'是' if result['is_configured'] else '否'}")

        # 打印更新后的脱敏配置
        notifier = next((n for n in notifiers if n.channel_name == args.channel), None)
        if notifier:
            print(f"\n  当前配置:")
            for key, val in notifier.get_masked_config().items():
                if key == "enabled":
                    continue
                print(f"    {key} = {val}")

        # 可选：更新后立即测试
        if args.test and result["is_configured"] and notifier:
            print(f"\n  正在测试连接...")
            test_result = notifier.test_connection()
            status = "✓" if test_result["success"] else "✗"
            print(f"  {status} {test_result['message']}")

        # 可选：保存到 .env 文件
        if args.save:
            from pathlib import Path
            env_path = args.env_file
            if env_path is None:
                candidates = [
                    Path.cwd() / ".env",
                    Path(__file__).parent.parent / ".env",
                ]
                env_path = str(next((p for p in candidates if p.exists()), candidates[0]))

            saved = _save_env_keys(env_path, new_config)
            print(f"\n  已保存 {saved} 个字段到 {env_path}")

        if not args.save:
            print(f"\n  提示: 此更新仅在内存中生效。加 --save 可持久化到 .env 文件。")

        print()
        return


if __name__ == "__main__":
    main()
