# nonebot-plugin-naga

与NagaAgent API交互的NoneBot插件

## 功能

- 与NagaAgent API交互，实现智能对话
- 支持流式对话和普通对话
- 支持MCP服务调用（符合最新API规范）
- 支持开发者模式切换
- 支持系统信息查询
- 支持工具调用循环（自动解析和执行LLM返回的工具调用）
- 支持多会话管理，可以创建、切换、重命名、删除会话
- 支持会话保持，同一用户连续对话使用相同会话ID
- 优化长消息处理，支持流式输出避免超时

## 安装

> 注意：当前为测试版本，尚未上架插件商店。

### 从源码安装

1. 克隆项目到本地：
   ```bash
   git clone <repository-url>
   ```

2. 进入项目目录：
   ```bash
   cd naga-bot
   ```

3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

4. 配置环境变量（参考下方配置说明）

## 配置

在`.env`文件中添加以下配置：

```env
# NagaAgent API 配置
NAGA_API_HOST=127.0.0.1
NAGA_API_PORT=8000

# HANDOFF 循环配置
NAGA_MAX_HANDOFF_LOOP=5
NAGA_SHOW_HANDOFF=false
```

## 使用方法

1. 发送以 `#naga` 开头的消息与AI交互，例如: `#naga 你好`
2. 配置自定义激活前缀: `#naga activate [前缀]`
   - 例如: `#naga activate AI>` 将设置 `AI>` 为激活前缀
   - 之后可用 `AI> 你好` 的方式与AI交互
   - 每个用户只能设置一个自定义前缀，重复设置会覆盖之前的设置
3. 多会话管理：
   - `#naga session list` - 列出所有会话
   - `#naga session switch <名称>` - 切换到指定会话
   - `#naga session create <名称>` - 创建新会话（自动激活）
   - `#naga session delete <名称>` - 删除指定会话
   - `#naga session rename <旧名称> <新名称>` - 重命名会话
   - `#naga session clear` - 清空所有会话
   - `#naga session info` - 显示当前会话信息
   - `#naga session` - 显示会话管理帮助
4. 特殊命令:(在使用默认激活方式`#naga`或自定义前缀后跟以下命令)
   - `devmode on` - 启用开发者模式
   - `devmode off` - 禁用开发者模式
   - `sysinfo` - 获取系统信息

## 会话管理

插件支持完整的多会话管理功能：

1. **按需创建**：用户首次发送消息时自动创建默认会话
2. **多会话支持**：可以创建多个会话，每个会话有独立的上下文
3. **会话切换**：可以在不同会话之间切换
4. **会话管理**：支持创建、重命名、删除会话
5. **会话保持**：同一会话内连续对话将保持上下文连贯性
6. **会话ID唯一性**：每个会话都有唯一的6位数字ID
7. **自动激活**：创建新会话后自动激活该会话
8. **智能提示**：在没有会话时显示友好提示
9. **当前会话标记**：在会话列表中标记当前激活的会话
10. **会话ID处理**：自动处理API返回的会话ID，确保会话连续性

## 工具调用支持

插件支持自动解析和执行LLM返回的工具调用，格式如下：

```json
{
  "agentType": "mcp",
  "service_name": "MCP服务名称",
  "tool_name": "工具名称",
  "参数名": "参数值"
}
```

插件会自动执行工具调用并将结果返回给LLM进行进一步处理。

## 依赖

- nonebot2>=2.0.0
- httpx>=0.23.0
- pydantic>=1.10.0

## 支持的适配器

所有适配器（插件仅使用基本适配器功能）

## 许可证

MIT