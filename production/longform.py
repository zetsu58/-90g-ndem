"""Long-form planning shared by football and explainer channels."""
from __future__ import annotations
import hashlib, re
from dataclasses import dataclass
from production.content_formats import football_longform_brief, explainer_longform_brief

@dataclass(frozen=True)
class LongScene:
    index:int; section:str; start:float; duration:float; narration:str
    visual_query:str; motion:str; transition:str

def _clean(value:str)->str:
    return re.sub(r"\s+"," ",value).strip()

def narration_budget(target_seconds:int, words_per_minute:int=150)->tuple[int,int]:
    target=max(150,target_seconds)
    center=round(target*words_per_minute/60)
    return max(300,center-60), center+60

def plan(subject:str, *, channel:str, facts:list[str]|None=None, target_seconds:int=210)->dict:
    subject=_clean(subject)
    if not subject: raise ValueError("subject required")
    facts=[_clean(x) for x in (facts or []) if _clean(x)]
    if channel=="viral_futbol":
        brief=football_longform_brief(subject)
    elif channel=="bamloop":
        brief=explainer_longform_brief(subject)
    else: raise ValueError("unsupported channel")
    scale=target_seconds/sum(x["seconds"] for x in brief["sections"])
    scenes=[]; start=0.0
    motions=("push-in","pan-left","parallax","pull-out","pan-right")
    scene_index=0
    for section_index,section in enumerate(brief["sections"]):
        section_duration=section["seconds"]*scale
        # Long-form needs visual refreshes inside editorial sections. Split each
        # section into bounded 12–24 second scenes instead of six static blocks.
        parts=max(1,round(section_duration/18))
        part_duration=section_duration/parts
        for part in range(parts):
            duration=round(part_duration,2)
            fact=facts[(scene_index)%len(facts)] if facts else subject
            narration=f"{section['name'].replace('_',' ').title()} {part+1}: {fact}"
            scenes.append(LongScene(scene_index,section["name"],round(start,2),duration,narration,
                                    f"{subject} {section['name'].replace('_',' ')} {part+1}",motions[scene_index%len(motions)],
                                    "crossfade" if scene_index else "cut"))
            start+=duration
            scene_index+=1
    low,high=narration_budget(target_seconds)
    return {"id":hashlib.sha256(f"{channel}|{subject}".encode()).hexdigest()[:24],
            "channel":channel,"content_format":"video","subject":subject,
            "target_seconds":target_seconds,"word_budget":{"min":low,"max":high},
            "sections":brief["sections"],"scenes":[s.__dict__ for s in scenes],
            "rules":brief["rules"],"facts":facts}
