"""
Excel相关性分析器模块。

本模块提供了分析Excel文件中的数据与指定关键词相关性的功能，
支持多种数据源（TripAdvisor、TikTok、Naver等），根据内容相关性过滤和处理数据。

主要功能:
- 分析不同数据源Excel文件的内容相关性
- 自动检测数据源类型
- 提取关键列用于相关性分析
- 批量处理大量数据
- 生成分析报告并保存结果
- 支持缓存已分析的结果

支持的数据源:
- tripadvisor: TripAdvisor评论数据
- tiktok: TikTok视频数据
- naver: Naver博客数据
- 4travel.jp: 日本旅游网站数据
- rednote: RedNote数据
- youtube: YouTube视频数据
- x: Twitter/X数据
- hardwarezoneForums: 硬件论坛数据
- facebook: Facebook数据
- ins: Instagram数据

依赖:
- pandas: 数据处理
- asyncio: 异步处理
- processor.analyzers.ark_analyzer: 方舟AI分析

使用示例:
    >>> from processor.relevance_analyzer.analyzer import RelevanceAnalyzer
    >>> analyzer = RelevanceAnalyzer()
    >>> output_file = await analyzer.analyze_excel(
    ...     "data/processed/tripadvisor_data.xlsx", 
    ...     "内容", 
    ...     "浙江旅游"
    ... )
"""

import os
import pandas as pd
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import json
from datetime import datetime
import glob
import sys

from processor.analyzers.ark_analyzer import ArkAnalyzer
from loguru import logger

