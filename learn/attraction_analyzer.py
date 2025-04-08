"""
景点分析流程

这个模块整合了以下功能：
1. 搜索景点相关笔记
2. 分析笔记相关性
3. 获取相关笔记详情
4. 分析发布时间，如果连续2个笔记都在2024年以前，则停止抓取

使用方法：
python -m learn.attraction_analyzer --keyword "西湖" --spot_id "1001"
"""

import asyncio
import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime
import argparse
from typing import Tuple, List, Dict, Any, Optional
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from learn.search_notes_runner import process_keyword, parse_cookie_string
from processor.relevance_analyzer.analyzer import RelevanceAnalyzer
from learn.get_note_detail_runner import NoteDetailRunner
from processor.analyzers.ark_analyzer import ArkAnalyzer

class ConsolePrintingArkAnalyzer(ArkAnalyzer):
    """ArkAnalyzer的装饰器，强制将日志输出到控制台"""
    
    def __init__(self, *args, **kwargs):
        # 保存日志级别
        self._custom_log_level = kwargs.get('log_level', 'INFO')
        super().__init__(*args, **kwargs)
        # 添加控制台输出
        self._setup_console_output()
    
    def _setup_console_output(self):
        """设置控制台输出"""
        # 确保系统模块已导入
        import sys
        
        # 添加控制台处理器
        logger.add(
            sys.stdout,
            level=self._custom_log_level,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>ArkAnalyzer</cyan> - <level>{message}</level>"
        )
        
        # 重定向原始logger的输出方法
        original_info = self.logger.info
        original_warning = self.logger.warning
        original_error = self.logger.error
        original_debug = self.logger.debug
        
        # 重写方法以同时输出到控制台
        def info_with_print(msg, *args, **kwargs):
            original_info(msg, *args, **kwargs)
            print(f"[ArkAnalyzer] INFO: {msg}")
            
        def warning_with_print(msg, *args, **kwargs):
            original_warning(msg, *args, **kwargs)
            print(f"[ArkAnalyzer] WARNING: {msg}")
            
        def error_with_print(msg, *args, **kwargs):
            original_error(msg, *args, **kwargs)
            print(f"[ArkAnalyzer] ERROR: {msg}")
            
        def debug_with_print(msg, *args, **kwargs):
            original_debug(msg, *args, **kwargs)
            if self._custom_log_level.upper() == 'DEBUG':
                print(f"[ArkAnalyzer] DEBUG: {msg}")
        
        # 替换方法
        self.logger.info = info_with_print
        self.logger.warning = warning_with_print
        self.logger.error = error_with_print
        self.logger.debug = debug_with_print

