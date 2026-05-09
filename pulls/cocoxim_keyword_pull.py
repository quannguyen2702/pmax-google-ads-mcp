#!/usr/bin/env python3
"""Keyword Puller — Cocoxim (FMCG / Nước dừa)"""

import os, json, re, csv, time
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests

load_dotenv()

CLIENT_NAME = "Cocoxim"
CUSTOMER_ID = "8409563791"
OUTPUT_FILE = ""

GEO = {
    "Vietnam": ["2704"],
    "HCM": ["9040373"],
    "HaNoi": ["9040331"],
}

RANGES = [
    ("2025", 2025, 1, 2025, 12),
]

SEED_GROUPS = {
    "Brand": {
        "lang": "1040",
        "seeds": [
            "cocoxim|nước dừa cocoxim|cocoxim nước dừa|cocoxim organic|cocoxim đóng hộp|mua cocoxim",
            "cocoxim giá|cocoxim shopee|cocoxim thùng|cocoxim bán ở đâu|cocoxim lazada",
        ]
    },
    "Product_NuocDua": {
        "lang": "1040",
        "seeds": [
            "nước dừa đóng hộp|nước dừa đóng chai|nước dừa tươi đóng hộp|nước dừa organic|nước dừa nguyên chất",
            "nước dừa uống liền|nước dừa lon|nước dừa hộp giấy|nước dừa thùng|nước dừa lốc",
            "nước dừa xiêm|nước dừa bến tre|nước dừa tươi|nước dừa dứa|nước dừa sáp",
        ]
    },
    "Generic_NuocDua": {
        "lang": "1040",
        "seeds": [
            "nước dừa|uống nước dừa|nước dừa có tốt không|nước dừa tốt cho sức khỏe|tác dụng nước dừa",
            "nước dừa giảm cân|nước dừa đẹp da|nước dừa bà bầu|nước dừa có bao nhiêu calo|nước dừa keto",
            "nước dừa mua ở đâu|mua nước dừa online|giá nước dừa|nước dừa giá sỉ|nước dừa thùng giá",
        ]
    },
    "Generic_DoUong": {
        "lang": "1040",
        "seeds": [
            "nước giải khát|đồ uống healthy|nước uống tốt cho sức khỏe|nước trái cây đóng hộp|nước ép đóng chai",
            "đồ uống ít calo|nước uống giảm cân|nước uống mùa hè|đồ uống organic|thức uống tự nhiên",
        ]
    },
    "Product_EN": {
        "lang": "1000",
        "seeds": [
            "coconut water|coconut water brand vietnam|best coconut water|organic coconut water|packaged coconut water",
            "coconut water benefits|coconut water calories|coconut water healthy|coconut water diet",
        ]
    },
    "Competitor_Vietcoco": {
        "lang": "1040",
        "seeds": [
            "vietcoco|nước dừa vietcoco|vietcoco nước dừa|vietcoco giá|vietcoco organic|mua vietcoco",
        ]
    },
    "Competitor_DuaBenTre": {
        "lang": "1040",
        "seeds": [
            "dừa bến tre|nước dừa bến tre đóng hộp|thương hiệu dừa bến tre|betrimex|betrimex nước dừa",
        ]
    },
    "Competitor_Others": {
        "lang": "1040",
        "seeds": [
            "wonderfarm nước dừa|vinamilk nước dừa|TH true milk nước dừa|nước dừa UFC",
            "vita coco|vita coco vietnam|harmless harvest|harmless harvest nước dừa|zico nước dừa",
        ]
    },
    "Comparison": {
        "lang": "1040",
        "seeds": [
            "nước dừa hãng nào ngon|so sánh nước dừa đóng hộp|nước dừa nào tốt nhất|review nước dừa đóng hộp",
            "nước dừa cocoxim hay vietcoco|top nước dừa đóng hộp|nước dừa đóng hộp nào ngon nhất",
        ]
    },
    "Seasonal_Occasion": {
        "lang": "1040",
        "seeds": [
            "nước dừa tết|nước dừa giỗ|nước dừa cúng|nước dừa tiệc|nước dừa liên hoan|nước dừa đám cưới",
            "nước dừa mùa hè|nước dừa giải nhiệt|nước dừa sau tập gym|nước dừa thể thao",
        ]
    },
}

GEO_STRATEGY = {
    "Brand": "all",
    "Product_NuocDua": "all",
    "Generic_NuocDua": "all",
    "Generic_DoUong": "all",
    "Product_EN": ["Vietnam"],
    "Competitor_Vietcoco": "all",
    "Competitor_DuaBenTre": "all",
    "Competitor_Others": ["Vietnam"],
    "Comparison": "all",
    "Seasonal_Occasion": "all",
}

