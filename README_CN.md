# Scopus MCP Server

<!-- mcp-name: io.github.qwe4559999/scopus-mcp -->

**中文** | [English](README.md)

> **💡 查看 [使用指南与提示词示例](USAGE_EXAMPLES.md) 了解如何与该工具进行对话！**

这是一个基于 Model Context Protocol (MCP) 的服务器，用于访问 Elsevier Scopus API。它允许 AI 助手（如 Claude）搜索学术论文、获取摘要以及查找作者资料。

**请注意，申请 Elsevier Scopus API 一般要求您的组织或机构订阅了 Elsevier 数据库服务。此外，要通过零配置方式运行此工具，您的设备必须安装 `uv` 包管理器。**

## 配置方法

### 设置步骤
1.  前往 [Elsevier Developer Portal](https://dev.elsevier.com/) 申请免费的 API Key。
2.  在项目根目录下创建一个 `config.json` 文件（或从 `config.json.example` 复制），并填入你的 Key：
    ```json
    {
      "api_key": "YOUR_KEY_HERE"
    }
    ```
3.  编辑 `MCP_tool_config.json`，修改文件夹路径（注意在 Windows 上也要使用正斜杠 `/` 或双反斜杠 `\\`）。
4.  最后，将 `MCP_tool_config.json` 的内容复制到你的 MCP 客户端配置文件中（例如 Claude Desktop）。

## 🚀 快速开始 (零配置启动)

**前提条件**: 你的电脑需要安装 `uv`。
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

如果你使用 Claude Desktop，你可以跳过去下载代码的繁琐步骤，直接通过以下配置使用：

1.  **获取 Key**: 从 [Elsevier Developer Portal](https://dev.elsevier.com/) 获取 API Key。(⚠️ **注意**: 建议使用教育/机构邮箱申请，普通邮箱可能无法通过或权限受限)
2.  **修改配置**: 编辑 `%APPDATA%\Claude\claude_desktop_config.json` (Windows) 或 `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)。
3.  **添加内容**:

```json
{
  "mcpServers": {
    "scopus-assistant": {
      "command": "uvx",
      "args": [
        "scopus-mcp"
      ],
      "env": {
        "SCOPUS_API_KEY": "把你的KEY填在这里"
      }
    }
  }
}
```

*(如果你没有安装 uv，也可以使用传统的 [安装说明](#安装说明) 手动部署)*

### 在 Trae 中使用

在 Trae 设置 -> MCP Servers -> 点击 **添加** -> 选择 **手动配置 (JSON)**，然后粘贴以下内容：

```json
{
  "mcpServers": {
    "scopus-assistant": {
      "command": "uvx",
      "args": [
        "scopus-mcp"
      ],
      "env": {
        "SCOPUS_API_KEY": "把你的KEY填在这里"
      }
    }
  }
}
```

### 在 Cursor 中使用

1.  打开 **Cursor Settings** -> **Features** -> **MCP Servers**。
2.  点击 **+ Add New MCP Server**。
3.  填写信息：
    *   **Name**: `scopus-mcp`
    *   **Type**: `command` (stdio)
    *   **Command**: `uvx scopus-mcp`
4.  **注意**: 你需要在系统环境变量中设置 `SCOPUS_API_KEY`。

## 安装说明

1.  确保你已安装 Python 3.10 或更高版本。
2.  安装依赖：
    ```bash
    pip install .
    ```

## 使用指南

### 运行服务器

你可以使用 `uvx` (推荐) 或直接通过 python 运行。

```bash
# 使用 uvx
uvx --from . scopus-mcp

# 或者直接使用 python
python -m scopus_mcp.server
```

### 可用工具

1.  **`search_scopus`**
    -   使用标准查询语法搜索 Scopus 数据库。
    -   参数:
        -   `query` (string): 搜索查询语句 (例如 `TITLE("Artificial Intelligence")`).
        -   `count` (integer): 返回结果数量 (默认: 5).
        -   `sort` (string): 排序方式 (例如 `coverDate`).

2.  **`get_abstract_details`**
    -   通过 Scopus ID 获取文档的详细信息。
    -   参数:
        -   `scopus_id` (string): 文档的 Scopus ID。

3.  **`get_author_profile`**
    -   获取作者的个人资料信息。
    -   参数:
        -   `author_id` (string): Scopus Author ID。

## 开发

运行测试:
```bash
pytest
```

## 许可证

本项目基于 MIT 许可证开源 - 详情请查看 [LICENSE](LICENSE) 文件。

## 致谢与贡献者

<a href="https://github.com/qwe4559999/scopus-mcp/graphs/contributors">
  <img alt="contributors" src="https://contrib.rocks/image?repo=qwe4559999/scopus-mcp" />
</a>

*   **[thinktraveller](https://github.com/thinktraveller)** - *初始工作与核心开发*
*   **[qwe4559999](https://github.com/qwe4559999)** - *维护者*
