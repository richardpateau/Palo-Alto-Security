import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "reports" / "security_rules.json"
OUTPUT_FILE = PROJECT_ROOT / "reports" / "security_audit.csv"


def load_security_rules():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def audit_rule(rule_name, rule):
    findings = []

    if rule.get("disabled", False):
        return findings

    if rule.get("action", "").lower() != "allow":
        return findings

    if "any" in rule.get("source_addresses", []):
        findings.append({
            "rule": rule_name,
            "severity": "Medium",
            "finding": "Source Address is too Broad (Any)",
            "recommendation": "Restrict the source to approved addresses (Please be more specific)"
        })
    if "any" in rule.get("destination_addresses", []):
        findings.append({
            "rule": rule_name,
            "severity": "Medium",
            "finding": "Destination Address is too Broad (Any)",
            "recommendation": "Restrict the Destination to approved addresses (Please be more speicifc)"
        })
    if "any" in rule.get("applications", []):
        findings.append({
            "rule": rule_name,
            "severity": "High",
            "finding": "Application Rule is too Broad (Any)",
            "recommendation": "Restrict to Only Approved Applications (Please be more speicifc)"
        })
    if "any" in rule.get("services", []):
        findings.append({
            "rule": rule_name,
            "severity": "High",
            "finding": "Service Rule is too Broad (Any)",
            "recommendation": "Restrict to Only Approved Services (Please be more speicifc)"
        })
    if not rule.get("log_end", False):
        findings.append({
            "rule": rule_name,
            "severity": "Medium",
            "finding": "Session-end logging is disabled",
            "recommendation": "Enable logging at session end where appropriate."
        })


    security_profiles = [
        "virus",
        "spyware",
        "vulnerability",
        "wildfire_analysis",
        "url_filtering",
        "file_blocking",
        "data_filtering"
    ]

    assigned_profiles = [
        rule.get(p, "")
        for p in security_profiles
        if rule.get(p, "")
    ]

    if not assigned_profiles:
        findings.append({
            "rule": rule_name,
            "severity": "Medium",
            "finding": "No Security Profile Assigned",
            "recommendation": "Review whether a Profile should be assigned please."
        })
    return findings


def main():
    rules = load_security_rules()
    all_findings = []

    print(
        f"---- Loaded {len(rules)} Security Rules ----"
    )

    for rule_name, rule_list in rules.items():
        rule = rule_list[0]
        findings = audit_rule(rule_name, rule)
        all_findings.extend(findings)

    field_names = [
        "rule",
        "severity",
        "finding",
        "recommendation"
    ]

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        write = csv.DictWriter(f, fieldnames=field_names)
        write.writeheader()
        write.writerows(all_findings)

    print(
        f"*** Audited {len(rules)} Security Rules ***"
    )
    print(
        f"*** Total Findings: {len(all_findings)} ***"
    )
    print(
        f"*** Report Saved to {OUTPUT_FILE} ***"
    )


if __name__=="__main__":
    main()
