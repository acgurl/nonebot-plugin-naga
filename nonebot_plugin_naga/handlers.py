from nonebot import on_message, logger
from nonebot.adapters import Bot, Event
from nonebot.typing import T_State
from nonebot.rule import Rule
import json

from .api_client import NagaAgentClient
from .utils import parse_handoff_content
from . import plugin_config

# 创建API客户端实例
naga_client = NagaAgentClient()

# 存储用户自定义前缀的字典 {user_id: prefix}
user_prefixes = {}

# 定义规则：消息以 #naga 开头或者匹配用户自定义前缀
async def message_match_naga(bot: Bot, event: Event, state: T_State) -> bool:
    """检查消息是否以 #naga 开头或者匹配用户自定义前缀"""
    # 检查是否是支持的消息事件类型
    plain_text = ""
    user_id = None
    
    # 尝试获取消息文本和用户ID（适用于所有适配器）
    if hasattr(event, 'get_plaintext'):
        plain_text = event.get_plaintext().strip()
    elif hasattr(event, 'get_message'):
        try:
            message = event.get_message()
            if hasattr(message, 'extract_plain_text'):
                plain_text = message.extract_plain_text().strip()
        except Exception:
            pass
    
    # 尝试获取用户ID
    if hasattr(event, 'get_user_id'):
        user_id = event.get_user_id()
    elif hasattr(event, 'user_id'):
        user_id = str(event.user_id)
    else:
        # 如果无法获取用户ID，使用事件类型和ID组合作为标识符
        user_id = f"{event.__class__.__name__}_{getattr(event, 'event_id', 'unknown')}"
    
    if plain_text and user_id:
        # 检查是否以 #naga 开头
        if plain_text.startswith("#naga"):
            state["user_id"] = user_id
            state["prefix_type"] = "default"
            logger.info(f"检测到Naga默认激活消息: {plain_text}")
            return True
            
        # 检查是否匹配用户自定义前缀
        user_prefix = user_prefixes.get(user_id)
        if user_prefix and plain_text.startswith(user_prefix):
            state["user_id"] = user_id
            state["prefix_type"] = "custom"
            state["custom_prefix"] = user_prefix
            logger.info(f"检测到Naga自定义激活消息: {plain_text} (前缀: {user_prefix})")
            return True
            
    return False

# 创建消息处理器
naga_handler = on_message(
    rule=Rule(message_match_naga),
    priority=10,
    block=True
)

logger.info("Naga处理器已注册，支持所有适配器")


