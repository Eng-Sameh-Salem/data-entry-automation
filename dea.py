#!/usr/bin/env python3
import argparse, time, sys, re, csv
from pathlib import Path
import pandas as pd
import yaml
from dataclasses import dataclass
from typing import Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

@dataclass
class FieldRule:
    selector: str
    type: str = "input"  # input|select|checkbox
    required: bool = False
    default: Optional[str] = None
    validators: Optional[list] = None

def load_mapping(path: Path) -> Dict[str, Any]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["fields"] = {k: FieldRule(**v) for k, v in cfg["fields"].items()}
    return cfg

def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in [".xlsx", ".xlsm", ".xls"]:
        return pd.read_excel(path)
    return pd.read_csv(path)

def coerce_truthy(v) -> bool:
    return str(v).strip().lower() in {"1","true","yes","y","on","t"}

def validate_row(row: dict, fields: Dict[str, FieldRule]) -> Optional[str]:
    for col, rule in fields.items():
        val = row.get(col, None)
        if (val is None or (isinstance(val, float) and pd.isna(val)) or str(val) == "") and rule.required and rule.default is None:
            return f"Missing required field: {col}"
        if rule.validators:
            for vd in rule.validators:
                if vd.get("type") == "regex" and val is not None and str(val) != "":
                    if re.fullmatch(vd["pattern"], str(val)) is None:
                        return vd.get("message", f"Invalid value for {col}")
                if vd.get("type") == "enum" and val is not None:
                    if str(val) not in set(map(str, vd["values"])):
                        return vd.get("message", f"{col} must be one of {vd['values']}")
    return None

def set_field(driver, rule: FieldRule, value: Any):
    elem = driver.find_element(By.CSS_SELECTOR, rule.selector)
    t = rule.type
    if t == "input":
        elem.clear()
        if value is None: value = ""
        elem.send_keys(str(value))
    elif t == "select":
        Select(elem).select_by_value(str(value))
    elif t == "checkbox":
        should_check = coerce_truthy(value)
        if elem.is_selected() != should_check:
            elem.click()
    else:
        raise ValueError(f"Unsupported field type: {t}")

def launch_browser(browser: str, headless: bool):
    if browser.lower() == "firefox":
        from selenium.webdriver.firefox.options import Options
        opts = Options()
        if headless: opts.add_argument("-headless")
        return webdriver.Firefox(options=opts)
    # default chrome
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless: opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=opts)

def main():
    ap = argparse.ArgumentParser(description="Data Entry Automation Tool")
    ap.add_argument("--input", required=True, type=Path, help="CSV or Excel file")
    ap.add_argument("--map", required=True, type=Path, help="YAML mapping with selectors and rules")
    ap.add_argument("--out", type=Path, default=Path("results.csv"), help="Where to write results (CSV)")
    ap.add_argument("--start", type=int, default=1, help="Start row index (1-based, after header)")
    ap.add_argument("--end", type=int, help="End row index (inclusive)")
    ap.add_argument("--filter", type=str, help='Pandas query to filter rows, e.g. "country == \'US\'"')
    ap.add_argument("--headless", action="store_true", help="Run browser headless")
    ap.add_argument("--dry-run", action="store_true", help="Do not submit the form")
    ap.add_argument("--resume", action="store_true", help="Skip rows already present in results.csv")
    ap.add_argument("--timeout", type=int, default=15, help="Seconds to wait for page and success check")
    args = ap.parse_args()

    cfg = load_mapping(args.map)
    df = read_table(args.input)

    # Slice rows
    df = df.iloc[args.start-1 : args.end] if args.end else df.iloc[args.start-1 :]
    if args.filter:
        df = df.query(args.filter)

    processed = set()
    if args.resume and args.out.exists():
        with args.out.open("r", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for r in rdr:
                if r.get("status") == "success":
                    processed.add(int(r["row"]))
    # Prepare results writer
    write_header = not args.out.exists()
    out_f = args.out.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(out_f, fieldnames=["row","status","message"])
    if write_header:
        writer.writeheader()

    # Start browser
    try:
        driver = launch_browser(cfg.get("browser","chrome"), args.headless or cfg.get("headless", False))
    except WebDriverException as e:
        print("ERROR: Failed to start browser. Make sure the driver is available.\n", e, file=sys.stderr)
        return 2

    wait = WebDriverWait(driver, args.timeout)
    successes, fails = 0, 0

    try:
        for idx, row in df.reset_index(drop=True).iterrows():
            row_no = args.start + idx
            if row_no in processed:
                writer.writerow({"row": row_no, "status": "success", "message": "skipped (resume)"})
                continue

            row_dict = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in row.to_dict().items()}
            # Validate
            err = validate_row(row_dict, cfg["fields"])
            if err:
                writer.writerow({"row": row_no, "status": "failed", "message": err})
                fails += 1
                continue

            try:
                driver.get(cfg["url"])
                # Fill fields
                for col, rule in cfg["fields"].items():
                    val = row_dict.get(col, None)
                    if (val is None or val == "") and rule.default is not None:
                        val = rule.default
                    set_field(driver, rule, val)

                if not args.dry_run:
                    # Submit
                    driver.find_element(By.CSS_SELECTOR, cfg["submit_selector"]).click()
                    # Success condition
                    sc = cfg.get("success_check", {})
                    if sc:
                        if sc.get("selector"):
                            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, sc["selector"])))
                        if sc.get("text_contains"):
                            wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, sc["selector"]), sc["text_contains"]))
                writer.writerow({"row": row_no, "status": "success", "message": ""})
                successes += 1
            except (TimeoutException, NoSuchElementException) as e:
                writer.writerow({"row": row_no, "status": "failed", "message": f"form error: {e.__class__.__name__}"})
                fails += 1
            except Exception as e:
                writer.writerow({"row": row_no, "status": "failed", "message": str(e)})
                fails += 1

        print(f"Done. Success: {successes}, Failed: {fails}")
    finally:
        out_f.close()
        driver.quit()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
