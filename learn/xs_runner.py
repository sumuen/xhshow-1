import asyncio
from encrypt.xs_encrypt import XsEncrypt
import time
async def main():
    # 参数说明
    url = "api/sns/web/v1/search/notes"  # API的URL
    a1 = "195c6bd1ad6xjpua10ilslgflhi677pwf88fzqlla50000253141"  # 签名参数a1
    ts = str(time.time()*1000)
    # 调用加密方法
    xs = await XsEncrypt.encrypt_xs(
        url=url,
        a1=a1,
        ts=ts,
        platform='xhs-pc-web'  # 平台参数，默认是xhs-pc-web
    )
    print(f"生成的xs签名: {xs}")

# 运行异步函数
if __name__ == "__main__":
    asyncio.run(main())