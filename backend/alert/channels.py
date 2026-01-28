"""
告警渠道实现
支持邮件、Telegram、Webhook 等通知方式
"""

import asyncio
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, Any, List
from datetime import datetime

from backend.core.logger import get_logger
from .alerter import AlertChannelHandler, Alert, AlertLevel

logger = get_logger("alert_channels")


class EmailChannel(AlertChannelHandler):
    """邮件告警渠道"""
    
    def __init__(
        self,
        smtp_host: str = "",
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        sender: str = "",
        recipients: List[str] = None,
        use_tls: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender or username
        self.recipients = recipients or []
        self.use_tls = use_tls
    
    def is_configured(self) -> bool:
        return bool(
            self.smtp_host and
            self.username and
            self.password and
            self.recipients
        )
    
    def _get_level_color(self, level: AlertLevel) -> str:
        colors = {
            AlertLevel.INFO: "#3498db",
            AlertLevel.WARNING: "#f39c12",
            AlertLevel.ERROR: "#e74c3c",
            AlertLevel.CRITICAL: "#9b59b6"
        }
        return colors.get(level, "#333333")
    
    def _build_html_content(self, alert: Alert) -> str:
        color = self._get_level_color(alert.level)
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; }}
                .alert-box {{ 
                    border-left: 4px solid {color}; 
                    padding: 15px; 
                    margin: 10px 0; 
                    background: #f9f9f9; 
                }}
                .alert-title {{ 
                    color: {color}; 
                    font-size: 18px; 
                    font-weight: bold; 
                    margin-bottom: 10px; 
                }}
                .alert-message {{ 
                    color: #333; 
                    font-size: 14px; 
                    line-height: 1.5; 
                }}
                .alert-meta {{ 
                    color: #666; 
                    font-size: 12px; 
                    margin-top: 15px; 
                    border-top: 1px solid #ddd; 
                    padding-top: 10px; 
                }}
                .level-badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 3px;
                    color: white;
                    background: {color};
                    font-size: 12px;
                    margin-right: 10px;
                }}
            </style>
        </head>
        <body>
            <div class="alert-box">
                <div class="alert-title">
                    <span class="level-badge">{alert.level.value.upper()}</span>
                    {alert.title}
                </div>
                <div class="alert-message">
                    {alert.message}
                </div>
                <div class="alert-meta">
                    <strong>时间:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}<br>
                    <strong>类别:</strong> {alert.category.value}<br>
                    <strong>来源:</strong> {alert.source or 'Trading Agent'}
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    async def send(self, alert: Alert) -> bool:
        if not self.is_configured():
            logger.warning("Email channel not configured")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[{alert.level.value.upper()}] {alert.title}"
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)
            
            # 纯文本版本
            text_content = f"""
{alert.level.value.upper()}: {alert.title}

{alert.message}

时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
类别: {alert.category.value}
来源: {alert.source or 'Trading Agent'}
            """
            
            # HTML 版本
            html_content = self._build_html_content(alert)
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            # 发送邮件（使用线程池避免阻塞）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email, msg)
            
            logger.info(f"Email alert sent to {len(self.recipients)} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_email(self, msg: MIMEMultipart):
        """同步发送邮件"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)


class TelegramChannel(AlertChannelHandler):
    """Telegram 告警渠道"""
    
    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        parse_mode: str = "HTML"
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.api_base = f"https://api.telegram.org/bot{bot_token}"
    
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)
    
    def _get_level_emoji(self, level: AlertLevel) -> str:
        emojis = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        return emojis.get(level, "📢")
    
    def _format_message(self, alert: Alert) -> str:
        emoji = self._get_level_emoji(alert.level)
        
        message = f"""
{emoji} <b>{alert.level.value.upper()}: {alert.title}</b>

{alert.message}

<i>时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</i>
<i>类别: {alert.category.value}</i>
        """
        return message.strip()
    
    async def send(self, alert: Alert) -> bool:
        if not self.is_configured():
            logger.warning("Telegram channel not configured")
            return False
        
        try:
            url = f"{self.api_base}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": self._format_message(alert),
                "parse_mode": self.parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                    
                    if result.get("ok"):
                        logger.info(f"Telegram alert sent to chat {self.chat_id}")
                        return True
                    else:
                        logger.error(f"Telegram API error: {result.get('description')}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
    
    async def send_photo(self, photo_url: str, caption: str = "") -> bool:
        """发送图片（用于发送图表等）"""
        if not self.is_configured():
            return False
        
        try:
            url = f"{self.api_base}/sendPhoto"
            payload = {
                "chat_id": self.chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": self.parse_mode
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    result = await resp.json()
                    return result.get("ok", False)
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")
            return False


class WebhookChannel(AlertChannelHandler):
    """Webhook 告警渠道"""
    
    def __init__(
        self,
        url: str = "",
        headers: Dict[str, str] = None,
        method: str = "POST",
        timeout: int = 10
    ):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.method = method.upper()
        self.timeout = timeout
    
    def is_configured(self) -> bool:
        return bool(self.url)
    
    def _build_payload(self, alert: Alert) -> Dict[str, Any]:
        """构建 Webhook 请求体"""
        return {
            "alert_id": alert.id,
            "level": alert.level.value,
            "category": alert.category.value,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "source": alert.source,
            "metadata": alert.metadata
        }
    
    async def send(self, alert: Alert) -> bool:
        if not self.is_configured():
            logger.warning("Webhook channel not configured")
            return False
        
        try:
            payload = self._build_payload(alert)
            
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                
                if self.method == "POST":
                    async with session.post(
                        self.url,
                        json=payload,
                        headers=self.headers,
                        timeout=timeout
                    ) as resp:
                        success = resp.status < 400
                elif self.method == "GET":
                    async with session.get(
                        self.url,
                        params=payload,
                        headers=self.headers,
                        timeout=timeout
                    ) as resp:
                        success = resp.status < 400
                else:
                    logger.error(f"Unsupported HTTP method: {self.method}")
                    return False
                
                if success:
                    logger.info(f"Webhook alert sent to {self.url}")
                else:
                    logger.error(f"Webhook returned status {resp.status}")
                
                return success
                
        except asyncio.TimeoutError:
            logger.error(f"Webhook request timed out: {self.url}")
            return False
        except Exception as e:
            logger.error(f"Failed to send Webhook alert: {e}")
            return False


class SlackChannel(AlertChannelHandler):
    """Slack 告警渠道"""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def _get_level_color(self, level: AlertLevel) -> str:
        colors = {
            AlertLevel.INFO: "#36a64f",
            AlertLevel.WARNING: "#ffcc00",
            AlertLevel.ERROR: "#ff0000",
            AlertLevel.CRITICAL: "#8b0000"
        }
        return colors.get(level, "#808080")
    
    def _build_slack_message(self, alert: Alert) -> Dict[str, Any]:
        """构建 Slack 消息格式"""
        return {
            "attachments": [{
                "color": self._get_level_color(alert.level),
                "title": f"[{alert.level.value.upper()}] {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Category",
                        "value": alert.category.value,
                        "short": True
                    },
                    {
                        "title": "Source",
                        "value": alert.source or "Trading Agent",
                        "short": True
                    }
                ],
                "footer": "Trading Agent Alert",
                "ts": int(alert.timestamp.timestamp())
            }]
        }
    
    async def send(self, alert: Alert) -> bool:
        if not self.is_configured():
            logger.warning("Slack channel not configured")
            return False
        
        try:
            payload = self._build_slack_message(alert)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload
                ) as resp:
                    success = resp.status == 200
                    
                    if success:
                        logger.info("Slack alert sent")
                    else:
                        logger.error(f"Slack webhook returned status {resp.status}")
                    
                    return success
                    
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False


class DiscordChannel(AlertChannelHandler):
    """Discord 告警渠道"""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
    
    def is_configured(self) -> bool:
        return bool(self.webhook_url)
    
    def _get_level_color(self, level: AlertLevel) -> int:
        colors = {
            AlertLevel.INFO: 0x3498db,
            AlertLevel.WARNING: 0xf39c12,
            AlertLevel.ERROR: 0xe74c3c,
            AlertLevel.CRITICAL: 0x9b59b6
        }
        return colors.get(level, 0x808080)
    
    def _build_discord_message(self, alert: Alert) -> Dict[str, Any]:
        """构建 Discord 消息格式"""
        return {
            "embeds": [{
                "title": f"[{alert.level.value.upper()}] {alert.title}",
                "description": alert.message,
                "color": self._get_level_color(alert.level),
                "fields": [
                    {
                        "name": "Category",
                        "value": alert.category.value,
                        "inline": True
                    },
                    {
                        "name": "Source",
                        "value": alert.source or "Trading Agent",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Trading Agent Alert"
                },
                "timestamp": alert.timestamp.isoformat()
            }]
        }
    
    async def send(self, alert: Alert) -> bool:
        if not self.is_configured():
            logger.warning("Discord channel not configured")
            return False
        
        try:
            payload = self._build_discord_message(alert)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload
                ) as resp:
                    success = resp.status in [200, 204]
                    
                    if success:
                        logger.info("Discord alert sent")
                    else:
                        logger.error(f"Discord webhook returned status {resp.status}")
                    
                    return success
                    
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
