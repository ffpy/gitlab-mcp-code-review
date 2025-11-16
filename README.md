# GitLab MCP 代码审查工具

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> 本项目 fork 自 [cayirtepeomer/gerrit-code-review-mcp](https://github.com/cayirtepeomer/gerrit-code-review-mcp) 并为 GitLab 集成进行了适配。

一个用于将 Claude 等 AI 助手与 GitLab 的合并请求集成的 MCP (Model Context Protocol) 服务器。这使得 AI 助手可以通过 GitLab API 直接审查代码变更。

<a href="https://glama.ai/mcp/servers/@ffpy/gitlab-mcp-code-review">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@ffpy/gitlab-mcp-code-review/badge" alt="GitLab Code Review MCP server" />
</a>

## 功能

- **完整的合并请求分析**: 获取合并请求的全部详情,包括差异、提交和评论
- **文件特定的差异**: 分析合并请求中特定文件的变更
- **版本比较**: 比较不同的分支、标签或提交
- **审查管理**: 添加评论、批准或取消批准合并请求
- **项目概览**: 获取项目中的所有合并请求列表

## 安装

### 先决条件

- Python 3.10+
- uv
- 具有 API 范围 (read_api, api) 的 GitLab 个人访问令牌
- 用于 MCP 集成的 [Cursor IDE](https://cursor.sh/) 或 [Claude 桌面应用](https://claude.ai/desktop)

## Cursor IDE 集成

克隆此仓库：
```bash
git clone https://gitea.ffpy.site/ffpy/gitlab-mcp-code-review.git
cd gitlab-mcp-code-review
```

要将此 MCP 与 Cursor IDE 一起使用,请将以下配置添加到你的 `~/.cursor/mcp.json` 文件中：

```json
{
  "mcpServers": {
    "gitlab-mcp-code-review": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/your/gitlab-mcp-code-review",
        "run",
        "server.py"
      ],
      "env": {
        "GITLAB_HOST": "gitlab.com",
        "GITLAB_TOKEN": "xxx"
      }
    }
  }
}
```

- 将 `/path/to/your/gitlab-mcp-code-review` 替换为你克隆仓库的实际路径。
- 将 `GITLAB_HOST` 修改为你的Gitlab地址
- 将 `GITLAB_TOKEN` 修改为你的AccessToken

## 可用工具

MCP 服务器提供以下工具用于与 GitLab 交互：

| 工具 | 描述 |
|---|---|
| `fetch_merge_request` | 获取有关合并请求的完整信息 |
| `compare_versions` | 比较不同的分支、标签或提交 |
| `add_merge_request_comment` | 向合并请求添加评论 |
| `approve_merge_request` | 批准合并请求 |
| `unapprove_merge_request` | 取消批准合并请求 |
| `get_project_merge_requests` | 获取项目的合并请求列表 |

## 故障排除

如果遇到问题：

1.  验证你的 GitLab 令牌是否具有适当的权限 (api, read_api)
2.  确保你的 MCP 配置路径正确
3.  使用以下命令测试连接：`curl -H "Private-Token: your-token" https://gitlab.com/api/v4/projects`

## 许可证

本项目根据 MIT 许可证授权 - 有关详细信息,请参阅 [LICENSE](LICENSE) 文件。