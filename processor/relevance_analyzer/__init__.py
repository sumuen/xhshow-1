"""
Excel相关性分析组件
用于分析不同数据源的Excel文件中的数据与指定关键词的相关性，并根据相关性过滤数据
"""

from .analyzer import RelevanceAnalyzer

__all__ = ['RelevanceAnalyzer'] 