import time
import random

def get_search_id():
    """
    生成一个唯一的搜索ID
    实现逻辑：
    1. 获取当前时间戳（毫秒）并左移64位
    2. 生成一个随机数（0-2147483646之间）
    3. 将时间戳和随机数相加
    4. 将结果转换为base36编码的字符串
    """
    # 获取当前时间戳（毫秒）并左移64位，这样可以保证时间戳部分不会与随机数部分重叠
    e = int(time.time() * 1000) << 64
    print(f"时间戳左移64位: {e}")
    print(f"时间戳左移64位(二进制): {bin(e)[2:]}")  # [2:]去掉'0b'前缀
    
    # 生成一个随机数，范围在0到2147483646之间
    t = int(random.uniform(0, 2147483646))
    print(f"随机数: {t}")
    print(f"随机数(二进制): {bin(t)[2:]}")  # [2:]去掉'0b'前缀
    
    # 将时间戳和随机数相加，然后转换为base36编码
    result = e + t
    print(f"相加结果: {result}")
    print(f"相加结果(二进制): {bin(result)[2:]}")  # [2:]去掉'0b'前缀
    
    return base36encode(result)

def base36encode(number, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    """
    将整数转换为base36编码的字符串
    
    参数:
        number: 要转换的整数
        alphabet: 用于编码的字符集，默认使用0-9和A-Z
    
    返回:
        base36编码的字符串
    """
    if not isinstance(number, int):
        raise TypeError('number must be an integer')
    base36 = ''
    sign = ''

    # 处理负数的情况
    if number < 0:
        sign = '-'
        number = -number

    # 如果数字小于字符集长度，直接返回对应的字符
    if 0 <= number < len(alphabet):
        return sign + alphabet[number]

    # 通过不断除以字符集长度来构建base36字符串
    while number != 0:
        print(f"number: {number}")
        number, i = divmod(number, len(alphabet))
        base36 = alphabet[i] + base36
        print(f"base36: {base36}")
    return sign + base36

# 测试代码
if __name__ == '__main__':
    print("\n=== 生成搜索ID的过程 ===")
    search_id = get_search_id()
    print(f"\n最终生成的搜索ID: {search_id}")