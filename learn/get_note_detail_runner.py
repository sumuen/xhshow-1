"""
获取小红书笔记详情的命令行工具
"""

import asyncio
import pandas as pd
from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Set, Dict, Any
from loguru import logger
import json
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from xhs.request.note import Notes
from xhs.request.AsyncRequestFramework import AsyncRequestFramework

class NoteDetailRunner:
    def __init__(self):
        self.processed_notes: Set[str] = set()  # 用于存储已处理的笔记ID
        self.note_details_cache: Dict[str, dict] = {}  # 用于缓存已获取的笔记详情
        
    async def get_note_detail(self, note_id: str, xsec_token: str, proxy=None):
        """获取单个笔记的详细信息
        
        Args:
            note_id: 笔记ID
            xsec_token: xsec_token
            proxy: 代理设置，例如 {"http": "http://127.0.0.1:30002"}
        """
        # 如果笔记已经处理过，直接返回缓存的结果
        if note_id in self.note_details_cache:
            logger.info(f"笔记 {note_id} 已存在于缓存中，跳过请求")
            return self.note_details_cache[note_id]
            
        try:
            arf = AsyncRequestFramework()
            # 初始化Notes请求对象
            note_request = Notes(arf)
            
            # 直接传递代理参数，不修改AsyncRequestFramework对象
            logger.debug(f"使用代理: {proxy}" if proxy else "不使用代理")
            
            # 显式传递xsec_token和proxy参数
            result = await note_request.get_note_detail(
                note_id=note_id,
                xsec_token=xsec_token,
                proxy=proxy or {}
            )
            
            # 验证返回的数据结构
            if result and isinstance(result, dict) and 'note' in result:
                self.note_details_cache[note_id] = result
                return result
            else:
                logger.error(f"笔记 {note_id} 返回的数据结构不正确")
                self._save_error_response(note_id, result, "invalid_structure")
                return None
            
        except json.JSONDecodeError as e:
            logger.error(f"笔记 {note_id} JSON解析错误: {str(e)}")
            # 保存原始响应内容
            self._save_error_response(note_id, e.doc, "json_decode_error")
            return None
        except Exception as e:
            logger.error(f"获取笔记详情出错 - 笔记ID: {note_id}, 错误: {str(e)}")
            return None

    def _save_error_response(self, note_id: str, content: Any, error_type: str) -> None:
        """保存错误响应内容
        
        Args:
            note_id: 笔记ID
            content: 响应内容
            error_type: 错误类型
        """
        try:
            # 确保error目录存在
            error_dir = "error"
            os.makedirs(error_dir, exist_ok=True)
            
            # 生成错误文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{error_dir}/{note_id}_{error_type}_{timestamp}.txt"
            
            # 保存错误内容
            with open(filename, 'w', encoding='utf-8') as f:
                if isinstance(content, (dict, list)):
                    json.dump(content, f, ensure_ascii=False, indent=2)
                else:
                    f.write(str(content))
            
            logger.info(f"错误响应已保存到: {filename}")
            
        except Exception as e:
            logger.error(f"保存错误响应失败: {str(e)}")

    def format_note_detail(self, note_detail):
        """格式化笔记详细信息"""
        if not note_detail or 'note' not in note_detail:
            return {}
        
        note = note_detail['note']
        interact_info = note.get('interactInfo', {})
        
        return {
            '笔记ID': note.get('noteId', ''),
            '标题': note.get('title', ''),
            '内容': note.get('desc', ''),
            '发布时间': note.get('time', ''),
            'ip属地': note.get('ipLocation', ''),
            '点赞数': interact_info.get('likedCount', '0'),
            '收藏数': interact_info.get('collectedCount', '0'),
            '评论数': interact_info.get('commentCount', '0'),
            '分享数': interact_info.get('shareCount', '0'),
            '笔记类型': note.get('type', ''),
            '作者ID': note.get('user', {}).get('userId', ''),
            '作者昵称': note.get('user', {}).get('nickname', ''),
            '作者头像': note.get('user', {}).get('avatar', ''),
            '最后更新时间': note.get('lastUpdateTime', ''),
            '话题标签': ','.join([tag.get('name', '') for tag in note.get('tagList', []) if tag.get('type') == 'topic'])
        }

    def load_existing_details(self, search_result_file: str) -> None:
        """加载已存在的笔记详情文件"""
        detail_file = self._get_detail_filename(search_result_file)
        if os.path.exists(detail_file):
            try:
                df = pd.read_excel(detail_file)
                self.processed_notes.update(df['笔记ID'].tolist())
                logger.info(f"从现有文件加载了 {len(self.processed_notes)} 条笔记记录")
            except Exception as e:
                logger.error(f"加载已存在的笔记详情文件失败: {str(e)}")

    def _get_detail_filename(self, search_result_file: str) -> str:
        """根据搜索结果文件名生成详情文件名"""
        base_name = os.path.basename(search_result_file)
        if base_name.startswith("search_results_"):
            detail_name = base_name.replace("search_results_", "note_details_")
            return os.path.join(os.path.dirname(search_result_file), detail_name)
        return os.path.join(os.path.dirname(search_result_file), f"note_details_{base_name}")

    def save_to_excel(self, data: list, output_file: str, existing_df: pd.DataFrame = None) -> None:
        """保存数据到Excel文件
        
        Args:
            data: 要保存的数据列表
            output_file: 输出文件路径
            existing_df: 现有的DataFrame
        """
        try:
            result_df = pd.DataFrame(data)
            if existing_df is not None and not existing_df.empty:
                result_df = pd.concat([existing_df, result_df], ignore_index=True)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            result_df.to_excel(output_file, index=False)
            logger.info(f"数据已保存到: {output_file}")
        except Exception as e:
            logger.error(f"保存Excel文件失败: {str(e)}")

    async def process_notes(self, input_file: str, is_test: bool = False, proxy=None):
        """处理笔记列表获取详细信息
        
        Args:
            input_file: 输入的Excel文件路径
            is_test: 是否为测试模式（只处理前3条）
            proxy: 代理设置，例如 {"http": "http://127.0.0.1:30002"}
        """
        try:
            # 加载已存在的笔记详情
            self.load_existing_details(input_file)
            
            # 读取输入文件
            df = pd.read_excel(input_file)
            logger.info(f"成功读取输入文件，共 {len(df)} 条记录")
            
            # 筛选相关性为TRUE的记录
            df = df[df['相关性'] == True]
            logger.info(f"筛选出相关性为TRUE的记录 {len(df)} 条")
            
            # 准备输出文件
            output_file = self._get_detail_filename(input_file)
            existing_df = None
            if os.path.exists(output_file):
                existing_df = pd.read_excel(output_file)
            
            # 如果是测试模式，只处理前3条
            if is_test:
                df = df.head(3)
                logger.info("测试模式：只处理前3条记录")
            
            # 处理每条笔记
            batch = []  # 用于临时存储处理结果
            batch_size = 5  # 每5条记录保存一次
            
            for index, row in df.iterrows():
                note_id = row['UID']
                
                # 如果笔记已经处理过，跳过
                if note_id in self.processed_notes:
                    logger.info(f"笔记 {note_id} 已处理过，跳过")
                    continue
                    
                xsec_token = row['xsec_token']
                logger.info(f"正在处理第 {index + 1} 条笔记，ID: {note_id}")
                
                # 传递proxy参数
                detail = await self.get_note_detail(note_id, xsec_token, proxy=proxy)
                if detail:
                    try:
                        note_info = self.format_note_detail(detail)
                        # 保留原始搜索结果的信息
                        for col in df.columns:
                            if col not in note_info:
                                note_info[col] = row[col]
                        batch.append(note_info)
                        self.processed_notes.add(note_id)
                        logger.info(f"成功获取笔记 {note_id} 的详细信息")
                        
                        # 每处理batch_size条记录保存一次
                        if len(batch) >= batch_size:
                            self.save_to_excel(batch, output_file, existing_df)
                            if existing_df is not None:
                                existing_df = pd.concat([existing_df, pd.DataFrame(batch)], ignore_index=True)
                            else:
                                existing_df = pd.DataFrame(batch)
                            batch = []  # 清空批次
                            
                    except Exception as e:
                        logger.error(f"处理笔记 {note_id} 详情时出错: {str(e)}")
                
                # 添加延时避免请求过快
                await asyncio.sleep(5)
            
            # 保存最后一批数据
            if batch:
                self.save_to_excel(batch, output_file, existing_df)
                logger.info(f"最后一批数据已保存，共 {len(batch)} 条")
                
        except Exception as e:
            logger.error(f"处理过程出错: {str(e)}")
            # 如果有未保存的数据，尝试保存
            if batch:
                self.save_to_excel(batch, output_file, existing_df)
                logger.info(f"异常发生时保存了 {len(batch)} 条未保存的数据")

    def setup_logger(self, is_test: bool = False):
        """配置日志"""
        log_type = "test" if is_test else "detail"
        logger.add(
            f"logs/note_{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            rotation="500 MB",
            encoding="utf-8",
            enqueue=True,
            compression="zip",
            retention="10 days",
            level="INFO"
        )

    def get_latest_search_file(self) -> str:
        """获取最新的搜索结果文件"""
        processed_dir = "processed/rednote"
        os.makedirs(processed_dir, exist_ok=True)
        search_results_files = [f for f in os.listdir(processed_dir) if f.startswith("search_results_")]
        if not search_results_files:
            raise FileNotFoundError("未找到搜索结果文件")
        
        latest_file = max(search_results_files, key=lambda x: os.path.getctime(os.path.join(processed_dir, x)))
        return os.path.join(processed_dir, latest_file)

    def run_interactive(self):
        """交互式运行获取笔记详情"""
        parser = argparse.ArgumentParser(description='获取小红书笔记详情')
        parser.add_argument('--input', '-i', help='输入文件路径')
        parser.add_argument('--test', '-t', action='store_true', help='测试模式（只处理前3条记录）')
        parser.add_argument('--proxy', '-p', help='代理设置（例如：http://127.0.0.1:30002）')
        args = parser.parse_args()
        
        # 设置日志
        self.setup_logger(args.test)
        
        # 处理输入文件参数
        input_file = args.input
        if not input_file:
            input_file = self.get_latest_search_file()
            if not input_file:
                logger.error("未找到输入文件，请指定--input参数")
                return
                
        logger.info(f"使用输入文件: {input_file}")
        
        # 处理代理参数
        proxy = None
        if args.proxy:
            if args.proxy.startswith('http'):
                proxy = {"http": args.proxy}
                logger.info(f"使用代理: {args.proxy}")
            else:
                logger.warning(f"无效的代理格式: {args.proxy}，应为http(s)://地址:端口")
        
        # 创建事件循环运行异步函数
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.process_notes(input_file, args.test, proxy=proxy))

def main():
    """主函数"""
    try:
        runner = NoteDetailRunner()
        runner.run_interactive()
    except KeyboardInterrupt:
        logger.warning("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {str(e)}")

if __name__ == "__main__":
    main() 