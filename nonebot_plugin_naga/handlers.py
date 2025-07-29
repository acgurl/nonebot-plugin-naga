from nonebot import on_message, logger
from nonebot.adapters import Bot, Event
from nonebot.typing import T_State
from nonebot.rule import Rule
import json
import asyncio

from .api_client import NagaAgentClient
from .utils import parse_handoff_content
from . import plugin_config

# 创建API客户端实例
naga_client = NagaAgentClient()

# 存储用户自定义前缀的字典 {user_id: prefix}
user_prefixes = {}

import random
import time

# 存储用户会话信息的字典 {user_id: {session_name: session_id, ...}}
user_sessions = {}

# 存储用户当前活跃会话名的字典 {user_id: active_session_name}
active_sessions = {}

# 已生成的会话ID集合，确保唯一性
generated_session_ids = set()

# 生成唯一的6位数字会话ID
def generate_session_id() -> str:
    """生成唯一的6位数字会话ID"""
    max_attempts = 100  # 最大尝试次数，防止无限循环
    for _ in range(max_attempts):
        # 使用时间戳和随机数生成唯一ID
        timestamp = int(time.time()) % 1000000  # 取时间戳后6位
        random_num = random.randint(0, 999999)  # 6位随机数
        # 组合生成6位数字ID
        session_id = (timestamp + random_num) % 1000000
        session_id_str = f"{session_id:06d}"  # 格式化为6位数字，不足的前面补0
        
        # 检查ID是否唯一
        if session_id_str not in generated_session_ids:
            generated_session_ids.add(session_id_str)
            return session_id_str
    
    # 如果尝试次数过多，使用随机生成
    while True:
        session_id_str = f"{random.randint(0, 999999):06d}"
        if session_id_str not in generated_session_ids:
            generated_session_ids.add(session_id_str)
            return session_id_str

# API服务器健康状态
api_healthy = None
# 健康检查是否已经执行过
health_check_done = False

# 定义规则：消息以 #naga 开头或者匹配用户自定义前缀
async def message_match_naga(bot: Bot, event: Event, state: T_State) -> bool:
    """检查消息是否以 #naga 开头或者匹配用户自定义前缀"""
    # 棣检查是否是支持的消息事件类型
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

# 插件启动时检查API服务器状态
async def check_api_health():
    """检查API服务器健康状态"""
    global api_healthy, health_check_done
    if not health_check_done:  # 只执行一次健康检查
        api_healthy = await naga_client.health_check()
        health_check_done = True
        if api_healthy:
            logger.success("NagaAgent API服务器连接正常")
        else:
            logger.error("NagaAgent API服务器未响应，请检查服务器是否启动")

# 我们不能直接在这里创建任务，因为此时可能还没有运行的事件循环
# 改为在第一次实际使用时检查健康状态


