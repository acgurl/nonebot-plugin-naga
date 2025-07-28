from pydantic import BaseModel


class Config(BaseModel):
    """Naga NoneBot 插件配置"""
    # NagaAgent API 配置
    naga_api_host: str = "127.0.0.1"
    naga_api_port: int = 8000
    
    # HANDOFF 循环配置
    max_handoff_loop: int = 5
    show_handoff: bool = False