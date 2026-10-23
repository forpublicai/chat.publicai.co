#!/usr/bin/env python3
"""
Lago Catalog Syncer
Reads a YAML catalog definition (plans, billable metrics, and model pricing filters)
and idempotently updates the Lago API.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import yaml

def make_request(url, method="GET", payload=None, api_key=None):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"[ERROR] HTTP {e.code} for {method} {url}: {err_body}", file=sys.stderr)
        raise

def fetch_all_paginated(url, item_key, api_key, per_page=100):
    """
    Fetches all items from a paginated Lago endpoint across all pages.
    """
    items = []
    page = 1
    while True:
        separator = "&" if "?" in url else "?"
        paged_url = f"{url}{separator}page={page}&per_page={per_page}"
        resp = make_request(paged_url, api_key=api_key)
        batch = resp.get(item_key, [])
        items.extend(batch)
        
        meta = resp.get("meta", {})
        next_page = meta.get("next_page")
        if next_page:
            page = next_page
        elif len(batch) == per_page:
            page += 1
        else:
            break
            
    return items

def sync_billable_metrics(lago_base_url, api_key, metric_defs):
    print("=== Syncing Billable Metrics ===")
    existing_metrics = fetch_all_paginated(f"{lago_base_url}/api/v1/billable_metrics", "billable_metrics", api_key=api_key)
    existing_by_code = {m["code"]: m for m in existing_metrics}
    
    synced_metrics = {}
    for m in metric_defs:
        code = m["code"]
        payload = {
            "billable_metric": {
                "name": m.get("name", code),
                "code": code,
                "description": m.get("description", ""),
                "aggregation_type": m.get("aggregation_type", "sum_agg"),
                "field_name": m.get("field_name", "tokens"),
                "recurring": m.get("recurring", False),
                "filters": m.get("filters", [])
            }
        }
        
        if code in existing_by_code:
            print(f"Updating billable metric: {code}")
            resp = make_request(f"{lago_base_url}/api/v1/billable_metrics/{code}", method="PUT", payload=payload, api_key=api_key)
            synced_metrics[code] = resp["billable_metric"]
        else:
            print(f"Creating billable metric: {code}")
            resp = make_request(f"{lago_base_url}/api/v1/billable_metrics", method="POST", payload=payload, api_key=api_key)
            synced_metrics[code] = resp["billable_metric"]
            
    return synced_metrics

def sync_plans(lago_base_url, api_key, plan_defs, synced_metrics):
    print("\n=== Syncing Plans & Charges ===")
    existing_plans = fetch_all_paginated(f"{lago_base_url}/api/v1/plans", "plans", api_key=api_key)
    existing_by_code = {p["code"]: p for p in existing_plans}
    
    for p in plan_defs:
        code = p["code"]
        existing_plan_data = None
        if code in existing_by_code:
            existing_plan_data = make_request(f"{lago_base_url}/api/v1/plans/{code}", api_key=api_key).get("plan", {})
            
        existing_charges_by_metric = {}
        if existing_plan_data:
            for ch in existing_plan_data.get("charges", []):
                metric_code = ch.get("billable_metric_code")
                existing_charges_by_metric[metric_code] = ch
                
        # Build charges payload
        charges_payload = []
        for ch in p.get("charges", []):
            m_code = ch["billable_metric_code"]
            m_id = synced_metrics[m_code]["lago_id"]
            
            charge_dict = {
                "billable_metric_id": m_id,
                "charge_model": ch.get("charge_model", "package"),
                "pay_in_advance": ch.get("pay_in_advance", True),
                "properties": {
                    "amount": str(ch["properties"]["amount"]),
                    "free_units": int(ch["properties"].get("free_units", 0)),
                    "package_size": int(ch["properties"].get("package_size", 1000))
                }
            }
            
            # If the charge already exists on the plan, preserve its ID
            if m_code in existing_charges_by_metric:
                charge_dict["id"] = existing_charges_by_metric[m_code]["lago_id"]
                
            # Build filters
            filters_list = []
            for f in ch.get("filters", []):
                filters_list.append({
                    "invoice_display_name": f.get("invoice_display_name"),
                    "properties": {
                        "amount": str(f["amount"]),
                        "free_units": int(f.get("free_units", 0)),
                        "package_size": int(f.get("package_size", 1000))
                    },
                    "values": {
                        "model": [f["model"]],
                        "type": [f["type"]]
                    }
                })
            charge_dict["filters"] = filters_list
            charges_payload.append(charge_dict)
            
        plan_body = {
            "plan": {
                "name": p.get("name", code),
                "code": code,
                "interval": p.get("interval", "monthly"),
                "pay_in_advance": p.get("pay_in_advance", True),
                "amount_cents": int(p.get("amount_cents", 0)),
                "amount_currency": p.get("amount_currency", "USD"),
                "charges": charges_payload
            }
        }
        
        if existing_plan_data:
            print(f"Updating plan: {code} (charges: {len(charges_payload)}, filters: {sum(len(c.get('filters', [])) for c in charges_payload)})")
            make_request(f"{lago_base_url}/api/v1/plans/{code}", method="PUT", payload=plan_body, api_key=api_key)
        else:
            print(f"Creating plan: {code}")
            make_request(f"{lago_base_url}/api/v1/plans", method="POST", payload=plan_body, api_key=api_key)
            
    print("\nCatalog sync completed successfully!")

def main():
    config_path = os.getenv("LAGO_CATALOG_CONFIG", "/config/catalog.yaml")
    lago_url = os.getenv("LAGO_API_URL", "http://platform-api-svc:3000").rstrip("/")
    api_key = os.getenv("LAGO_API_KEY")
    
    if not api_key:
        print("[ERROR] LAGO_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(config_path):
        print(f"[ERROR] Catalog configuration file not found at: {config_path}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loading catalog configuration from: {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
        
    metrics = config.get("billable_metrics", [])
    plans = config.get("plans", [])
    
    synced_metrics = sync_billable_metrics(lago_url, api_key, metrics)
    sync_plans(lago_url, api_key, plans, synced_metrics)

if __name__ == "__main__":
    main()
