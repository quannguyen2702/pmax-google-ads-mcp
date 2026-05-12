# Keyword Puller Agent — SKILL.md

> Skill cho Claude Desktop. Tự động pull keyword từ Google Keyword Planner khi nhận email request.

---

## TRIGGER

Khi được yêu cầu check Gmail hoặc khi phát hiện email có:
- **Subject chứa** `[KW Pull]`
- **To:** haiquan.nguyen@pmax.com.vn

## MAIL TEMPLATE EXPECTED

```
Subject: [KW Pull] Tên Client — Ngành

Client: Tên client
Google Ads ID: 10 chữ số (nếu có)
Ngành: Auto / Beauty / Digital Product / Education / FMCG / Fashion / Finance / Healthcare / Home&Electronics / Real Estate / Retail / Travel / Other
Mục đích: Proposal (kéo hết) / Chạy ads (chỉ high-intent)
Geo: Vietnam + HCM + ... (tên tỉnh thành)
Time: 2024 + 2025 (hoặc range tùy chọn)
Scope: Brand + Generic + Competitor
Product Focus: (nếu có — ví dụ "chỉ LINEN", "Travel SIM", "nước dừa")
Competitors: Tên đối thủ (nếu có)
Landing page: URL (để extract seeds)
Brief/Context: (optional)
```

---

## EXECUTION FLOW

### Step 1: Parse Email Brief
Extract các field từ mail body. Map vào variables:
- `client_name` → CLIENT_NAME
- `google_ads_id` → CUSTOMER_ID (10 digits, no dashes)
- `nganh` → dùng để chọn seed strategy + EXCLUDE_PATTERNS
- `muc_dich` → "proposal" hoặc "ads" → quyết định QC mode
- `product_focus` → enforce vào tất cả seeds (Rule 6)
- `geo_list` → cần tra geo IDs
- `time_ranges` → RANGES
- `scope` → quyết định angles nào (Brand/Generic/Competitor/Product...)
- `competitors` → tên đối thủ, dùng cho Competitor seeds
- `landing_page` → fetch page, extract relevant terms cho seeds

### Step 2: Resolve Geo IDs
Dùng MCP tool `search_geo_targets` để tra location IDs.

**Geo IDs đã biết (cache):**
```
Vietnam=2704, HCM=9040373, Bình Dương=9047166, Bà Rịa VT=9040374
Hà Nội=9040331, Đồng Nai=9040372, Long An=9047181, Bình Phước=9047167
Cần Thơ=9040377, Vĩnh Long=9047188, Đà Nẵng=9047170, Khánh Hòa=9040364
Huế=9040349, Quảng Nam=9040351, Hải Phòng=9040353
Singapore=2702, Philippines=2608, Kazakhstan=2398, Czechia=2203
Almaty=9063099, Astana=1009806, Prague=1003803
```
Nếu tỉnh thành không có trong cache → gọi `search_geo_targets`.

### Step 3: Generate Seed Keywords
Dựa trên ngành + scope + competitors + landing page + product_focus.

**Nguyên tắc seeds:**
- Seeds phải contextual, KHÔNG generic
- Mỗi seed string tối đa 10 keywords, phân cách bằng `|`
- Language: Vietnamese = `1040`, English = `1000`, Russian = `1031`, Czech = `1021`
- **XEM RULE 6 (Product Focus)** trước khi viết seeds

### Step 4: Build GEO_STRATEGY
- **Brand, USP**: pull tất cả geo levels
- **Product, Generic**: pull nationwide + major cities
- **Competitor**: chỉ nationwide

### Step 5: Generate Script File
Copy `keyword_pull.py` template, fill CONFIG section, save:
```
~/mcp-google-ads-cohnen/pulls/{client_name_lower}_keyword_pull.py
```
**CRITICAL:** Script file phải copy TOÀN BỘ code phía sau CONFIG từ template. Chỉ thay đổi CONFIG.
**CRITICAL:** EXCLUDE_PATTERNS phải auto-populate từ UNIVERSAL + INDUSTRY patterns (xem Rule 7).

### Step 6: Run Script via Desktop Commander
```bash
cd ~/mcp-google-ads-cohnen && .venv/bin/python pulls/{client_name_lower}_keyword_pull.py
```
Expected runtime: 1-5 phút. Output: `~/mcp-google-ads-cohnen/{client}_keywords_full.csv`

