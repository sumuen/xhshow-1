"""
批量景点分析工具

这个脚本用于批量分析多个景点，从Excel中读取景点列表，并依次进行分析。

使用方法：
    python -m learn.batch_analyze_attractions --input attractions.xlsx --cookie "your_cookie"
"""

import asyncio
import argparse
import pandas as pd
from pathlib import Path
import sys
import os
from datetime import datetime
from loguru import logger
from typing import List, Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from learn.attraction_analyzer import AttractionAnalyzer

class BatchAttractionProcessor:
    """批量景点处理器"""
    
    def __init__(self, input_file: str, cookie: str = "", log_level: str = "INFO"):
        """初始化批量景点处理器
        
        Args:
            input_file: 输入的Excel文件路径
            cookie: 小红书cookie
            log_level: 日志级别
        """
        self.input_file = input_file
        self.cookie = cookie
        self.log_level = log_level
        self.setup_logger()
        
        # 初始化景点分析器
        self.analyzer = AttractionAnalyzer(log_level=log_level)
        
    def setup_logger(self):
        """设置日志记录器"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'BatchAttraction_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
            level=self.log_level
        )
        
        # 添加控制台处理器
        logger.add(
            sys.stdout,
            level=self.log_level,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        logger.info("批量处理日志系统初始化完成")
    
    def load_attractions(self) -> List[Dict[str, str]]:
        """加载景点列表
        
        Returns:
            List[Dict[str, str]]: 景点列表
        """
        try:
            df = pd.read_excel(self.input_file)
            required_columns = ['英文关键词', '景点ID']
            
            # 检查必要的列是否存在
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"输入文件缺少必要的列: {', '.join(missing_columns)}")
                return []
            
            # 转换为字典列表
            attractions = []
            for index, row in df.iterrows():
                # 跳过任何缺少关键词或ID的行
                if pd.isna(row['英文关键词']) or pd.isna(row['景点ID']):
                    logger.warning(f"第 {index+1} 行缺少关键词或ID，跳过")
                    continue
                
                # 处理景点ID，确保它是整数字符串（移除.0）
                spot_id = row['景点ID']
                try:
                    if isinstance(spot_id, float):
                        # 如果是浮点数，转换为整数字符串
                        spot_id = str(int(spot_id))
                    elif isinstance(spot_id, (int, str)):
                        # 确保其他类型也被正确处理
                        spot_id = str(spot_id).split('.')[0]  # 移除任何可能的小数部分
                except (ValueError, TypeError) as e:
                    logger.warning(f"第 {index+1} 行景点ID格式无效: {spot_id}, 错误: {str(e)}, 跳过此行")
                    continue
                
                attraction = {
                    'keyword': row['英文关键词'],
                    'spot_id': spot_id
                }
                attractions.append(attraction)
            
            if not attractions:
                logger.warning("没有找到有效的景点数据")
                return []
                
            logger.info(f"成功加载 {len(attractions)} 个景点")
            return attractions
        except Exception as e:
            logger.error(f"加载景点列表失败: {str(e)}")
            return []
    
    async def process_attractions(self) -> List[Dict[str, Any]]:
        """处理所有景点
        
        Returns:
            List[Dict[str, Any]]: 处理结果列表
        """
        attractions = self.load_attractions()
        if not attractions:
            logger.error("未加载到任何景点，无法处理")
            return []
        
        results = []
        
        for i, attraction in enumerate(attractions):
            try:
                logger.info("=" * 50)
                logger.info(f"开始处理第 {i+1}/{len(attractions)} 个景点: {attraction['keyword']} (ID: {attraction['spot_id']})")
                logger.info("=" * 50)
                
                start_time = datetime.now()
                
                result = await self.analyzer.analyze_attraction(
                    attraction['keyword'],
                    attraction['spot_id'],
                    self.cookie
                )
                
                # 计算处理时间
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                hours, remainder = divmod(duration, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                # 添加处理时间和耗时
                result['process_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                result['duration'] = f"{int(hours)}小时 {int(minutes)}分钟 {int(seconds)}秒"
                results.append(result)
                
                # 记录结果
                if result['success']:
                    logger.success(f"景点 {attraction['keyword']} 分析完成")
                    logger.info(f"搜索到 {result['note_count']} 条笔记")
                    logger.info(f"其中相关笔记 {result['relevant_count']} 条") 
                    logger.info(f"成功获取详情 {result['processed_count']} 条")
                    if result['detail_file']:
                        logger.info(f"结果文件: {result['detail_file']}")
                else:
                    logger.error(f"景点 {attraction['keyword']} 分析失败")
                
                logger.info(f"处理耗时: {result['duration']}")
                
                # 每处理一个景点后保存一次结果
                self.save_results(results)
                
                # 在景点之间添加延时，避免过快请求
                if i < len(attractions) - 1:
                    delay = 10  # 10秒延时
                    logger.info(f"等待 {delay} 秒后处理下一个景点...")
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                logger.error(f"处理景点 {attraction['keyword']} 时发生错误: {str(e)}")
                # 记录错误结果
                error_result = {
                    'keyword': attraction['keyword'],
                    'attraction_id': attraction['spot_id'],
                    'success': False,
                    'error': str(e),
                    'process_time': datetime.now().strftime('%Y-%m-%d %H:%M%S'),
                    'note_count': 0,
                    'relevant_count': 0,
                    'processed_count': 0
                }
                results.append(error_result)
                # 保存结果，确保错误也被记录
                self.save_results(results)
                # 短暂延时后继续处理下一个景点
                await asyncio.sleep(5)
        
        return results
    
    def save_results(self, results: List[Dict[str, Any]]) -> str:
        """保存处理结果
        
        Args:
            results: 处理结果列表
            
        Returns:
            str: 结果文件路径
        """
        try:
            # 创建结果目录
            result_dir = Path('results/rednote')
            result_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成结果文件名
            result_file = result_dir / f"batch_results_{datetime.now().strftime('%Y%m%d')}.xlsx"
            
            # 转换为DataFrame
            df = pd.DataFrame(results)
            
            # 保存到Excel
            df.to_excel(result_file, index=False)
            logger.info(f"处理结果已保存到: {result_file}")
            
            return str(result_file)
        except Exception as e:
            logger.error(f"保存处理结果失败: {str(e)}")
            return ""

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='批量景点分析工具')
    parser.add_argument('--input', required=True, help='输入的Excel文件路径，包含英文关键词和ID')
    parser.add_argument('--cookie', default="", help='小红书cookie')
    parser.add_argument('--log_level', default='INFO', help='日志级别')
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_args()
    
    # 初始化批量处理器
    processor = BatchAttractionProcessor(args.input, args.cookie, args.log_level)
    
    # 处理所有景点
    results = await processor.process_attractions()
    
    # 输出总结
    print("\n=== 批量处理完成 ===")
    print(f"共处理 {len(results)} 个景点")
    
    success_count = sum(1 for r in results if r['success'])
    print(f"成功: {success_count}, 失败: {len(results) - success_count}")
    
    # 显示详细结果
    print("\n详细结果:")
    for r in results:
        status = "成功" if r['success'] else "失败"
        print(f"{r['keyword']} (ID: {r['attraction_id']}): {status}")
        if r['success']:
            print(f"  - 笔记数: {r['note_count']}, 相关笔记: {r['relevant_count']}, 处理笔记: {r['processed_count']}")

if __name__ == "__main__":
    asyncio.run(main()) 