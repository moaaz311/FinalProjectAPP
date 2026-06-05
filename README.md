# Egypt Trade AI Dashboard Web App

A Flask web application for viewing embedded Power BI dashboards, chatting with an AI assistant over SQL Server BI data, sending dashboard exports through Power Automate, and allowing users to subscribe to dashboard update notifications.

## Features

- Embedded Power BI reports and paginated reports
- AI chat assistant connected to SQL Server views
- Natural-language question answering with SQL generation and validation
- Dashboard PDF sharing through Power Automate
- Local update-alert subscription system using `data/update_subscribers.json`
- Separated frontend structure:
  - HTML in `templates/index2.html`
  - CSS in `static/css/style.css`

## Project Structure

```text
newapp/
│
├── app2.py
├── requirements.txt              # optional, recommended
├── .env                          # local only, do not upload
├── .env.example                  # safe template for GitHub
├── .gitignore
│
├── data/
│   └── update_subscribers.json
│
├── knowledge/
│   ├── schema.json
│   └── schema.txt
│
├── middleware/
│   ├── prompt_builder.py
│   ├── schema_retriever.py
│   └── sql_validator.py
│
├── static/
│   └── css/
│       └── style.css
│
└── templates/
    └── index2.html
```

## Requirements

- Python 3.10+
- SQL Server
- ODBC Driver 17 for SQL Server
- Power BI workspace and embedded report links
- Power Automate HTTP trigger for PDF sending
- OpenRouter API key

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install flask flask-cors python-dotenv openai flask-mail reportlab pyodbc pandas requests numpy sqlalchemy cachetools
```

Optional: save dependencies:

```powershell
python -m pip freeze > requirements.txt
```

## Environment Variables

Create a `.env` file in the project root. Do not upload `.env` to GitHub.

Use `.env.example` as a template:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
HTTP_REFERER=http://localhost:5000
X_TITLE=EgyptTradeAI

SQL_SERVER=YOUR_SERVER_NAME
SQL_DATABASE=EgyptBI_DWH1

POWER_AUTOMATE_URL=your_power_automate_pdf_flow_url

UPDATE_SUBSCRIBERS_FILE=data/update_subscribers.json
SUBSCRIBERS_API_KEY=your_secret_key_for_subscribers_endpoint
```

## Running the App

```powershell
python app2.py
```

Open:

```text
http://127.0.0.1:5000
```

## Update Alerts Feature

Users can subscribe to report update alerts from the web UI. Emails are stored locally in:

```text
data/update_subscribers.json
```

The app exposes an endpoint that Power Automate can call:

```http
GET /update-subscribers
```

Required header:

```text
X-API-Key: your_secret_key_for_subscribers_endpoint
```

Response example:

```json
{
  "count": 2,
  "emails": ["user1@example.com", "user2@example.com"],
  "emailsString": "user1@example.com;user2@example.com"
}
```

Because the app is local, Power Automate cannot call `localhost`. For testing, expose the local app using ngrok:

```powershell
ngrok http 5000
```

Then use this URL in Power Automate:

```text
https://your-ngrok-url.ngrok-free.app/update-subscribers
```

## Power Automate Update Flow

Suggested flow:

```text
Recurrence
↓
HTTP POST - Get Power BI Access Token
↓
HTTP GET - Get Power BI Reports
↓
HTTP GET - Get Subscribers
↓
Apply to each report
    ↓
    Get SharePoint item by ReportId
    ↓
    If new report:
        Create item
        Send email to subscribers
    ↓
    If existing report and ReportName changed:
        Update item
        Send email to subscribers
```

Use this value in the "To" field of Send email:

```powerautomate
body('HTTP_GET_-_Get_Subscribers')?['emailsString']
```

Add a condition before sending:

```powerautomate
not(empty(body('HTTP_GET_-_Get_Subscribers')?['emailsString']))
```

## GitHub Upload Steps

Initialize Git:

```powershell
git init
git add .
git status
git commit -m "Initial commit - Egypt Trade AI dashboard app"
```

Create a new GitHub repository, then connect it:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git push -u origin main
```

## Important Security Notes

- Never upload `.env`
- Never upload real API keys, client secrets, or access tokens
- If secrets were ever exposed, rotate them immediately
- Keep `SUBSCRIBERS_API_KEY` private
- Use `.env.example` for public configuration documentation

## License

This project is for educational and portfolio use.
