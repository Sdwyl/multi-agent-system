"""
内容生成Agent (Content Agent)
负责文案创作、内容生成、SEO优化等
"""

import asyncio
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from ..utils.logger import get_logger
from ..utils.config import get_config


class ContentAgent(AgentBase):
    """
    内容生成Agent
    负责各种文案和内容的生成
    """
    
    def __init__(self, agent_id: str = "content", config: Dict[str, Any] = None):
        """
        初始化内容生成Agent
        
        Args:
            agent_id: Agent唯一标识
            config: Agent配置
        """
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.CONTENT,
            name="内容生成器",
            config=config or {}
        )
        
        # LLM配置
        self.llm_config = get_config().llm
        self._llm_client = None
        
        # 内容模板
        self._templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, str]:
        """加载内容模板"""
        return {
            "article": "请根据以下主题写一篇完整的文章：\n主题：{topic}\n要求：{requirements}",
            "social_post": "请为以下产品/服务写一条社交媒体推广文案：\n产品：{product}\n风格：{style}\n字数：{length}",
            "email": "请写一封专业的商务邮件：\n主题：{subject}\n收件人：{recipient}\n内容要点：{points}",
            "seo_title": "请为以下内容生成SEO标题（不超过60字）：\n内容：{content}",
            "seo_description": "请为以下内容生成SEO描述（不超过160字）：\n内容：{content}",
            "headline": "请生成5个吸引人的标题：\n主题：{topic}",
            "summary": "请用简洁的语言总结以下内容：\n{content}"
        }
    
    async def initialize(self) -> None:
        """初始化内容生成Agent"""
        await super().initialize()
        
        # 初始化LLM客户端
        await self._init_llm_client()
        
        # 注册内容生成处理器
        self.register_message_handler("generate", self._handle_generate)
        self.register_message_handler("optimize", self._handle_optimize)
        self.register_message_handler("summarize", self._handle_summarize)
        
        self.logger.info("内容生成Agent初始化完成")
    
    async def _init_llm_client(self) -> None:
        """初始化LLM客户端"""
        try:
            # 尝试导入OpenAI客户端
            from openai import AsyncOpenAI
            
            api_key = self.llm_config.get("api_key", "")
            base_url = self.llm_config.get("base_url", "https://api.openai.com/v1")
            
            if api_key and api_key != "${OPENAI_API_KEY}":
                self._llm_client = AsyncOpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
                self.logger.info("LLM客户端初始化成功")
            else:
                self.logger.warning("未配置LLM API Key，将使用模拟模式")
                
        except ImportError:
            self.logger.warning("未安装openai库，将使用模拟模式")
        except Exception as e:
            self.logger.error(f"LLM客户端初始化失败: {e}")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        return None
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行内容生成任务"""
        action = task.get("action", task.get("type", "generate"))
        
        if action == "generate":
            return await self._generate_content(task)
        elif action == "optimize":
            return await self._optimize_content(task)
        elif action == "summarize":
            return await self._summarize_content(task)
        elif action == "seo":
            return await self._generate_seo(task)
        elif action == "social":
            return await self._generate_social_post(task)
        elif action == "email":
            return await self._generate_email(task)
        else:
            return {"success": False, "error": f"未知动作: {action}"}
    
    async def _generate_content(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成内容
        
        Args:
            task: 任务参数
                - topic: 主题
                - requirements: 特殊要求
                - content_type: 内容类型 (article/blog/post)
                - length: 长度要求
                
        Returns:
            生成的内容
        """
        topic = task.get("topic", "")
        requirements = task.get("requirements", "")
        content_type = task.get("content_type", "article")
        length = task.get("length", "medium")
        
        if not topic:
            return {"success": False, "error": "未提供主题"}
        
        self.logger.info(f"生成{content_type}内容: {topic}")
        
        # 如果配置了LLM，使用LLM生成
        if self._llm_client:
            try:
                prompt = self._build_generate_prompt(topic, requirements, content_type, length)
                response = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "content": response,
                    "topic": topic,
                    "content_type": content_type,
                    "length": length
                }
            except Exception as e:
                self.logger.error(f"LLM生成失败: {e}")
                return {"success": False, "error": str(e)}
        else:
            # 模拟模式
            return {
                "success": True,
                "content": self._generate_mock_content(topic, content_type, length),
                "topic": topic,
                "content_type": content_type,
                "length": length,
                "mock": True
            }
    
    def _build_generate_prompt(self, topic: str, requirements: str, 
                               content_type: str, length: str) -> str:
        """构建生成提示"""
        length_guide = {
            "short": "简短精炼，约200字",
            "medium": "中等长度，约500字",
            "long": "详细深入，约1000字",
            "extensive": "全面详尽，约2000字"
        }
        
        prompts = {
            "article": f"请撰写一篇关于「{topic}」的完整文章。\n"
                      f"要求：{requirements if requirements else '内容专业、结构清晰、有实用价值'}\n"
                      f"篇幅：{length_guide.get(length, length_guide['medium'])}",
                      
            "blog": f"请撰写一篇关于「{topic}」的博客文章。\n"
                   f"要求：{requirements if requirements else '轻松活泼、有个人见解、便于分享'}\n"
                   f"篇幅：{length_guide.get(length, length_guide['medium'])}",
                   
            "post": f"请撰写一条关于「{topic}」的短内容。\n"
                   f"要求：{requirements if requirements else '简洁有力、吸引眼球'}\n"
                   f"篇幅：约100-200字"
        }
        
        return prompts.get(content_type, prompts["article"])
    
    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        if not self._llm_client:
            return self._generate_mock_content(prompt, "text", "medium")
        
        try:
            response = await self._llm_client.chat.completions.create(
                model=self.llm_config.get("model", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": "你是一位专业的内容创作者，擅长撰写各类高质量内容。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.llm_config.get("temperature", 0.7),
                max_tokens=self.llm_config.get("max_tokens", 2000)
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"LLM调用失败: {e}")
            raise
    
    def _generate_mock_content(self, topic: str, content_type: str, length: str) -> str:
        """生成模拟内容（用于测试）"""
        templates = {
            "article": """# {topic}

## 引言

{topic}是当今社会中一个重要的话题。本文将深入探讨这一主题，为读者提供全面的分析和见解。

## 主要内容

### 第一部分：背景与意义

{topic}在我们的日常生活和工作中扮演着越来越重要的角色。了解其本质对于我们更好地应对挑战至关重要。

### 第二部分：核心要素

1. 关键要素一：基础认知
2. 关键要素二：实践应用
3. 关键要素三：未来发展

### 第三部分：实践建议

基于以上分析，我们提出以下建议：
- 建议一：从小事做起
- 建议二：持续学习
- 建议三：积极实践

## 结论

总的来说，{topic}是一个值得深入研究和实践的领域。希望本文能为读者提供有价值的参考。

---
*本文由多Agent系统自动生成*
""",
            "blog": """## {topic}的那些事儿

嗨，大家好！今天想和大家聊聊{topic}这个话题。

说实话，之前我对这个也不是特别了解，但深入研究后发现还挺有意思的。

### 我的几点心得

1. **不要急于求成** - 罗马不是一天建成的
2. **多尝试、多总结** - 实践出真知
3. **保持好奇心** - 好奇心是最好的老师

总的来说，这段探索之旅让我收获颇丰。如果你也有类似的经历，欢迎留言交流！

### 写在最后

希望我的分享对你有帮助，我们下次再见！

#相关内容 #分享""",
            "post": """🚀 关于「{topic}」的一些思考

最近在研究{topic}，发现这里面有很多值得深入探讨的地方。

关键点：
• 核心价值
• 实践方法
• 未来趋势

有同样兴趣的朋友，欢迎交流~ 👇

#{topic} #观点 #思考"""
        }
        
        template = templates.get(content_type, templates["article"])
        return template.format(topic=topic)
    
    async def _optimize_content(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化内容
        
        Args:
            task: 任务参数
                - content: 原始内容
                - target: 优化目标 (readability/seo/engagement)
                
        Returns:
            优化后的内容
        """
        content = task.get("content", "")
        target = task.get("target", "readability")
        
        if not content:
            return {"success": False, "error": "未提供内容"}
        
        self.logger.info(f"优化内容 (目标: {target})")
        
        if self._llm_client:
            try:
                prompt = f"请优化以下内容，优化目标：{target}\n\n原始内容：\n{content}"
                optimized = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "original": content,
                    "optimized": optimized,
                    "target": target
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": True,
                "original": content,
                "optimized": f"[优化后的{content[:50]}...]",
                "target": target,
                "mock": True
            }
    
    async def _summarize_content(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        总结内容
        
        Args:
            task: 任务参数
                - content: 原始内容
                - length: 总结长度
                
        Returns:
            总结内容
        """
        content = task.get("content", "")
        length = task.get("length", "medium")
        
        if not content:
            return {"success": False, "error": "未提供内容"}
        
        self.logger.info(f"总结内容 (长度: {length})")
        
        if self._llm_client:
            try:
                prompt = f"请用{length}长度总结以下内容：\n\n{content}"
                summary = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "summary": summary,
                    "original_length": len(content),
                    "summary_length": len(summary)
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # 简单模拟
            summary_length = {"short": 50, "medium": 150, "long": 300}.get(length, 150)
            return {
                "success": True,
                "summary": content[:summary_length] + "..." if len(content) > summary_length else content,
                "original_length": len(content),
                "summary_length": min(summary_length, len(content)),
                "mock": True
            }
    
    async def _generate_seo(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成SEO内容
        
        Args:
            task: 任务参数
                - content: 内容主题
                - keywords: 关键词
                
        Returns:
            SEO优化内容
        """
        content = task.get("content", "")
        keywords = task.get("keywords", [])
        
        self.logger.info(f"生成SEO内容: {keywords}")
        
        if self._llm_client:
            try:
                prompt = f"""请为以下内容生成SEO优化：
主题：{content}
关键词：{', '.join(keywords)}

请生成：
1. SEO标题（60字以内）
2. SEO描述（160字以内）
3. 建议的内部链接策略"""
                
                result = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "seo_title": result,
                    "seo_description": result,
                    "keywords": keywords
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": True,
                "seo_title": f"{content} - 专业指南 | 关键词优化",
                "seo_description": f"深入了解{content}，包含专业分析和实用技巧。{', '.join(keywords[:3])}等关键词全面覆盖。",
                "keywords": keywords,
                "mock": True
            }
    
    async def _generate_social_post(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """生成社交媒体帖子"""
        platform = task.get("platform", "general")
        topic = task.get("topic", "")
        style = task.get("style", "professional")
        
        if not topic:
            return {"success": False, "error": "未提供主题"}
        
        self.logger.info(f"生成社交媒体帖子: {platform}")
        
        # 平台特点
        platform_limits = {
            "twitter": {"length": 280, "hashtags": True},
            "weibo": {"length": 2000, "hashtags": True},
            "linkedin": {"length": 3000, "hashtags": True},
            "instagram": {"length": 2200, "hashtags": True},
            "general": {"length": 500, "hashtags": True}
        }
        
        limits = platform_limits.get(platform, platform_limits["general"])
        
        if self._llm_client:
            try:
                prompt = f"请为{platform}生成一条社交媒体帖子：\n主题：{topic}\n风格：{style}"
                content = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "content": content[:limits["length"]],
                    "platform": platform,
                    "topic": topic
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": True,
                "content": f"📢 {topic}\n\n今天想和大家分享关于{topic}的一些见解。\n\n欢迎留言讨论！ #话题",
                "platform": platform,
                "topic": topic,
                "mock": True
            }
    
    async def _generate_email(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """生成邮件"""
        subject = task.get("subject", "")
        recipient = task.get("recipient", "")
        points = task.get("points", [])
        
        if not subject:
            return {"success": False, "error": "未提供邮件主题"}
        
        self.logger.info(f"生成邮件: {subject}")
        
        if self._llm_client:
            try:
                prompt = f"""请撰写一封专业邮件：
主题：{subject}
收件人：{recipient}
要点：{', '.join(points) if points else '请根据主题自行组织内容'}"""
                
                content = await self._call_llm(prompt)
                
                return {
                    "success": True,
                    "subject": subject,
                    "recipient": recipient,
                    "content": content
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {
                "success": True,
                "subject": subject,
                "recipient": recipient,
                "content": f"尊敬的{recipient or '您好'}：\n\n{subject}\n\n" + "\n".join([f"- {p}" for p in points]) + "\n\n此致\n敬礼",
                "mock": True
            }
    
    # ==================== 消息处理器 ====================
    
    async def _handle_generate(self, message: AgentMessage) -> AgentMessage:
        """处理内容生成请求"""
        result = await self._generate_content(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="generation_result",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_optimize(self, message: AgentMessage) -> AgentMessage:
        """处理内容优化请求"""
        result = await self._optimize_content(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="optimize_result",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_summarize(self, message: AgentMessage) -> AgentMessage:
        """处理内容总结请求"""
        result = await self._summarize_content(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="summarize_result",
            content=result,
            correlation_id=message.correlation_id
        )
