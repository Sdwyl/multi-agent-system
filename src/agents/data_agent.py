"""
数据分析Agent (Data Agent)
负责数据采集、统计分析、报表生成
"""

import asyncio
import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from ..utils.logger import get_logger
from ..utils.config import get_config


class DataAgent(AgentBase):
    """
    数据分析Agent
    负责数据采集、统计分析、报表生成
    """
    
    def __init__(self, agent_id: str = "data", config: Dict[str, Any] = None):
        """
        初始化数据分析Agent
        
        Args:
            agent_id: Agent唯一标识
            config: Agent配置
        """
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.DATA,
            name="数据分析器",
            config=config or {}
        )
        
        # 数据源配置
        self.data_sources = config.get("data_sources", ["internal"]) if config else ["internal"]
        self.cache_ttl = config.get("cache_ttl", 3600) if config else 3600
        
        # 数据缓存
        self._data_cache: Dict[str, Any] = {}
    
    async def initialize(self) -> None:
        """初始化数据分析Agent"""
        await super().initialize()
        
        # 注册数据处理处理器
        self.register_message_handler("collect", self._handle_collect)
        self.register_message_handler("analyze", self._handle_analyze)
        self.register_message_handler("report", self._handle_report)
        self.register_message_handler("query", self._handle_query)
        
        self.logger.info("数据分析Agent初始化完成")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        return None
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行数据分析任务"""
        action = task.get("action", task.get("type", "collect"))
        
        if action == "collect":
            return await self._collect_data(task)
        elif action == "analyze":
            return await self._analyze_data(task)
        elif action == "report":
            return await self._generate_report(task)
        elif action == "statistics":
            return await self._calculate_statistics(task)
        elif action == "trend":
            return await self._analyze_trend(task)
        elif action == "compare":
            return await self._compare_data(task)
        else:
            return {"success": False, "error": f"未知动作: {action}"}
    
    async def _collect_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        采集数据
        
        Args:
            task: 任务参数
                - source: 数据源 (internal/external)
                - data_type: 数据类型
                - filters: 过滤条件
                - time_range: 时间范围
                
        Returns:
            采集的数据
        """
        source = task.get("source", "internal")
        data_type = task.get("data_type", "general")
        filters = task.get("filters", {})
        time_range = task.get("time_range", "7d")
        
        self.logger.info(f"采集数据: source={source}, type={data_type}")
        
        # 检查缓存
        cache_key = f"{source}:{data_type}:{json.dumps(filters)}:{time_range}"
        if cache_key in self._data_cache:
            cached_data, cached_time = self._data_cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self.cache_ttl:
                self.logger.debug("从缓存返回数据")
                return {
                    "success": True,
                    "data": cached_data,
                    "from_cache": True
                }
        
        # 模拟数据采集
        await asyncio.sleep(0.5)  # 模拟耗时操作
        
        if source == "internal":
            data = self._generate_internal_data(data_type, filters, time_range)
        elif source == "external":
            data = await self._collect_external_data(data_type, filters, time_range)
        else:
            data = []
        
        # 缓存数据
        self._data_cache[cache_key] = (data, datetime.now())
        
        return {
            "success": True,
            "data": data,
            "source": source,
            "data_type": data_type,
            "count": len(data) if isinstance(data, list) else 0,
            "time_range": time_range
        }
    
    def _generate_internal_data(self, data_type: str, filters: Dict, time_range: str) -> List[Dict]:
        """生成内部测试数据"""
        count = random.randint(50, 200)
        data = []
        
        # 解析时间范围
        days = self._parse_time_range(time_range)
        base_date = datetime.now() - timedelta(days=days)
        
        for i in range(count):
            record = {
                "id": f"rec_{i+1}",
                "timestamp": (base_date + timedelta(hours=random.randint(0, days*24))).isoformat(),
                "value": round(random.uniform(10, 100), 2),
                "category": random.choice(["A", "B", "C", "D"]),
                "status": random.choice(["active", "inactive", "pending"])
            }
            
            if data_type == "user":
                record.update({
                    "user_id": f"user_{random.randint(1000, 9999)}",
                    "action": random.choice(["view", "click", "purchase"]),
                    "session_duration": random.randint(10, 600)
                })
            elif data_type == "sales":
                record.update({
                    "product_id": f"prod_{random.randint(100, 999)}",
                    "amount": round(random.uniform(50, 5000), 2),
                    "quantity": random.randint(1, 10)
                })
            
            data.append(record)
        
        return data
    
    async def _collect_external_data(self, data_type: str, filters: Dict, time_range: str) -> List[Dict]:
        """采集外部数据（模拟）"""
        # 模拟API调用
        await asyncio.sleep(1)
        
        count = random.randint(20, 100)
        return [
            {
                "id": f"ext_{i+1}",
                "source": "external_api",
                "timestamp": datetime.now().isoformat(),
                "data": f"external_data_{i+1}"
            }
            for i in range(count)
        ]
    
    def _parse_time_range(self, time_range: str) -> int:
        """解析时间范围字符串"""
        if time_range.endswith("d"):
            return int(time_range[:-1])
        elif time_range.endswith("h"):
            return int(time_range[:-1]) // 24
        elif time_range.endswith("w"):
            return int(time_range[:-1]) * 7
        elif time_range.endswith("m"):
            return int(time_range[:-1]) * 30
        return 7  # 默认7天
    
    async def _analyze_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析数据
        
        Args:
            task: 任务参数
                - data: 分析数据
                - analysis_type: 分析类型 (correlation/aggregation/classification)
                
        Returns:
            分析结果
        """
        data = task.get("data", [])
        analysis_type = task.get("analysis_type", "basic")
        
        if not data:
            return {"success": False, "error": "没有数据可供分析"}
        
        self.logger.info(f"分析数据: type={analysis_type}, count={len(data)}")
        
        # 根据分析类型执行分析
        if analysis_type == "correlation":
            result = self._correlation_analysis(data)
        elif analysis_type == "aggregation":
            result = self._aggregation_analysis(data)
        elif analysis_type == "classification":
            result = self._classification_analysis(data)
        else:
            result = self._basic_analysis(data)
        
        return {
            "success": True,
            "analysis_type": analysis_type,
            "result": result,
            "record_count": len(data)
        }
    
    def _basic_analysis(self, data: List[Dict]) -> Dict[str, Any]:
        """基础分析"""
        if not data:
            return {}
        
        numeric_fields = []
        for record in data:
            for key, value in record.items():
                if isinstance(value, (int, float)) and key not in ["id"]:
                    numeric_fields.append(key)
                    break
        
        analysis = {
            "total_records": len(data),
            "numeric_fields": list(set(numeric_fields)),
            "timestamp_range": {
                "earliest": min((r.get("timestamp", "") for r in data if r.get("timestamp")), default=None),
                "latest": max((r.get("timestamp", "") for r in data if r.get("timestamp")), default=None)
            }
        }
        
        # 数值字段统计
        for field in list(set(numeric_fields))[:5]:  # 限制字段数
            values = [r.get(field, 0) for r in data if isinstance(r.get(field), (int, float))]
            if values:
                analysis[f"{field}_stats"] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": round(sum(values) / len(values), 2),
                    "count": len(values)
                }
        
        return analysis
    
    def _correlation_analysis(self, data: List[Dict]) -> Dict[str, Any]:
        """相关性分析"""
        # 简化版：查找数值字段之间的关联
        numeric_data = []
        field_names = []
        
        for record in data[:100]:  # 限制样本数
            numeric_record = {}
            for key, value in record.items():
                if isinstance(value, (int, float)):
                    numeric_record[key] = value
            if numeric_record:
                numeric_data.append(numeric_record)
                if not field_names:
                    field_names = list(numeric_record.keys())
        
        correlations = []
        for i, field1 in enumerate(field_names):
            for field2 in field_names[i+1:]:
                # 简化的相关性计算（实际应使用Pearson相关系数）
                values1 = [r.get(field1, 0) for r in numeric_data]
                values2 = [r.get(field2, 0) for r in numeric_data]
                
                avg1 = sum(values1) / len(values1) if values1 else 0
                avg2 = sum(values2) / len(values2) if values2 else 0
                
                correlations.append({
                    "field1": field1,
                    "field2": field2,
                    "correlation": round(random.uniform(-1, 1), 2)  # 模拟值
                })
        
        return {
            "correlations": correlations,
            "significant_correlations": [c for c in correlations if abs(c["correlation"]) > 0.5]
        }
    
    def _aggregation_analysis(self, data: List[Dict]) -> Dict[str, Any]:
        """聚合分析"""
        # 按类别聚合
        category_field = None
        for field in ["category", "status", "type"]:
            if data and field in data[0]:
                category_field = field
                break
        
        if not category_field:
            return {"message": "没有可聚合的分类字段"}
        
        aggregated = {}
        for record in data:
            category = record.get(category_field, "unknown")
            if category not in aggregated:
                aggregated[category] = {"count": 0, "sum": 0, "records": []}
            
            aggregated[category]["count"] += 1
            
            # 尝试累加数值字段
            for key, value in record.items():
                if isinstance(value, (int, float)):
                    aggregated[category].setdefault("sum_by_field", {})[key] = \
                        aggregated[category]["sum_by_field"].get(key, 0) + value
            
            aggregated[category]["records"].append(record["id"])
        
        return {
            "grouped_by": category_field,
            "groups": {
                k: {
                    "count": v["count"],
                    "sum": v.get("sum_by_field", {})
                }
                for k, v in aggregated.items()
            },
            "total_groups": len(aggregated)
        }
    
    def _classification_analysis(self, data: List[Dict]) -> Dict[str, Any]:
        """分类分析"""
        # 简化的分类分析
        categories = {}
        
        for record in data:
            for key, value in record.items():
                if key in ["category", "status", "type", "label"]:
                    if value not in categories:
                        categories[value] = {"count": 0, "percentage": 0}
                    categories[value]["count"] += 1
        
        total = sum(c["count"] for c in categories.values())
        for category in categories:
            categories[category]["percentage"] = round(
                categories[category]["count"] / total * 100, 2
            ) if total > 0 else 0
        
        return {
            "classifications": categories,
            "total_records": total,
            "distinct_classes": len(categories)
        }
    
    async def _generate_report(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成报表
        
        Args:
            task: 任务参数
                - report_type: 报表类型 (daily/weekly/monthly/summary)
                - data: 数据
                - format: 格式 (json/table/markdown)
                
        Returns:
            报表内容
        """
        report_type = task.get("report_type", "summary")
        data = task.get("data", [])
        report_format = task.get("format", "json")
        
        self.logger.info(f"生成报表: type={report_type}, format={report_format}")
        
        # 分析数据
        analysis = self._basic_analysis(data)
        
        # 生成报表内容
        if report_format == "markdown":
            report = self._generate_markdown_report(report_type, analysis, data)
        elif report_format == "table":
            report = self._generate_table_report(analysis, data)
        else:
            report = {
                "type": report_type,
                "generated_at": datetime.now().isoformat(),
                "analysis": analysis,
                "data_sample": data[:10] if len(data) > 10 else data
            }
        
        return {
            "success": True,
            "report": report,
            "report_type": report_type,
            "format": report_format
        }
    
    def _generate_markdown_report(self, report_type: str, analysis: Dict, data: List) -> str:
        """生成Markdown格式报表"""
        report = f"""# {report_type.capitalize()} 数据报表

## 报表概要

- **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **数据记录数**: {analysis.get('total_records', len(data))}
- **分析字段**: {', '.join(analysis.get('numeric_fields', []))}

## 数据统计

### 数值字段统计

"""
        
        for field, stats in analysis.items():
            if field.endswith("_stats"):
                report += f"""#### {field.replace('_stats', '')}

| 指标 | 值 |
|------|-----|
| 最小值 | {stats.get('min', 'N/A')} |
| 最大值 | {stats.get('max', 'N/A')} |
| 平均值 | {stats.get('avg', 'N/A')} |
| 记录数 | {stats.get('count', 'N/A')} |

"""
        
        report += """
---

*本报表由多Agent数据分析系统自动生成*
"""
        
        return report
    
    def _generate_table_report(self, analysis: Dict, data: List) -> str:
        """生成表格格式报表"""
        if not data:
            return "没有数据"
        
        # 简单表格格式
        headers = list(data[0].keys())
        rows = [[str(r.get(h, "")) for h in headers] for r in data[:20]]
        
        return {
            "headers": headers,
            "rows": rows,
            "total_rows": len(data)
        }
    
    async def _calculate_statistics(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """计算统计指标"""
        values = task.get("values", [])
        
        if not values:
            return {"success": False, "error": "没有数据"}
        
        numeric_values = [v for v in values if isinstance(v, (int, float))]
        
        if not numeric_values:
            return {"success": False, "error": "数据不是数值类型"}
        
        sorted_values = sorted(numeric_values)
        n = len(sorted_values)
        
        return {
            "success": True,
            "count": n,
            "sum": sum(sorted_values),
            "mean": round(sum(sorted_values) / n, 2),
            "median": sorted_values[n // 2],
            "min": min(sorted_values),
            "max": max(sorted_values),
            "std_dev": round(self._calculate_std_dev(sorted_values), 2)
        }
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """计算标准差"""
        n = len(values)
        if n < 2:
            return 0
        
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        return variance ** 0.5
    
    async def _analyze_trend(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """分析趋势"""
        data = task.get("data", [])
        field = task.get("field", "value")
        period = task.get("period", "daily")
        
        # 简化的趋势分析
        values = [r.get(field, 0) for r in data if isinstance(r.get(field), (int, float))]
        
        if len(values) < 2:
            return {"success": False, "error": "数据点不足"}
        
        # 计算趋势
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        change = ((second_avg - first_avg) / first_avg * 100) if first_avg != 0 else 0
        
        return {
            "success": True,
            "trend": "increasing" if change > 5 else ("decreasing" if change < -5 else "stable"),
            "change_percentage": round(change, 2),
            "first_period_avg": round(first_avg, 2),
            "second_period_avg": round(second_avg, 2),
            "analysis_field": field
        }
    
    async def _compare_data(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """对比数据"""
        data1 = task.get("data1", [])
        data2 = task.get("data2", [])
        comparison_type = task.get("comparison_type", "count")
        
        if comparison_type == "count":
            return {
                "success": True,
                "dataset1_count": len(data1),
                "dataset2_count": len(data2),
                "difference": len(data1) - len(data2)
            }
        
        # 数值对比
        analysis1 = self._basic_analysis(data1)
        analysis2 = self._basic_analysis(data2)
        
        return {
            "success": True,
            "dataset1_analysis": analysis1,
            "dataset2_analysis": analysis2
        }
    
    # ==================== 消息处理器 ====================
    
    async def _handle_collect(self, message: AgentMessage) -> AgentMessage:
        """处理数据采集请求"""
        result = await self._collect_data(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="collect_result",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_analyze(self, message: AgentMessage) -> AgentMessage:
        """处理数据分析请求"""
        result = await self._analyze_data(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="analyze_result",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_report(self, message: AgentMessage) -> AgentMessage:
        """处理报表生成请求"""
        result = await self._generate_report(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="report_result",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_query(self, message: AgentMessage) -> AgentMessage:
        """处理数据查询请求"""
        # 返回缓存的数据概览
        cache_info = {
            "cached_keys": list(self._data_cache.keys()),
            "cache_size": len(self._data_cache)
        }
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="query_result",
            content=cache_info,
            correlation_id=message.correlation_id
        )
