# Data Entry Automation Tool (Python CLI)

A portfolio-ready command-line tool that automates data entry into web forms.  
It reads rows from **CSV/Excel** files and fills form fields via **Selenium** using a declarative **YAML mapping**.  
Perfect for showcasing Python automation, Selenium, YAML configuration, and error handling.

---

## ✨ Features
- **CSV/Excel input** (`.csv`, `.xlsx`)
- **YAML mapping**: column → CSS selector, field types, defaults, validators
- **Form automation** via Selenium (Chrome/Firefox, headless optional)
- **Validation** (required fields, regex, enum values)
- **Dry-run mode**: preview actions without submitting
- **Filter/query** rows with Pandas expressions
- **Start/End row** ranges
- **Resume**: skip rows already processed using results CSV
- **Detailed results** CSV with row status (success/failure and reason)

---

## 📂 Repository Layout
```
data-entry-automation/
├─ dea.py                   # Main CLI script
├─ mappings/
│  └─ example_form.yaml     # Sample mapping config
├─ samples/
│  ├─ input.csv             # Example CSV input
│  └─ input.xlsx            # Example Excel input
├─ requirements.txt         # Dependencies
├─ .gitignore
└─ README.md
```

---

## ⚡ Quickstart

### 1. Setup environment
```bash
python -m venv .venv
# Activate:
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Run (dry-run first!)
```bash
python dea.py --input samples/input.csv --map mappings/example_form.yaml --dry-run --headless
```

### 3. Real submission
```bash
python dea.py --input samples/input.csv --map mappings/example_form.yaml --resume --headless
```

---

## 📝 Mapping Example (`mappings/example_form.yaml`)
```yaml
url: "https://example.com/forms/customer"
submit_selector: "button[type='submit']"
success_check:
  selector: "div.alert-success"
  text_contains: "Thank you"

browser: "chrome"
headless: false

fields:
  first_name:
    selector: "#firstName"
    required: true
  last_name:
    selector: "#lastName"
    required: true
  email:
    selector: "input[name='email']"
    required: true
    validators:
      - type: regex
        pattern: "^[^@\s]+@[^@\s]+\.[^@\s]+$"
        message: "Invalid email format"
  country:
    selector: "#country"
    type: select
  newsletter:
    selector: "#newsletter"
    type: checkbox
  notes:
    selector: "textarea[name='notes']"
    default: ""
```

---

## 📊 Sample Input (`samples/input.csv`)
```csv
first_name,last_name,email,country,newsletter,notes
Ava,Stone,ava@example.com,US,1,Priority customer
Liam,Brown,liam@sample.org,GB,0,
```

---

## 🔧 CLI Options
- `--input`: Path to CSV/Excel input
- `--map`: Path to YAML mapping file
- `--dry-run`: Don’t actually submit
- `--headless`: Run without opening browser window
- `--filter`: Pandas query filter, e.g. `"country == 'US'"`
- `--start`, `--end`: Row ranges
- `--resume`: Skip rows already processed

---

## ⚠️ Notes
- Requires Chrome/Firefox browser + matching Selenium WebDriver installed.
- Only use automation on websites where it is **permitted** by Terms of Service.
- Always test with `--dry-run` before real submissions.

---

## 📜 License
Apache License 2.0
