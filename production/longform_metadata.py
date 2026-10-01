"""YouTube metadata for regular long-form videos."""
from __future__ import annotations
import re

def longform_metadata(title:str, channel:str, kind:str="explainer")->dict:
    clean=re.sub(r"\s+"," ",title).strip().rstrip(" .")
    if not clean: raise ValueError("title required")
    if channel=="viral_futbol":
        labels={"player_career":"Futbolcu Kariyeri","club_history":"Kulüp Tarihi","football_story":"Futbol Hikâyesi"}
        label=labels.get(kind,"Futbol Dosyası")
        return {"title":clean[:100],
                "description":f"{clean}. 90+ Gündem {label.lower()} formatında özgün anlatım ve görsel kurgu sunuyor.\n\n#Futbol",
                "tags":["futbol",label.lower()],"content_format":"video","kind":kind}
    if channel=="bamloop":
        return {"title":clean[:100],
                "description":f"{clean}. Kısa ve anlaşılır, özgün bilgilendirici video.",
                "tags":["bilgi","açıklayıcı video"],"content_format":"video","kind":"explainer"}
    raise ValueError("unsupported channel")
