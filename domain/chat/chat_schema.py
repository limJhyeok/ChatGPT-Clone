from pydantic import BaseModel
from typing import Optional

class ChatSessionCreate(BaseModel):
    user_id: int
    title: Optional[str] = "New chat"


class ChatSessionCreateRequest(BaseModel):
    title: str

class ChatSessionUpdateRequest(BaseModel):
    renamed_title: str


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
   context: Optional[list]