"""
景点分析命令行工具

这个脚本提供了一个命令行界面，用于执行景点分析流程。

使用方法：
    python -m learn.analyze_attraction_cmd --keyword "西湖" --spot_id "1001"
"""

import asyncio
import argparse
from pathlib import Path
import sys
from loguru import logger
from datetime import datetime
import os

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from learn.attraction_analyzer import AttractionAnalyzer

def setup_logger(log_level):
    """设置命令行工具的日志"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f'CMD_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # 移除所有默认处理器
    logger.remove()
    
    # 添加文件处理器
    logger.add(
        log_file,
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
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )
    
    # 强制所有日志输出到控制台
    # 这将创建一个简单的钩子，直接将所有消息打印到控制台
    logger_hack_id = logger.add(
        lambda msg: print(f"[LOG] {msg}", flush=True),
        level=log_level,
        format="{message}",
        filter=lambda record: record["name"].startswith("processor") or record["name"].startswith("learn")
    )
    
    # 设置环境变量，告诉所有模块应该将日志输出到控制台
    os.environ["PRINT_LOGS_TO_CONSOLE"] = "1"
    
    logger.info("命令行工具日志系统初始化完成，强制所有日志显示到控制台")

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='景点分析命令行工具')
    parser.add_argument('--keyword', required=True, help='搜索关键词')
    parser.add_argument('--spot_id', required=True, help='景点ID')
    parser.add_argument('--cookie', default="", help='小红书cookie')
    parser.add_argument('--log_level', default='INFO', help='日志级别')
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_args()
    
    # 设置命令行工具的日志
    setup_logger(args.log_level)
    
    # 打印欢迎信息
    logger.info("=" * 50)
    logger.info(f"开始分析景点: {args.keyword} (ID: {args.spot_id})")
    logger.info("=" * 50)
    
    start_time = datetime.now()
    
    # 初始化景点分析器
    analyzer = AttractionAnalyzer(log_level=args.log_level)
    
    # 运行分析
    results = await analyzer.analyze_attraction(args.keyword, args.spot_id, args.cookie)
    
    # 计算运行时间
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    # 输出详细结果
    logger.info("=" * 50)
    if results['success']:
        logger.success(f"景点 {args.keyword} 分析完成!")
        logger.info(f"搜索到 {results['note_count']} 条笔记")
        logger.info(f"其中相关笔记 {results['relevant_count']} 条")
        logger.info(f"结果文件: {results['detail_file']}")
    else:
        logger.error(f"景点 {args.keyword} 分析失败!")
    
    logger.info(f"总耗时: {int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒")
    logger.info("=" * 50)
if __name__ == "__main__":
    asyncio.run(main()) 