from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from domain.chat import chat_crud, chat_schema, chat_utils
from domain.user import user_router
from models import User
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import asyncio
import json
from operator import itemgetter
from langchain_core.runnables import RunnablePassthrough
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import HumanMessage

router = APIRouter(
    prefix = "/api/chat"
)

EMPTY_CHAT_SESSION_ID = -1
DELEAY_SECONDS_FOR_STREAM = 0.0001

EEVE_KOREAN_MAX_TOKENS = 4096
EEVE_KOREAN_BUFFER_TOKENS = 96

@router.get("/titles")
def get_chat_history_titles(current_user: User = Depends(user_router.get_current_user), db: Session = Depends(get_db)):
    db_chat_sessions = chat_crud.get_chat_session_histories(db, current_user.id)
    if not db_chat_sessions:
        return []
    
    chat_session_titles = [{'id': db_chat_session.id, 'name': db_chat_session.title} for db_chat_session in db_chat_sessions]
    return chat_session_titles

@router.get("/recent")
def get_recent_chat_session_id(current_user: User = Depends(user_router.get_current_user), db: Session = Depends(get_db)):
    recent_chat_session = chat_crud.get_recent_chat_session(db, current_user.id)
    return {
        "id": recent_chat_session.id
    }
@router.get("/session/{chat_session_id}")
def get_conversations(chat_session_id: int, db: Session = Depends(get_db), current_user: User = Depends(user_router.get_current_user)):
    res = {"message_history": {
        "messages": []
        }
    }
    if chat_session_id == EMPTY_CHAT_SESSION_ID:
        return res

    db_conversations = chat_crud.get_conversations(db, chat_session_id)
    if db_conversations:
        res["message_history"]["messages"] = [{"sender": db_conversation.sender, "text": db_conversation.message} for db_conversation in db_conversations]
    return res


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_chat(chat_session_create_request: chat_schema.ChatSessionCreateRequest,
                db: Session = Depends(get_db),
                current_user: User = Depends(user_router.get_current_user)):
    chat_session_create = chat_schema.ChatSessionCreate(
        user_id = current_user.id,
        title = chat_session_create_request.title
    )
    chat_crud.create_chat_session(
        db = db,
        chat_session_create = chat_session_create
    )

@router.put("/rename/{chat_session_id}")
def update_chat(chat_session_id: int,
    chat_session_update_request: chat_schema.ChatSessionUpdateRequest,
    db: Session = Depends(get_db)):
    chat_crud.update_chat_session(
        db,
        chat_session_id,
        chat_session_update_request
    )

@router.delete("/delete/{chat_session_id}")
def delete_chat(chat_session_id: int, db: Session = Depends(get_db)):
    chat_crud.delete_chat_session(db, chat_session_id)

@router.post("/session", status_code=status.HTTP_201_CREATED)
def post_user_conversation(user_chat_session_create_request: chat_schema.UserChatSessionCreateRequest,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(user_router.get_current_user)):
    chat_session = chat_crud.get_chat_session(db, user_chat_session_create_request.chat_session_id)
    if not chat_session:
        # TODO: refactoring?(모듈화): create_chat과 매우 비슷
        # TODO: user_chat_session_create_request.message와 AI를 이용하여 chat의 title 부여한 후에 ChatCreate 만들기
        chat_session_create = chat_schema.ChatSessionCreate(
        user_id = current_user.id,
        )
        db_chat_session = chat_crud.create_chat_session(
            db=db,
            chat_session_create=chat_session_create
        )
        user_chat_session_create_request.chat_session_id = db_chat_session.id

    conversation_create = chat_schema.ConversationCreate(
        sender_id = current_user.id,
        chat_session_id = user_chat_session_create_request.chat_session_id,
        sender = user_chat_session_create_request.sender,
        message = user_chat_session_create_request.message
    )
    chat_crud.create_conversation(
        db=db,
        conversation_create=conversation_create
    )

@router.post("/generate-answer", status_code=status.HTTP_201_CREATED)
async def generate_answer(generate_answer_request: chat_schema.GenerateAnswerRequest, db: Session = Depends(get_db)):
    # TODO: bot에 따라 다르게 모델 불러오는 Logic 필요
    chat_session_id = generate_answer_request.chat_session_id
    question = generate_answer_request.question
    await ensure_chat_session_initialized(chat_session_id, question, db)

    bot = chat_crud.get_bot(db, generate_answer_request.bot_id)
    llm = get_llm()

    token_trimmer = chat_utils.get_token_trimmer(model = llm, max_tokens = EEVE_KOREAN_MAX_TOKENS - EEVE_KOREAN_BUFFER_TOKENS)
    return StreamingResponse(stream_answer(llm, question, chat_session_id, db, bot, token_trimmer, DELEAY_SECONDS_FOR_STREAM),
                            media_type = "text/event-stream")


