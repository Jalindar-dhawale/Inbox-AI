from __future__ import annotations
import base64, html, re, secrets
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
import httpx
from .config import get_settings

def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()

def _labels(subject: str, body: str) -> dict:
    text = f"{subject} {body}".lower()
    if any(w in text for w in ("invoice","payment","billing","receipt")): category="Finance"
    elif any(w in text for w in ("candidate","interview","resume","recruit")): category="Recruitment"
    elif any(w in text for w in ("newsletter","unsubscribe","weekly digest")): category="Newsletter"
    elif any(w in text for w in ("prize","winner","claim now","crypto offer")): category="Spam"
    else: category="Important"
    priority = "High" if any(w in text for w in ("urgent","deadline","approval","today")) else "Medium"
    if category in {"Newsletter","Spam"}: priority="Low"
    summary = _clean_html(body)[:180] or f"Message regarding {subject}."
    return {"category":category,"priority":priority,"sentiment":"Suspicious" if category=="Spam" else "Neutral","summary":summary}

class EmailProvider(ABC):
    @abstractmethod
    def authorization_url(self, state: str) -> str: ...
    @abstractmethod
    async def exchange_code(self, code: str) -> dict: ...
    @abstractmethod
    async def profile(self, tokens: dict) -> dict: ...
    @abstractmethod
    async def messages(self, tokens: dict) -> list[dict]: ...
    @abstractmethod
    async def refresh(self, tokens: dict) -> dict: ...

class GoogleProvider(EmailProvider):
    scopes="openid email profile https://www.googleapis.com/auth/gmail.readonly"
    def authorization_url(self,state):
        s=get_settings(); p={"client_id":s.google_client_id,"redirect_uri":f"{s.backend_url}/api/auth/google/callback","response_type":"code","scope":self.scopes,"access_type":"offline","include_granted_scopes":"true","state":state}
        return "https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(p)
    async def exchange_code(self,code):
        s=get_settings()
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":s.google_client_id,"client_secret":s.google_client_secret,"redirect_uri":f"{s.backend_url}/api/auth/google/callback","grant_type":"authorization_code"})
        r.raise_for_status(); return r.json()
    async def profile(self,tokens):
        async with httpx.AsyncClient(timeout=20) as c: r=await c.get("https://openidconnect.googleapis.com/v1/userinfo",headers={"Authorization":f"Bearer {tokens['access_token']}"})
        r.raise_for_status(); d=r.json(); return {"id":d["sub"],"email":d["email"],"name":d.get("name",d["email"]),"avatar":d.get("picture")}
    async def messages(self,tokens):
        headers={"Authorization":f"Bearer {tokens['access_token']}"}; today=datetime.now(timezone.utc).strftime("%Y/%m/%d")
        async with httpx.AsyncClient(timeout=30) as c:
            listing=await c.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",headers=headers,params={"q":f"after:{today}","maxResults":30}); listing.raise_for_status(); results=[]
            for item in listing.json().get("messages",[]):
                r=await c.get(f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",headers=headers,params={"format":"full"}); r.raise_for_status(); results.append(self._normalize(r.json()))
        return results
    async def refresh(self,tokens):
        if not tokens.get("refresh_token"): return tokens
        s=get_settings()
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post("https://oauth2.googleapis.com/token",data={"client_id":s.google_client_id,"client_secret":s.google_client_secret,"refresh_token":tokens["refresh_token"],"grant_type":"refresh_token"})
        r.raise_for_status(); return {**tokens,**r.json(),"obtained_at":datetime.now(timezone.utc).isoformat()}
    def _normalize(self,raw):
        payload=raw.get("payload",{}); headers={x["name"].lower():x["value"] for x in payload.get("headers",[])}; body=self._body(payload); subject=headers.get("subject","No subject")
        return {"id":raw["id"],"sender":headers.get("from","Unknown sender"),"subject":subject,"received_at":headers.get("date",""),"snippet":raw.get("snippet",""),**_labels(subject,body)}
    def _body(self,payload):
        data=payload.get("body",{}).get("data")
        if data and payload.get("mimeType") in {"text/plain","text/html"}: return base64.urlsafe_b64decode(data+"="*(-len(data)%4)).decode(errors="replace")
        for part in payload.get("parts",[]):
            value=self._body(part)
            if value: return value
        return ""

class MicrosoftProvider(EmailProvider):
    scopes="openid profile email offline_access User.Read Mail.Read"
    def _base(self): return f"https://login.microsoftonline.com/{get_settings().microsoft_tenant}/oauth2/v2.0"
    def authorization_url(self,state):
        s=get_settings(); p={"client_id":s.microsoft_client_id,"response_type":"code","redirect_uri":f"{s.backend_url}/api/auth/microsoft/callback","response_mode":"query","scope":self.scopes,"state":state}
        return f"{self._base()}/authorize?"+urlencode(p)
    async def exchange_code(self,code):
        s=get_settings()
        async with httpx.AsyncClient(timeout=20) as c: r=await c.post(f"{self._base()}/token",data={"client_id":s.microsoft_client_id,"client_secret":s.microsoft_client_secret,"code":code,"redirect_uri":f"{s.backend_url}/api/auth/microsoft/callback","grant_type":"authorization_code","scope":self.scopes})
        r.raise_for_status(); return r.json()
    async def profile(self,tokens):
        async with httpx.AsyncClient(timeout=20) as c: r=await c.get("https://graph.microsoft.com/v1.0/me",headers=self._headers(tokens))
        r.raise_for_status(); d=r.json(); email=d.get("mail") or d.get("userPrincipalName"); return {"id":d["id"],"email":email,"name":d.get("displayName",email),"avatar":None}
    async def messages(self,tokens):
        params={"$top":30,"$orderby":"receivedDateTime desc","$select":"id,subject,from,receivedDateTime,bodyPreview"}
        async with httpx.AsyncClient(timeout=30) as c: r=await c.get("https://graph.microsoft.com/v1.0/me/messages",headers=self._headers(tokens),params=params)
        r.raise_for_status(); output=[]
        for item in r.json().get("value",[]):
            a=item.get("from",{}).get("emailAddress",{}); sender=f"{a.get('name','')} <{a.get('address','')}>".strip(); subject=item.get("subject") or "No subject"; body=item.get("bodyPreview") or ""
            output.append({"id":item["id"],"sender":sender,"subject":subject,"received_at":item.get("receivedDateTime",""),"snippet":body,**_labels(subject,body)})
        return output
    async def refresh(self,tokens):
        if not tokens.get("refresh_token"): return tokens
        s=get_settings()
        async with httpx.AsyncClient(timeout=20) as c:
            r=await c.post(f"{self._base()}/token",data={"client_id":s.microsoft_client_id,"client_secret":s.microsoft_client_secret,"refresh_token":tokens["refresh_token"],"grant_type":"refresh_token","scope":self.scopes})
        r.raise_for_status(); return {**tokens,**r.json(),"obtained_at":datetime.now(timezone.utc).isoformat()}
    @staticmethod
    def _headers(tokens): return {"Authorization":f"Bearer {tokens['access_token']}"}

PROVIDERS={"google":GoogleProvider(),"microsoft":MicrosoftProvider()}
def new_state(): return secrets.token_urlsafe(32)

def token_needs_refresh(tokens: dict) -> bool:
    obtained = tokens.get("obtained_at")
    expires_in = tokens.get("expires_in")
    if not obtained or not expires_in: return False
    expiry = datetime.fromisoformat(obtained) + timedelta(seconds=int(expires_in))
    return expiry <= datetime.now(timezone.utc) + timedelta(minutes=2)
