import { writable } from "svelte/store";

const persist_storage = (key, initValue) => {
  const storedValueStr = localStorage.getItem(key);

  // 만약 storedValueStr이 null 또는 undefined라면 initValue를 사용
  const store = writable(storedValueStr !== null && storedValueStr !== 'undefined' ? JSON.parse(storedValueStr) : initValue);

  store.subscribe((val) => {
    localStorage.setItem(key, JSON.stringify(val));
  });

  return store;
}

export const isLogin = persist_storage("isLogin", false)
export const userEmail = persist_storage("userEmail", "")
export const accessToken = persist_storage("accessToken", "")
export const isSignUpPage = persist_storage("isSignUpPage", false)
export const chatTitles = persist_storage("chatTitles", []);
export const chatSessionMessages = persist_storage("chatSessionMessages", []);
