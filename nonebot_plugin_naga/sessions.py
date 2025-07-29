import uuid
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class Session:
    """会话数据类"""
    id: str
    user_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_used: datetime = field(default_factory=datetime.now)
    alias: Optional[str] = None
    
    def update_last_used(self):
        """更新最后使用时间"""
        self.last_used = datetime.now()
    
    def is_expired(self, timeout: timedelta = timedelta(hours=2)) -> bool:
        """检查会话是否过期"""
        return datetime.now() - self.last_used > timeout


class SessionManager:
    """会话管理器"""
    
    def __init__(self):
        # 存储所有会话 {session_id: Session}
        self.sessions: Dict[str, Session] = {}
        # 存储用户默认会话 {user_id: session_id}
        self.user_default_sessions: Dict[str, str] = {}
        # 存储用户会话别名 {user_id: {alias: session_id}}
        self.user_session_aliases: Dict[str, Dict[str, str]] = {}
    
    def create_session(self, user_id: str, alias: Optional[str] = None) -> Session:
        """为用户创建新会话"""
        session_id = str(uuid.uuid4())
        session = Session(id=session_id, user_id=user_id, alias=alias)
        self.sessions[session_id] = session
        
        # 如果是用户第一个会话，设为默认会话
        if user_id not in self.user_default_sessions:
            self.user_default_sessions[user_id] = session_id
            
        # 如果有别名，添加别名映射
        if alias:
            if user_id not in self.user_session_aliases:
                self.user_session_aliases[user_id] = {}
            self.user_session_aliases[user_id][alias] = session_id
            
        return session
    
    def get_session(self, user_id: str, session_id: Optional[str] = None, alias: Optional[str] = None) -> Optional[Session]:
        """获取用户会话"""
        # 如果指定了session_id，直接返回
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            if session.user_id == user_id:
                session.update_last_used()
                return session
            return None
            
        # 如果指定了别名，尝试通过别名查找
        if alias and user_id in self.user_session_aliases:
            alias_map = self.user_session_aliases[user_id]
            if alias in alias_map:
                session_id = alias_map[alias]
                if session_id in self.sessions:
                    session = self.sessions[session_id]
                    session.update_last_used()
                    return session
                    
        # 如果没有指定session_id或alias，返回用户的默认会话
        if user_id in self.user_default_sessions:
            default_session_id = self.user_default_sessions[user_id]
            if default_session_id in self.sessions:
                session = self.sessions[default_session_id]
                session.update_last_used()
                return session
                
        return None
    
    def set_default_session(self, user_id: str, session_id: str) -> bool:
        """设置用户默认会话"""
        if session_id in self.sessions and self.sessions[session_id].user_id == user_id:
            self.user_default_sessions[user_id] = session_id
            self.sessions[session_id].update_last_used()
            return True
        return False
    
    def set_session_alias(self, user_id: str, session_id: str, alias: str) -> bool:
        """为会话设置别名"""
        if session_id in self.sessions and self.sessions[session_id].user_id == user_id:
            if user_id not in self.user_session_aliases:
                self.user_session_aliases[user_id] = {}
            self.user_session_aliases[user_id][alias] = session_id
            self.sessions[session_id].alias = alias
            self.sessions[session_id].update_last_used()
            return True
        return False
    
    def remove_session_alias(self, user_id: str, alias: str) -> bool:
        """移除会话别名"""
        if user_id in self.user_session_aliases and alias in self.user_session_aliases[user_id]:
            del self.user_session_aliases[user_id][alias]
            # 查找并清除会话对象中的别名
            for session in self.sessions.values():
                if session.user_id == user_id and session.alias == alias:
                    session.alias = None
                    break
            return True
        return False
    
    def delete_session(self, user_id: str, session_id: str) -> bool:
        """删除会话"""
        if session_id in self.sessions and self.sessions[session_id].user_id == user_id:
            session = self.sessions[session_id]
            
            # 从别名映射中移除
            if session.alias and user_id in self.user_session_aliases:
                if session.alias in self.user_session_aliases[user_id]:
                    del self.user_session_aliases[user_id][session.alias]
            
            # 如果是默认会话，清除默认会话设置
            if user_id in self.user_default_sessions and self.user_default_sessions[user_id] == session_id:
                del self.user_default_sessions[user_id]
                
            # 删除会话
            del self.sessions[session_id]
            return True
        return False
    
    def list_user_sessions(self, user_id: str) -> List[Session]:
        """列出用户的所有会话"""
        return [session for session in self.sessions.values() if session.user_id == user_id]
    
    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            return {
                "id": session.id,
                "user_id": session.user_id,
                "created_at": session.created_at.isoformat(),
                "last_used": session.last_used.isoformat(),
                "alias": session.alias,
                "is_default": session.id == self.user_default_sessions.get(session.user_id)
            }
        return None
    
    def cleanup_expired_sessions(self, timeout: timedelta = timedelta(hours=2)):
        """清理过期会话"""
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.is_expired(timeout):
                expired_sessions.append(session_id)
                
        for session_id in expired_sessions:
            # 从别名映射中移除
            user_id = self.sessions[session_id].user_id
            if self.sessions[session_id].alias and user_id in self.user_session_aliases:
                alias = self.sessions[session_id].alias
                if alias in self.user_session_aliases[user_id]:
                    del self.user_session_aliases[user_id][alias]
            
            # 如果是默认会话，清除默认会话设置
            if user_id in self.user_default_sessions and self.user_default_sessions[user_id] == session_id:
                del self.user_default_sessions[user_id]
                
            # 删除会话
            del self.sessions[session_id]


# 全局会话管理器实例
session_manager = SessionManager()