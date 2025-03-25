import asyncio
import json
import pandas as pd
from datetime import datetime
from xhs.encrypt.misc_encrypt import MiscEncrypt
from xhs.request.note import Notes
from xhs.request.AsyncRequestFramework import AsyncRequestFramework
from loguru import logger

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

async def process_keyword(keyword: str, attraction_id: str, cookie: str):
    """处理单个关键词的搜索"""
    all_notes = []
    
    # 为每个关键词生成一个search_id
    search_id = await MiscEncrypt.search_id()
    logger.info(f"开始处理关键词: {keyword} (景点ID: {attraction_id}), search_id: {search_id}")
    
    for page in range(1, 12):  # 1-11页
        logger.info(f"正在搜索关键词 '{keyword}' 的第 {page} 页")
        result = await search_xhs_notes(keyword, page=page, cookie=cookie, search_id=search_id)
        
        if result and result.get('success'):
            data = result.get('data', {})
            items = data.get('items', [])
            
            for item in items:
                if item.get('model_type') == 'note':
                    note_info = format_note_info(item)
                    note_info['景区ID'] = attraction_id
                    note_info['景区关键词'] = keyword
                    note_info['数据来源'] = '小红书'
                    note_info['链接'] = f"https://www.xiaohongshu.com/explore/{note_info['UID']}?xsec_token={note_info['xsec_token']}"
                    all_notes.append(note_info)
            
            logger.info(f"关键词 '{keyword}' 第 {page} 页找到 {len(items)} 条笔记")
            
            if not data.get('has_more'):
                logger.info(f"关键词 '{keyword}' 没有更多结果，停止搜索")
                break
        else:
            logger.warning(f"关键词 '{keyword}' 第 {page} 页搜索失败")
    
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
    
    cookie = "abRequestId=87bd2bac-2376-5b13-b127-2ae18c57efdd; a1=195c6bd1ad6xjpua10ilslgflhi677pwf88fzqlla50000253141; webId=8ca236804996c89a734101e591aec49a; gid=yj2SKDf2fJifyj2SKDfy0YA1fKCVU70y831MY101ki1x3i28KWWUEu888J2qy4y8Y8y0jq80; webBuild=4.60.2; acw_tc=0a0b13d917428867116887578e8861e7e0d7d3beb70edc0333204b617e4f7b; xsecappid=xhs-pc-web; websectiga=cf46039d1971c7b9a650d87269f31ac8fe3bf71d61ebf9d9a0a87efb414b816c; sec_poison_id=6b898c3b-4df7-4ca9-a267-d5b73d3c8807; web_session=040069b16a6515567369b413d7354bb27a088e; unread={%22ub%22:%2267bee4ad000000000603dc76%22%2C%22ue%22:%2267d14fca000000000d01712e%22%2C%22uc%22:33}; loadts=1742887929785"
    
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
        output_file = f"processed/search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        result_df.to_excel(output_file, index=False)
        logger.info(f"结果已保存到: {output_file}")
        logger.info(f"总共找到 {len(all_results)} 条笔记")
    else:
        logger.warning("未找到任何笔记")

if __name__ == "__main__":
    asyncio.run(main())