EXCLUDE_PATTERNS = []

# ╔═══════════════════════════════════════════════════════════╗
# ║  VALIDATION                                               ║
# ╚═══════════════════════════════════════════════════════════╝

def validate_config():
    errors = []
    if not CLIENT_NAME:
        errors.append("CLIENT_NAME chưa điền")
    if not CUSTOMER_ID or len(CUSTOMER_ID) != 10 or not CUSTOMER_ID.isdigit():
        errors.append(f"CUSTOMER_ID không hợp lệ: '{CUSTOMER_ID}' (cần 10 chữ số)")
    if not GEO:
        errors.append("GEO chưa có location nào")
    if not RANGES:
        errors.append("RANGES chưa có time range nào")
    if not SEED_GROUPS:
        errors.append("SEED_GROUPS chưa có angle nào")
    for angle, config in SEED_GROUPS.items():
        if not config.get("seeds"):
            errors.append(f"SEED_GROUPS['{angle}'] chưa có seeds")
        if not config.get("lang"):
            errors.append(f"SEED_GROUPS['{angle}'] chưa có lang")
    if errors:
        print("❌ CONFIG ERRORS:")
        for e in errors:
            print(f"   - {e}")
        print("\nSửa CONFIG rồi chạy lại.")
        exit(1)

# ╔═══════════════════════════════════════════════════════════╗
# ║  CODE — KHÔNG CẦN SỬA                                    ║
# ╚═══════════════════════════════════════════════════════════╝

API_VERSION = "v24"
MONTH_NAMES = {1:"JANUARY",2:"FEBRUARY",3:"MARCH",4:"APRIL",5:"MAY",6:"JUNE",7:"JULY",8:"AUGUST",9:"SEPTEMBER",10:"OCTOBER",11:"NOVEMBER",12:"DECEMBER"}
MONTH_SHORT = {"JANUARY":"Jan","FEBRUARY":"Feb","MARCH":"Mar","APRIL":"Apr","MAY":"May","JUNE":"Jun","JULY":"Jul","AUGUST":"Aug","SEPTEMBER":"Sep","OCTOBER":"Oct","NOVEMBER":"Nov","DECEMBER":"Dec"}

def is_relevant(kw):
    if not EXCLUDE_PATTERNS: return True
    kl = kw.lower().strip()
    return not any(re.search(p, kl) for p in EXCLUDE_PATTERNS)

def get_auth_headers():
    cred_path = os.environ.get('GOOGLE_ADS_CREDENTIALS_PATH')
    if not cred_path or not os.path.exists(cred_path):
        print(f"❌ Credentials not found: {cred_path}\n   Check .env file."); exit(1)
    with open(cred_path) as f: creds_data = json.load(f)
    creds = Credentials.from_authorized_user_info(creds_data, ['https://www.googleapis.com/auth/adwords'])
    if creds.expired: creds.refresh(Request())
    dev_token = os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN')
    if not dev_token: print("❌ GOOGLE_ADS_DEVELOPER_TOKEN not in .env"); exit(1)
    return {'Authorization':f'Bearer {creds.token}','developer-token':dev_token,'content-type':'application/json'}

def pull_keywords(headers, seeds_str, lang, loc_ids, sy, sm, ey, em):
    url = f"https://googleads.googleapis.com/{API_VERSION}/customers/{CUSTOMER_ID}:generateKeywordIdeas"
    kws = [k.strip() for k in seeds_str.split('|') if k.strip()]
    payload = {"keywordSeed":{"keywords":kws},"language":f"languageConstants/{lang}","geoTargetConstants":[f"geoTargetConstants/{l}" for l in loc_ids],"keywordPlanNetwork":"GOOGLE_SEARCH","historicalMetricsOptions":{"yearMonthRange":{"start":{"year":sy,"month":MONTH_NAMES[sm]},"end":{"year":ey,"month":MONTH_NAMES[em]}}},"pageSize":100}
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200: print(f"  ERROR {resp.status_code}: {resp.text[:200]}"); return []
    results = []
    for idea in resp.json().get('results', []):
        text = idea.get('text',''); km = idea.get('keywordIdeaMetrics',{})
        comp = km.get('competition','UNSPECIFIED'); ci = km.get('competitionIndex','')
        monthly = {}
        for m in km.get('monthlySearchVolumes',[]): monthly[f"{MONTH_SHORT.get(m.get('month',''),'')}-{m.get('year',0)}"] = int(m.get('monthlySearches',0))
        results.append((text, monthly, f"{comp}({ci})" if ci else comp))
    return results

