# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个 MCP (Model Context Protocol) 服务器，用于将 AI 助手与 GitLab 的合并请求集成。它允许 AI 助手通过 GitLab API 直接审查代码变更、添加评论和管理审批流程。

## 核心架构

### 主要文件
- `server.py`: MCP 服务器的主入口文件，包含所有工具定义和 GitLab API 集成逻辑
- `config.toml`: 配置文件，定义代码审查时需要忽略的文件模式
- `pyproject.toml`: Python 项目配置，包含依赖和工具配置

### 关键组件

1. **FastMCP 服务器**: 使用 `mcp.server.fastmcp.FastMCP` 创建 MCP 服务器
2. **GitLab 客户端**: 通过 `python-gitlab` 库与 GitLab API 交互
3. **生命周期管理**: 使用 `gitlab_lifespan` 异步上下文管理器管理 GitLab 连接

### MCP 工具列表

服务器暴露以下工具（位于 server.py）:

- `fetch_merge_request`: 获取合并请求的完整信息（包括变更、提交和讨论）
- `compare_versions`: 比较两个提交/分支/标签之间的差异
- `add_merge_request_comment`: 添加常规评论到合并请求
- `add_merge_request_discussion`: 在文件特定位置添加讨论
- `reply_to_merge_request_discussion`: 回复讨论
- `resolve_merge_request_discussion`: 解决或取消解决讨论
- `delete_merge_request_discussion`: 删除讨论
- `approve_merge_request`: 批准合并请求
- `unapprove_merge_request`: 取消批准合并请求
- `get_project_merge_requests`: 获取项目的合并请求列表
- `search_projects`: 按名称搜索 GitLab 项目
- `fetch_code_review_rules`: 通过 SSH 从远程服务器获取团队的代码审查规范

### 数据过滤机制

`fetch_merge_request` 工具实现了智能数据过滤：
- 使用 `config.toml` 中的 `exclude_patterns` 过滤不需要审查的文件
- 精简 API 响应数据，只返回必要字段，减少 token 使用
- 支持通配符模式和目录模式匹配（见 `is_path_excluded` 函数）

## 环境变量

### 必需的环境变量（可以在 `.env` 文件中设置）:
- `GITLAB_HOST`: GitLab 实例的主机名（默认: gitlab.com）
- `GITLAB_TOKEN`: GitLab 个人访问令牌（必需，需要 api 和 read_api 权限）

### 可选的环境变量（用于代码审查规范功能）:
- `CODE_REVIEW_SSH_HOST`: SSH 服务器地址
- `CODE_REVIEW_SSH_PORT`: SSH 端口（默认: 22）
- `CODE_REVIEW_SSH_USERNAME`: SSH 用户名
- `CODE_REVIEW_SSH_PASSWORD`: SSH 密码
- `CODE_REVIEW_RULE_FILE`: 规范文件在服务器上的绝对路径

## 常用命令

### 运行服务器
```bash
uv run server.py
```

### 安装依赖
```bash
uv sync
```

### 开发依赖（可选）
```bash
uv sync --extra dev
```

## 修改代码时的注意事项

1. **添加新的 MCP 工具**: 使用 `@mcp.tool()` 装饰器，第一个参数必须是 `ctx: Context`
2. **访问 GitLab 客户端**: 通过 `ctx.request_context.lifespan_context` 获取 GitLab 客户端实例
3. **数据精简**: 当从 GitLab API 获取数据时，应该只返回必要的字段以减少响应大小
4. **文件过滤**: 修改 `config.toml` 中的 `exclude_patterns` 来调整忽略的文件类型
5. **错误处理**: 使用 logger 记录错误，遵循现有的日志模式
6. **返回类型**: 所有工具函数都应该返回可序列化的 Dict 或 List

## 代码审查工作流程

**重要提醒**: 在审查任何合并请求或代码变更之前，应该先调用 `fetch_code_review_rules` 工具获取团队的代码审查规范。这样可以确保按照团队统一的标准进行审查。

推荐的代码审查流程：
1. 调用 `fetch_code_review_rules` 获取团队的代码审查规范
2. 调用 `fetch_merge_request` 获取合并请求的详细信息
3. 根据规范审查代码变更
4. 使用 `add_merge_request_discussion` 在具体代码行添加审查意见
5. 如果需要，使用 `approve_merge_request` 或提供改进建议

## GitLab API 集成细节

- 项目 ID 可以是数字 ID 或 URL 编码的项目路径
- 合并请求使用项目内的 IID（非全局 ID）
- 讨论位置需要包含 base_sha、start_sha、head_sha 等完整的 diff 引用信息
- 删除讨论是通过删除其第一个 note 来实现的
