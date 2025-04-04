from datetime import datetime

from pydantic import BaseModel, field_validator


class ChatSessionPublic(BaseModel):
    id: int
    user_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatSessionPublicList(BaseModel):
    data: list[ChatSessionPublic]


class ChatSessionTitle(BaseModel):
    id: int
    title: str | None

    class Config:
        from_attributes = True


class ChatSessionTitleList(BaseModel):
    data: list[ChatSessionTitle]


class ChatSessionId(BaseModel):
    id: int


class ChatSessionMessage(BaseModel):
    sender: str
    text: str


class ChatSessionMessageList(BaseModel):
    data: list[ChatSessionMessage]


class ChatSessionCreate(BaseModel):
    user_id: int
    title: str | None = "New chat"

    @field_validator("title")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("null value is not allowed")
        return v


class ChatSessionCreateRequest(BaseModel):
    title: str


class ChatSessionUpdateRequest(BaseModel):
    title: str


class ConversationCreate(BaseModel):
    chat_session_id: int
    sender: str
    message: str
    sender_id: int


class UserChatSessionCreateRequest(BaseModel):
    chat_session_id: int
    sender: str
    message: str


class GenerateAnswerRequest(BaseModel):
    chat_session_id: int
    bot_id: int
    question: str
    context: list | None