def main():
    validate_config()
    output_file = OUTPUT_FILE or f"{CLIENT_NAME.lower().replace(' ','_')}_keywords_full.csv"
    print("="*60); print(f"Keyword Puller — {CLIENT_NAME}"); print("="*60)
    headers = get_auth_headers(); print("✅ Auth OK\n")
    
    total_est = 0
    for angle, config in SEED_GROUPS.items():
        strategy = GEO_STRATEGY.get(angle, list(GEO.keys())[:1])
        gl = list(GEO.keys()) if strategy == "all" else [g for g in strategy if g in GEO]
        total_est += len(config["seeds"]) * len(gl) * len(RANGES)
    print(f"Config: {len(SEED_GROUPS)} angles × {len(GEO)} geos × {len(RANGES)} ranges")
    print(f"Estimated: {total_est} API calls (max {total_est*100:,} raw keywords)\n")
    
    all_data = {}; total_raw = 0; call_num = 0
    for angle, config in SEED_GROUPS.items():
        lang = config["lang"]
        strategy = GEO_STRATEGY.get(angle, list(GEO.keys())[:1])
        gl = list(GEO.keys()) if strategy == "all" else [g for g in strategy if g in GEO]
        for geo_name in gl:
            for yl, sy, sm, ey, em in RANGES:
                for si, seeds in enumerate(config["seeds"]):
                    call_num += 1
                    print(f"[{call_num:3d}/{total_est}] {angle} | {geo_name} | {yl} | #{si+1}...", end=" ", flush=True)
                    results = pull_keywords(headers, seeds, lang, GEO[geo_name], sy, sm, ey, em)
                    total_raw += len(results); new = 0
                    for kw, monthly, comp in results:
                        key = (kw.lower().strip(), geo_name)
                        if key not in all_data:
                            all_data[key] = {"keyword":kw,"angle":angle,"location":geo_name,"language":"EN" if lang=="1000" else "VI","months":{},"competition":comp}
                            new += 1
                        for mk, mv in monthly.items():
                            if mk not in all_data[key]["months"] or mv > 0: all_data[key]["months"][mk] = mv
                    print(f"{len(results)} raw, {new} new")
                    time.sleep(0.3)
    
    print(f"\n{'='*60}"); print(f"Raw: {total_raw:,} | Dedup: {len(all_data):,}", end="")
    filtered = {k:v for k,v in all_data.items() if is_relevant(v["keyword"])}
    rm = len(all_data) - len(filtered)
    print(f" | Clean: {len(filtered):,}" + (f" (removed {rm} noise)" if rm else ""))
    if not filtered: print("\n❌ No keywords. Check seeds/filter/token."); exit(1)
    
    month_cols = []
    for _,sy,sm,ey,em in RANGES:
        for y in range(sy,ey+1):
            for m in range(sm if y==sy else 1, (em if y==ey else 12)+1):
                c = f"{MONTH_SHORT[MONTH_NAMES[m]]}-{y}"
                if c not in month_cols: month_cols.append(c)
    
    ao = {a:i for i,a in enumerate(SEED_GROUPS.keys())}
    sorted_data = sorted(filtered.items(), key=lambda x:(ao.get(x[1]["angle"],99),x[1]["location"],-sum(x[1]["months"].get(mc,0) for mc in month_cols)/max(len(month_cols),1)))
    
    with open(output_file,'w',newline='',encoding='utf-8-sig') as f:
        w = csv.writer(f); w.writerow(["Keyword","Angle","Location","Language"]+month_cols+["Competition"])
        for k,v in sorted_data:
            w.writerow([v["keyword"],v["angle"],v["location"],v["language"]]+[str(v["months"].get(mc,"")) if v["months"].get(mc,"") != "" else "" for mc in month_cols]+[v["competition"]])
    
    ba={}; bl={}
    for k,v in sorted_data: ba[v["angle"]]=ba.get(v["angle"],0)+1; bl[v["location"]]=bl.get(v["location"],0)+1
    print(f"\n✅ Output: {output_file}\n   {len(sorted_data):,} keywords × {len(month_cols)} months\n")
    print("By Angle:"); [print(f"  {a}: {ba.get(a,0)}") for a in SEED_GROUPS.keys()]
    print("\nBy Location:"); [print(f"  {l}: {bl.get(l,0)}") for l in GEO.keys()]
    print(f"\n{'='*60}\nDone! Import {output_file} vào Google Sheets → feed Duy's Agent")

if __name__ == "__main__": main()
