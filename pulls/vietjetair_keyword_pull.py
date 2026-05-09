#!/usr/bin/env python3
"""Keyword Puller — Vietjet Air (Aviation) — Multi-country, multi-language"""

import os, json, re, csv, time
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import requests

load_dotenv()

CLIENT_NAME = "VietjetAir"
CUSTOMER_ID = "8409563791"
OUTPUT_FILE = ""

GEO = {
    "Vietnam": ["2704"],
    "HCM": ["9040373"],
    "HaNoi": ["9040331"],
    "Kazakhstan": ["2398"],
    "Almaty": ["9063099"],
    "Astana": ["1009806"],
    "Czechia": ["2203"],
    "Prague": ["1003803"],
}

RANGES = [
    ("2025-2026", 2025, 5, 2026, 4),
]

SEED_GROUPS = {
    # === BRAND ===
    "Brand_VI": {
        "lang": "1040",
        "seeds": [
            "vietjet|vietjet air|vé máy bay vietjet|vietjet khuyến mãi|vietjet giá rẻ|đặt vé vietjet",
            "vietjet air khuyến mãi|vietjet bay quốc tế|vietjet đường bay mới|vietjet 2026",
        ]
    },
    "Brand_EN": {
        "lang": "1000",
        "seeds": [
            "vietjet|vietjet air|vietjet flight|vietjet booking|vietjet promotion|vietjet international",
            "vietjet air review|vietjet baggage|vietjet check in|vietjet air booking",
        ]
    },
    "Brand_RU": {
        "lang": "1031",
        "seeds": [
            "vietjet|vietjet air|вьетджет|вьетджет эйр|билеты вьетджет|вьетджет отзывы",
        ]
    },

    # === ROUTE: VN → KAZ (Vietnamese market) ===
    "VN_KAZ_VI": {
        "lang": "1040",
        "seeds": [
            "vé máy bay đi kazakhstan|bay đi almaty|vé máy bay almaty|vé máy bay astana|bay việt nam kazakhstan",
            "du lịch kazakhstan|tour kazakhstan|kazakhstan có gì|almaty du lịch|astana du lịch",
            "visa kazakhstan|xin visa kazakhstan|kazakhstan có cần visa không|thời tiết kazakhstan",
        ]
    },

    # === ROUTE: VN → CZK (Vietnamese market) ===
    "VN_CZK_VI": {
        "lang": "1040",
        "seeds": [
            "vé máy bay đi séc|vé máy bay prague|bay đi praha|vé máy bay cộng hòa séc|bay việt nam séc",
            "du lịch séc|tour séc|du lịch prague|prague có gì|cộng hòa séc du lịch",
            "visa séc|xin visa séc|visa schengen|visa châu âu|thời tiết prague",
        ]
    },

    # === ROUTE: KAZ → VN (Kazakhstan market — Russian) ===
    "KAZ_VN_RU": {
        "lang": "1031",
        "seeds": [
            "авиабилеты во вьетнам|билеты вьетнам|рейсы во вьетнам|перелёт во вьетнам|вьетнам из казахстана",
            "вьетнам отдых|тур во вьетнам|вьетнам из алматы|вьетнам из астаны|прямой рейс вьетнам",
            "виза во вьетнам|нужна ли виза во вьетнам|вьетнам безвиз|вьетнам погода",
        ]
    },
    "KAZ_VN_EN": {
        "lang": "1000",
        "seeds": [
            "flights to vietnam|vietnam flights from kazakhstan|cheap flights vietnam|almaty to vietnam|astana to vietnam",
            "vietnam travel|vietnam tourism|vietnam visa|vietnam holiday|direct flight vietnam",
        ]
    },

    # === ROUTE: KAZ → CZK (Kazakhstan market — Russian) ===
    "KAZ_CZK_RU": {
        "lang": "1031",
        "seeds": [
            "авиабилеты в прагу|билеты прага|рейсы в чехию|перелёт в прагу|прага из казахстана",
            "прага отдых|тур в прагу|чехия туризм|прага из алматы|прага из астаны",
        ]
    },
    "KAZ_CZK_EN": {
        "lang": "1000",
        "seeds": [
            "flights to prague|prague flights from kazakhstan|cheap flights prague|almaty to prague|astana to prague",
        ]
    },

    # === ROUTE: CZK → VN (Czech market — Czech) ===
    "CZK_VN_CZ": {
        "lang": "1021",
        "seeds": [
            "letenky do vietnamu|lety vietnam|vietnam letenky|levné letenky vietnam|přímý let vietnam",
            "vietnam dovolená|vietnam turistika|vietnam víza|vietnam počasí|zájezd vietnam",
        ]
    },
    "CZK_VN_EN": {
        "lang": "1000",
        "seeds": [
            "flights to vietnam from prague|cheap flights vietnam|prague to vietnam|direct flight vietnam|vietnam flights europe",
        ]
    },

    # === ROUTE: CZK → KAZ (Czech market) ===
    "CZK_KAZ_CZ": {
        "lang": "1021",
        "seeds": [
            "letenky do kazachstánu|lety almaty|kazachstán letenky|praha almaty|praha astana",
        ]
    },

    # === GENERIC FLIGHTS ===
    "Generic_Flight_VI": {
        "lang": "1040",
        "seeds": [
            "vé máy bay giá rẻ|vé máy bay quốc tế|đặt vé máy bay|vé máy bay khuyến mãi|săn vé máy bay giá rẻ",
            "vé máy bay châu âu|vé máy bay trung á|bay thẳng quốc tế|hãng bay giá rẻ",
        ]
    },
    "Generic_Flight_RU": {
        "lang": "1031",
        "seeds": [
            "дешёвые авиабилеты|купить авиабилеты|авиабилеты онлайн|бюджетные авиалинии|лоукостер",
            "прямые рейсы из алматы|прямые рейсы из астаны|международные рейсы казахстан",
        ]
    },
    "Generic_Flight_CZ": {
        "lang": "1021",
        "seeds": [
            "levné letenky|letenky online|nízkonákladové aerolinky|přímé lety z prahy|letenky akce",
        ]
    },
    "Generic_Flight_EN": {
        "lang": "1000",
        "seeds": [
            "cheap flights|budget airline|low cost carrier|book flights online|flight deals|international flights",
        ]
    },

    # === COMPETITORS ===
    "Comp_AirAstana_RU": {
        "lang": "1031",
        "seeds": [
            "эйр астана|air astana|билеты air astana|air astana отзывы|air astana рейсы|air astana акции",
        ]
    },
    "Comp_FlyArystan_RU": {
        "lang": "1031",
        "seeds": [
            "fly arystan|флай арыстан|билеты fly arystan|fly arystan рейсы|fly arystan отзывы",
        ]
    },
    "Comp_VietnamAirlines_VI": {
        "lang": "1040",
        "seeds": [
            "vietnam airlines|vé vietnam airlines|vietnam airlines quốc tế|vietnam airlines khuyến mãi|đặt vé vietnam airlines",
        ]
    },
    "Comp_Turkish_EN": {
        "lang": "1000",
        "seeds": [
            "turkish airlines|turkish airlines flights|turkish airlines review|turkish airlines transit|istanbul transit",
        ]
    },
    "Comp_Czech_CZ": {
        "lang": "1021",
        "seeds": [
            "czech airlines|čsa letenky|lot polish airlines|lot letenky|lot airlines praha",
        ]
    },
}