class RelevanceAnalyzer:
    """
    Excel相关性分析器
    分析不同数据源Excel文件中的数据与指定关键词的相关性，并根据相关性过滤数据
    """
    
    # 不同数据源的特有列，用于发送给AI进行相关性分析
    SOURCE_SPECIFIC_COLUMNS_FOR_AI = {
        'tripadvisor': ['评论内容', '景点描述'],
        'tiktok': ['标签'],
        'naver': ['内容', '内容（翻译）'],
        '4travel.jp': ['内容', '标签'],
        'trip': [],
        'rednote': ['详情'],
        'youtube': ['详情'],
        'x': [],
        'hardwarezoneForums': ['详情'],
        'facebook': ['内容'],
        'ins': ['内容']
    }
    
    # 分析配置
    DEFAULT_BATCH_SIZE = 10
    DEFAULT_CONCURRENT_TASKS = 28
    RELEVANCE_THRESHOLD = 25
    
    def __init__(self, log_level: str = 'INFO'):
        """
        初始化Excel相关性分析器
        
        Args:
            log_level: 日志级别，默认为'INFO'
        """
        self._setup_logging(log_level)
        self.processed_dir = Path('processed')
        self.processed_dir.mkdir(exist_ok=True)
        self.log_level = log_level
        
        # 初始化分析器
        self.analyzer = ArkAnalyzer(
            log_level=log_level,
            batch_size=self.DEFAULT_BATCH_SIZE,
            concurrent_tasks=self.DEFAULT_CONCURRENT_TASKS
        )
        
    def _setup_logging(self, log_level: str):
        """设置日志记录器"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        self.log_file = log_dir / f'RelevanceAnalyzer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        # 移除所有默认处理器
        logger.remove()
        
        # 添加文件处理器
        logger.add(
            self.log_file,
            rotation="500 MB",
            encoding="utf-8",
            enqueue=True,
            compression="zip",
            retention="10 days",
            level=log_level
        )
        
        # 添加控制台处理器
        logger.add(
            sys.stdout,
            level=log_level,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        # 保存logger实例
        self.logger = logger
        
        # 输出初始化信息
        logger.info("RelevanceAnalyzer日志系统初始化完成")

    def _log(self, message: str, level: str = 'info') -> None:
        """记录日志，支持不同级别"""
        getattr(self.logger, level.lower())(message)

    def _find_cached_analysis(self, keyword: str) -> Optional[pd.DataFrame]:
        """
        查找已缓存的分析结果
        
        Args:
            keyword: 关键词
            
        Returns:
            Optional[pd.DataFrame]: 缓存的DataFrame，如果没有找到则返回None
        """
        # 查找所有已分析的文件
        analyzed_files = glob.glob(str(self.processed_dir / "*_analyzed.xlsx"))
        
        for file_path in analyzed_files:
            try:
                df = pd.read_excel(file_path)
                # 检查是否包含相同的关键词分析结果
                if '关键词' in df.columns and df['关键词'].iloc[0] == keyword:
                    self._log(f"找到缓存的分析结果: {file_path}")
                    return df
            except Exception as e:
                self._log(f"读取缓存文件 {file_path} 时出错: {str(e)}", 'error')
                continue
        
        return None

    def _merge_with_cache(self, new_df: pd.DataFrame, cached_df: pd.DataFrame) -> pd.DataFrame:
        """
        合并新的分析结果与缓存结果
        
        Args:
            new_df: 新的分析结果DataFrame
            cached_df: 缓存的DataFrame
            
        Returns:
            pd.DataFrame: 合并后的DataFrame
        """
        # 确保两个DataFrame都有UID列
        if 'UID' not in new_df.columns or 'UID' not in cached_df.columns:
            self._log("DataFrame中缺少UID列，无法合并缓存", 'warning')
            return new_df
            
        # 合并DataFrame，保留新的分析结果
        merged_df = pd.concat([cached_df, new_df]).drop_duplicates(subset=['UID'], keep='last')
        return merged_df
    
    def get_available_excel_files(self) -> List[str]:
        """
        获取processed目录下可用的Excel文件列表
        
        Returns:
            List[str]: Excel文件名列表
        """
        excel_files = []
        for file_path in glob.glob(str(self.processed_dir / "*.xlsx")):
            # 排除已分析和已过滤的文件
            file_name = os.path.basename(file_path)
            if not file_name.endswith(('_analyzed.xlsx', '_filtered.xlsx')):
                excel_files.append(file_name)
        
        return excel_files
    
    def detect_data_source(self, df: pd.DataFrame) -> str:
        """
        检测Excel文件的数据源
        
        Args:
            df: DataFrame对象
            
        Returns:
            str: 数据源名称
        """
        # 尝试从DataFrame中获取数据来源列
        if '数据来源' in df.columns:
            # 获取第一行的数据来源
            data_source = df['数据来源'].iloc[0]
            if isinstance(data_source, str) and data_source:
                return data_source.lower()
        
        # 如果没有数据来源列，尝试从列名推断
        column_sets = {
            'tripadvisor': {'评论内容', '景点描述', '评分'},
            'tiktok': {'点赞数', '标签', '作者'},
            'naver': {'内容', '内容（翻译）', '博客链接'},
            '4travel.jp': {'详情', '标签', '作者'},
            'trip': {'链接', '评分', '评论数'},
            'rednote': {'详情', '点赞数', '收藏数'},
            'youtube': {'播放量', '简介', '作者'},
            'x': {'转发数', '点赞数', '浏览量'},
            'hardwarezoneForums': {'服务名称', '发帖账号属性'},
            'facebook': {'内容', '点赞数', '评论数'},
            'ins': {}
        }
        
        df_columns = set(df.columns)
        best_match = None
        best_match_count = 0
        
        for source, columns in column_sets.items():
            match_count = len(columns.intersection(df_columns))
            if match_count > best_match_count:
                best_match = source
                best_match_count = match_count
        
        return best_match if best_match else 'unknown'
    
    def prepare_text_for_analysis(self, row: pd.Series, title_column: str, 
                                 source: str, specific_columns: List[str]) -> str:
        """
        准备用于分析的文本
        
        Args:
            row: DataFrame的一行
            title_column: 标题列名
            source: 数据源
            specific_columns: 特定列名列表
            
        Returns:
            str: 合并后的文本
        """
        text_parts = []
        
        # 添加标题
        if title_column in row and pd.notna(row[title_column]):
            text_parts.append(f"标题: {row[title_column]}")
        
        # 添加特定列的内容
        for col in specific_columns:
            if col in row and pd.notna(row[col]):
                text_parts.append(f"{col}: {row[col]}")
        
        return "\n".join(text_parts)
    
    async def analyze_excel(self, file_name: str, title_column: str, 
                           keyword: str, specific_columns: Optional[Dict[str, List[str]]] = None) -> Tuple[str, str]:
        """
        分析Excel文件中数据与关键词的相关性
        
        Args:
            file_name: Excel文件名
            title_column: 标题列名
            keyword: 关键词
            specific_columns: 特定列名字典，键为数据源，值为列名列表
            
        Returns:
            Tuple[str, str]: 分析后的文件名和过滤后的文件名
        """
        file_path = self.processed_dir / file_name
        self._log(f"开始分析Excel文件: {file_name}")
        
        # 读取Excel文件
        df = pd.read_excel(file_path)
        
        # 检查是否有缓存的分析结果
        cached_df = self._find_cached_analysis(keyword)
        if cached_df is not None:
            self._log("找到缓存的分析结果，将跳过已分析的数据")
            # 过滤出未分析的数据
            if 'UID' in df.columns and 'UID' in cached_df.columns:
                analyzed_uids = set(cached_df['UID'])
                new_df = df[~df['UID'].isin(analyzed_uids)].copy()
                if len(new_df) == 0:
                    self._log("所有数据都已分析过，直接使用缓存结果")
                    return self._save_results(cached_df, file_name, keyword)
            else:
                self._log("DataFrame中缺少UID列，将重新分析所有数据", 'warning')
                new_df = df
        else:
            new_df = df
        
        # 检测数据源
        source = self.detect_data_source(new_df)
        self._log(f"检测到数据源: {source}")
        
        # 确定要分析的特定列
        if specific_columns and source in specific_columns:
            columns_to_analyze = specific_columns[source]
        else:
            columns_to_analyze = self.SOURCE_SPECIFIC_COLUMNS_FOR_AI.get(source, [])
        
        self._log(f"将使用以下列进行分析: {title_column} 和 {columns_to_analyze}")
        
        # 准备分析数据
        texts_to_analyze = []
        for _, row in new_df.iterrows():
            text = self.prepare_text_for_analysis(row, title_column, source, columns_to_analyze)
            texts_to_analyze.append(text)
        
        # 批量分析 - 让ArkAnalyzer处理并发控制
        self._log(f"开始分析 {len(texts_to_analyze)} 条新数据")
        
        try:
            # 直接使用ArkAnalyzer的analyze_contents方法，让它内部处理并发和批处理
            results = await self.analyzer.analyze_contents(texts_to_analyze, keyword)
            
        except Exception as e:
            self._log(f"分析过程中出错: {str(e)}", 'error')
            # 返回空结果
            results = [{'relevance_score': 0.0, 'explanation': f'分析错误: {str(e)}'} for _ in range(len(texts_to_analyze))]
        
        # 将结果添加到DataFrame
        new_df['相关性分值'] = [result.get('relevance_score', 0.0) for result in results]
        new_df['相关性'] = new_df['相关性分值'].apply(lambda x: True if x >= self.RELEVANCE_THRESHOLD else False)
        new_df['相关性解释'] = [result.get('explanation', '') for result in results]        
        # 如果有缓存结果，合并新旧数据
        if cached_df is not None:
            final_df = self._merge_with_cache(new_df, cached_df)
        else:
            final_df = new_df
        
        return self._save_results(final_df, file_name, keyword)
    
    def _save_results(self, df: pd.DataFrame, file_name: str, keyword: str) -> Tuple[str, str]:
        """
        保存分析结果
        
        Args:
            df: 要保存的DataFrame
            file_name: 原始文件名
            keyword: 关键词
            
        Returns:
            Tuple[str, str]: 分析后的文件名和过滤后的文件名
        """
        # 保存分析结果
        analyzed_file_name = f"{os.path.splitext(file_name)[0]}_analyzed.xlsx"
        analyzed_file_path = self.processed_dir / analyzed_file_name
        df.to_excel(analyzed_file_path, index=False)
        self._log(f"分析结果已保存至: {analyzed_file_name}")
        
        # 过滤相关数据
        filtered_df = df[df['相关性'] == True].copy()
        filtered_file_name = f"{os.path.splitext(file_name)[0]}_filtered.xlsx"
        filtered_file_path = self.processed_dir / filtered_file_name
        filtered_df.to_excel(filtered_file_path, index=False)
        self._log(f"过滤后的数据已保存至: {filtered_file_name}, 共 {len(filtered_df)} 条相关数据")
        
        return analyzed_file_name, filtered_file_name
    
    def run_interactive(self):
        """
        交互式运行相关性分析
        """
        print("欢迎使用Excel相关性分析工具")
        print("=" * 50)
        
        # 获取可用的Excel文件
        excel_files = self.get_available_excel_files()
        if not excel_files:
            print("未找到可分析的Excel文件，请将文件放入processed目录")
            return
        
        # 显示可用文件
        print("可用的Excel文件:")
        for i, file_name in enumerate(excel_files, 1):
            print(f"{i}. {file_name}")
        
        # 选择文件
        while True:
            try:
                file_index = int(input("\n请选择要分析的文件编号: "))
                if 1 <= file_index <= len(excel_files):
                    selected_file = excel_files[file_index - 1]
                    break
                else:
                    print(f"请输入1-{len(excel_files)}之间的数字")
            except ValueError:
                print("请输入有效的数字")
        
        # 输入标题列名
        title_column = input("\n请输入标题列名 (默认为'标题'): ") or '标题'
        
        # 输入关键词
        keyword = input("\n请输入要分析的关键词(默认浙江旅游): ")or '浙江旅游'
        if not keyword:
            print("关键词不能为空")
            return
        
        # 询问是否自定义特定列
        custom_columns = input("\n是否要自定义特定列? (y/n, 默认为n): ").lower() == 'y'
        specific_columns = {}
        
        if custom_columns:
            # 读取Excel文件以获取数据源
            file_path = self.processed_dir / selected_file
            df = pd.read_excel(file_path)
            source = self.detect_data_source(df)
            
            print(f"\n检测到数据源: {source}")
            print(f"默认分析列: {self.SOURCE_SPECIFIC_COLUMNS_FOR_AI.get(source, [])}")
            
            columns_input = input("\n请输入要分析的列名，用逗号分隔: ")
            if columns_input:
                specific_columns[source] = [col.strip() for col in columns_input.split(',')]
        
        print("\n开始分析，请稍候...")
        
        # 运行分析
        loop = asyncio.get_event_loop()
        analyzed_file, filtered_file = loop.run_until_complete(
            self.analyze_excel(selected_file, title_column, keyword, specific_columns)
        )
        
        print("\n分析完成!")
        print(f"分析结果已保存至: {analyzed_file}")
        print(f"过滤后的数据已保存至: {filtered_file}")

if __name__ == "__main__":
    analyzer = RelevanceAnalyzer()
    analyzer.run_interactive() 