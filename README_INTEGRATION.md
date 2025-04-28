# 小红书爬虫集成指南

本文档介绍如何将小红书爬虫集成到主项目中，以便通过统一的界面调用小红书数据分析功能。

## 安装步骤

1. 首先修改了 `pyproject.toml` 中的 Pillow 版本，解决了不兼容问题：
   ```
   pillow~=10.2.0  # 原来是 11.2.0，这个版本被撤回了
   ```

2. 运行安装脚本，将小红书爬虫安装到主项目环境中：
   ```bash
   uv run install_rednote.py
   ```

3. 这将使用开发模式安装小红书爬虫包，以便在修改代码后不需要重新安装。

## 最新修复

1. 修复了景点ID浮点数问题：Excel中的数字在读取时会被转换为浮点数（如386917.0），现在会自动转换为整数字符串。

2. 修复了AsyncRequestFramework类中缺少session属性导致的错误。

3. 修复了文件路径不一致问题：统一使用 `processed/rednote` 目录存储处理结果。

4. 增强了错误处理和重试机制，提高了程序稳定性。

## 使用方法

安装成功后，可以通过两种方式使用小红书爬虫：

### 1. 通过主程序菜单

运行主程序：
```bash
uv run main.py
```

在菜单中选择以下选项：
- 15 - 小红书单个景点分析：分析单个景点的小红书数据
- 16 - 小红书批量景点分析：批量分析多个景点的小红书数据

### 2. 直接调用小红书爬虫模块

也可以直接运行小红书爬虫模块：

```bash
# 单个景点分析
uv run -m crawler.rednote.learn.analyze_attraction_cmd --keyword "西湖" --spot_id "1001"

# 批量景点分析
uv run -m crawler.rednote.learn.batch_analyze_attractions --input "attractions/attractions.xlsx"
```

## 批量分析模板文件

为了方便进行批量分析，提供了一个模板生成工具：


## 数据格式要求

### 单个景点分析

不需要特殊的数据格式，直接输入景点名称和ID即可。

### 批量景点分析

需要提供一个Excel文件，包含以下列：
- 英文关键词：景点的英文名称（用于搜索）
- 景点ID：景点的唯一ID

Excel示例：

| 英文关键词 | 景点ID |
|---------|-------|
| West Lake hangzhou | 386917 |
| Forbidden City Beijing | 386918 |
| Yu Garden Shanghai | 386919 |

## 常见问题

1. **问题**：安装时报错 "Could not find a version that satisfies the requirement"
   **解决方案**：检查 `pyproject.toml` 和 `setup.py` 中的依赖版本是否兼容

2. **问题**：运行时报错 "Module not found"
   **解决方案**：确认已正确安装小红书爬虫包，可以尝试重新运行安装脚本

3. **问题**：获取不到小红书数据
   **解决方案**：更新 cookie 或检查网络连接，cookie 可以通过浏览器开发者工具获取

4. **问题**：Excel中的景点ID带有.0后缀
   **解决方案**：已修复此问题，程序会自动将386917.0转换为386917

5. **问题**：文件路径错误导致相关性分析文件保存后无法找到
   **解决方案**：已修复此问题，统一使用processed/rednote目录

## 联系与支持

如有问题或需要支持，请提交 Issue 或联系项目维护者。 