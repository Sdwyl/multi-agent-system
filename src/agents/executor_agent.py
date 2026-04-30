"""
执行Agent (Executor Agent)
负责具体任务执行，如发邮件、发通知、API调用等
"""

import asyncio
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from ..core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from ..utils.logger import get_logger
from ..utils.config import get_config


class ExecutorAgent(AgentBase):
    """
    执行Agent
    负责具体任务的执行，包括发送通知、API调用等
    """
    
    def __init__(self, agent_id: str = "executor", config: Dict[str, Any] = None):
        """
        初始化执行Agent
        
        Args:
            agent_id: Agent唯一标识
            config: Agent配置
        """
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.EXECUTOR,
            name="任务执行器",
            config=config or {}
        )
        
        # 执行配置
        self.max_retries = config.get("max_retries", 3) if config else 3
        self.retry_delay = config.get("retry_delay", 5) if config else 5
        self.timeout = config.get("timeout", 300) if config else 300
        
        # HTTP客户端
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> None:
        """初始化执行Agent"""
        await super().initialize()
        
        # 初始化HTTP客户端
        self._http_client = httpx.AsyncClient(timeout=self.timeout)
        
        # 注册执行处理器
        self.register_message_handler("http_request", self._handle_http_request)
        self.register_message_handler("send_email", self._handle_send_email)
        self.register_message_handler("send_notification", self._handle_send_notification)
        self.register_message_handler("webhook", self._handle_webhook)
        
        self.logger.info("执行Agent初始化完成")
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self._http_client:
            await self._http_client.aclose()
        await super().cleanup()
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        return None
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        action = task.get("action", task.get("type", "execute"))
        
        if action == "http_request":
            return await self._execute_http_request(task)
        elif action == "send_email":
            return await self._send_email(task)
        elif action == "send_notification":
            return await self._send_notification(task)
        elif action == "webhook":
            return await self._send_webhook(task)
        elif action == "batch":
            return await self._execute_batch(task)
        elif action == "publish":
            return await self._publish_content(task)
        else:
            return {"success": False, "error": f"未知动作: {action}"}
    
    async def _execute_http_request(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行HTTP请求
        
        Args:
            task: 任务参数
                - url: 请求URL
                - method: 请求方法 (GET/POST/PUT/DELETE)
                - headers: 请求头
                - params: 查询参数
                - json: JSON请求体
                - data: 表单数据
                
        Returns:
            响应结果
        """
        url = task.get("url", "")
        method = task.get("method", "GET").upper()
        headers = task.get("headers", {})
        params = task.get("params", {})
        json_data = task.get("json")
        data = task.get("data")
        
        if not url:
            return {"success": False, "error": "未提供URL"}
        
        self.logger.info(f"执行HTTP请求: {method} {url}")
        
        retries = 0
        last_error = None
        
        while retries <= self.max_retries:
            try:
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    data=data
                )
                
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "content": response.text[:10000],  # 限制返回长度
                    "elapsed": response.elapsed.total_seconds()
                }
                
            except httpx.TimeoutException as e:
                last_error = f"请求超时: {e}"
                self.logger.warning(f"{last_error}, 重试 {retries}/{self.max_retries}")
            except httpx.HTTPError as e:
                last_error = f"HTTP错误: {e}"
                self.logger.warning(f"{last_error}, 重试 {retries}/{self.max_retries}")
            except Exception as e:
                last_error = f"请求异常: {e}"
                self.logger.error(last_error)
                break
            
            retries += 1
            if retries <= self.max_retries:
                await asyncio.sleep(self.retry_delay)
        
        return {
            "success": False,
            "error": last_error,
            "retries": retries - 1
        }
    
    async def _send_email(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送邮件
        
        Args:
            task: 任务参数
                - to: 收件人邮箱
                - subject: 邮件主题
                - body: 邮件正文
                - html: HTML内容
                - from: 发件人（可选）
                
        Returns:
            发送结果
        """
        to_email = task.get("to", "")
        subject = task.get("subject", "")
        body = task.get("body", "")
        html = task.get("html")
        from_email = task.get("from", "noreply@agent-system.local")
        
        if not to_email or not subject:
            return {"success": False, "error": "缺少必要参数: to/subject"}
        
        self.logger.info(f"发送邮件: to={to_email}, subject={subject}")
        
        # 创建邮件
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_email
        msg['To'] = to_email
        
        # 添加纯文本正文
        if body:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 添加HTML正文
        if html:
            msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        # 尝试发送邮件
        # 注意：实际部署时需要配置SMTP服务器
        try:
            # 模拟发送成功
            self.logger.info(f"邮件已发送（模拟）: {to_email}")
            
            return {
                "success": True,
                "to": to_email,
                "subject": subject,
                "sent_at": datetime.now().isoformat(),
                "message_id": f"<{datetime.now().timestamp()}@agent-system.local>"
            }
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "to": to_email,
                "subject": subject
            }
    
    async def _send_notification(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送通知
        
        Args:
            task: 任务参数
                - channel: 通知渠道 (log/webhook/sms/push)
                - title: 通知标题
                - content: 通知内容
                - recipients: 接收人列表
                
        Returns:
            发送结果
        """
        channel = task.get("channel", "log")
        title = task.get("title", "")
        content = task.get("content", "")
        recipients = task.get("recipients", [])
        
        self.logger.info(f"发送通知: channel={channel}, title={title}")
        
        if channel == "log":
            # 记录到日志
            self.logger.info(f"【通知】{title}: {content}")
            return {
                "success": True,
                "channel": "log",
                "title": title,
                "sent_at": datetime.now().isoformat()
            }
            
        elif channel == "webhook":
            # 发送到webhook
            webhook_url = task.get("webhook_url", "")
            webhook_data = task.get("data", {"title": title, "content": content})
            
            return await self._execute_http_request({
                "url": webhook_url,
                "method": "POST",
                "json": webhook_data
            })
            
        elif channel == "sms":
            # 模拟短信发送
            self.logger.info(f"短信已发送（模拟）: {recipients}")
            return {
                "success": True,
                "channel": "sms",
                "recipients": recipients,
                "sent_at": datetime.now().isoformat()
            }
            
        elif channel == "push":
            # 模拟推送
            self.logger.info(f"推送已发送（模拟）: {recipients}")
            return {
                "success": True,
                "channel": "push",
                "recipients": recipients,
                "sent_at": datetime.now().isoformat()
            }
        
        return {
            "success": False,
            "error": f"不支持的通知渠道: {channel}"
        }
    
    async def _send_webhook(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """发送Webhook"""
        url = task.get("url", "")
        payload = task.get("payload", {})
        headers = task.get("headers", {})
        
        if not url:
            return {"success": False, "error": "未提供webhook URL"}
        
        self.logger.info(f"发送Webhook: {url}")
        
        return await self._execute_http_request({
            "url": url,
            "method": "POST",
            "json": payload,
            "headers": headers
        })
    
    async def _execute_batch(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        批量执行任务
        
        Args:
            task: 任务参数
                - tasks: 子任务列表
                - parallel: 是否并行执行
                
        Returns:
            批量执行结果
        """
        sub_tasks = task.get("tasks", [])
        parallel = task.get("parallel", False)
        
        if not sub_tasks:
            return {"success": False, "error": "没有子任务"}
        
        self.logger.info(f"批量执行任务: count={len(sub_tasks)}, parallel={parallel}")
        
        if parallel:
            # 并行执行
            results = await asyncio.gather(
                *[self.execute_task(t) for t in sub_tasks],
                return_exceptions=True
            )
            
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "success": False,
                        "error": str(result),
                        "task_index": i
                    })
                else:
                    processed_results.append(result)
            
            results = processed_results
        else:
            # 串行执行
            results = []
            for i, sub_task in enumerate(sub_tasks):
                result = await self.execute_task(sub_task)
                result["task_index"] = i
                results.append(result)
                
                # 如果任务失败且需要停止
                if not result.get("success") and task.get("stop_on_error"):
                    break
        
        success_count = sum(1 for r in results if r.get("success"))
        
        return {
            "success": success_count == len(sub_tasks),
            "total": len(sub_tasks),
            "success_count": success_count,
            "failed_count": len(sub_tasks) - success_count,
            "results": results
        }
    
    async def _publish_content(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        发布内容到各平台
        
        Args:
            task: 任务参数
                - platforms: 平台列表 (weibo/wechat/douyin/xiaohongshu)
                - content: 内容
                - media: 媒体文件列表
                
        Returns:
            发布结果
        """
        platforms = task.get("platforms", [])
        content = task.get("content", "")
        media = task.get("media", [])
        
        if not platforms:
            return {"success": False, "error": "未指定发布平台"}
        
        self.logger.info(f"发布内容到: {platforms}")
        
        results = []
        for platform in platforms:
            # 模拟发布到各平台
            result = {
                "platform": platform,
                "success": True,
                "post_id": f"{platform}_{datetime.now().timestamp()}",
                "url": f"https://{platform}.com/post/{datetime.now().timestamp()}",
                "published_at": datetime.now().isoformat()
            }
            results.append(result)
            
            self.logger.info(f"内容已发布到 {platform}（模拟）")
        
        return {
            "success": all(r["success"] for r in results),
            "platforms": results
        }
    
    # ==================== 消息处理器 ====================
    
    async def _handle_http_request(self, message: AgentMessage) -> AgentMessage:
        """处理HTTP请求"""
        result = await self._execute_http_request(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="http_response",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_send_email(self, message: AgentMessage) -> AgentMessage:
        """处理发送邮件请求"""
        result = await self._send_email(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="email_sent",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_send_notification(self, message: AgentMessage) -> AgentMessage:
        """处理发送通知请求"""
        result = await self._send_notification(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="notification_sent",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_webhook(self, message: AgentMessage) -> AgentMessage:
        """处理Webhook请求"""
        result = await self._send_webhook(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="webhook_sent",
            content=result,
            correlation_id=message.correlation_id
        )