### Step 7: Post-pull QC (BẮT BUỘC — xem Rule 8)
Chạy QC script tự động → tách Clean + Flagged → verify trước khi deliver.

### Step 8: Upload CSV to Google Sheet
Tạo Google Sheet mới, import CSV, lấy URL.

### Step 9: Reply Email (CHỈ khi Quân confirm — xem Rule 4)

---

## MCP CONNECTORS REQUIRED

| Connector | Customer ID | Dùng cho |
|-----------|-------------|----------|
| google-ads | 8409563791 | VGU — geo search, keyword ideas (test only) |
| google-ads-fec | 7312895768 (MCC: 4107864898) | FEC account |
| Google Workspace MCP | — | Gmail, Google Sheet |
| Desktop Commander | — | Chạy Python script trên máy |

## FILE LOCATIONS

| File | Path |
|------|------|
| Template script | `~/mcp-google-ads-cohnen/keyword_pull.py` |
| Client scripts | `~/mcp-google-ads-cohnen/pulls/` |
| Output CSVs | `~/mcp-google-ads-cohnen/{client}_keywords_full.csv` |
| Credentials | `~/mcp-google-ads-cohnen/.env` |

## DECISION RULES

**Pull size routing:**
- < 100 keywords (1-2 seeds, 1 geo): Pull qua MCP `get_keyword_ideas` — CHỈ để test
- 100+ keywords: BẮT BUỘC dùng script qua Desktop Commander

**Customer ID routing:**
- Mail có Google Ads ID → dùng ID đó
- Không có → dùng VGU (8409563791) hoặc FEC (7312895768)

---

## CRITICAL RULES — KHÔNG ĐƯỢC VI PHẠM

### Rule 1: KHÔNG BAO GIỜ bịa data
- KHÔNG được gõ tay search volume vào CSV
- Mọi data PHẢI đến từ API response (qua script hoặc MCP tool)
- Nếu không có data → nói thẳng, KHÔNG bịa

### Rule 2: Script lỗi → DEBUG script, KHÔNG switch sang manual
- Script output thiếu data → ĐỌC code → FIX → CHẠY LẠI
- KHÔNG ĐƯỢC bỏ script để pull thủ công qua MCP chat
- MCP chat chỉ dùng cho: quick test (<100 kw), geo ID search, debug

### Rule 3: Verify TRƯỚC khi deliver
- Đọc 10-20 dòng đầu CSV check columns đầy đủ
- Check monthly volume có data (không toàn trống)
- Count total rows
- Chạy QC filter (Rule 8)
- KHÔNG deliver file lỗi. KHÔNG deliver nhiều lần.

### Rule 4: KHÔNG tự ý gửi mail
- Quân confirm "oke gửi đi" → mới reply mail
- KHÔNG auto-reply khi chưa được confirm

### Rule 5: Detect & flag sensitive/negative keywords
- UNIVERSAL patterns luôn apply (xem Rule 7)
- Khi phát hiện: tách Clean + Flagged (2 tabs), báo Quân review
- KHÔNG tự ý xóa — flagged vẫn có insight value

### Rule 6: Product Focus Enforcement (NEW)
Khi brief có product focus cụ thể (ví dụ "chỉ LINEN", "Travel SIM", "nước dừa"):
- TẤT CẢ seeds (kể cả Brand, Competitor) PHẢI chứa product qualifier
- KHÔNG BAO GIỜ dùng brand/competitor name đứng một mình

```
Brief: Muji — Fashion (LINEN only)
  SAI:  "muji" → trả về sofa, chocolate, mã sản phẩm
  ĐÚNG: "muji linen|áo linen muji|quần linen muji"
  SAI:  "uniqlo" → trả về mọi thứ Uniqlo
  ĐÚNG: "uniqlo linen|áo linen uniqlo"

Brief: Xplori — Travel SIM
  SAI:  "du lịch thái lan" → trả về tour, hotel, visa
  ĐÚNG: "sim du lịch thái lan|esim thái lan"
```

Exception: Nếu brief KHÔNG có product focus → được dùng brand standalone.

### Rule 7: EXCLUDE_PATTERNS by Industry (NEW)
Script auto-apply: UNIVERSAL patterns + Industry-specific patterns.
Claude detect ngành từ brief → chọn đúng pattern list.