async def handle_session_commands(user_id: str, command: str, handler) -> None:
    """处理会话管理命令"""
    logger.debug(f"用户 {user_id} 请求会话管理命令: {command}")
    
    # 初始化用户会话字典
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    # 初始化用户活跃会话
    if user_id not in active_sessions:
        active_sessions[user_id] = None  # 没有活跃会话
    
    # 分析命令
    if command == "list":
        # 列出所有会话
        sessions = user_sessions.get(user_id, {})
        active_session = active_sessions.get(user_id)
        
        # 如果没有任何会话，显示提示信息
        if not sessions:
            await handler.finish("""📋 会话列表:\n  ❗ 暂无会话\n\n💡 提示：\n • 发送任意消息即可自动创建默认会话\n • 使用 '#naga session create <名称>' 创建新会话""")
            return
        
        session_list = "📋 会话列表:\n"
        for name, session_id in sessions.items():
            marker = "🔹" if name == active_session else "  "
            active_marker = " ← 当前激活" if name == active_session else ""
            session_list += f"{marker} {name}: {session_id or '未激活'}{active_marker}\n"
        await handler.finish(session_list.rstrip())
    
    elif command == "clear":
        # 清空所有会话
        user_sessions[user_id] = {}
        active_sessions[user_id] = None
        await handler.finish("✅ 已清空所有会话")
    
    elif command.startswith("switch "):
        # 切换会话
        session_name = command[7:].strip()  # 7是"switch "的长度
        if not session_name:
            await handler.finish("❌ 请提供会话名称")
        
        sessions = user_sessions.get(user_id, {})
        if session_name not in sessions:
            await handler.finish(f"❌ 会话 '{session_name}' 不存在")
        
        active_sessions[user_id] = session_name
        await handler.finish(f"✅ 已切换到会话 '{session_name}'")
    
    elif command.startswith("create "):
        # 创建新会话
        session_name = command[7:].strip()  # 7是"create "的长度
        if not session_name:
            await handler.finish("❌ 请提供会话名称")
        
        sessions = user_sessions.get(user_id, {})
        if session_name in sessions:
            await handler.finish(f"❌ 会话 '{session_name}' 已存在")
        
        # 创建新会话（初始ID为None，将在首次使用时由API分配）
        sessions[session_name] = None
        user_sessions[user_id] = sessions
        
        # 自动激活新创建的会话
        active_sessions[user_id] = session_name
        await handler.finish(f"✅ 已创建并激活会话 '{session_name}'")
    
    elif command.startswith("delete "):
        # 删除会话
        session_name = command[7:].strip()  # 7是"delete "的长度
        if not session_name:
            await handler.finish("❌ 请提供会话名称")
        
        sessions = user_sessions.get(user_id, {})
        if session_name not in sessions:
            await handler.finish(f"❌ 会话 '{session_name}' 不存在")
        
        # 删除会话
        del sessions[session_name]
        user_sessions[user_id] = sessions
        
        # 如果删除的是当前活跃会话，清除活跃会话
        if active_sessions.get(user_id) == session_name:
            active_sessions[user_id] = None
        
        await handler.finish(f"✅ 已删除会话 '{session_name}'")
    
    elif command.startswith("rename "):
        # 重命名会话
        parts = command[7:].strip().split(" ", 1)  # 7是"rename "的长度
        if len(parts) != 2:
            await handler.finish("❌ 命令格式错误，请使用: session rename <旧名称> <新名称>")
        
        old_name, new_name = parts
        if not old_name or not new_name:
            await handler.finish("❌ 请提供旧会话名称和新会话名称")
        
        sessions = user_sessions.get(user_id, {})
        if old_name not in sessions:
            await handler.finish(f"❌ 会话 '{old_name}' 不存在")
        
        if new_name in sessions:
            await handler.finish(f"❌ 会话 '{new_name}' 已存在")
        
        # 重命名会话
        session_id = sessions.pop(old_name)
        sessions[new_name] = session_id
        user_sessions[user_id] = sessions
        
        # 如果重命名的是当前活跃会话，更新活跃会话名
        if active_sessions.get(user_id) == old_name:
            active_sessions[user_id] = new_name
        
        await handler.finish(f"✅ 已将会话 '{old_name}' 重命名为 '{new_name}'")
    
    elif command == "info":
        # 显示当前会话信息
        active_session = active_sessions.get(user_id)
        sessions = user_sessions.get(user_id, {})
        session_id = sessions.get(active_session) if active_session else None
        
        info_text = "📊 当前会话信息:\n"
        if active_session:
            info_text += f"  活跃会话: {active_session}\n"
            info_text += f"  会话ID: {session_id or '未分配'}\n"
        else:
            info_text += "  活跃会话: 无\n"
        info_text += f"  总会话数: {len(sessions)}"
        await handler.finish(info_text)
    
    else:
        # 显示帮助信息
        help_text = """📋 会话管理命令:
#naga session list - 列出所有会话
#naga session switch <名称> - 切换到指定会话
#naga session create <名称> - 创建新会话
#naga session delete <名称> - 删除指定会话
#naga session rename <旧名称> <新名称> - 重命名会话
#naga session clear - 清空所有会话
#naga session info - 显示当前会话信息
#naga session - 显示此帮助信息"""
        await handler.finish(help_text)


