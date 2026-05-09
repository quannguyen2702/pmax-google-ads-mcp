# PMAX Google Ads MCP

Self-hosted Google Ads MCP server cho Claude Desktop + Keyword Puller script.

## Tại sao dùng repo này?

- **Self-hosted** — client data chỉ chạy trên máy bạn, không qua third-party
- **Keyword Planner trong Claude** — pull keywords với monthly breakdown + custom date range
- **Scale linh hoạt** — số keyword output phụ thuộc CONFIG, từ vài trăm đến vài nghìn tùy nhu cầu
- **10 tools MCP mới** — keyword ideas, geo search, negative keyword suggest, PMax analysis, v.v.

## Quick Start — Keyword Puller (không cần Claude Desktop)

```bash
# Clone
git clone https://github.com/YOUR_ORG/pmax-google-ads-mcp.git ~/mcp-google-ads
cd ~/mcp-google-ads

# Setup
python3 -m venv .venv                              # Windows: python -m venv .venv
.venv/bin/pip install -r requirements.txt           # Windows: .venv\Scripts\pip install -r requirements.txt
cp .env.example .env                                # Windows: copy .env.example .env
# Sửa .env với credentials

# Sửa CONFIG trong keyword_pull.py cho client bạn, rồi:
.venv/bin/python keyword_pull.py                    # Windows: .venv\Scripts\python keyword_pull.py
# Output: clientname_keywords_full.csv → import Google Sheets → feed Duy's Agent
```

Chi tiết setup từ zero: [SETUP.md](SETUP.md)

## ⚠️ Keyword Puller — PHẢI dùng Python Script, KHÔNG kéo qua chat

Tool `get_keyword_ideas` trong MCP **CHỈ dùng để test/verify nhanh** (check 1-2 seed xem API hoạt động, data format đúng không). **KHÔNG BAO GIỜ** dùng tool này để kéo keyword giao cho khách hoặc dùng trong proposal.

**Lý do:**
- Kéo qua chat **cực kỳ chậm** — mỗi lần gọi MCP tool phải qua chat roundtrip, response lớn ngốn token
- **Giới hạn response size** — MCP trả về trong context window, nhiều keyword sẽ bị cắt hoặc gây lỗi
- **Tốn token vô ích** — 1 lần pull 500 keywords qua chat tốn hàng chục nghìn token; script chạy local tốn 0 token
- **Dễ gây bug** — Claude phải parse response lớn trong chat, hay bị mất data hoặc hallucinate

**Flow đúng (bắt buộc):**

```
1. Claude đọc brief (mail/chat)
2. Claude generate Python script (CONFIG + seed keywords + API calls)
3. Desktop Commander chạy script trực tiếp trên máy
4. Script output → CSV file (không giới hạn số lượng keyword)
5. Claude đọc CSV → QC → Upload Google Sheet → Reply mail
```

**Kết quả thực tế:**
- Lotte Finance: 647 keywords, 21 giây, zero errors, 0 token cho phần kéo data
- Muji: 1,237 keywords, ~45 giây
- Xplori (multi-country): 2,000+ keywords

**Yêu cầu:** Cài [Desktop Commander](https://github.com/wonderwhy-er/DesktopCommanderMCP) để Claude tự chạy script:

```bash
npx @wonderwhy-er/desktop-commander@latest setup
```

Restart Claude Desktop sau khi cài.

## Hỗ trợ

- macOS ✅ | Linux ✅ | Windows ✅
- Python 3.10+
- Google Ads API v21

## Base

Upgraded từ [cohnen/mcp-google-ads](https://github.com/cohnen/mcp-google-ads).
