<script>
  import { faBars, faComments, faEllipsis } from '@fortawesome/free-solid-svg-icons';
  import { FontAwesomeIcon } from '@fortawesome/svelte-fontawesome';
  import { isLogin, isSignUpPage, chatTitles, sessionMessages, accessToken, userEmail } from "../lib/store"
  import fastapi from "../lib/api";
  import { onMount, tick } from 'svelte';
  $: chatTitles, sessionMessages
  let activeMessages = []
  let userMessage = '';
  let activeChatSessionId = -1;
  let isSidebarVisible = true;
  let newChatTitle = '';
  let isNewChatModalOpen = false;
  let answer = '';
  let generateLoading = false;
  let checkDeleteChatModalOpen = false;
  let selectedChatId = null;
  
  function openNewChatModal() {
    isNewChatModalOpen = true;
  }

  function closeNewChatModal() {
    isNewChatModalOpen = false;
    newChatTitle = '';
  }

  function sendMessage() {
    if (userMessage.trim()) {
      let url = '/api/chat/session'
      let params = {
        chat_session_id: activeChatSessionId,
        sender: 'user',
        message: userMessage
      }
      fastapi('post', url, params, 
        (json) => {
          sessionMessages.update(state => {
            return {
              ...state,
              messages: [...state.messages, { sender: 'user', text: userMessage }]
            };
          });
          generateAnswer();
          userMessage = '';
          
        },
        (json_error) => {
          error = json_error
        }
      )
    }
  }

  function generateAnswer() {
    generateLoading = true;
    let _url = "/api/chat/generate-answer"
    let url = import.meta.env.VITE_SERVER_URL + _url
    let method = "POST"
    let headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        }
    let params = {
            chat_session_id: activeChatSessionId,
            bot_id: 1,
            question: userMessage,
            context: $sessionMessages.messages
        }

    fetch(url, {
        method: method,
        headers: headers,
        body: JSON.stringify(params)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        function read() {
            reader.read().then(({ done, value }) => {
              try {
                generateLoading = false;
                if (done) {
                      sessionMessages.update(state => {
                                    return {
                                        ...state,
                                        messages: [...state.messages, { sender: 'bot', text: answer }]
                                    };
                                });
                      answer = '';
                      return;
                }

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');
                lines.forEach(line => {
                    if (line.trim()) {
                        const parsedLine = JSON.parse(line);
                        const status = parsedLine.status;
                        const data = parsedLine.data;
                        if (status === 'processing') {
                            answer = (answer ?? '') + data;                        
                        }
                    }
                });
                read(); 
              } catch (err) {
                handleGenerateError(err)
              }
            }
          );
        }
        read();
    })
    .catch(error => {
        console.error('Fetch error:', error);
    });
  }
  
  function handleGenerateError(err){
    answer = ''
    generateLoading = false;
    console.error(err)
  }

  function getChatTitles() {
    let url = "/api/chat/titles"
    let params = {}

    fastapi('get', url, params, 
        (json) => {
          chatTitles.set(json);
        },
        (json_error) => {
            error = json_error
        }
    )
  }
  getChatTitles()
  function getSessionMessages(chat_id) {
    let url = "/api/chat/session/" + chat_id
    let params = {}
    fastapi('get', url, params, 
        (json) => {
          sessionMessages.set(json.message_history)
        },
        (json_error) => {
            error = json_error
        }
    )
  }
  function createNewChat(){
    let url = "/api/chat/create"
    let params = {title: newChatTitle}
    fastapi('post', url, params, 
        (json) => {
            newChatTitle=''
            getChatTitles();
            closeNewChatModal(); 
        },
        (json_error) => {
            error = json_error
        }
    )
  }
  function selectChat(id) {
    activeChatSessionId = id
    getSessionMessages(id)
  }
  function toggleSidebar() {
    isSidebarVisible = !isSidebarVisible;
  }
  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault(); 
      sendMessage();
    }
  }
  
  function goToSignUp(){
    $isSignUpPage = true
    window.location.hash = '#/authorize';
  }
  function goToLogin(){
    $isSignUpPage = false
    window.location.hash = '#/authorize';
  }
  function handleLogOut(){
    $accessToken=""
    $isLogin=false
    $userEmail=""
    window.location.reload();
  }
  function autoResizeTextArea(event) {
        const textarea = event.target;
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
    }

  let editingChatTitleId = null;
  let inputElement = null;
  function handleRenameChatButton(chatId){
    editingChatTitleId = chatId
    closePopup();
    tick().then(() => {
      if (inputElement) {
        inputElement.focus();  // 인풋 요소에 포커스
      }
    });
  }
  function openCheckDeleteChatModal(chatId){
    closePopup();
    checkDeleteChatModalOpen = true;
    selectedChatId = chatId;
  }
  function closeCheckDeleteChatModal(){
    checkDeleteChatModalOpen = false;
  }
  function deleteChat(chatId){
    openCheckDeleteChatModal(chatId);
  }
  function renameChatTitle(chatTitle) {
    if (newChatTitle.trim() === '' || newChatTitle === chatTitle.name) {
      return
    }
    let url = `/api/chat/rename/${chatTitle.id}`;  // TODO: url 및 inDTO 변경
    let params = { renamed_title: newChatTitle };
    
    fastapi('put', url, params,
      (json) => {
        editingChatTitleId = null;
        newChatTitle='';
        getChatTitles();
      },
      (json_error) => {
        console.error("Error updating chat title:", json_error);
      }
    );
  }
  function cancelEdit() {
    newChatTitle = '';
    inputElement=null;
    editingChatTitleId = null;
    
  }

  function handleKeyPress(event, chatTitle) {
    if (event.key === 'Enter') {
      renameChatTitle(chatTitle);
      cancelEdit();
    } else if (event.key === 'Escape') {
      cancelEdit();
    } 
  }
  
  function confirmDeleteChat() {
    let url = `/api/chat/delete/${selectedChatId}`  
    let params = {}  

    fastapi('delete', url, params,
      (json) => { 
        selectedChatId = null;
        activeChatSessionId = -1;
        closeCheckDeleteChatModal();
        getChatTitles();
      },
      (json_error) => {
        error = json_error;
        selectedChatId = null;
        closeCheckDeleteChatModal();
      }
    );
  }
  let activePopupId = null
  let popupContainer;

  function togglePopup(chatId, event) {
    event.stopPropagation();
    const button = event.currentTarget;
    const buttonRect = button.getBoundingClientRect();

    if (activePopupId === chatId) {
      closePopup();
    } else {
      activePopupId = chatId;
      if (popupContainer) {
        popupContainer.style.display = 'block';
        popupContainer.style.top = `${buttonRect.bottom}px`;
        popupContainer.style.left = `${buttonRect.right}px`;
      }
    }
  }

  function closePopup() {
    activePopupId = null;
    if (popupContainer) {
      popupContainer.style.display = 'none';
    }
  }

  function handleClickOutside(event) {
    if (popupContainer && !popupContainer.contains(event.target) && !event.target.closest('.options-container')) {
      closePopup();
    }
  }

  onMount(() => {
    document.addEventListener('click', handleClickOutside);
    return () => {
      document.removeEventListener('click', handleClickOutside);
    };
  });
