"use client";

import { FormEvent, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type User = { user_id: string; email: string };
type Session = { session_id: string; user_id: string; created_at: string; updated_at: string };
type Message = { message_id: string; role: string; content: string; metadata?: Record<string, unknown> };

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(`${API}${path}`, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...(init.headers || {}) } });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || `HTTP ${response.status}`);
  return response.json();
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [registering, setRegistering] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadUser() {
    try {
      const current = await request("/auth/me");
      setUser(current);
      const result = await request("/conversations");
      setSessions(result.conversations);
      if (result.conversations[0]) setSessionId(result.conversations[0].session_id);
    } catch { setUser(null); }
  }

  useEffect(() => { void loadUser(); }, []);

  useEffect(() => {
    if (!sessionId) { setMessages([]); return; }
    request(`/conversations/${sessionId}/messages`).then(result => setMessages(result.messages)).catch(err => setError(err.message));
  }, [sessionId]);

  async function submitAuth(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      await request(`/auth/${registering ? "register" : "login"}`, { method: "POST", body: JSON.stringify({ email, password }) });
      if (registering) await request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setPassword(""); await loadUser();
    } catch (err) { setError(err instanceof Error ? err.message : "Authentication failed"); }
    finally { setBusy(false); }
  }

  async function newChat() {
    setError("");
    try {
      const result = await request("/conversations", { method: "POST", body: JSON.stringify({}) });
      setSessions(current => [{ session_id: result.session_id, user_id: result.user_id, created_at: new Date().toISOString(), updated_at: new Date().toISOString() }, ...current]);
      setSessionId(result.session_id); setMessages([]);
    } catch (err) { setError(err instanceof Error ? err.message : "Cannot create conversation"); }
  }

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    if (!input.trim() || !sessionId || busy) return;
    const query = input.trim(); setInput(""); setBusy(true); setError("");
    setMessages(current => [...current, { message_id: `local-${Date.now()}`, role: "user", content: query }]);
    try {
      const result = await request(`/conversations/${sessionId}/messages`, { method: "POST", body: JSON.stringify({ query }) });
      const content = typeof result.report === "string" ? result.report : JSON.stringify(result.report, null, 2);
      const citations = (result.agent_outputs || []).flatMap((item: any) => item.sources || []);
      setMessages(current => [...current, { message_id: result.task_id, role: "assistant", content, metadata: { task_id: result.task_id, citations } }]);
      setSessions(current => current.map(item => item.session_id === sessionId ? { ...item, updated_at: new Date().toISOString() } : item));
    } catch (err) { setError(err instanceof Error ? err.message : "Request failed"); }
    finally { setBusy(false); }
  }

  async function logout() {
    await request("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null); setSessions([]); setSessionId(""); setMessages([]);
  }

  if (!user) return <main className="auth"><section className="card"><h1>OfficeAgent</h1><p>{registering ? "Create a local account" : "Sign in to continue"}</p><form className="form" onSubmit={submitAuth}><input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required /><input type="password" placeholder="Password (8+ characters)" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required /><button className="primary" disabled={busy}>{busy ? "Please wait…" : registering ? "Register" : "Login"}</button></form>{error && <p className="error">{error}</p>}<button className="secondary" onClick={() => setRegistering(value => !value)}>{registering ? "Already have an account? Login" : "Create an account"}</button></section></main>;

  return <main className="app"><aside className="sidebar"><button className="primary" onClick={newChat}>+ New Chat</button><div className="sessions">{sessions.map(item => <button key={item.session_id} className={`session ${item.session_id === sessionId ? "active" : ""}`} onClick={() => setSessionId(item.session_id)}>{item.session_id.slice(0, 8)}…<small>{new Date(item.updated_at).toLocaleString()}</small></button>)}</div><div className="profile"><div>{user.email}</div><div>User ID: {user.user_id}</div><button className="secondary" onClick={logout}>Logout</button></div></aside><section className="chat"><header className="header"><strong>OfficeAgent</strong><div className="debug">User: {user.user_id}<br />Session: {sessionId || "-"}</div></header><div className="messages">{messages.length === 0 && <div>选择一个会话或创建新 Chat，然后开始提问。</div>}{messages.map(message => <article key={message.message_id} className={`message ${message.role === "user" ? "user" : "assistant"}`}><div>{message.content}</div>{message.role !== "user" && Array.isArray(message.metadata?.citations) && message.metadata?.citations.length > 0 && <div className="citations">Sources: {message.metadata.citations.length}</div>}</article>)}</div><form className="composer" onSubmit={sendMessage}><input value={input} onChange={e => setInput(e.target.value)} placeholder={sessionId ? "输入消息…" : "先创建会话"} disabled={!sessionId || busy} /><button className="primary" disabled={!sessionId || !input.trim() || busy}>{busy ? "处理中…" : "发送"}</button></form>{error && <div className="error">{error}</div>}</section></main>;
}
