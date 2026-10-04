from collections import Counter
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from .config import get_settings
from .db import disconnect, get_connection, get_tokens, get_user, initialize_database, save_tokens, upsert_user
from .demo import demo_messages
from .llm import analyze_messages
from .providers import PROVIDERS, new_state, token_needs_refresh

settings=get_settings()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_database()
    yield

app=FastAPI(title="InboxPilot API",version="2.0.0",lifespan=lifespan)
app.add_middleware(SessionMiddleware,secret_key=settings.session_secret,same_site="lax",https_only=settings.environment=="production",max_age=604800)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def current_user(request:Request):
    if request.session.get("demo"): return {"id":0,"name":"Demo Workspace","email":"demo@inboxpilot.ai","provider":"demo","avatar_url":None}
    user_id=request.session.get("user_id"); user=get_user(int(user_id)) if user_id else None
    if not user: raise HTTPException(status_code=401,detail="Authentication required")
    return user

@app.get("/api/health")
def health(): return {"status":"ok","version":"2.0.0"}

@app.get("/api/auth/{provider}")
def begin_auth(provider:str,request:Request):
    adapter=PROVIDERS.get(provider)
    if not adapter: raise HTTPException(status_code=404,detail="Unknown provider")
    if not getattr(settings,f"{provider}_client_id") or not getattr(settings,f"{provider}_client_secret"):
        return RedirectResponse(f"{settings.frontend_url}/login?error={provider}_not_configured")
    state=new_state(); request.session["oauth_state"]=state; request.session["oauth_provider"]=provider
    return RedirectResponse(adapter.authorization_url(state))

@app.get("/api/auth/{provider}/callback")
async def auth_callback(provider:str,request:Request,code:str="",state:str=""):
    if not code or state!=request.session.get("oauth_state") or provider!=request.session.get("oauth_provider"):
        return RedirectResponse(f"{settings.frontend_url}/login?error=invalid_oauth_state")
    adapter=PROVIDERS.get(provider)
    if not adapter: raise HTTPException(status_code=404,detail="Unknown provider")
    try:
        tokens=await adapter.exchange_code(code); profile=await adapter.profile(tokens); user_id=upsert_user(provider,profile,tokens)
    except Exception:
        return RedirectResponse(f"{settings.frontend_url}/login?error=oauth_failed")
    request.session.clear(); request.session["user_id"]=user_id
    return RedirectResponse(f"{settings.frontend_url}/dashboard")

@app.post("/api/auth/demo")
def demo_login(request:Request): request.session.clear(); request.session["demo"]=True; return {"ok":True}

@app.post("/api/logout")
def logout(request:Request): request.session.clear(); return {"ok":True}

@app.delete("/api/account")
def delete_connection(request:Request):
    user=current_user(request)
    if user["provider"]!="demo": disconnect(user["id"])
    request.session.clear(); return {"ok":True}

@app.get("/api/me")
def me(request:Request): return current_user(request)

@app.get("/api/account")
def account(request:Request):
    user=current_user(request)
    connection=None if user["provider"]=="demo" else get_connection(user["id"])
    return {"user":user,"connection":connection,"session":{"remembered_for_days":7},"ai":{"provider":settings.llm_provider,"groq_model":settings.groq_model,"ollama_model":settings.ollama_model}}

@app.get("/api/emails")
async def emails(request:Request):
    user=current_user(request)
    if user["provider"]=="demo":
        messages=demo_messages()
    else:
        adapter=PROVIDERS[user["provider"]]
        tokens=get_tokens(user["id"],user["provider"])
        if token_needs_refresh(tokens):
            tokens=await adapter.refresh(tokens)
            save_tokens(user["id"],user["provider"],tokens)
        messages=await adapter.messages(tokens)
    messages, ai_metadata = await analyze_messages(messages)
    counts=Counter(m["category"] for m in messages)
    return {"messages":messages,"ai":ai_metadata,"stats":{"total":len(messages),"urgent":sum(m["priority"]=="High" for m in messages),"categories":counts,"minutes_saved":max(1,round(len(messages)*1.8))}}
