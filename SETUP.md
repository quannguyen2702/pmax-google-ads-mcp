# PMAX Google Ads MCP — Setup Guide

> Hướng dẫn cài đặt từ đầu cho **macOS, Linux, và Windows**.
> Thời gian: ~30-60 phút lần đầu.

---

## Bước 1: Cài Python

### macOS
```bash
# Check đã có chưa
python3 --version    # Cần 3.10+

# Nếu chưa có:
brew install python3
```

### Windows
1. Download Python từ https://www.python.org/downloads/ (3.10+)
2. Khi cài, **✅ tick "Add Python to PATH"** (quan trọng!)
3. Verify: mở Command Prompt → `python --version`

### Linux
```bash
sudo apt update && sudo apt install python3 python3-pip python3-venv
```

---

## Bước 2: Clone repo

### macOS/Linux
```bash
git clone https://github.com/YOUR_ORG/pmax-google-ads-mcp.git ~/mcp-google-ads
cd ~/mcp-google-ads
```

### Windows (Command Prompt)
```cmd
git clone https://github.com/YOUR_ORG/pmax-google-ads-mcp.git %USERPROFILE%\mcp-google-ads
cd %USERPROFILE%\mcp-google-ads
```

> Nếu chưa có git: download zip từ GitHub → extract vào folder.

---

## Bước 3: Setup Python environment

### macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Windows
```cmd
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Verify: chạy `pip list` — phải thấy `requests`, `google-auth`, `python-dotenv`.

---

## Bước 4: Google Cloud credentials

### 4A. Tạo Google Cloud Project

1. Vào https://console.cloud.google.com
2. Tạo project mới (hoặc dùng project có sẵn)
3. Enable **Google Ads API**: Menu → APIs & Services → Library → tìm "Google Ads API" → Enable

### 4B. Tạo OAuth credentials

1. APIs & Services → Credentials → Create Credentials → **OAuth client ID**
2. Application type: **Desktop app**
3. Download JSON → đổi tên thành `client_secret.json` → copy vào folder `mcp-google-ads`

### 4C. Generate refresh token

```bash
# macOS/Linux:
.venv/bin/python generate_credentials.py

# Windows:
.venv\Scripts\python generate_credentials.py
```

Browser sẽ mở → login Google account có quyền Google Ads → Authorize → file `credentials.json` được tạo.

> ⚠️ Nếu không có `generate_credentials.py`, tạo thủ công theo hướng dẫn `cohnen/mcp-google-ads` README.

### 4D. Lấy Developer Token

1. Vào Google Ads → Tools & Settings → API Center
2. Copy Developer Token
3. **Lưu ý:** Token level "Test" sẽ trả kết quả rỗng cho Keyword Planner. Cần level Standard hoặc Basic.

---

## Bước 5: Config .env

```bash
# macOS/Linux:
cp .env.example .env

# Windows:
copy .env.example .env
```

Mở `.env`, sửa:
```env
GOOGLE_ADS_DEVELOPER_TOKEN=paste_token_here
GOOGLE_ADS_CREDENTIALS_PATH=./credentials.json
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

| Field | Mô tả |
|---|---|
| `DEVELOPER_TOKEN` | Từ bước 4D |
| `CREDENTIALS_PATH` | Path tới `credentials.json` (từ bước 4C) |
| `LOGIN_CUSTOMER_ID` | MCC ID nếu access qua MCC. Để trống nếu access trực tiếp |

---

## Bước 6: Verify

```bash
# macOS/Linux:
.venv/bin/python -c "
from dotenv import load_dotenv; import os; load_dotenv()
t = os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN','')
p = os.environ.get('GOOGLE_ADS_CREDENTIALS_PATH','')
print(f'Token: {t[:10]}...' if t else '❌ Token NOT SET')
print(f'Creds: ✅ EXISTS' if os.path.exists(p) else f'❌ NOT FOUND: {p}')
"

# Windows:
.venv\Scripts\python -c "from dotenv import load_dotenv; import os; load_dotenv(); t=os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN',''); p=os.environ.get('GOOGLE_ADS_CREDENTIALS_PATH',''); print(f'Token: {t[:10]}...' if t else 'Token NOT SET'); print('Creds: EXISTS' if os.path.exists(p) else f'Creds NOT FOUND: {p}')"
```

