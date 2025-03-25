"""基础分析器类，定义通用接口和方法"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
from loguru import logger

class BaseAnalyzer(ABC):
    def __init__(self, api_token: str = None, log_level: str = 'INFO'):
        """
        初始化基础分析器
        
        Args:
            api_token: API认证token，如果为None则从环境变量读取
            log_level: 日志级别，默认为'INFO'
        """
        self._setup_logging(log_level)
        self.api_token = api_token
        
    def _setup_logging(self, log_level: str):
        """设置日志记录器"""
        # 使用logs目录
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        self.log_file = log_dir / f'{self.__class__.__name__}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        # 移除所有默认处理器
        logger.remove()
        
        # 添加新的日志处理器
        logger.add(
            self.log_file,
            rotation="500 MB",
            encoding="utf-8",
            enqueue=True,
            compression="zip",
            retention="10 days",
            level=log_level
        )
        
        # 保存logger实例
        self.logger = logger
        
    def _log(self, message: str, level: str = 'info') -> None:
        """记录日志"""
        getattr(self.logger, level.lower())(message)
        
    @abstractmethod
    async def analyze_content(self, text: str, keyword: str) -> Dict[str, Any]:
        """
        分析单条内容的相关性
        
        Args:
            text: 源文本
            keyword: 搜索关键词
            
        Returns:
            Dict[str, Any]: 相关性分析结果
        """
        pass
        
    @abstractmethod
    async def analyze_contents(self, texts: List[str], keyword: str) -> List[Dict[str, Any]]:
        """
        批量分析内容相关性
        
        Args:
            texts: 源文本列表
            keyword: 搜索关键词
            
        Returns:
            List[Dict[str, Any]]: 相关性分析结果列表
        """
        pass
        
    @abstractmethod
    def _parse_response(self, response: Any, expected_count: int = 1) -> List[Dict[str, Any]]:
        """
        解析API响应
        
        Args:
            response: API响应对象
            expected_count: 预期结果数量
            
        Returns:
            List[Dict[str, Any]]: 解析后的结果列表
        """
        pass
        
    def save_results(self, results: List[Dict], output_file: str) -> None:
        """
        保存分析结果到文件
        
        Args:
            results: 分析结果列表
            output_file: 输出文件路径
        """
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
                
            self._log(f"结果已保存至: {output_file}")
            
        except Exception as e:
            self._log(f"保存结果时出错: {str(e)}", 'error')
            raise
            
    def load_results(self, input_file: str) -> Optional[List[Dict]]:
        """
        从文件加载分析结果
        
        Args:
            input_file: 输入文件路径
            
        Returns:
            Optional[List[Dict]]: 加载的结果列表，如果加载失败则返回None
        """
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._log(f"加载结果时出错: {str(e)}", 'error')
            return None
            
    def validate_input(self, source_text: str, search_keyword: str) -> bool:
        """
        验证输入数据的有效性
        
        Args:
            source_text: 源文本
            search_keyword: 搜索关键词
            
        Returns:
            bool: 输入是否有效
        """
        if not source_text or not isinstance(source_text, str):
            self._log("源文本无效", 'warning')
            return False
            
        if not search_keyword or not isinstance(search_keyword, str):
            self._log("搜索关键词无效", 'warning')
            return False
            
        return True 