class AttractionAnalyzer:
    """景点分析器，整合搜索、相关性分析和详情获取的完整流程"""

    def __init__(self, log_level: str = 'INFO'):
        """初始化景点分析器
        
        Args:
            log_level: 日志级别
        """
        self.log_level = log_level
        self.setup_logger()
        
        # 确保processed目录存在
        self.processed_dir = Path('processed/rednote')
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化相关性分析器 - 使用修改后的相关性分析器
        self.relevance_analyzer = RelevanceAnalyzer(log_level=log_level)
        
        # 直接设置RelevanceAnalyzer的processed_dir路径
        self.relevance_analyzer.processed_dir = self.processed_dir
        
        # 替换ArkAnalyzer为控制台输出版本
        self.relevance_analyzer.analyzer = ConsolePrintingArkAnalyzer(
            log_level=log_level,
            batch_size=self.relevance_analyzer.DEFAULT_BATCH_SIZE,
            concurrent_tasks=self.relevance_analyzer.DEFAULT_CONCURRENT_TASKS
        )
        
        # 初始化笔记详情获取器
        self.note_detail_runner = NoteDetailRunner()
        
    def setup_logger(self):
        """设置日志记录器"""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f'AttractionAnalyzer_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
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
        
        # 添加控制台处理器 - 使用标准输出
        logger.add(
            sys.stdout,
            level=self.log_level,
            colorize=True,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        # 设置环境变量通知其他模块也输出到控制台
        os.environ["PRINT_LOGS_TO_CONSOLE"] = "1"
        
        # 添加一个直接打印到控制台的处理器
        logger.add(
            lambda msg: print(f"[LOG] {msg}", flush=True), 
            level=self.log_level,
            format="{message}",
            filter=lambda record: record["name"].startswith("processor") or record["name"].startswith("learn")
        )
        
        # 确保ArkAnalyzer的日志也会输出到控制台
        logger.bind(sink="attraction").info("日志系统初始化完成，强制所有日志输出到控制台")
        
    async def search_attraction_notes(self, keyword: str, attraction_id: str, cookie: str) -> str:
        """搜索景点相关的笔记
        
        Args:
            keyword: 搜索关键词
            attraction_id: 景点ID
            cookie: cookie字符串
            
        Returns:
            str: 生成的Excel文件路径
        """
        logger.info(f"开始搜索景点: {keyword} (ID: {attraction_id})")
        
        # 搜索景点相关笔记
        notes = await process_keyword(keyword, attraction_id, cookie)
        
        # 保存结果
        if notes:
            result_df = pd.DataFrame(notes)
            filename = f"{attraction_id}.xlsx"
            output_file = self.processed_dir / filename
            result_df.to_excel(output_file, index=False)
            logger.info(f"搜索结果已保存到: {output_file}, 共找到 {len(notes)} 条笔记")
            return str(output_file)
        else:
            logger.warning(f"景点 {keyword} 未找到任何笔记")
            return ""
    
    async def analyze_relevance(self, file_path: str, keyword: str) -> Optional[str]:
        """分析笔记相关性
        
        Args:
            file_path: Excel文件路径
            keyword: 分析关键词
            
        Returns:
            Optional[str]: 分析后的文件路径，如果分析失败则返回None
        """
        logger.info(f"开始分析文件 {file_path} 中笔记与关键词 '{keyword}' 的相关性")
        
        try:
            # 获取文件名
            file_name = os.path.basename(file_path)
            
            # 直接调用RelevanceAnalyzer进行分析，传递文件名
            analyzed_file, _ = await self.relevance_analyzer.analyze_excel(
                file_name, 
                "标题", 
                keyword
            )
            
            # 获取分析后的文件路径
            analyzed_path = self.processed_dir / analyzed_file
            logger.info(f"相关性分析完成，结果保存至: {analyzed_path}")
            return str(analyzed_path)
        except Exception as e:
            logger.error(f"相关性分析失败: {str(e)}")
            return None
    
    async def get_note_details(self, file_path: str) -> Optional[str]:
        """获取相关性为True的笔记详情
        
        Args:
            file_path: 相关性分析后的Excel文件路径
            
        Returns:
            Optional[str]: 详情文件路径，如果获取失败则返回None
        """
        logger.info(f"开始获取相关笔记详情: {file_path}")
        
        try:
            # 读取相关性分析后的文件
            df = pd.read_excel(file_path)
            
            # 只处理相关性为True的笔记
            df_relevant = df[df['相关性'] == True].copy()
            
            if df_relevant.empty:
                logger.warning(f"文件 {file_path} 中没有相关性为True的笔记")
                return None
            
            logger.info(f"找到 {len(df_relevant)} 条相关笔记，将获取详情")
            
            # 保存筛选后的数据
            relevant_file = file_path.replace('_analyzed.xlsx', '_relevant.xlsx')
            df_relevant.to_excel(relevant_file, index=False)
            
            # 根据发布时间排序（如果有的话）
            if '发布时间' in df_relevant.columns:
                df_relevant = df_relevant.sort_values(by='发布时间', ascending=False)
            
            # 用于跟踪连续旧帖子的计数
            consecutive_old_posts = 0
            
            # 转换时间戳判断基准
            cutoff_timestamp = int(datetime(2024, 1, 1).timestamp() * 1000)  # 转换为毫秒
            
            # 生成详情文件名
            detail_file = file_path.replace('_analyzed.xlsx', '_details.xlsx')
            
            # 检查是否已存在详情文件，如果存在则加载已有数据
            existing_details = {}
            existing_df = None
            if os.path.exists(detail_file):
                try:
                    existing_df = pd.read_excel(detail_file)
                    logger.info(f"找到已存在的详情文件 {detail_file}，包含 {len(existing_df)} 条笔记详情")
                    
                    # 如果存在UID列，将已有数据转换为字典，以UID为键
                    if 'UID' in existing_df.columns:
                        existing_details = {row['UID']: row.to_dict() for _, row in existing_df.iterrows()}
                        logger.info(f"已加载 {len(existing_details)} 条已存在的笔记详情数据")
                except Exception as e:
                    logger.warning(f"读取已存在的详情文件出错: {str(e)}，将重新创建")
            
            # 批量处理
            batch = []
            batch_size = 5
            all_processed = []
            
            # 确保NoteDetailRunner已初始化
            if not hasattr(self, 'note_detail_runner') or self.note_detail_runner is None:
                self.note_detail_runner = NoteDetailRunner()
                logger.info("重新初始化NoteDetailRunner")
            
            for index, row in df_relevant.iterrows():
                try:
                    # 确保必要的字段存在
                    if 'UID' not in row or 'xsec_token' not in row:
                        logger.warning(f"行 {index} 缺少必要的字段 UID 或 xsec_token，跳过")
                        continue
                    
                    note_id = row['UID']
                    xsec_token = row['xsec_token']
                    
                    logger.info(f"正在处理第 {index} 行，笔记ID: {note_id}")
                    
                    # 检查是否已经获取过该笔记的详情
                    if note_id in existing_details:
                        logger.info(f"笔记 {note_id} 已存在于详情文件中，跳过请求")
                        note_info = existing_details[note_id]
                        
                        # 保留原始相关性分析的信息
                        for col in df_relevant.columns:
                            if col not in note_info and col in row:
                                note_info[col] = row[col]
                        
                        # 设置爬取状态为缓存
                        note_info['爬取状态'] = 'cached'
                        
                        batch.append(note_info)
                        all_processed.append(note_info)
                        
                        # 检查已缓存数据中的发布时间
                        if '发布时间' in note_info and pd.notna(note_info['发布时间']):
                            try:
                                publish_time = int(note_info['发布时间'])
                                
                                # 检查是否是2024年之前的帖子
                                if publish_time < cutoff_timestamp:
                                    consecutive_old_posts += 1
                                    logger.info(f"缓存中笔记 {note_id} 发布于2024年前 ({publish_time}), 连续旧帖计数: {consecutive_old_posts}")
                                    
                                    # 如果连续两个帖子都是2024年前的，标记剩余帖子为unnecessary并停止抓取
                                    if consecutive_old_posts >= 2:
                                        logger.warning("检测到连续2个2024年前的帖子，将停止继续抓取")
                                        
                                        # 将剩余的帖子标记为unnecessary
                                        remaining_indices = df_relevant.index[df_relevant.index > index]
                                        if len(remaining_indices) > 0:
                                            df_relevant.loc[remaining_indices, '爬取状态'] = 'unnecessary'
                                            df_relevant.to_excel(relevant_file, index=False)
                                            logger.info(f"已将剩余 {len(remaining_indices)} 条帖子标记为unnecessary")
                                        
                                        break
                                else:
                                    consecutive_old_posts = 0  # 重置计数器
                            except (ValueError, TypeError) as e:
                                logger.warning(f"无法解析缓存中的发布时间: {note_info['发布时间']}, 错误: {str(e)}")
                        
                        # 每处理batch_size条记录保存一次
                        if len(batch) >= batch_size:
                            try:
                                # 读取当前文件内容，确保不会覆盖已有数据
                                current_df = None
                                if os.path.exists(detail_file):
                                    try:
                                        current_df = pd.read_excel(detail_file)
                                    except Exception as read_e:
                                        logger.warning(f"读取现有详情文件出错: {str(read_e)}，将创建新文件")
                                
                                # 保存数据，包括之前的内容
                                self.note_detail_runner.save_to_excel(batch, detail_file, current_df)
                                logger.info(f"已保存一批 {len(batch)} 条笔记详情")
                                batch = []  # 清空批次
                            except Exception as save_e:
                                logger.error(f"保存批次数据时出错: {str(save_e)}")
                                
                        continue  # 已处理缓存数据，继续下一条
                    
                    # 检查是否有发布时间字段
                    if '发布时间' in row and pd.notna(row['发布时间']):
                        try:
                            publish_time = int(row['发布时间'])
                            
                            # 检查是否是2024年之前的帖子
                            if publish_time < cutoff_timestamp:
                                consecutive_old_posts += 1
                                logger.info(f"笔记 {note_id} 发布于2024年前 ({publish_time}), 连续旧帖计数: {consecutive_old_posts}")
                                
                                # 如果连续两个帖子都是2024年前的，标记剩余帖子为unnecessary并停止抓取
                                if consecutive_old_posts >= 2:
                                    logger.warning("检测到连续2个2024年前的帖子，将停止继续抓取")
                                    
                                    # 将剩余的帖子标记为unnecessary
                                    remaining_indices = df_relevant.index[df_relevant.index > index]
                                    if len(remaining_indices) > 0:
                                        df_relevant.loc[remaining_indices, '爬取状态'] = 'unnecessary'
                                        df_relevant.to_excel(relevant_file, index=False)
                                        logger.info(f"已将剩余 {len(remaining_indices)} 条帖子标记为unnecessary")
                                    
                                    break
                            else:
                                consecutive_old_posts = 0  # 重置计数器
                        except (ValueError, TypeError) as e:
                            logger.warning(f"无法解析发布时间: {row['发布时间']}, 错误: {str(e)}")
                    
                    logger.info(f"正在获取笔记 {note_id} 的详情")
                    
                    # 使用可配置的方式决定是否使用代理
                    use_proxy = os.environ.get("USE_PROXY", "0") == "1"
                    proxy_config = {"http": "http://127.0.0.1:30002"} if use_proxy else None
                    
                    detail = await self.note_detail_runner.get_note_detail(note_id, xsec_token, proxy=proxy_config)
                    
                    if detail:
                        try:
                            note_info = self.note_detail_runner.format_note_detail(detail)
                            
                            # 保留原始相关性分析的信息
                            for col in df_relevant.columns:
                                if col not in note_info and col in row:
                                    note_info[col] = row[col]
                            
                            # 设置爬取状态
                            note_info['爬取状态'] = 'success'
                            
                            batch.append(note_info)
                            all_processed.append(note_info)
                            logger.info(f"成功获取笔记 {note_id} 的详细信息")
                            
                            # 获取详情中的发布时间并解析
                            if '发布时间' in note_info and pd.notna(note_info['发布时间']):
                                try:
                                    publish_time = int(note_info['发布时间'])
                                    
                                    # 更新发布时间到原始DataFrame
                                    df_relevant.loc[index, '发布时间'] = publish_time
                                    
                                    # 检查是否是2024年之前的帖子
                                    if publish_time < cutoff_timestamp:
                                        consecutive_old_posts += 1
                                        logger.info(f"详情中笔记 {note_id} 发布于2024年前 ({publish_time}), 连续旧帖计数: {consecutive_old_posts}")
                                        
                                        # 如果连续两个帖子都是2024年前的，标记剩余帖子为unnecessary并停止抓取
                                        if consecutive_old_posts >= 2:
                                            logger.warning("检测到连续2个2024年前的帖子，将停止继续抓取")
                                            
                                            # 将剩余的帖子标记为unnecessary
                                            remaining_indices = df_relevant.index[df_relevant.index > index]
                                            if len(remaining_indices) > 0:
                                                df_relevant.loc[remaining_indices, '爬取状态'] = 'unnecessary'
                                                df_relevant.to_excel(relevant_file, index=False)
                                                logger.info(f"已将剩余 {len(remaining_indices)} 条帖子标记为unnecessary")
                                            
                                            break
                                    else:
                                        consecutive_old_posts = 0  # 重置计数器
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"无法解析详情中的发布时间: {note_info['发布时间']}, 错误: {str(e)}")
                            
                            # 每处理batch_size条记录保存一次
                            if len(batch) >= batch_size:
                                try:
                                    # 读取当前文件内容，确保不会覆盖已有数据
                                    current_df = None
                                    if os.path.exists(detail_file):
                                        try:
                                            current_df = pd.read_excel(detail_file)
                                        except Exception as read_e:
                                            logger.warning(f"读取现有详情文件出错: {str(read_e)}，将创建新文件")
                                    
                                    # 保存数据，包括之前的内容
                                    self.note_detail_runner.save_to_excel(batch, detail_file, current_df)
                                    logger.info(f"已保存一批 {len(batch)} 条笔记详情")
                                    batch = []  # 清空批次
                                except Exception as save_e:
                                    logger.error(f"保存批次数据时出错: {str(save_e)}")
                                
                        except Exception as format_e:
                            logger.error(f"处理笔记 {note_id} 详情时出错: {str(format_e)}")
                    else:
                        logger.warning(f"未能获取笔记 {note_id} 的详情")
                        # 标记为获取失败
                        df_relevant.loc[index, '爬取状态'] = 'failed'
                
                except Exception as row_e:
                    logger.error(f"处理行 {index} 时出错: {str(row_e)}")
                
                # 添加延时避免请求过快
                await asyncio.sleep(3)
            
            # 保存最后一批数据
            if batch:
                try:
                    # 读取当前文件内容，确保不会覆盖已有数据
                    current_df = None
                    if os.path.exists(detail_file):
                        try:
                            current_df = pd.read_excel(detail_file)
                        except Exception as read_e:
                            logger.warning(f"读取现有详情文件出错: {str(read_e)}，将创建新文件")
                    
                    # 保存数据，包括之前的内容
                    self.note_detail_runner.save_to_excel(batch, detail_file, current_df)
                    logger.info(f"最后一批数据已保存，共 {len(batch)} 条")
                except Exception as e:
                    logger.error(f"保存最后一批数据出错: {str(e)}")
            
            # 更新并保存相关性文件
            df_relevant.to_excel(relevant_file, index=False)
            
            # 返回详情文件路径
            if all_processed:
                logger.info(f"成功获取 {len(all_processed)} 条笔记详情，结果保存到 {detail_file}")
                return detail_file
            else:
                # 如果没有处理任何笔记，但文件已存在，说明之前可能已经处理过
                if os.path.exists(detail_file):
                    logger.info(f"未处理任何新笔记，但文件 {detail_file} 已存在，可能之前已处理过")
                    return detail_file
                
                logger.warning("未成功获取任何笔记详情")
                return None
            
        except Exception as e:
            logger.error(f"获取笔记详情失败: {str(e)}")
            return None
    
    async def analyze_attraction(self, keyword: str, attraction_id: str, cookie: str) -> Dict[str, Any]:
        """执行完整的景点分析流程
        
        Args:
            keyword: 搜索关键词
            attraction_id: 景点ID
            cookie: cookie字符串
            
        Returns:
            Dict[str, Any]: 包含分析结果的字典
        """
        results = {
            'keyword': keyword,
            'attraction_id': attraction_id,
            'search_file': None,
            'analyzed_file': None,
            'detail_file': None,
            'success': False,
            'note_count': 0,
            'relevant_count': 0,
            'processed_count': 0
        }
        
        try:
            # 1. 搜索景点相关笔记
            search_file = await self.search_attraction_notes(keyword, attraction_id, cookie)
            if not search_file:
                logger.error(f"搜索景点 {keyword} 失败")
                return results
            
            results['search_file'] = search_file
            
            # 2. 分析笔记相关性
            analyzed_file = await self.analyze_relevance(search_file, keyword)
            if not analyzed_file:
                logger.error(f"分析文件 {search_file} 相关性失败")
                return results
            
            results['analyzed_file'] = analyzed_file
            
            # 获取相关笔记数量
            try:
                df = pd.read_excel(analyzed_file)
                results['note_count'] = len(df)
                results['relevant_count'] = len(df[df['相关性'] == True])
            except Exception as e:
                logger.error(f"读取分析结果失败: {str(e)}")
            
            # 3. 获取相关性为True的笔记详情
            detail_file = await self.get_note_details(analyzed_file)
            if detail_file:
                results['detail_file'] = detail_file
                try:
                    df_detail = pd.read_excel(detail_file)
                    results['processed_count'] = len(df_detail)
                except Exception as e:
                    logger.error(f"读取详情结果失败: {str(e)}")
            
            results['success'] = True
            return results
            
        except Exception as e:
            logger.error(f"景点分析过程中出错: {str(e)}")
            return results

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='景点分析工具')
    parser.add_argument('--keyword', required=True, help='搜索关键词')
    parser.add_argument('--spot_id', required=True, help='景点ID')
    parser.add_argument('--cookie', default="", help='小红书cookie')
    parser.add_argument('--log_level', default='INFO', help='日志级别')
    parser.add_argument('--use_proxy', action='store_true', help='是否使用代理')
    return parser.parse_args()

async def main():
    """主函数"""
    args = parse_args()
    
    # 设置代理环境变量
    if args.use_proxy:
        os.environ["USE_PROXY"] = "1"
        logger.info("已启用代理")
    else:
        os.environ["USE_PROXY"] = "0"
    
    # 初始化景点分析器
    analyzer = AttractionAnalyzer(log_level=args.log_level)
    
    # 运行分析
    results = await analyzer.analyze_attraction(args.keyword, args.spot_id, args.cookie)
    
    # 输出结果
    if results['success']:
        logger.info(f"景点 {args.keyword} 分析完成!")
        logger.info(f"搜索到 {results['note_count']} 条笔记")
        logger.info(f"其中相关笔记 {results['relevant_count']} 条")
        logger.info(f"成功获取详情 {results['processed_count']} 条")
        logger.info(f"结果文件: {results['detail_file']}")
    else:
        logger.error(f"景点 {args.keyword} 分析失败!")

if __name__ == "__main__":
    asyncio.run(main()) 