**UNIVERSAL (mọi ngành):**
```
tuyển dụng, việc làm, ứng tuyển, nhân viên, lương,
career, hiring, job, recruitment, salary,
lừa đảo, scam, fraud, bóc phốt, tố cáo, bị lừa,
kiện, khiếu nại, complaint, lawsuit, phá sản,
\d{7,} (product codes/SKU)
```

**INDUSTRY-SPECIFIC PATTERNS:**

**Auto:** bảo dưỡng, sửa chữa, triệu hồi, recall, phạt nguội, tai nạn, bằng lái, bảo hiểm xe, xe cũ, đăng ký xe, đăng kiểm, trước bạ

**Beauty:** tác hại, dị ứng, kích ứng, side effect, hàng giả, fake, nhái, hết hạn, da liễu, thuốc trị, kê đơn, tự làm, homemade, diy, hoàn tiền, trả hàng

**Digital Product:** crack, keygen, free download, bẻ khóa, torrent, bị lỗi, error, crash, hủy tài khoản, xóa tài khoản, cancel subscription, open source, miễn phí thay thế

**Education:** miễn phí, free course, đáp án, đề thi, mua bằng, bằng giả, bài tập, homework, luận văn, thesis, học bổng 100, ra trường làm gì

**FMCG:** tác hại, ngộ độc, hết hạn, thu hồi, chất cấm, gây ung thư, nhiễm khuẩn, cách làm, tự làm, recipe, đại lý, nhượng quyền, giá sỉ, nhà máy

**Fashion:** \d{6,} (SKU), bảng size, đổi size, trả hàng, hàng giả, replica, super fake, cách giặt, bảo quản, mã giảm giá, voucher, coupon, thanh lý, secondhand

**Finance:** hotline, tổng đài, số điện thoại, cskh, nợ xấu, xóa nợ, đòi nợ, tất toán, thanh toán khoản vay, trả nợ, gia hạn, tra cứu hợp đồng, bảo hiểm, tiết kiệm

**Healthcare:** triệu chứng, dấu hiệu, symptom, chữa tại nhà, mẹo chữa, dân gian, tự chữa, tác dụng phụ, liều dùng, quá liều, bảo hiểm y tế, cấp cứu, nghiên cứu

**Home & Electronics:** sửa chữa, thay pin, thay màn, repair, bảo hành, jailbreak, root, bẻ khóa, thanh lý, cũ, secondhand, refurbished, cách sử dụng, hướng dẫn, bị lỗi, không hoạt động

**Real Estate:** tranh chấp, quy hoạch treo, giải tỏa, thu hồi đất, đền bù, dự án ma, sổ đỏ giả, thuế chuyển nhượng, sửa nhà, cải tạo, thiết kế nội thất, phong thủy, hướng nhà

**Retail:** mã giảm giá, voucher, coupon, flash sale, freeship, hoàn tiền, trả hàng, hàng lỗi, giao sai, hàng giả, hàng nhái, bán hàng trên, mở shop, đăng ký bán, seller center

**Travel (chung):** delay, hủy chuyến, trễ chuyến, lost baggage, bị từ chối visa, nguy hiểm, cảnh báo, chiến tranh

**Travel SIM (sub):** tour, khách sạn, hotel, resort, hostel, booking, đặt phòng, airbnb, địa điểm, ăn gì, chơi gì, visa, hộ chiếu, passport, vé máy bay

**Aviation (sub):** sân bay, terminal, phòng chờ, lounge, claim hành lý, phi công, tiếp viên, cabin crew, pilot salary

**Other:** apply UNIVERSAL only + Claude tự detect thêm từ brief context

### Rule 8: Post-pull QC Filter (NEW)
Sau khi script chạy xong, BẮT BUỘC chạy QC:
1. Match output keywords vs UNIVERSAL + INDUSTRY patterns
2. Check product focus compliance (nếu có — Rule 6)
3. Flag product codes (regex \d{7,})
4. Phân loại: Clean tab + Flagged tab (ghi reason)
5. Nếu mục đích = proposal → giữ flagged ở tab riêng
6. Nếu mục đích = chạy ads → auto-remove flagged

