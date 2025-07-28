from nonebot import get_plugin_config, logger
from nonebot.plugin import PluginMetadata

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-naga",
    description="与NagaAgent API交互的NoneBot插件",
    usage="发送以 #naga 开头的消息与AI交互，例如: #naga 你好",
    config=Config,
    type="application",
    homepage="https://github.com/your-org/nonebot-plugin-naga",
    supported_adapters=None,  # 支持所有适配器
    extra={
        "author": "your-name",
        "email": "your-email@example.com",
        "license": "MIT",
        "dependencies": {
            "nonebot2": ">=2.0.0",
            "httpx": ">=0.23.0",
            "pydantic": ">=1.10.0"
        }
    }
)

# 获取插件配置
plugin_config = get_plugin_config(Config)

# 记录插件成功加载的日志
logger.success("Naga-NoneBot 插件加载成功")

# 导入处理器以注册事件处理函数
from . import handlers

