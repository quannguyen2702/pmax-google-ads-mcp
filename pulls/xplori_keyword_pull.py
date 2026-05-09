#!/usr/bin/env python3
"""
Keyword Puller — Xplori (Travel SIM/eSIM)
Purpose: Proposal — kéo hết, càng nhiều insight càng tốt
Auto-generated. DO NOT edit code section.
"""

import os, json, re, csv, time
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests

load_dotenv()

# ╔═══════════════════════════════════════════════════════════╗
# ║  CONFIG — XPLORI                                          ║
# ╚═══════════════════════════════════════════════════════════╝

CLIENT_NAME = "Xplori"
CUSTOMER_ID = "8409563791"
OUTPUT_FILE = ""

GEO = {
    "Vietnam": ["2704"],
    "Singapore": ["2702"],
    "Philippines": ["2608"],
}

RANGES = [
    ("2024", 2024, 1, 2024, 12),
    ("2025", 2025, 1, 2025, 12),
]

SEED_GROUPS = {
    # === BRAND ===
    "Brand": {
        "lang": "1000",
        "seeds": [
            "xplori|xplori sim|xplori esim|xplori app|xplori travel sim|xplori data|xplori review",
        ]
    },
    "Brand_VI": {
        "lang": "1040",
        "seeds": [
            "xplori|xplori sim du lịch|xplori esim|mua sim xplori|xplori giá rẻ",
        ]
    },
    # === PRODUCT — Vietnamese ===
    "Product_SIM_VI": {
        "lang": "1040",
        "seeds": [
            "sim du lịch|sim du lịch quốc tế|sim du lịch nước ngoài|mua sim du lịch|sim data du lịch|sim du lịch giá rẻ",
            "sim 4g du lịch|sim du lịch không giới hạn|sim du lịch online|đặt sim du lịch",
        ]
    },
    "Product_eSIM_VI": {
        "lang": "1040",
        "seeds": [
            "esim du lịch|esim quốc tế|esim là gì|cách cài esim|esim du lịch giá rẻ|mua esim du lịch",
            "esim du lịch nước ngoài|esim data du lịch|esim không giới hạn|cài đặt esim du lịch",
        ]
    },
    "Product_Roaming_VI": {
        "lang": "1040",
        "seeds": [
            "gói roaming quốc tế|roaming du lịch|cước roaming|tắt roaming|bật roaming|phí roaming",
            "gói roaming viettel|roaming mobifone|roaming vinaphone|gói cước quốc tế viettel",
        ]
    },
    "Generic_Travel_VI": {
        "lang": "1040",
        "seeds": [
            "wifi du lịch|wifi bỏ túi du lịch|thuê wifi du lịch|internet du lịch nước ngoài",
            "mua sim ở sân bay|sim sân bay|đổi sim du lịch|wifi pocket du lịch",
        ]
    },

    # === PRODUCT — English ===
    "Product_SIM_EN": {
        "lang": "1000",
        "seeds": [
            "travel sim card|international sim card|prepaid travel sim|travel data sim|buy sim card online",
            "tourist sim card|travel sim card unlimited data|best travel sim card|cheap travel sim",
        ]
    },
    "Product_eSIM_EN": {
        "lang": "1000",
        "seeds": [
            "esim travel|esim international|buy esim online|esim data plan travel|best esim for travel",
            "esim prepaid|esim unlimited data travel|esim plans international|how to use esim travel",
        ]
    },
    "Generic_Travel_EN": {
        "lang": "1000",
        "seeds": [
            "pocket wifi travel|international roaming plan|data roaming abroad|wifi rental travel",
            "stay connected abroad|internet while traveling|mobile data overseas|travel connectivity",
        ]
    },

    # === DESTINATION — Vietnamese (top travel destinations from VN) ===
    "Dest_Asia_VI": {
        "lang": "1040",
        "seeds": [
            "sim du lịch thái lan|sim du lịch hàn quốc|sim du lịch nhật bản|sim du lịch đài loan|sim du lịch trung quốc",
            "esim thái lan|esim hàn quốc|esim nhật bản|esim đài loan|esim trung quốc|esim hong kong",
            "sim du lịch singapore|sim du lịch malaysia|sim du lịch indonesia|sim du lịch bali",
            "esim singapore|esim malaysia|esim indonesia|esim philippines|esim campuchia",
        ]
    },
    "Dest_EU_US_VI": {
        "lang": "1040",
        "seeds": [
            "sim du lịch châu âu|sim du lịch mỹ|sim du lịch úc|sim du lịch anh|sim du lịch pháp",
            "esim châu âu|esim mỹ|esim úc|esim canada|esim du lịch châu âu giá rẻ",
            "sim du lịch dubai|sim du lịch thổ nhĩ kỳ|sim du lịch ấn độ",
        ]
    },

    # === DESTINATION — English (searched from SG & PH) ===
    "Dest_Asia_EN": {
        "lang": "1000",
        "seeds": [
            "thailand sim card|japan sim card|korea sim card|taiwan sim card|china sim card",
            "japan esim|korea esim|thailand esim|taiwan esim|hong kong esim|china esim",
            "bali sim card|vietnam sim card|cambodia sim card|malaysia sim card|indonesia sim card",
        ]
    },
    "Dest_EU_EN": {
        "lang": "1000",
        "seeds": [
            "europe sim card|france sim card|italy sim card|spain sim card|uk sim card|germany sim card",
            "europe esim|uk esim|france esim|italy esim|spain esim|switzerland esim",
        ]
    },
    "Dest_US_ME_EN": {
        "lang": "1000",
        "seeds": [
            "usa sim card|us esim|canada sim card|australia sim card|new zealand sim card",
            "dubai sim card|turkey sim card|turkey esim|dubai esim|qatar sim card|india esim",
        ]
    },

    # === COMPETITORS — from brief ===
    "Competitor_Gigago": {
        "lang": "1040",
        "seeds": [
            "gigago|gigago sim|gigago esim|mua sim gigago|gigago review|sim du lịch gigago|gigago giá",
        ]
    },
    "Competitor_Gohub": {
        "lang": "1040",
        "seeds": [
            "gohub|gohub sim|gohub esim|mua sim gohub|sim du lịch gohub|gohub review|gohub giá",
        ]
    },
    "Competitor_GoFlex": {
        "lang": "1040",
        "seeds": [
            "goflex|goflex sim|goflex esim|sim du lịch goflex|goflex review|mua sim goflex",
        ]
    },
    "Competitor_Airalo": {
        "lang": "1000",
        "seeds": [
            "airalo|airalo esim|airalo review|airalo app|airalo promo code|airalo vs holafly|buy airalo esim",
        ]
    },
    "Competitor_Holafly": {
        "lang": "1000",
        "seeds": [
            "holafly|holafly esim|holafly review|holafly app|holafly promo code|holafly vs airalo",
        ]
    },
    "Competitor_VN_Local": {
        "lang": "1040",
        "seeds": [
            "kohab|kohab sim|kohab esim|simstation|simstation sim|sim du lịch kohab|sim du lịch simstation",
        ]
    },

    # === PLATFORM & CHANNEL ===
    "Platform_VI": {
        "lang": "1040",
        "seeds": [
            "mua sim traveloka|sim du lịch shopee|esim klook|sim du lịch lazada|esim traveloka",
            "mua esim shopee|sim du lịch trên traveloka|đặt sim du lịch online|sim du lịch kkday",
        ]
    },
    "Platform_EN": {
        "lang": "1000",
        "seeds": [
            "traveloka esim|klook sim card|shopee sim card travel|kkday sim card|agoda esim",
        ]
    },

    # === COMPARISON & REVIEW ===
    "Comparison_VI": {
        "lang": "1040",
        "seeds": [
            "sim du lịch nào tốt|so sánh sim du lịch|review sim du lịch|sim du lịch tốt nhất 2025",
            "esim hay sim vật lý|nên mua sim du lịch ở đâu|sim du lịch hay wifi|top sim du lịch",
        ]
    },
    "Comparison_EN": {
        "lang": "1000",
        "seeds": [
            "best esim for travel 2025|esim vs physical sim|best travel sim card review|esim comparison",
            "airalo vs holafly vs gigago|best esim app|cheapest esim|travel sim vs pocket wifi",
        ]
    },
}

