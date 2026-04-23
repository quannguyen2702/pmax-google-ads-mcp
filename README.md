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

## Hỗ trợ

- macOS ✅ | Linux ✅ | Windows ✅
- Python 3.10+
- Google Ads API v21

## Base

Upgraded từ [cohnen/mcp-google-ads](https://github.com/cohnen/mcp-google-ads).