GEO_STRATEGY = {
    "Brand_VI": ["Vietnam", "HCM", "HaNoi"],
    "Brand_EN": ["Kazakhstan", "Almaty", "Astana", "Czechia", "Prague"],
    "Brand_RU": ["Kazakhstan", "Almaty", "Astana"],
    "VN_KAZ_VI": ["Vietnam", "HCM", "HaNoi"],
    "VN_CZK_VI": ["Vietnam", "HCM", "HaNoi"],
    "KAZ_VN_RU": ["Kazakhstan", "Almaty", "Astana"],
    "KAZ_VN_EN": ["Kazakhstan", "Almaty", "Astana"],
    "KAZ_CZK_RU": ["Kazakhstan", "Almaty", "Astana"],
    "KAZ_CZK_EN": ["Kazakhstan", "Almaty", "Astana"],
    "CZK_VN_CZ": ["Czechia", "Prague"],
    "CZK_VN_EN": ["Czechia", "Prague"],
    "CZK_KAZ_CZ": ["Czechia", "Prague"],
    "Generic_Flight_VI": ["Vietnam"],
    "Generic_Flight_RU": ["Kazakhstan", "Almaty", "Astana"],
    "Generic_Flight_CZ": ["Czechia", "Prague"],
    "Generic_Flight_EN": ["Kazakhstan", "Czechia"],
    "Comp_AirAstana_RU": ["Kazakhstan", "Almaty", "Astana"],
    "Comp_FlyArystan_RU": ["Kazakhstan", "Almaty", "Astana"],
    "Comp_VietnamAirlines_VI": ["Vietnam", "HCM", "HaNoi"],
    "Comp_Turkish_EN": ["Kazakhstan", "Czechia"],
    "Comp_Czech_CZ": ["Czechia", "Prague"],
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