Thấy Token + Creds OK → tiếp bước 7.

---

## Bước 7: Chạy Keyword Puller

### 7A. Sửa CONFIG trong `keyword_pull.py`

Mở file, sửa phần CONFIG ở đầu:
- `CLIENT_NAME` = tên client
- `CUSTOMER_ID` = Google Ads ID (10 chữ số)
- `GEO` = locations cần pull
- `SEED_GROUPS` = keywords theo từng angle

File có ví dụ cho Education, Real Estate, Finance — chọn ngành gần nhất, sửa cho phù hợp.

### 7B. Chạy

```bash
# macOS/Linux:
.venv/bin/python keyword_pull.py

# Windows:
.venv\Scripts\python keyword_pull.py
```

### 7C. Output

File CSV xuất hiện cùng folder: `clientname_keywords_full.csv`

Import vào Google Sheets → gửi cho Duy's Agent.

---

## Bước 8 (Optional): Setup Claude Desktop MCP

Nếu muốn dùng MCP tools trong Claude chat (keyword lookup, geo search, v.v.):

### Config file location

| OS | Path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

### Config content

**macOS/Linux:**
```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/Users/YOUR_USERNAME/mcp-google-ads/.venv/bin/python",
      "args": ["/Users/YOUR_USERNAME/mcp-google-ads/google_ads_server.py"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your_token",
        "GOOGLE_ADS_CREDENTIALS_PATH": "/Users/YOUR_USERNAME/mcp-google-ads/credentials.json",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ""
      }
    }
  }
}
```

**Windows:**
```json
{
  "mcpServers": {
    "google-ads": {
      "command": "C:\\Users\\YOUR_USERNAME\\mcp-google-ads\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\YOUR_USERNAME\\mcp-google-ads\\google_ads_server.py"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your_token",
        "GOOGLE_ADS_CREDENTIALS_PATH": "C:\\Users\\YOUR_USERNAME\\mcp-google-ads\\credentials.json",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": ""
      }
    }
  }
}
```

> ⚠️ Thay `YOUR_USERNAME`. Dùng **absolute path**, không dùng `~` hay `%USERPROFILE%`.

Restart Claude Desktop (Cmd+Q / Alt+F4 → mở lại).

---

## Troubleshooting

| Lỗi | Nguyên nhân | Fix |
|---|---|---|
| Script báo "CONFIG ERRORS" | Chưa điền CONFIG | Mở `keyword_pull.py`, sửa phần CONFIG |
| "No keyword ideas found" hoặc 0 raw | Developer Token level Test | Cần upgrade lên Standard/Basic |
| "Error 401 / Invalid credentials" | Token expired | Xóa `credentials.json`, chạy lại `generate_credentials.py` |
| "Error 403 / Not authorized" | Account chưa link Cloud project | Google Ads → Admin → API Access → link |
| MCP không load trong Claude | Path sai | Check absolute path trong config, restart Claude |
| Output ít keywords | Ít seed groups | Thêm seed groups, mỗi group = max 100 kw thêm |
| Output nhiều noise | Filter chưa đủ | Thêm pattern vào `EXCLUDE_PATTERNS`, chạy lại |
| Windows: "python not found" | Python chưa trong PATH | Cài lại Python, tick "Add to PATH" |
| Windows: "venv activate lỗi" | Execution policy | Chạy: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

---

## File Structure

```
mcp-google-ads/
├── google_ads_server.py       ← MCP server (upgraded)
├── keyword_pull.py            ← Keyword Puller template
├── requirements.txt           ← Dependencies
├── .env.example               ← Template
├── .env                       ← Credentials (GIT IGNORED)
├── credentials.json           ← OAuth (GIT IGNORED)
├── client_secret.json         ← OAuth client (GIT IGNORED)
├── SETUP.md                   ← File này
├── README.md                  ← Overview
└── .gitignore
```
