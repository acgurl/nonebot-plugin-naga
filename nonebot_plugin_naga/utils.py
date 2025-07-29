import re
import json
from typing import Dict, Any, Optional


def parse_handoff_content(content: str) -> Optional[Dict[str, Any]]:
    """
    解析LLM返回的工具调用格式内容（JSON格式）
    支持两种格式：
    1. 特殊括号格式：｛"agentType": "mcp", "service_name": "...", ...｝
    2. 标准JSON格式：{"agentType": "mcp", "service_name": "...", ...}
    
    Args:
        content: 包含工具调用格式的文本
        
    Returns:
        解析后的字典，包含service_name和参数，如果未找到则返回None
    """
    # 查找JSON格式的工具调用，支持标准JSON格式和特殊括号格式
    # 首先尝试查找特殊括号格式 ｛...｝
    special_pattern = r'｛([\s\S]*?)｝'
    special_match = re.search(special_pattern, content)
    
    if special_match:
        try:
            # 提取并解析JSON内容
            json_content = "{" + special_match.group(1).strip() + "}"
            tool_args = json.loads(json_content)
        except json.JSONDecodeError:
            return None
    else:
        # 如果没有特殊括号格式，尝试查找标准JSON格式
        # 查找包含agentType和service_name的JSON对象
        standard_pattern = r'\{[^{}]*"agentType"\s*:\s*"[^"]*"[^{}]*"service_name"\s*:\s*"[^"]*"[^{}]*\}'
        standard_match = re.search(standard_pattern, content)
        if not standard_match:
            return None
            
        try:
            tool_args = json.loads(standard_match.group(0))
        except json.JSONDecodeError:
            return None
    
    # 检查agentType是否为mcp
    agent_type = tool_args.get('agentType')
    if agent_type != 'mcp':
        return None
        
    # 获取服务名称
    service_name = tool_args.get('service_name')
    if not service_name:
        return None
        
    # 提取参数（排除service_name和agentType）
    params = {k: v for k, v in tool_args.items() 
             if k not in ['service_name', 'agentType']}
    
    return {
        "service_name": service_name,
        "params": params
    }