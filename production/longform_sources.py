"""Runtime evidence retrieval for autonomous long-form production."""
from __future__ import annotations
import json,re,urllib.parse,urllib.request
from datetime import datetime
from production.longform_research import Evidence
from viral_futbol.service import fetch_google_news

UA={"User-Agent":"90Gundem-BAMLOOP/1.0"}

def _json(url:str)->dict:
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=20) as response:
        return json.loads(response.read())

def _qid(subject:str)->tuple[str,str]:
    params=urllib.parse.urlencode({"action":"wbsearchentities","search":subject,"language":"tr","uselang":"tr","format":"json","limit":"1"})
    data=_json("https://www.wikidata.org/w/api.php?"+params)
    rows=data.get("search") or []
    if not rows:
        params=urllib.parse.urlencode({"action":"wbsearchentities","search":subject,"language":"en","uselang":"en","format":"json","limit":"1"})
        rows=_json("https://www.wikidata.org/w/api.php?"+params).get("search") or []
    if not rows:
        raise ValueError("wikidata_subject_not_found")
    row=rows[0]
    return str(row["id"]),str(row.get("label") or subject)

def _labels(ids:set[str])->dict[str,str]:
    if not ids:
        return {}
    result={}
    values=list(ids)
    for start in range(0,len(values),40):
        params=urllib.parse.urlencode({"action":"wbgetentities","ids":"|".join(values[start:start+40]),"props":"labels","languages":"tr|en","format":"json"})
        data=_json("https://www.wikidata.org/w/api.php?"+params)
        for qid,entity in (data.get("entities") or {}).items():
            labels=entity.get("labels") or {}
            result[qid]=str((labels.get("tr") or labels.get("en") or {}).get("value") or qid)
    return result

def _date(value:dict)->str:
    raw=str(value.get("time") or "")
    m=re.match(r"([+-]\d{4,})-(\d{2})-(\d{2})",raw)
    if not m:
        return raw[:10]
    year=m.group(1).lstrip("+").lstrip("0") or "0"
    month,day=m.group(2),m.group(3)
    return year if month=="00" else (f"{year}-{month}" if day=="00" else f"{year}-{month}-{day}")

def wikidata_evidence(subject:str,limit:int=18)->list[Evidence]:
    qid,label=_qid(subject)
    entity=_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json").get("entities",{}).get(qid,{})
    url=f"https://www.wikidata.org/wiki/{qid}"
    rows=[]
    description=str(((entity.get("descriptions") or {}).get("tr") or (entity.get("descriptions") or {}).get("en") or {}).get("value") or "").strip()
    if description:
        rows.append(Evidence(f"{label}, {description}.","Wikidata",url))
    mapping={
      "P31":"türü","P279":"üst sınıfı","P17":"ülkesi","P19":"doğum yeri","P106":"mesleği",
      "P54":"forma giydiği takım","P118":"ligi","P115":"stadyumu","P166":"ödülü",
      "P641":"spor dalı","P361":"parçası olduğu yapı","P463":"üyesi olduğu oluşum","P131":"bulunduğu idari bölge"
    }
    item_ids=set()
    claims=entity.get("claims") or {}
    for prop in mapping:
        for statement in claims.get(prop,[])[:12]:
            value=((statement.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if isinstance(value,dict) and value.get("id"):
                item_ids.add(str(value["id"]))
    labels=_labels(item_ids)
    date_props={"P569":"doğum tarihi","P571":"kuruluş tarihi","P577":"yayın tarihi"}
    for prop,label_name in date_props.items():
        for statement in claims.get(prop,[])[:2]:
            value=((statement.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if isinstance(value,dict) and value.get("time"):
                rows.append(Evidence(f"{label} için {label_name}: {_date(value)}.","Wikidata",url))
    for prop,label_name in mapping.items():
        for statement in claims.get(prop,[])[:12]:
            value=((statement.get("mainsnak") or {}).get("datavalue") or {}).get("value")
            if not isinstance(value,dict) or not value.get("id"):
                continue
            target=labels.get(str(value["id"]),str(value["id"]))
            suffix=""
            qualifiers=statement.get("qualifiers") or {}
            starts=qualifiers.get("P580") or []
            ends=qualifiers.get("P582") or []
            if starts:
                v=((starts[0].get("datavalue") or {}).get("value") or {})
                if isinstance(v,dict) and v.get("time"): suffix=f", başlangıç {_date(v)}"
            if ends:
                v=((ends[0].get("datavalue") or {}).get("value") or {})
                if isinstance(v,dict) and v.get("time"): suffix+=f", bitiş {_date(v)}"
            rows.append(Evidence(f"{label} için {label_name}: {target}{suffix}.","Wikidata",url))
            if len(rows)>=limit:
                return rows
    return rows[:limit]

def news_evidence(subject:str,limit:int=10)->list[Evidence]:
    rows=[]
    for story in fetch_google_news(subject,language="tr",country="TR")[:limit]:
        rows.append(Evidence(story.title,story.publisher,story.url,False))
    return rows

def research(subject:str,min_items:int=10,max_items:int=24)->list[Evidence]:
    rows=[]
    try:
        rows.extend(wikidata_evidence(subject,max_items))
    except Exception as exc:
        print(f"Longform Wikidata deferred: {type(exc).__name__}",flush=True)
    try:
        rows.extend(news_evidence(subject,max_items))
    except Exception as exc:
        print(f"Longform news evidence deferred: {type(exc).__name__}",flush=True)
    unique=[];seen=set()
    for row in rows:
        key=re.sub(r"\s+"," ",row.claim).strip().casefold()
        if key and key not in seen:
            seen.add(key);unique.append(row)
    if len(unique)<min_items:
        raise ValueError("insufficient_runtime_evidence")
    return unique[:max_items]
