# GDGoC LNCTS Certificate Generator

This repository contains the reusable script for generating GDGoC LNCTS tenure completion certificates. It is intended for future team leads so they can use the same process each tenure.

## Files to keep in this repository

```text
certificate-generator/
├── automate_cert.py
├── requirements.txt
├── members.example.csv
└── README.md
```

The signed certificate template is **not included** because it contains people's signatures. Keep the approved `template.png` in a trusted club drive and share it only with people who need it. Each lead should download it to their local `certificate-generator` folder before generating certificates.

## Local files for each run

Keep these files together on the lead's computer:

```text
certificate-generator/
├── automate_cert.py
├── requirements.txt
├── template.png          # obtained separately; do not commit
├── members.csv           # current roster; do not commit
├── Roboto-Regular.ttf    # optional
├── Roboto-Bold.ttf       # optional
└── generated_certs/      # created by the script; do not commit
```

`members.csv` must have these first-row headers (the `E-mail` spelling is accepted):

```csv
Name,E-mail,Designation,Team,Serial
```

Copy `members.example.csv` to `members.csv` and add the current members. Use one test row addressed to yourself first. Check names, email addresses, designations, team names, and unique serial numbers before generating or emailing certificates.

## Setup on Windows

Open PowerShell in the local `certificate-generator` folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell does not allow environment activation, use the environment's Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Generate and review certificates

Run preview mode first. It creates PNGs in `generated_certs` and does not send email:

```powershell
python automate_cert.py
```

Open the generated images and carefully review placement, spelling, paragraph wrapping, signatures, and recipient details. The script uses the Roboto font files if supplied; otherwise it falls back to Arial. Adjust the layout coordinates in the script if the approved template changes.

## Email certificates

Email mode sends one message to every address in `members.csv`, attaching each member's PNG. Gmail requires an App Password with 2-Step Verification enabled. Set credentials only in the current PowerShell window; never save them in this repository, CSV, or script:

```powershell
$env:GMAIL_ADDRESS = "your.club.sender@gmail.com"
$env:GMAIL_APP_PASSWORD = "paste-app-password-here"
python automate_cert.py --send
```

Before using `--send`, confirm the full recipient list and preview images. After sending, clear the session variables:

```powershell
Remove-Item Env:GMAIL_ADDRESS
Remove-Item Env:GMAIL_APP_PASSWORD
```

## Keep private data out of GitHub

Never commit:

- The signed `template.png` or any other restricted signature artwork
- `members.csv`, `members.xlsx`, or other files containing member names and email addresses
- Generated certificates or `generated_certs/`
- Gmail App Passwords, `.env` files, or other credentials
- `.venv/` or Python cache files

Add these entries to the repository's `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
generated_certs/
template.png
members.csv
members.xlsx
.env
```

Keep the repository private if it includes any club-only materials. Give new leads repository access through their own GitHub accounts, and remove access when their role ends.
