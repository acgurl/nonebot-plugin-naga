import re
import json
from typing import Dict, Any, Optional


def parse_handoff_content(content: str) -> Optional[Dict[str, Any]]:
    """
    解析LLM返回的工具调用格式内容（JSON格式）
    
    Args:
        content: 包含工具调用格式的文本
        
    Returns:
        解析后的字典，包含service_name和参数，如果未找到则返回None
    """
    # 查找JSON格式的工具调用 ｛...｝
    pattern = r'｛([\s\S]*?)｝'
    match = re.search(pattern, content)
    if not match:
        return None
    
    try:
        # 提取并解析JSON内容
        json_content = "{" + match.group(1).strip() + "}"
        tool_args = json.loads(json_content)
        
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
    except json.JSONDecodeError:
        return None