</script>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
<!-- TODO: refactoring style sheet -->
<style>
  .sidebar {
    width: 200px;
    height: 90vh;
    display: flex;
    flex-direction: column;
    transition: width 0.3s;
  }
  .sidebar.hidden {
    width: 0;
    overflow: hidden;
    transition: width 0.3s;
  }
  .fa-bars-comments-container {
    display: flex;
    align-items: center;
    transition: all 0.3s ease;
  }
  .chat-item {
  position: relative;
  }

  .chat-button-container {
    display: flex;
    align-items: center;
    transition: background-color 0.3s ease;
    margin-top: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .chat-button-container:hover,
  .chat-button-container.active {
    background-color: #eee;
  }

  .sidebar button {
    flex-grow: 1;
    background: transparent;
    border: none;
    text-align: left;
    padding: 0.5rem 1rem;
  }
  .options-container {
    opacity: 0;
    transition: opacity 0.3s ease;
  }

  .chat-button-container:hover .options-container,
  .chat-button-container.active .options-container {
    opacity: 1;
  }

  .options-popup {
    position: fixed;
    background-color: white;
    border-radius: 8px;
    padding: 10px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    z-index: 9999;
    width: 150px;
  }
  .sidebar button.active {
    background-color: #eee;
  }
  .sidebar button:hover {
    background-color: #eee;
  }

  .sidebar ul {
    list-style: none;
    padding: 15px 20px;
    cursor: pointer;
  }
  .top-bar {
    display: flex;
    justify-content: flex-end;
    padding: 10px;
  }

  .messages {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
    padding: 1rem;
    height: 100vh;
  }
  .input-container {
    display: flex;
    padding: 1rem;
    background-color: #fff;
    margin-right: 20vh;
    margin-left: 20vh;
  }
  .input-container textarea {
    flex: 1;
    padding: 0.5rem;
    font-size: 1rem;
    min-height: 5vh;
    max-height: 30vh;
    overflow-y: auto;
    resize: none;
  }
  .input-container button {
    margin-left: 0.5rem;
    padding: 0.5rem 1rem;
    font-size: 1rem;
    border: none;
    background-color: #007bff;
    color: white;
    border-radius: 4px;
    cursor: pointer;
  }
  .input-container button:hover {
    background-color: #0056b3;
  }
  .message {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    border-radius: 10px;
    white-space: pre-wrap;
    margin-right: 20vh;
    margin-left: 20vh;
  }
  .message.user {
    text-align: right;
    background-color: #eee;
    align-self: flex-end;
  }
  .message.bot {
    text-align: left;
    align-self: flex-start; 
    display: flex;
  }
  .message.bot::before {
    content: "\f544"; 
    font-family: "Font Awesome 5 Free"; 
    font-weight: 900; 
    color: black; 
    margin-right: 18px;
    display: inline-block;
    font-size: 1.3rem;
  }
  .toggle-button {
    color: black;
    border: white;
    border: none;
    top: 20px;
    left: 20px;
    padding: 10px;
    border-radius: 4px;
    cursor: pointer;
  }
  .toggle-button:hover {
    background-color: #f5f5f5;
  }
  .h-14 {
    height: 3.5rem;
  }
  .nav-bg-grey {
    background-color: #e3e3e3;
  }
  .message-input {
    width: 100%;
    min-height: 50px;
    padding: 10px;
    box-sizing: border-box;
    font-size: 16px;
    border: 1px solid #ccc;
    border-radius: 5px;
    resize: none;
  }
  .message-input:focus {
    outline: none;
    border-color: #007BFF;
  }
  .center-text {
    display: flex;
    justify-content: center;
    align-items: center;
    text-align: center;
  }
  .mr-6 {
    margin-right: 6px;
  }
  

  .options-icon {
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
    margin: 0;
    color: #bbb;
  }

  .options-popup button {
    display: block;
    width: 100%;
    padding: 5px 10px;
    border: none;
    background-color: #fff;
  }
  .options-popup button:hover {
    background-color: #eee;
  }
</style>

<!-- TODO: Component -->

<div bind:this={popupContainer} class="options-popup" style="display: none;">
  <button on:click={() => handleRenameChatButton(activePopupId)}>Rename</button>
  <button on:click={() => openCheckDeleteChatModal(activePopupId)} class="text-danger">Delete</button>
</div>

<!-- TODO: modal refactoring -->
<!-- delete chat modal -->
{#if checkDeleteChatModalOpen}
  <div class="modal fade show d-block" tabindex="-1" style="background-color: rgba(0, 0, 0, 0.5);">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title">해당 채팅을 삭제하고 싶습니까? 돌이킬 수 없습니다.</h5>
          <button type="button" class="btn-close" aria-label="Close" on:click="{closeCheckDeleteChatModal}"></button>
        </div>
        <div class="modal-body">
          <p>정말로 이 채팅을 삭제하시겠습니까?</p>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" on:click="{closeCheckDeleteChatModal}">취소</button>
          <button type="button" class="btn btn-danger" on:click="{confirmDeleteChat}">삭제</button>
        </div>
      </div>
    </div>
  </div>
{/if}


<div class="d-flex">
  <nav class="h-full w-full {isSidebarVisible ? 'nav-bg-grey' : ''}">
    <div class="h-14 d-flex justify-content-between items-center px-4 align-items-center">
      <div>
        <button class="toggle-button" on:click="{toggleSidebar}">
          <FontAwesomeIcon icon={faBars} />
        </button>
      </div>
      <button class="toggle-button" on:click="{openNewChatModal}">
        <FontAwesomeIcon icon={faComments} />
      </button>
    </div>
    <div class="sidebar overflow-auto border-end {isSidebarVisible ? '' : 'hidden'}">
      <ul>
        {#each $chatTitles as chatTitle}
        <li class="chat-item">
          <div class="chat-button-container p-2 rounded 
          {activeChatSessionId === chatTitle.id ? 'active' : ''}
          {activePopupId === chatTitle.id ? 'active' : ''}">
          {#if editingChatTitleId === chatTitle.id}
            <input 
              bind:this={inputElement}
              type="text" 
              class="form-control"
              bind:value={newChatTitle}
              on:keydown={(event) => handleKeyPress(event, chatTitle)}
              on:blur={(cancelEdit)}  
              placeholder={chatTitle.name}
            />
          {:else}
            <button
              on:click={() => selectChat(chatTitle.id)}
              class="btn w-100 text-start py-2 {chatTitle.id === activeChatSessionId ? 'active' : ''}"
            >
              {chatTitle.name}
            </button>
          {/if}
            <div class="options-container">
              <button
                class="options-icon btn btn-link p-0 border-0"
                on:click={(event) => togglePopup(chatTitle.id, event)}
              >
                <FontAwesomeIcon icon={faEllipsis} />
              </button>
            </div>
          </div>
        </li>
        {/each}
      </ul>
    </div>
    <!-- TODO: 새 채팅 생성 후 자동으로 채팅 목록에 추가한 화면 rendering -->
    {#if isNewChatModalOpen}
      <div class="modal fade show d-block" tabindex="-1" style="background-color: rgba(0, 0, 0, 0.5);">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content">
            <div class="modal-header">
              <h5 class="modal-title">새 채팅 생성</h5>
              <button type="button" class="btn-close" aria-label="Close" on:click="{closeNewChatModal}"></button>
            </div>
            <div class="modal-body">
              <input
                type="text"
                class="form-control"
                bind:value={newChatTitle}
                placeholder="채팅 제목을 입력하세요"
              />
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" on:click="{closeNewChatModal}">취소</button>
              <button type="button" class="btn btn-primary" on:click="{createNewChat}">생성</button>
            </div>
          </div>
        </div>
      </div>
    {/if}
  </nav>

  <div class="flex-grow-1 d-flex flex-column vh-100">
    <div class="top-bar">

      {#if $isLogin == false}
      <button class="btn relative btn-primary btn-small mr-6" on:click|preventDefault={goToLogin}>
        <div class="flex items-center justify-center">
          로그인
        </div>
      </button>
      <button class="btn relative btn-secondary btn-small" on:click|preventDefault={goToSignUp}>
        <div class = "flex items-center justify-center">
          회원가입
        </div>
      </button>
      {:else}
        <button class="btn relative btn-primary btn-small mr-6" on:click|preventDefault={handleLogOut}>
          <div class="flex items-center justify-center">
            로그아웃
          </div>
        </button>
      {/if}
      
    </div>
    <!-- TODO: Active Chat ID 가 -1일 경우 비어있는 chatting으로 화면 rendering(store 변수 때문에 계속 남아있음) -->
    <div class="messages">
      {#if activeChatSessionId !== -1}
        {#each $sessionMessages.messages as message }
          <div class="message {message.sender}">
            {message.text}
          </div>
        {/each}
        {#if answer !== ''}
          <div class="message bot">
            {answer}
          </div>
        {/if}
        {#if generateLoading === true}
          <div class="message bot">
            loading...
          </div>
        {/if}
      {/if}
    </div>
    <div class="input-container">
      <textarea
        bind:value={userMessage}
        on:keydown={handleKeyDown}
        on:input={autoResizeTextArea}
        placeholder="Type your message here..."
        class="message-input"
      ></textarea>
      <button on:click="{sendMessage}">Send</button>
    </div>
    <div class="center-text">
      LLM은 실수할 수 있습니다. 중요한 정보를 확인하세요.
    </div>
  </div>
</div>