def load_and_split_documents(pdf_path: str, chunk_size=1000, chunk_overlap=200):
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    splits = text_splitter.split_documents(documents)
    return splits

def create_vectorstore_and_retriever(splits):
    vectorstore = Chroma.from_documents(documents=splits, embedding=HuggingFaceBgeEmbeddings())
    return vectorstore.as_retriever()

def create_history_aware_retriever_chain(llm, retriever):
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    
    history_aware_retriever = create_history_aware_retriever(llm, retriever, contextualize_q_prompt)
    return history_aware_retriever

def create_question_answer_chain(llm):
    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer "
        "the question. If you don't know the answer, say that you "
        "don't know. Use three sentences maximum and keep the "
        "answer concise."
        "\n\n"
        "{context}"
    )
    
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    return question_answer_chain

def create_rag_chain(llm, retriever):
    question_answer_chain = create_question_answer_chain(llm)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    return rag_chain

async def stream_answer(llm, question, chat_session_id, db, bot, token_trimmer, delay_seconds_for_stream):
    # TODO: use rag shuole be requested from frontend
    use_rag = False
    config = {"configurable": {"session_id": f"{chat_session_id}"}}
    if use_rag:
        retriever = None
        # TODO: pdf should be served from frontend
        pdf_path = "some_document.pdf"
        splits = load_and_split_documents(pdf_path)
        retriever = create_vectorstore_and_retriever(splits)

        history_aware_retriever = create_history_aware_retriever_chain(llm, retriever)
        chain = create_rag_chain(llm, history_aware_retriever)
        with_message_history_keys = {
            "input_messages_key": "input",
            "history_messages_key": "chat_history",
            "output_messages_key": "answer"
        }
        message_history_inputs = {
            "input": question,
        }
    else:
        prompt = get_prompt()
        with_message_history_keys = {
            "input_messages_key":"messages",
        }
        chain = create_chain_with_trimmer(token_trimmer, prompt, llm)
        if chat_session_id not in chat_utils.chat_session_store or not chat_utils.chat_session_store[chat_session_id].messages:
            messages = chat_utils.chat_session_store[chat_session_id].messages
        else:
            messages = [HumanMessage(content=question)]
        message_history_inputs = {
        "messages": messages
        }

    with_message_history = RunnableWithMessageHistory(chain, chat_utils.get_chat_session_history_from_dict, 
                                                        **with_message_history_keys)
    
    final_response = ""
    for response in with_message_history.stream(message_history_inputs,
                                                config = config):
        answer = response.get("answer") if use_rag else response.content
        if answer:
            final_response += answer
            yield json.dumps({"status": "processing", "data": answer}, ensure_ascii=False) + "\n"
            await asyncio.sleep(delay_seconds_for_stream) 
    await save_bot_conversation(db = db,
                        chat_session_id = chat_session_id,
                        message = final_response,
                        sender_id = bot.id)
    yield json.dumps({"status": "complete", "data": "Stream finished"}, ensure_ascii=False) + "\n"


async def ensure_chat_session_initialized(chat_session_id: int, question: str, db) -> list:
    if chat_session_id not in chat_utils.chat_session_store or not chat_utils.chat_session_store[chat_session_id].messages:
        chat_utils.get_chat_session_history_from_db(chat_utils.chat_session_store, db, chat_session_id)

def create_chain_with_trimmer(token_trimmer, prompt, llm):
    chain = (
        RunnablePassthrough.assign(messages=itemgetter("messages") | token_trimmer)
        | prompt
        | llm
    )
    return chain

async def save_bot_conversation(db, chat_session_id: int, message: str, sender_id: int):
    bot_conversation_create = chat_schema.ConversationCreate(
        chat_session_id=chat_session_id,
        sender='bot',
        message=message,
        sender_id=sender_id
    )
    chat_crud.create_conversation(db, bot_conversation_create)

def get_prompt():
    prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a helpful assistant. Answer all questions to the best of your ability.",
        ),
        MessagesPlaceholder(variable_name="messages"),
    ]
    )
    return prompt

def get_llm():
    llm = ChatOllama(
        model="EEVE-Korean-10.8B:latest"
        )
    return llm