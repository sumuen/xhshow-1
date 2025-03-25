"""方舟 API 分析器实现"""
import os
import json
import re
import asyncio
from typing import List, Dict, Any, Tuple, Optional, Union
from dotenv import load_dotenv
from openai import AsyncOpenAI
from .base_analyzer import BaseAnalyzer
from .prompt_templates import RELEVANCE_USER_PROMPT, RELEVANCE_SYSTEM_PROMPT

load_dotenv()

class ArkAnalyzer(BaseAnalyzer):
    """
    方舟API分析器，用于分析文本与关键词的相关性
    
    使用方舟API进行文本相关性分析，支持批量处理和并发请求
    """
    
    def __init__(self, 
                 api_token: str = None, 
                 max_retries: int = 3, 
                 retry_delay: int = 5,
                 batch_size: int = 25, 
                 concurrent_tasks: int = 3,
                 system_prompt: str = None,
                 user_prompt_template: str = None,
                 base_url: str = "https://ark.cn-beijing.volces.com/api/v3/",
                 ARK_ENDPOINT_ID: str = "ARK_ENDPOINT_ID",
                 ARK_API_KEY: str = "ARK_API_KEY",
                 log_level: str = 'INFO'):
        """
        初始化方舟分析器
        
        Args:
            api_token: API认证token，如果为None则从环境变量读取
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
            batch_size: 每批处理的数据量
            concurrent_tasks: 并发任务数量
            system_prompt: 系统提示词，如果为None则使用默认值
            user_prompt_template: 用户提示词模板，如果为None则使用默认值
            base_url: API基础URL
            ARK_ENDPOINT_ID: 环境变量中endpoint_id的键名
            ARK_API_KEY: 环境变量中api_key的键名
            log_level: 日志级别
        """
        # 先调用父类的初始化方法，确保日志配置正确
        super().__init__(api_token, log_level)
        
        # API配置
        self.api_token = api_token or os.getenv(ARK_API_KEY)
        if not self.api_token:
            raise ValueError(f"必须提供api_token或设置{ARK_API_KEY}环境变量")
            
        self.endpoint_id = os.getenv(ARK_ENDPOINT_ID)
        if not self.endpoint_id:
            raise ValueError(f"必须设置{ARK_ENDPOINT_ID}环境变量")
            
        self.client = AsyncOpenAI(
            api_key=self.api_token,
            base_url=base_url,
        )
        
        # 性能配置
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.concurrent_tasks = concurrent_tasks
        
        # 提示词配置
        self.system_prompt = system_prompt or RELEVANCE_SYSTEM_PROMPT
        self.user_prompt_template = user_prompt_template or RELEVANCE_USER_PROMPT
        
    async def analyze_batch(self, 
                           texts: List[str], 
                           keyword: str) -> List[Dict[str, Any]]:
        """
        分析一批文本的相关性
        
        Args:
            texts: 文本列表
            keyword: 关键词
            
        Returns:
            List[Dict[str, Any]]: 分析结果列表
        """
        if not texts or not keyword:
            self._log("输入为空，返回空结果")
            return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(len(texts))]
            
        # 格式化文本列表
        formatted_texts = [f"{i+1}. {text}" for i, text in enumerate(texts)]
        
        # 构建提示词
        user_prompt = self.user_prompt_template.format(
            source_texts="\n".join(formatted_texts),
            search_keyword=keyword
        )

        self._log(f"发送方舟API请求，关键词: {keyword}, 数据量: {len(texts)}")
        
        # 尝试请求API
        for attempt in range(self.max_retries):
            try:
                # 发送请求
                completion = await self.client.chat.completions.create(
                    model=self.endpoint_id,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                )
                
                # 记录响应内容到日志（格式化JSON）
                if hasattr(completion, 'choices') and completion.choices and hasattr(completion.choices[0], 'message'):
                    response_content = completion.choices[0].message.content
                    try:
                        # 尝试解析并格式化JSON
                        json_data = json.loads(response_content)
                        formatted_json = json.dumps(json_data, ensure_ascii=False, indent=2)
                        self._log(f"API响应内容(JSON格式):\n{formatted_json[:1000]}{'...' if len(formatted_json) > 1000 else ''}")
                    except json.JSONDecodeError:
                        # 如果不是JSON，直接输出文本
                        self._log(f"API响应内容(文本格式):\n{response_content[:500]}{'...' if len(response_content) > 500 else ''}")
                else:
                    self._log("API响应没有有效内容", 'warning')
                
                # 解析响应
                results = self._parse_response(completion, len(texts))
                
                # 检查是否有实际错误需要重试（不再使用need_retry标志）
                if self._should_retry_response(results) and attempt < self.max_retries - 1:
                    self._log(f"检测到无效结果，进行第 {attempt + 2}/{self.max_retries} 次请求")
                    await asyncio.sleep(self.retry_delay)
                    continue
                
                return results
                
            except Exception as e:
                self._log(f"API请求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}", 'error')
                if attempt < self.max_retries - 1:
                    self._log(f"等待 {self.retry_delay} 秒后重试...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    self._log(f"达到最大重试次数，返回空结果")
                    return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(len(texts))]
            except KeyboardInterrupt:
                self._log("用户中断操作", 'warning')
                raise
    
    def _should_retry_response(self, results: List[Dict[str, Any]]) -> bool:
        """
        判断是否应该重试请求
        
        Args:
            results: 解析后的结果列表
            
        Returns:
            bool: 是否应该重试
        """
        # 只有在所有结果都是0分且没有解释时才重试
        all_zero = all(result.get('relevance_score', 0) == 0 for result in results)
        all_empty_explanation = all(not result.get('explanation', '') for result in results)
        
        return all_zero and all_empty_explanation
    
    async def analyze_contents(self, texts: List[str], keyword: str) -> List[Dict[str, Any]]:
        """
        批量分析文本相关性，内部控制并发
        
        Args:
            texts: 文本列表
            keyword: 关键词
            
        Returns:
            List[Dict[str, Any]]: 分析结果列表
        """
        # 将数据分成多个批次
        batches = [texts[i:i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        self._log(f"将 {len(texts)} 条数据分为 {len(batches)} 个批次进行处理")
        
        # 创建信号量控制并发
        semaphore = asyncio.Semaphore(self.concurrent_tasks)
        
        async def process_batch_with_semaphore(batch):
            async with semaphore:
                return await self.analyze_batch(batch, keyword)
        
        # 创建批处理任务
        tasks = [process_batch_with_semaphore(batch) for batch in batches]
        
        # 并发执行所有批次
        self._log(f"开始并发处理，最大并发数: {self.concurrent_tasks}")
        batch_results = await asyncio.gather(*tasks)
        
        # 合并结果
        results = []
        for batch in batch_results:
            results.extend(batch)
        
        # 确保结果数量与输入数量一致
        return results[:len(texts)]
    
    async def analyze_content(self, text: str, keyword: str) -> Dict[str, Any]:
        """
        分析单条文本相关性
        
        Args:
            text: 文本
            keyword: 关键词
            
        Returns:
            Dict[str, Any]: 分析结果
        """
        results = await self.analyze_contents([text], keyword)
        return results[0] if results else {'relevance_score': 0.0, 'explanation': ''}
    
    def _parse_response(self, response: Any, expected_count: int = 1) -> List[Dict[str, Any]]:
        """
        解析API响应
        
        Args:
            response: API响应对象
            expected_count: 预期结果数量
            
        Returns:
            List[Dict[str, Any]]: 解析后的结果列表
        """
        try:
            # 检查响应是否有效
            if not hasattr(response, 'choices') or not response.choices:
                self._log("响应中没有choices字段", 'warning')
                return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(expected_count)]
            
            # 解析结果
            results = []
            
            for choice in response.choices:
                if not hasattr(choice, 'message') or not choice.message.content:
                    continue
                
                content = choice.message.content.strip()
                
                # 尝试解析JSON格式
                try:
                    parsed_data = json.loads(content)
                    if isinstance(parsed_data, list):
                        for item in parsed_data:
                            if isinstance(item, dict):
                                # 提取相关性分数
                                relevance = item.get('relevance', '0%')
                                explanation = item.get('explanation', '')
                                
                                # 解析相关性分数
                                score = self._parse_relevance_score(relevance)
                                
                                results.append({
                                    'relevance_score': score,
                                    'explanation': explanation
                                })
                except json.JSONDecodeError:
                    # 尝试使用正则表达式解析
                    self._log("响应不是JSON格式，尝试正则表达式解析")
                    results.extend(self._parse_text_response(content, expected_count))
            
            # 处理结果数量
            if not results:
                self._log("未能解析出有效结果，返回空结果", 'warning')
                return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(expected_count)]
            
            # 补充或截断结果
            while len(results) < expected_count:
                results.append({'relevance_score': 0.0, 'explanation': ''})
            
            if len(results) > expected_count:
                results = results[:expected_count]
            
            return results
            
        except Exception as e:
            self._log(f"解析响应时出错: {str(e)}", 'error')
            return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(expected_count)]
    
    def _parse_text_response(self, content: str, expected_count: int) -> List[Dict[str, Any]]:
        """
        使用正则表达式解析文本响应
        
        Args:
            content: 响应内容
            expected_count: 预期结果数量
            
        Returns:
            List[Dict[str, Any]]: 解析后的结果列表
        """
        # 匹配格式: 1. 相关性: 85% 解释: 这是解释文本
        pattern = r'(\d+)\.\s*相关性[:：]\s*(\d+)%\s*解释[:：]\s*(.+?)(?=\d+\.\s*相关性[:：]|\Z)'
        matches = re.findall(pattern, content, re.DOTALL)
        
        if matches:
            return [
                {
                    'relevance_score': float(score_str),
                    'explanation': explanation.strip()
                }
                for _, score_str, explanation in matches
            ]
        
        # 无法解析
        self._log("无法使用正则表达式解析响应内容", 'warning')
        return [{'relevance_score': 0.0, 'explanation': ''} for _ in range(expected_count)]
    
    def _parse_relevance_score(self, relevance: Union[str, int, float]) -> float:
        """
        解析相关性分数
        
        Args:
            relevance: 原始相关性值
            
        Returns:
            float: 解析后的分数
        """
        if isinstance(relevance, str) and '%' in relevance:
            # 处理百分比格式
            try:
                return float(relevance.rstrip('%'))
            except ValueError:
                return 0.0
        elif isinstance(relevance, (int, float)):
            # 处理数字格式
            return float(relevance)
        else:
            # 无法解析
            return 0.0 