### Rule 9: Ambiguous Brand Name Handling (NEW)
Khi brand name trùng từ phổ biến hoặc nhiều nghĩa:
- Cake (fintech vs bánh) → chỉ "cake vay", "cake app", KHÔNG "cake" standalone
- Lotte (finance vs mart vs cinema) → chỉ "lotte finance", KHÔNG "lotte"
- Home (credit vs nhà) → chỉ "home credit", KHÔNG "home"
- Rule: brand ≤ 1 từ VÀ là từ phổ biến → BẮT BUỘC gắn product/company qualifier

### Rule 10: Pre-pull Demand Validation (NEW)
Với multi-geo/multi-route pulls:
1. Chạy 1 test call nhỏ cho mỗi geo/route combination
2. Test trả về < 20 keywords → SKIP, ghi note "low demand"
3. Tiết kiệm API calls + giảm noise
Ví dụ: Vietjet CZK→KAZ = 5 results → skip

### Rule 11: Seed Specificity Check (NEW)
Trước khi chạy script, verify TỪNG seed:
- "Nếu tôi search từ này trên Google, trang 1 có liên quan client không?"
- Không = bỏ seed hoặc thêm qualifier
```
Brief: Cocoxim — Nước dừa
  SAI:  "nước giải khát" → page 1 = trà, nước ngọt = quá broad
  ĐÚNG: "nước dừa đóng hộp" → page 1 = nước dừa brands
```

### Rule 12: Brief Compliance Check (NEW)
Trước khi deliver, verify output vs brief:
1. Angles match brief scope (không thêm angle ngoài brief)
2. Geo coverage match (không có data ngoài brief geo)
3. Time range match
4. Product focus match (nếu brief nói "chỉ LINEN" → 100% kw phải liên quan linen)

---

## ERROR HANDLING

| Error | Nguyên nhân | Fix |
|-------|-------------|-----|
| 401 Unauthorized | Token expired | Refresh token hoặc báo Quân |
| 403 Forbidden | Customer ID sai | Check ID, hỏi lại sender |
| 0 keywords returned | Seeds quá generic/niche | Điều chỉnh seeds |
| Script > 10 phút | Quá nhiều API calls | Giảm seed groups hoặc geo |

---

## SEED STRATEGY BY INDUSTRY (Reference)

**Education:** Brand + viết tắt + tuyển sinh + học phí + ngành học + USP + competitor
**Real Estate:** Dự án + chủ đầu tư + loại hình + khu vực + competitor
**Finance:** Brand + sản phẩm (vay/thẻ/bảo hiểm) + nhu cầu + competitor
**Auto:** Brand + dòng xe + phân khúc + mục đích (mua/lái thử) + competitor
**Beauty:** Brand + loại SP (serum/kem/toner) + concern (da dầu/mụn) + competitor
**FMCG:** Brand + category (nước dừa/sữa/snack) + occasion + competitor
**Fashion:** Brand + chất liệu + loại đồ + phong cách + competitor
**Healthcare:** Brand/cơ sở + chuyên khoa + dịch vụ + triệu chứng mua + competitor
**Home&Electronics:** Brand + model + category + specs so sánh + competitor
**Travel:** Brand + destination + loại hình (tour/SIM/vé) + competitor
**Retail:** Brand/platform + category + deal + competitor
**Digital:** Brand + feature + pricing + use case + competitor

---

## LESSON LEARNED — KHÔNG TỰ DEBUG NHIỀU VÒNG

Khi output bất thường (ví dụ: 78% keywords không có volume, data trống, số liệu lệch nhiều):

1. **DỪNG LẠI** — không tự debug thêm
2. **Hỏi Quân verify thủ công** trên Google Keyword Planner / Google Ads UI / tool gốc
3. **Chờ confirm** trước khi chạy lại

SAI: Output trống → tự test 3 time ranges → test 2 accounts → build script v2 → test account thứ 3 → tốn 5 vòng debug vô ích
ĐÚNG: Output trống → "78% trống, có thể volume thấp thật hoặc bug. Quân check thử 2-3 keyword trên GKP trước được không?"

Lý do: Nhiều trường hợp data đúng nhưng trông bất thường (volume thấp thật, ngành niche, brand mới). Tự debug nhiều vòng = tốn token + tốn thời gian + không giải quyết gì.
