import asyncio
import json
import pandas as pd
from datetime import datetime
from xhs.encrypt.misc_encrypt import MiscEncrypt
from xhs.request.note import Notes
from xhs.request.AsyncRequestFramework import AsyncRequestFramework
from loguru import logger
import os
import random
import string

def parse_cookie_string(cookie_str: str) -> dict:
    """将 cookie 字符串解析为字典
    
    Args:
        cookie_str: cookie 字符串
        
    Returns:
        dict: cookie 字典
    """
    cookie_dict = {}
    for item in cookie_str.split(';'):
        if '=' in item:
            key, value = item.strip().split('=', 1)
            cookie_dict[key] = value
    return cookie_dict

async def search_xhs_notes(keyword: str, page: int = 1, page_size: int = 20, cookie: str = "", search_id: str = None):
    """
    搜索小红书笔记
    
    Args:
        keyword: 搜索关键词
        page: 页码，默认1
        page_size: 每页大小，默认20
        cookie: cookie 字符串
        search_id: 搜索ID，如果为None则生成新的
    """
    try:
        arf = AsyncRequestFramework()
        note_request = Notes(arf)
        
        if search_id is None:
            search_id = await MiscEncrypt.search_id()
            logger.info(f"关键词 '{keyword}' - 生成的search_id: {search_id}")
        
        cookie_dict = parse_cookie_string(cookie) if cookie else {}
        
        result = await note_request.search_notes(
            keyword=keyword,
            search_id=search_id,
            page=page,
            page_size=page_size,
            cookie=cookie_dict
        )
        
        return result
        
    except Exception as e:
        logger.error(f"搜索出错 - 关键词: {keyword}, 页码: {page}, 错误: {str(e)}")
        return None

def format_note_info(note):
    """格式化笔记信息"""
    note_card = note.get('note_card', {})
    user = note_card.get('user', {})
    
    return {
        '标题': note_card.get('display_title', ''),
        '类型': note_card.get('type', 'normal'),
        '作者': user.get('nickname', ''),
        '用户ID': user.get('user_id', ''),
        'UID': note.get('id', ''),
        '点赞数': note_card.get('interact_info', {}).get('liked_count', ''),
        'xsec_token': note.get('xsec_token', '')
    }

