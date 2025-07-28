# nonebot-plugin-naga

与NagaAgent API交互的NoneBot插件

## 功能

- 与NagaAgent API交互，实现智能对话
- 支持流式对话和普通对话
- 支持MCP服务调用
- 支持开发者模式切换
- 支持系统信息查询

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
3. 特殊命令:(在使用默认激活方式`#naga`或自定义前缀后跟以下命令)
   - `devmode on` - 启用开发者模式
   - `devmode off` - 禁用开发者模式
   - `sysinfo` - 获取系统信息

## 依赖

- nonebot2>=2.0.0
- httpx>=0.23.0
- pydantic>=1.10.0

## 支持的适配器

所有适配器（插件仅使用基本适配器功能）

## 许可证

MIT