@naga_handler.handle()
async def handle_naga_command(bot: Bot, event: Event, state: T_State):
    """处理以 #naga 开头或匹配自定义前缀的命令"""
    # 获取用户消息
    plain_text = ""
    user_id = None
    
    # 获取消息文本内容和用户ID（适用于所有适配器）
    if hasattr(event, 'get_plaintext'):
        plain_text = event.get_plaintext().strip()
    elif hasattr(event, 'get_message'):
        try:
            message = event.get_message()
            if hasattr(message, 'extract_plain_text'):
                plain_text = message.extract_plain_text().strip()
        except Exception:
            pass
    
    # 获取用户ID
    if hasattr(event, 'get_user_id'):
        user_id = event.get_user_id()
    elif hasattr(event, 'user_id'):
        user_id = str(event.user_id)
    else:
        # 如果无法获取用户ID，使用事件类型和ID组合作为标识符
        user_id = f"{event.__class__.__name__}_{getattr(event, 'event_id', 'unknown')}"
    
    if not plain_text or not user_id:
        logger.warning("无法从事件中提取消息文本或用户ID")
        await naga_handler.finish("无法处理该消息")
    
    # 根据激活方式提取用户消息
    prefix_type = state.get("prefix_type", "default")
    user_message = ""
    
    if prefix_type == "default":
        # 以 #naga 开头的情况
        if plain_text.startswith("#naga"):
            # 移除 #naga 前缀和可能的空格
            user_message = plain_text[5:].lstrip()  # 5是"#naga"的长度
    elif prefix_type == "custom":
        # 匹配自定义前缀的情况
        custom_prefix = state.get("custom_prefix", "")
        if custom_prefix and plain_text.startswith(custom_prefix):
            # 移除自定义前缀和可能的空格
            user_message = plain_text[len(custom_prefix):].lstrip()
    
    logger.info(f"Naga功能被激活，用户ID: {user_id}, 消息: {user_message}")
    
    if not user_message:
        # 如果没有消息内容，显示帮助信息
        await naga_handler.finish("用法:\n#naga [消息] - 发送消息给AI\n#naga activate [前缀] - 设置自定义激活前缀")
    
    # 检查是否是配置命令
    if user_message.startswith("activate "):
        # 设置用户自定义前缀
        new_prefix = user_message[9:].strip()  # 9是"activate "的长度
        if new_prefix:
            user_prefixes[user_id] = new_prefix
            logger.info(f"用户 {user_id} 设置自定义前缀: {new_prefix}")
            await naga_handler.finish(f"✅ 已设置自定义激活前缀为: {new_prefix}")
        else:
            await naga_handler.finish("❌ 请提供有效的前缀")
    
    # 检查API服务器是否在线
    is_api_healthy = await naga_client.health_check()
    logger.debug(f"API健康检查结果: {is_api_healthy}")
    if not is_api_healthy:
        logger.error("NagaAgent API服务器未响应，请检查服务器是否启动")
        await naga_handler.finish("NagaAgent API服务器未响应，请检查服务器是否启动")
    
    # 检查是否是特殊命令
    logger.debug(f"用户消息: '{user_message}'")
    if user_message == "devmode on":
        logger.info("用户请求启用开发者模式")
        result = await naga_client.toggle_developer_mode(True)
        logger.debug(f"开发者模式切换结果: {result}")
        # 检查结果格式
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get('message', '未知错误')
            logger.error(f"开发者模式启用失败: {error_msg}")
            await naga_handler.finish(f"❌ 操作失败: {error_msg}")
        await naga_handler.finish("✅ 开发者模式已启用")
    elif user_message == "devmode off":
        logger.info("用户请求禁用开发者模式")
        result = await naga_client.toggle_developer_mode(False)
        logger.debug(f"开发者模式切换结果: {result}")
        # 检查结果格式
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get('message', '未知错误')
            logger.error(f"开发者模式禁用失败: {error_msg}")
            await naga_handler.finish(f"❌ 操作失败: {error_msg}")
        await naga_handler.finish("✅ 开发者模式已禁用")
    elif user_message == "sysinfo":
        logger.info("用户请求获取系统信息")
        result = await naga_client.get_system_info()
        logger.debug(f"系统信息获取结果: {result}")
        # 检查结果格式
        if isinstance(result, dict) and result.get("status") == "error":
            error_msg = result.get('message', '未知错误')
            logger.error(f"系统信息获取失败: {error_msg}")
            await naga_handler.finish(f"❌ 操作失败: {error_msg}")
        # 格式化系统信息
        info_text = "🔧 系统信息:\n"
        for key, value in result.items():
            info_text += f"  {key}: {value}\n"
        await naga_handler.finish(info_text.rstrip())
    
    # 处理普通对话
    try:
        logger.info(f"开始处理普通对话请求: {user_message}")
        # 先尝试普通对话
        response = await naga_client.chat(user_message)
        logger.debug(f"API响应: {response}")
        
        # 检查响应格式
        if not isinstance(response, dict):
            logger.error(f"API响应格式错误，期望dict，实际得到: {type(response)}")
            await naga_handler.finish("API响应格式错误")
            
        # 检查API调用是否成功
        if response.get("status") == "error":
            error_msg = response.get("message", "API调用失败")
            logger.error(f"API调用失败: {error_msg}")
            await naga_handler.finish(f"API调用失败: {error_msg}")
            
        if response.get("status") == "success":
            reply = response.get("response", "")
            session_id = response.get("session_id")
            logger.info(f"API调用成功，回复长度: {len(reply) if reply else 0}, session_id: {session_id}")
            
            # 检查回复是否为空
            if not reply:
                logger.warning("API返回了空回复")
                await naga_handler.finish("API返回了空回复")
            
            # 检查是否有HANDOFF内容需要处理
            handoff_data = parse_handoff_content(reply)
            if handoff_data:
                logger.info(f"检测到HANDOFF内容，开始处理工具调用循环: {handoff_data['service_name']}")
                # 处理工具调用循环
                for i in range(plugin_config.max_handoff_loop):
                    logger.info(f"执行第 {i+1} 次工具调用: {handoff_data['service_name']}")
                    # 执行MCP服务调用
                    service_result = await naga_client.mcp_handoff(
                        handoff_data["service_name"],
                        {"action": "execute", "params": handoff_data["params"]},
                        session_id
                    )
                    logger.debug(f"工具调用结果: {service_result}")
                    
                    # 检查工具调用结果
                    if not isinstance(service_result, dict):
                        logger.error(f"工具调用响应格式错误: {type(service_result)}")
                        await naga_handler.finish("工具调用响应格式错误")
                    
                    # 检查工具调用是否成功
                    if service_result.get("status") == "error":
                        error_msg = service_result.get("message", "工具调用失败")
                        logger.error(f"工具调用失败: {error_msg}")
                        await naga_handler.finish(f"工具调用失败: {error_msg}")
                    
                    # 将结果发送回LLM进行下一步处理
                    followup_message = f"工具 {handoff_data['service_name']} 执行结果: {json.dumps(service_result, ensure_ascii=False)}"
                    logger.debug(f"发送给LLM的消息: {followup_message}")
                    followup_response = await naga_client.chat(
                        followup_message,
                        session_id
                    )
                    logger.debug(f"LLM响应: {followup_response}")
                    
                    # 检查LLM响应格式
                    if not isinstance(followup_response, dict):
                        logger.error(f"LLM响应格式错误: {type(followup_response)}")
                        await naga_handler.finish("LLM响应格式错误")
                        
                    # 检查LLM调用是否成功
                    if followup_response.get("status") == "error":
                        error_msg = followup_response.get("message", "LLM调用失败")
                        logger.error(f"LLM调用失败: {error_msg}")
                        await naga_handler.finish(f"LLM调用失败: {error_msg}")
                        
                    reply = followup_response.get("response", "")
                    handoff_data = parse_handoff_content(reply)
                    
                    # 如果没有更多的HANDOFF内容，跳出循环
                    if not handoff_data:
                        logger.info("工具调用循环结束")
                        break
                    
                    if plugin_config.show_handoff:
                        await naga_handler.send(f"中间结果: {reply}")
            
            # 发送最终回复
            logger.info(f"发送最终回复给用户，长度: {len(reply) if reply else 0}")
            if not reply:
                await naga_handler.finish("未收到有效的回复内容")
            await naga_handler.finish(reply)
        else:
            error_msg = f"API调用失败: {response.get('message', '未知错误')}"
            logger.error(error_msg)
            await naga_handler.finish(error_msg)
            
    except Exception as e:
        # 检查是否是 Matcher 相关的异常，这些是正常的流程控制异常
        from nonebot.exception import MatcherException, FinishedException
        if isinstance(e, FinishedException):
            # 这是正常的 finish 调用，不需要记录错误日志
            logger.debug("事件处理正常结束")
            raise  # 重新抛出异常以确保正常流程
        elif isinstance(e, MatcherException):
            # 其他 Matcher 异常，记录但不视为错误
            logger.info(f"Matcher 流程控制: {type(e).__name__}")
            raise  # 重新抛出异常以确保正常流程
        else:
            # 真正的异常情况
            logger.error(f"NagaAgent API调用出错: {e}", exc_info=True)
            try:
                await naga_handler.finish("处理命令时发生错误，请稍后重试")
            except FinishedException:
                # 如果 finish 也抛出 FinishedException，这是正常的
                pass