@naga_handler.handle()
async def handle_naga_command(bot: Bot, event: Event, state: T_State):
    """处理以 #naga 开头或匹配自定义前缀的命令"""
    global api_healthy
    
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
    
    # 为用户ID添加平台标识以避免不同平台间的会话混淆
    if hasattr(event, 'adapter'):
        adapter_name = event.adapter.get_name()
        user_id = f"{adapter_name}_{user_id}"
    elif hasattr(bot, 'adapter') and hasattr(bot.adapter, 'get_name'):
        adapter_name = bot.adapter.get_name()
        user_id = f"{adapter_name}_{user_id}"
    
    # 记录用户ID和消息内容以便调试
    logger.debug(f"获取到用户ID: {user_id}, 消息内容: '{plain_text}'")
    
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
        help_text = """🤖 NagaAgent AI助手使用说明:
#naga [消息] - 发送消息给AI
#naga activate [前缀] - 设置自定义激活前缀

🔧 会话管理命令:
#naga session list - 列出所有会话
#naga session switch <名称> - 切换到指定会话
#naga session create <名称> - 创建新会话
#naga session delete <名称> - 删除指定会话
#naga session rename <旧名称> <新名称> - 重命名会话
#naga session clear - 清空所有会话
#naga session info - 显示当前会话信息
#naga session - 显示此帮助信息

⚙️ 系统管理命令:
#naga devmode on - 启用开发者模式
#naga devmode off - 禁用开发者模式
#naga sysinfo - 获取系统信息"""
        await naga_handler.finish(help_text)
    
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
    
    # 检查API服务器是否在线（首次使用时执行健康检查）
    if api_healthy is None:
        # 首次使用时执行健康检查
        await check_api_health()
    
    if not api_healthy:
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
    
    # 会话管理命令
    elif user_message.startswith("session "):
        await handle_session_commands(user_id, user_message[8:], naga_handler)  # 8是"session "的长度
        return
    
    # 处理普通对话
    try:
        logger.info(f"开始处理普通对话请求: {user_message}")
        
        # 获取用户的会话ID（如果存在）
        # 如果用户没有任何会话，自动创建一个默认会话
        if user_id not in user_sessions:
            user_sessions[user_id] = {}
        
        user_session_dict = user_sessions.get(user_id, {})
        active_session_name = active_sessions.get(user_id)
        
        # 初始化session_id变量
        session_id = None
        
        # 如果没有任何会话，自动创建默认会话
        if not user_session_dict:
            # 创建默认会话，使用生成的6位数字ID
            default_session_id = generate_session_id()
            user_session_dict["default"] = default_session_id
            user_sessions[user_id] = user_session_dict
            active_sessions[user_id] = "default"
            active_session_name = "default"
            session_id = default_session_id
            logger.debug(f"为用户 {user_id} 自动创建默认会话，ID: {default_session_id}")
        # 如果没有活跃会话但有会话存在，使用第一个会话
        elif not active_session_name and user_session_dict:
            active_session_name = next(iter(user_session_dict))
            active_sessions[user_id] = active_session_name
            # 确保会话有有效的ID
            session_id = user_session_dict.get(active_session_name)
            if not session_id:
                session_id = generate_session_id()
                user_session_dict[active_session_name] = session_id
                user_sessions[user_id] = user_session_dict
                logger.debug(f"为用户 {user_id} 的会话 '{active_session_name}' 分配ID: {session_id}")
        else:
            # 如果有活跃会话，获取会话ID
            if active_session_name:
                session_id = user_session_dict.get(active_session_name)
                # 如果会话ID不存在或无效，生成新的ID
                if not session_id:
                    session_id = generate_session_id()
                    user_session_dict[active_session_name] = session_id
                    user_sessions[user_id] = user_session_dict
                    logger.debug(f"为用户 {user_id} 的会话 '{active_session_name}' 分配ID: {session_id}")
        
        # 确保session_id不为None
        if not session_id:
            session_id = generate_session_id()
            # 如果有活跃会话，则更新该会话的ID
            if active_session_name:
                user_session_dict[active_session_name] = session_id
                user_sessions[user_id] = user_session_dict
                logger.debug(f"为用户 {user_id} 的会话 '{active_session_name}' 更新ID: {session_id}")
            else:
                # 如果没有活跃会话，创建默认会话
                user_session_dict["default"] = session_id
                user_sessions[user_id] = user_session_dict
                active_sessions[user_id] = "default"
                active_session_name = "default"
                logger.debug(f"为用户 {user_id} 创建默认会话，ID: {session_id}")
        
        logger.debug(f"用户 {user_id} 的活跃会话 '{active_session_name}' ID: {session_id}")
        
        # 先尝试普通对话
        response = await naga_client.chat(user_message, session_id)
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
            new_session_id = response.get("session_id")
            
            # 保存用户的会话ID以供后续对话使用
            # 如果API没有返回新的会话ID，使用我们生成的ID
            actual_session_id = new_session_id if new_session_id else session_id
            
            if actual_session_id:
                # 初始化用户会话字典
                if user_id not in user_sessions:
                    user_sessions[user_id] = {}
                
                # 获取当前活跃会话名
                active_session_name = active_sessions.get(user_id)
                
                # 如果有活跃会话，保存会话ID
                if active_session_name:
                    user_sessions[user_id][active_session_name] = actual_session_id
                    logger.debug(f"为用户 {user_id} 的会话 '{active_session_name}' 保存ID: {actual_session_id}")
                    
                    # 更新当前会话ID变量，确保在后续工具调用中使用正确的会话ID
                    session_id = actual_session_id
                
            logger.info(f"API调用成功，回复长度: {len(reply) if reply else 0}, session_id: {session_id}")
            
            # 检查回复是否为空
            if not reply:
                logger.warning("API返回了空回复")
                await naga_handler.finish("API返回了空回复")
            
            # 检查是否有HANDOFF内容需要处理（工具调用）
            handoff_data = parse_handoff_content(reply)
            if handoff_data:
                logger.info(f"检测到工具调用，开始处理工具调用循环: {handoff_data['service_name']}")
                # 确保session_id已定义
                if 'session_id' not in locals():
                    logger.warning("在工具调用循环中，session_id未定义，使用默认值")
                    session_id = None
                
                # 处理工具调用循环
                for i in range(plugin_config.max_handoff_loop):
                    logger.info(f"执行第 {i+1} 次工具调用: {handoff_data['service_name']}")
                    # 执行MCP服务调用
                    # 根据新的API文档，task应该包含tool_name和其他参数
                    task_data = handoff_data["params"].copy()
                    service_result = await naga_client.mcp_handoff(
                        handoff_data["service_name"],
                        task_data,
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
                    # 确保session_id在调用前已定义
                    if 'session_id' not in locals() or session_id is None:
                        logger.warning("在工具调用循环中，session_id未定义，使用默认值")
                        session_id = None
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
                    # 更新会话ID（如果API返回了新的会话ID）
                    new_session_id = followup_response.get("session_id")
                    # 如果API没有返回新的会话ID，使用我们生成的ID
                    actual_session_id = new_session_id if new_session_id else session_id
                    
                    if actual_session_id:
                        # 初始化用户会话字典
                        if user_id not in user_sessions:
                            user_sessions[user_id] = {}
                        
                        # 获取当前活跃会话名
                        active_session_name = active_sessions.get(user_id)
                        
                        # 如果有活跃会话，保存会话ID
                        if active_session_name:
                            user_sessions[user_id][active_session_name] = actual_session_id
                            logger.debug(f"为用户 {user_id} 的会话 '{active_session_name}' 更新ID: {actual_session_id}")
                            
                            # 更新当前会话ID变量
                            session_id = actual_session_id
                    
                    handoff_data = parse_handoff_content(reply)
                    
                    # 如果没有更多的工具调用内容，跳出循环
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