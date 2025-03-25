"""
Excel相关性分析工具的命令行入口
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from processor.relevance_analyzer.analyzer import RelevanceAnalyzer

def main():
    """命令行入口函数"""
    analyzer = RelevanceAnalyzer()
    analyzer.run_interactive()

if __name__ == "__main__":
    main() 