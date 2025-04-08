import asyncio
import json
import time
from collections.abc import Mapping
from urllib.parse import urlencode
import random

from curl_cffi.requests import AsyncSession, Response
from loguru import logger

from ..encrypt import MiscEncrypt, XscEncrypt, XsEncrypt


class AsyncRequestFramework:
    """异步请求框架

    Args:
        verify_ssl (bool, optional): 是否验证 SSL 证书 默认为 True
    """
    def __init__(self, verify_ssl=True):
        self.verify_ssl = verify_ssl
        self.session = None  # 初始化session属性为None

    async def init_session(self):
        """初始化异步会话

        创建一个新的 AsyncSession 实例
        """
        self.session = AsyncSession(
            verify=self.verify_ssl,
            impersonate="chrome124"
        )
        return self.session

    async def close_session(self, session: AsyncSession):
        """关闭异步会话

        如果会话已创建 则关闭会话并将其设置为 None
        """
        return await session.close()

    async def __pre_headers(
        self,
        uri: str,
        xsc_schemas,
        a1: str,
        cookie: dict,
        method: str,
        params: dict,
        data: dict,
    ):
        session = await self.init_session()
        session.cookies.update(cookie)

        xt = str(int(time.time() * 1000))

        match method:
            case 'GET':
                xs = await XsEncrypt.encrypt_xs(url=f"{uri}?{json.dumps(params, separators=(',', ':'), ensure_ascii=False)}",
                                                a1=a1, ts=xt)
            case 'POST':
                xs = await XsEncrypt.encrypt_xs(url=f"{uri}{json.dumps(data,separators=(',', ':'),ensure_ascii=False)}",
                                                a1=a1, ts=xt)
            case _:
                xs = ""

        xsc = await XscEncrypt.encrypt_xsc(xs=xs, xt=xt, platform=xsc_schemas.platform, a1=a1,
                                           x1=xsc_schemas.x1, x4=xsc_schemas.x4)

        session.headers.update({"x-s": xs})
        session.headers.update({"x-t": xt})
        session.headers.update({"x-s-common": xsc})

        x_b3 = await MiscEncrypt.x_b3_traceid()

        session.headers.update({
            "x-b3-traceid": x_b3,
            "x-xray-traceid": await MiscEncrypt.x_xray_traceid(x_b3),
        })

        return session

    async def send_http_request(self, url, method='GET', xsc_schemas=None, uri: str = "", auto_sign: bool = False,
                                params=None, data=None, headers=None, timeout=30, proxy=None, cookie=None, back_fun=False,
                                max_retries=5, retry_delay=3.0, **kwargs):
        """发送 HTTP 请求

        Args:
            url (str): 完整的 URL 地址
            method (str, optional): HTTP 方法. Defaults to 'GET'.
            xsc_schemas (dict, optional): xsc_schemas. Defaults to None.
            uri (str, optional): URI. Defaults to "".
            auto_sign (bool, optional): 是否自动签名. Defaults to False.
            params (dict, optional): URL 参数. Defaults to None.
            data (dict, optional): 请求体. Defaults to None.
            headers (dict, optional): 请求头. Defaults to None.
            timeout (int, optional): 超时时间. Defaults to 30.
            proxy (str, optional): 代理地址. Defaults to None.
            cookie (dict, optional): cookie. Defaults to None.
            back_fun (bool, optional): 返回 Response 对象. Defaults to False.
            max_retries (int, optional): 最大重试次数. Defaults to 5.
            retry_delay (float, optional): 重试延迟. Defaults to 3.0.

        Returns:
            dict: 响应数据
        """
        params = params or {}
        data = data or {}
        if headers is None:
            headers = {}

        if auto_sign:
            # 不需要签名，所以略过
            pass
        
        if not self.session:
            await self.init_session()
            session = self.session
        else:
            session = AsyncSession()

        method = method.upper()
        kwargs['stream'] = True

        for attempt in range(max_retries):
            try:
                logger.debug(f"尝试 {attempt + 1}/{max_retries}: {url}")
                
                # 增加随机延迟，避免请求过于规律
                if attempt > 0:
                    jitter = random.uniform(0.5, 1.5)
                    delay = retry_delay * jitter
                    logger.info(f"第 {attempt + 1} 次重试，等待 {delay:.2f} 秒")
                    await asyncio.sleep(delay)
                
                try:
                    response: Response = await session.request(
                        method=method,
                        url=url,
                        params=params,
                        data=data,
                        headers=headers,
                        proxy=proxy,
                        timeout=timeout,
                        cookies=cookie,
                        quote=False,
                        **kwargs
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"请求超时 (attempt {attempt + 1}/{max_retries}): {url}")
                    continue
                except asyncio.CancelledError:
                    logger.warning(f"请求被取消 (attempt {attempt + 1}/{max_retries}): {url}")
                    # 特殊处理被取消的请求
                    if attempt < max_retries - 1:
                        continue
                    else:
                        logger.error("请求被取消且达到最大重试次数，放弃请求")
                        return {"error": "request_cancelled", "message": "请求被取消且达到最大重试次数"}
                
                if back_fun:
                    return response

                if response.status_code == 404:
                    logger.error(f" {url} 状态404")
                    return {"error": "not_found", "status_code": 404}
                
                if response.status_code >= 400:
                    logger.error(f"{url} 状态码错误: {response.status_code}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return {"error": "http_error", "status_code": response.status_code}

                content = await response.acontent()

                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.exception(f"JSON解析错误: {e}")
                    try:
                        text_content = content.decode('utf-8', errors='replace')
                        # 检查是否是常见的错误页面
                        if "请求过于频繁" in text_content or "访问频率过高" in text_content:
                            logger.warning("检测到访问频率限制，稍后重试")
                            await asyncio.sleep(retry_delay * 2)  # 额外延迟
                            continue
                        return {"error": "invalid_json", "content": text_content[:500]}  # 只返回部分内容
                    except Exception:
                        return {"error": "decode_error"}

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(
                    f"尝试 {attempt + 1}/{max_retries}: {url} 请求错误 {error_type}: {error_msg}"
                )
                
                # 针对不同类型的错误采取不同的处理策略
                if "连接" in error_msg or "Connection" in error_msg:
                    # 连接问题可能需要更长的等待时间
                    retry_time = retry_delay * 2
                elif "超时" in error_msg or "timeout" in error_msg.lower():
                    # 超时问题
                    retry_time = retry_delay * 1.5
                else:
                    retry_time = retry_delay
                
                if attempt < max_retries - 1:
                    logger.warning(f"将在 {retry_time:.2f} 秒后重试...")
                    await asyncio.sleep(retry_time)
                else:
                    logger.error(f"重试{max_retries}次后仍然失败: {error_type} - {error_msg}")
                    return {"error": error_type, "message": error_msg}

    async def get_redirect_url(self, url: str) -> Mapping:
        """获取重定向 URL

        Args:
            url (str): 原始 URL

        Returns:
            dict: 包含原始 URL、最终 URL 和状态码的字典
        """
        try:
            await self.init_session()
            response = await self.session.get(url, allow_redirects=False)

            if response.status in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location')
                return {
                    'original_url': url,
                    'final_url': redirect_url,
                    'status': response.status
                }

            return {
                'original_url': url,
                'final_url': str(response.url),
                'status': response.status
            }

        except Exception as e:
            return {
                'original_url': url,
                'error': str(e)
            }
