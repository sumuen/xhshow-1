"""
通用景点数据分析工具

分析已过滤的数据源数据，统计不同景点的有效数据量与景点的相关性平均值
"""
import os
import sys
import argparse
import pandas as pd
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def analyze_attractions_data(input_file: str, output_file: str = None) -> pd.DataFrame:
    """
    分析已过滤的数据中不同景点的统计信息
    
    Args:
        input_file (str): 输入Excel文件路径，应为已过滤的分析结果
        output_file (str, optional): 输出Excel文件路径，默认为None
        
    Returns:
        pd.DataFrame: 包含景点统计信息的数据框
    """
    print(f"开始分析景点数据: {input_file}")
    
    # 确保输入文件存在
    if not os.path.exists(input_file):
        print(f"错误: 输入文件不存在: {input_file}")
        return None
    
    # 加载数据
    df = pd.read_excel(input_file)
    print(f"加载了 {len(df)} 行数据")
    
    # 检查必要的列是否存在
    required_columns = ['景点ID', '相关性分值']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        # 尝试查找替代列
        if '景点ID' in missing_columns:
            for alt_col in ['attraction_id', 'id']:
                if alt_col in df.columns:
                    df['景点ID'] = df[alt_col]
                    missing_columns.remove('景点ID')
                    break
        
        if '景点(中文)' in missing_columns:
            for alt_col in ['attraction_name', '名称', 'name', '景点名称']:
                if alt_col in df.columns:
                    df['景点(中文)'] = df[alt_col]
                    missing_columns.remove('景点(中文)')
                    break
    
    if missing_columns:
        print(f"错误: 缺少必要的列: {', '.join(missing_columns)}")
        return None
    
    # 确保景点(中文)列存在，用于显示
    if '景点(中文)' not in df.columns:
        print("警告: 缺少景点(中文)列，将使用景点ID作为显示名称")
        df['景点(中文)'] = df['景点ID']
    
    # 提取景点景点关键词信息
    keyword_columns = ['景点关键词', 'keyword', 'keywords']
    keyword_col = None
    for col in keyword_columns:
        if col in df.columns:
            keyword_col = col
            break
    
    # 创建景点ID到景点关键词的映射
    id_to_keyword = {}
    if keyword_col:
        print(f"找到景点关键词列: {keyword_col}")
        for _, row in df.drop_duplicates(['景点ID']).iterrows():
            if pd.notna(row[keyword_col]):
                id_to_keyword[row['景点ID']] = row[keyword_col]
    else:
        print("警告: 未找到景点关键词列")
    
    # 按景点ID分组统计
    attraction_stats = df.groupby('景点ID').agg(
        数据量=('相关性分值', 'count'),
        相关性平均值=('相关性分值', 'mean'),
        相关性中位数=('相关性分值', 'median'),
        相关性最大值=('相关性分值', 'max'),
        相关性最小值=('相关性分值', 'min'),
        相关性标准差=('相关性分值', 'std')
    ).reset_index()
    
    # 添加景点(中文)列
    # 为每个景点ID找到对应的景点(中文)名称
    id_to_name = {}
    for _, row in df.drop_duplicates(['景点ID']).iterrows():
        id_to_name[row['景点ID']] = row['景点(中文)']
    
    attraction_stats['景点(中文)'] = attraction_stats['景点ID'].map(id_to_name)
    
    # 添加景点关键词列
    if id_to_keyword:
        attraction_stats['景点关键词'] = attraction_stats['景点ID'].map(id_to_keyword)
    
    # 计算正式爬取量
    attraction_stats['正式爬取量'] = attraction_stats.apply(
        lambda row: round((row['数据量'] * row['相关性平均值']) / 10, 0),
        axis=1
    ).astype(int)
    
    # 按数据量排序
    attraction_stats = attraction_stats.sort_values(by='数据量', ascending=False)
    
    # 添加相关性平均值排名
    attraction_stats['相关性平均值排名'] = attraction_stats['相关性平均值'].rank(ascending=False, method='min').astype(int)
    
    # 选择需要的列并重新排序
    columns = ['景点ID', '景点(中文)', '数据量', '相关性平均值', '相关性平均值排名', '正式爬取量']
    if id_to_keyword:
        columns.insert(2, '景点关键词')
    
    result_df = attraction_stats[columns]
    
    # 保存结果
    if output_file:
        # 确保输出目录存在
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        try:
            result_df.to_excel(output_file, index=False)
            print(f"分析结果已保存到: {output_file}")
        except PermissionError:
            # 如果遇到权限错误，使用带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = os.path.basename(output_file)
            name, ext = os.path.splitext(file_name)
            new_output_file = os.path.join(output_dir, f"{name}_{timestamp}{ext}")
            
            result_df.to_excel(new_output_file, index=False)
            print(f"由于权限问题，分析结果已保存到: {new_output_file}")
    
    # 打印统计信息
    print("\n景点数据统计:")
    print(f"总景点数: {len(result_df)}")
    print(f"总数据量: {result_df['数据量'].sum()}")
    print(f"总正式爬取量: {result_df['正式爬取量'].sum()}")
    
    # 显示列
    display_columns = ['景点ID', '景点(中文)', '数据量', '相关性平均值', '相关性平均值排名', '正式爬取量']
    if id_to_keyword:
        display_columns.insert(2, '景点关键词')
    
    return result_df