GEO_STRATEGY = {
    # Brand — all markets
    "Brand": ["Vietnam", "Singapore", "Philippines"],
    "Brand_VI": ["Vietnam"],
    # Product Vietnamese — Vietnam only
    "Product_SIM_VI": ["Vietnam"],
    "Product_eSIM_VI": ["Vietnam"],
    "Product_Roaming_VI": ["Vietnam"],
    "Generic_Travel_VI": ["Vietnam"],
    # Product English — all markets
    "Product_SIM_EN": ["Vietnam", "Singapore", "Philippines"],
    "Product_eSIM_EN": ["Vietnam", "Singapore", "Philippines"],
    "Generic_Travel_EN": ["Vietnam", "Singapore", "Philippines"],
    # Destination Vietnamese — Vietnam only
    "Dest_Asia_VI": ["Vietnam"],
    "Dest_EU_US_VI": ["Vietnam"],
    # Destination English — SG + PH (+ VN for English searchers)
    "Dest_Asia_EN": ["Vietnam", "Singapore", "Philippines"],
    "Dest_EU_EN": ["Vietnam", "Singapore", "Philippines"],
    "Dest_US_ME_EN": ["Vietnam", "Singapore", "Philippines"],
    # Competitors VN — Vietnam only
    "Competitor_Gigago": ["Vietnam"],
    "Competitor_Gohub": ["Vietnam"],
    "Competitor_GoFlex": ["Vietnam"],
    "Competitor_VN_Local": ["Vietnam"],
    # Competitors Global — all markets
    "Competitor_Airalo": ["Vietnam", "Singapore", "Philippines"],
    "Competitor_Holafly": ["Vietnam", "Singapore", "Philippines"],
    # Platform & Comparison
    "Platform_VI": ["Vietnam"],
    "Platform_EN": ["Singapore", "Philippines"],
    "Comparison_VI": ["Vietnam"],
    "Comparison_EN": ["Vietnam", "Singapore", "Philippines"],
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
