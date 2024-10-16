import enum
from datetime import datetime

import pytz
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

KST = pytz.timezone("Asia/Seoul")


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_social = Column(Boolean, default=False)
    social_accounts = relationship("SocialAccount", backref="user")


class SocialAccount(Base):
    __tablename__ = "social_account"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    provider = Column(String, nullable=False)
    provider_user_id = Column(String, unique=True, nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_session"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"))
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(KST), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(KST),
        onupdate=lambda: datetime.now(KST),
        nullable=False,
    )
    user = relationship("User", backref="chat_sessions")


class ConversationSenderType(enum.Enum):
    user = "user"
    bot = "bot"


class Conversation(Base):
    __tablename__ = "conversation"
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_session.id"), nullable=False)
    sender = Column(Enum(ConversationSenderType), nullable=False)
    sender_id = Column(Integer, nullable=False, default=-1)
    message = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(KST), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(KST),
        onupdate=lambda: datetime.now(KST),
        nullable=False,
    )
    chat_session = relationship("ChatSession", backref="conversations")

    def get_sender(self):
        if self.sender == ConversationSenderType.user:
            return self.conversation.query(User).get(self.sender_id)
        elif self.sender == ConversationSenderType.bot:
            return self.conversation.query(Bot).get(self.sender_id)


class Bot(Base):
    __tablename__ = "bot"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(KST), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(KST),
        onupdate=lambda: datetime.now(KST),
        nullable=False,
    )