async def process_keyword(keyword: str, attraction_id: str, cookie: str, max_pages: int = 11, max_retries: int = 3, retry_delay: float = 5.0):
    """处理单个关键词的搜索
    
    Args:
        keyword: 搜索关键词
        attraction_id: 景点ID
        cookie: 小红书cookie
        max_pages: 最大页数，默认11页
        max_retries: 最大重试次数，默认3次
        retry_delay: 重试延迟时间，默认5秒
        
    Returns:
        list: 搜索结果列表
    """
    all_notes = []
    
    # 为每个关键词生成一个search_id
    try:
        search_id = await MiscEncrypt.search_id()
        logger.info(f"开始处理关键词: {keyword} (景点ID: {attraction_id}), search_id: {search_id}")
    except Exception as e:
        logger.error(f"生成search_id失败: {str(e)}")
        # 使用备用方法
        search_id = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(21))
        logger.warning(f"使用随机生成的search_id: {search_id}")
    
    # 检查cookie是否有效
    if not cookie:
        logger.warning(f"未提供cookie，搜索可能受限")
    
    for page in range(1, max_pages):  # 1-10页
        logger.info(f"正在搜索关键词 '{keyword}' 的第 {page} 页")
        
        # 重试机制
        for retry in range(max_retries):
            try:
                result = await search_xhs_notes(keyword, page=page, cookie=cookie, search_id=search_id)
                
                if result:
                    if "error" in result:
                        logger.warning(f"搜索返回错误: {result.get('error')} - {result.get('message', '')}")
                        if retry < max_retries - 1:
                            logger.info(f"将在 {retry_delay} 秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"搜索关键词 '{keyword}' 第 {page} 页失败，达到最大重试次数")
                            break
                    
                    if result.get('success'):
                        data = result.get('data', {})
                        items = data.get('items', [])
                        
                        # 提取笔记信息
                        page_notes = []
                        for item in items:
                            if item.get('model_type') == 'note':
                                note_info = format_note_info(item)
                                note_info['景区ID'] = attraction_id
                                note_info['景区关键词'] = keyword
                                note_info['数据来源'] = '小红书'
                                note_info['链接'] = f"https://www.xiaohongshu.com/explore/{note_info['UID']}?xsec_token={note_info['xsec_token']}"
                                page_notes.append(note_info)
                        
                        all_notes.extend(page_notes)
                        logger.info(f"关键词 '{keyword}' 第 {page} 页找到 {len(page_notes)} 条笔记")
                        
                        # 检查是否有更多结果
                        if not data.get('has_more'):
                            logger.info(f"关键词 '{keyword}' 没有更多结果，停止搜索")
                            break
                        
                        # 成功处理，跳出重试循环
                        break
                    else:
                        logger.warning(f"关键词 '{keyword}' 第 {page} 页搜索返回非成功状态")
                        if retry < max_retries - 1:
                            logger.info(f"将在 {retry_delay} 秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"搜索关键词 '{keyword}' 第 {page} 页失败，达到最大重试次数")
                            break
                else:
                    logger.warning(f"关键词 '{keyword}' 第 {page} 页搜索返回空结果")
                    if retry < max_retries - 1:
                        logger.info(f"将在 {retry_delay} 秒后重试...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"搜索关键词 '{keyword}' 第 {page} 页失败，达到最大重试次数")
                        break
                        
            except Exception as e:
                logger.error(f"搜索关键词 '{keyword}' 第 {page} 页时发生错误: {str(e)}")
                if retry < max_retries - 1:
                    logger.info(f"将在 {retry_delay} 秒后重试...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"搜索关键词 '{keyword}' 第 {page} 页失败，达到最大重试次数")
                    break
        
        # 每页之间添加延迟，避免请求过快
        if page < max_pages - 1:
            page_delay = random.uniform(3.0, 6.0)
            logger.info(f"等待 {page_delay:.2f} 秒后搜索下一页...")
            await asyncio.sleep(page_delay)
    
    logger.info(f"关键词 '{keyword}' 搜索完成，共找到 {len(all_notes)} 条笔记")
    return all_notes

async def main():
    # 配置日志
    logger.add(
        f"logs/search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        rotation="500 MB",
        encoding="utf-8",
        enqueue=True,
        compression="zip",
        retention="10 days",
        level="INFO"
    )
    
    # 读取关键词文件
    try:
        df = pd.read_excel('keywords.xlsx')
        logger.info(f"成功读取关键词文件，共 {len(df)} 个关键词")
    except Exception as e:
        logger.error(f"读取关键词文件失败: {str(e)}")
        return
    
    cookie = "ABBBCCCCC"
    
    all_results = []
    
    # 处理每个关键词
    for index, row in df.iterrows():
        keyword = row['英文关键词']
        spot_id = row['景点ID']
        
        notes = await process_keyword(keyword, spot_id, cookie)
        all_results.extend(notes)
        
        logger.info(f"关键词 '{keyword}' 处理完成，找到 {len(notes)} 条笔记")
    
    # 保存结果
    if all_results:
        result_df = pd.DataFrame(all_results)
        # 保存到processed目录
        output_dir = "processed/rednote"
        os.makedirs(output_dir, exist_ok=True)
        output_file = f"{output_dir}/search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        result_df.to_excel(output_file, index=False)
        logger.info(f"结果已保存到: {output_file}")
        logger.info(f"总共找到 {len(all_results)} 条笔记")
    else:
        logger.warning("未找到任何笔记")

if __name__ == "__main__":
    asyncio.run(main())