def get_data_sources() -> List[str]:
    """
    获取processed目录下所有可用的数据源
    
    Returns:
        List[str]: 可用数据源列表
    """
    processed_dir = os.path.join(project_root, "processed")
    if not os.path.exists(processed_dir):
        return []
    
    # 查找所有以_analyzed.xlsx结尾的文件
    data_sources = []
    for file in os.listdir(processed_dir):
        if file.endswith("_analyzed.xlsx"):
            source = file.replace("_analyzed.xlsx", "")
            data_sources.append(source)
    
    return data_sources

def run_interactive():
    """交互式运行分析工具"""
    print("欢迎使用景点数据分析工具")
    print("=" * 50)
    
    # 获取可用数据源
    data_sources = get_data_sources()
    if not data_sources:
        print("错误: 未找到任何可用的数据源")
        return
    
    # 显示可用数据源
    print("可用数据源:")
    for i, source in enumerate(data_sources, 1):
        print(f"{i}. {source}")
    
    # 选择数据源
    while True:
        try:
            choice = input("\n请选择数据源 (输入序号或数据源名称，输入q退出): ")
            if choice.lower() == 'q':
                return
            
            if choice.isdigit() and 1 <= int(choice) <= len(data_sources):
                source = data_sources[int(choice) - 1]
            elif choice in data_sources:
                source = choice
            else:
                print("无效的选择，请重试")
                continue
            
            break
        except (ValueError, IndexError):
            print("无效的选择，请重试")
    
    # 构建输入和输出文件路径
    input_file = os.path.join(project_root, "processed", f"{source}_analyzed.xlsx")
    output_file = os.path.join(project_root, "processed", f"{source}_attractions_stats.xlsx")
    
    # 分析数据
    analyze_attractions_data(input_file, output_file)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="景点数据分析工具")
    parser.add_argument("-s", "--source", help="数据源名称，如facebook、ins等")
    parser.add_argument("-i", "--input", help="输入文件路径，优先级高于数据源名称")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument("-l", "--list", action="store_true", help="列出所有可用的数据源")
    parser.add_argument("--interactive", action="store_true", help="交互式运行")
    
    return parser.parse_args()

def main():
    """主函数"""
    args = parse_args()
    
    # 列出所有可用的数据源
    if args.list:
        data_sources = get_data_sources()
        if data_sources:
            print("可用数据源:")
            for source in data_sources:
                print(f"- {source}")
        else:
            print("未找到任何可用的数据源")
        return
    
    # 交互式运行
    if args.interactive:
        run_interactive()
        return
    
    # 确定输入文件
    input_file = None
    if args.input:
        input_file = args.input
    elif args.source:
        input_file = os.path.join(project_root, "processed", f"{args.source}_analyzed.xlsx")
    else:
        print("错误: 必须指定数据源名称或输入文件路径")
        return
    
    # 确定输出文件
    output_file = None
    if args.output:
        output_file = args.output
    elif args.source:
        output_file = os.path.join(project_root, "processed", f"{args.source}_attractions_stats.xlsx")
    else:
        # 从输入文件名生成输出文件名
        input_basename = os.path.basename(input_file)
        input_name, _ = os.path.splitext(input_basename)
        output_file = os.path.join(os.path.dirname(input_file), f"{input_name.replace('_analyzed', '')}_attractions_stats.xlsx")
    
    # 分析数据
    analyze_attractions_data(input_file, output_file)

if __name__ == "__main__":
    main()