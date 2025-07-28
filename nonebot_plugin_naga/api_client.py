import httpx
from typing import AsyncGenerator, Dict, Any, Optional
import json
import logging

from . import plugin_config


# 创建日志记录器
logger = logging.getLogger(__name__)


class NagaAgentClient:
    """NagaAgent API 客户端"""
    
    def __init__(self):
        """初始化客户端"""
        self.base_url = f"http://{plugin_config.naga_api_host}:{plugin_config.naga_api_port}"
        self.client = httpx.AsyncClient()
    
    async def health_check(self) -> bool:
        """
        健康检查
        
        Returns:
            bool: 服务器是否健康
        """
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            is_healthy = response.status_code == 200
            logger.debug(f"健康检查结果: {is_healthy}")
            return is_healthy
        except Exception as e:
            logger.warning(f"健康检查失败: {str(e)}")
            return False
    
    async def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        普通对话接口
        
        Args:
            message: 用户消息
            session_id: 会话ID（可选）
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/chat"
        data = {
            "message": message,
            "stream": False
        }
        if session_id:
            data["session_id"] = session_id
            
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()  # 检查HTTP错误
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "message": f"HTTP错误 {e.response.status_code}: {getattr(e.response, 'text', str(e))}"
            }
        except httpx.RequestError as e:
            return {
                "status": "error",
                "message": f"无法连接到 NagaAgent API: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"API响应格式错误: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"API调用失败: {str(e)}"
            }
    
    async def chat_stream(self, message: str, session_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """
        流式对话接口
        
        Args:
            message: 用户消息
            session_id: 会话ID（可选）
            
        Yields:
            流式响应数据
        """
        url = f"{self.base_url}/chat/stream"
        data = {
            "message": message,
            "stream": True
        }
        if session_id:
            data["session_id"] = session_id
            
        try:
            async with self.client.stream("POST", url, json=data) as response:
                response.raise_for_status()  # 检查HTTP错误
                async for chunk in response.aiter_text():
                    if chunk.startswith("data: "):
                        yield chunk[6:]  # 去掉 "data: " 前缀
        except httpx.HTTPStatusError as e:
            yield f"HTTP错误 {e.response.status_code}: {getattr(e.response, 'text', str(e))}"
        except httpx.RequestError as e:
            yield f"错误: 无法连接到 NagaAgent API: {str(e)}"
        except Exception as e:
            yield f"错误: API调用失败: {str(e)}"
    
    async def mcp_handoff(self, service_name: str, task: Dict[str, Any], session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        MCP服务调用接口
        
        Args:
            service_name: 服务名称
            task: 任务信息
            session_id: 会话ID（可选）
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/mcp/handoff"
        data = {
            "service_name": service_name,
            "task": task
        }
        if session_id:
            data["session_id"] = session_id
            
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()  # 检查HTTP错误
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "message": f"HTTP错误 {e.response.status_code}: {getattr(e.response, 'text', str(e))}"
            }
        except httpx.RequestError as e:
            return {
                "status": "error",
                "message": f"无法连接到 NagaAgent API: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"API响应格式错误: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"API调用失败: {str(e)}"
            }
    
    async def toggle_developer_mode(self, enabled: bool) -> Dict[str, Any]:
        """
        切换开发者模式
        
        Args:
            enabled: 是否启用开发者模式
            
        Returns:
            API响应结果
        """
        url = f"{self.base_url}/system/devmode"
        data = {"enabled": enabled}
        try:
            response = await self.client.post(url, json=data)
            response.raise_for_status()  # 检查HTTP错误
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP错误 {e.response.status_code}: {getattr(e.response, 'text', str(e))}"
            logger.error(f"切换开发者模式HTTP错误: {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }
        except httpx.RequestError as e:
            error_msg = f"无法连接到 NagaAgent API: {str(e)}"
            logger.error(f"切换开发者模式请求错误: {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }
        except json.JSONDecodeError as e:
            error_msg = f"API响应格式错误: {str(e)}"
            logger.error(f"切换开发者模式JSON解析错误: {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }
        except Exception as e:
            error_msg = f"API调用失败: {str(e)}"
            logger.error(f"切换开发者模式未知错误: {error_msg}")
            return {
                "status": "error",
                "message": error_msg
            }
    
    async def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息
        
        Returns:
            系统信息
        """
        url = f"{self.base_url}/system/info"
        try:
            response = await self.client.get(url)
            response.raise_for_status()  # 检查HTTP错误
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "status": "error",
                "message": f"HTTP错误 {e.response.status_code}: {getattr(e.response, 'text', str(e))}"
            }
        except httpx.RequestError as e:
            return {
                "status": "error",
                "message": f"无法连接到 NagaAgent API: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"API响应格式错误: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"API调用失败: {str(e)}"
            }