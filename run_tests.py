"""
BlogPilot — Master Test Runner

Runs all test suites, reports results, and checks key configurations.
Usage:
    python run_tests.py          # Run all tests
    python run_tests.py --quick  # Run only fast unit tests (skip e2e)
    python run_tests.py --check  # Only check configuration (no tests)
"""
import os
import sys
import subprocess
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def banner(text):
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


def check_pass(label, ok, detail=""):
    status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    print(f"  [{status}] {label}")
    if detail and not ok:
        print(f"         {YELLOW}{detail}{RESET}")
    return ok


# ── Configuration Checks ────────────────────────────────────────────────

def check_config():
    banner("Configuration & Credentials Check")
    all_ok = True

    # 1. settings.yaml exists
    settings_path = PROJECT_ROOT / "config" / "settings.yaml"
    all_ok &= check_pass("config/settings.yaml exists", settings_path.exists())

    # 2. Encryption key
    key_file = PROJECT_ROOT / "config" / ".secrets.key"
    all_ok &= check_pass("Encryption key (config/.secrets.key)", key_file.exists(),
                         "Run: python -m backend.utils.setup_credentials")

    # 3. Encryption salt
    salt_file = PROJECT_ROOT / "config" / ".secrets.salt"
    all_ok &= check_pass("Encryption salt (config/.secrets.salt)", salt_file.exists(),
                         "Auto-generated on first encrypt() call")

    # 4. LinkedIn credentials
    linkedin_creds = PROJECT_ROOT / "config" / ".secrets" / "linkedin.json"
    all_ok &= check_pass("LinkedIn credentials (config/.secrets/linkedin.json)", linkedin_creds.exists(),
                         "Run: python -m backend.utils.setup_credentials")

    if linkedin_creds.exists():
        try:
            with open(linkedin_creds) as f:
                data = json.load(f)
            has_email = "email" in data and len(data["email"]) > 10
            has_pass = "password" in data and len(data["password"]) > 10
            all_ok &= check_pass("  LinkedIn email (encrypted)", has_email, "Email field missing or too short")
            all_ok &= check_pass("  LinkedIn password (encrypted)", has_pass, "Password field missing or too short")
        except Exception as e:
            all_ok &= check_pass("  LinkedIn creds readable", False, str(e))

    # 5. Groq API key
    groq_env = os.environ.get("GROQ_API_KEY", "")
    groq_file = PROJECT_ROOT / "config" / ".secrets" / "groq.json"
    groq_ok = bool(groq_env) or groq_file.exists()
    source = "env var" if groq_env else ("groq.json" if groq_file.exists() else "NOT FOUND")
    all_ok &= check_pass(f"Groq API key (source: {source})", groq_ok,
                         "Set GROQ_API_KEY env var or create config/.secrets/groq.json with {\"api_key\": \"...\"}")

    # 6. Hunter.io (optional)
    hunter_file = PROJECT_ROOT / "config" / ".secrets" / "hunter.json"
    check_pass(f"Hunter.io API key (optional)", hunter_file.exists(),
               "Not required — pattern generator + SMTP verifier work without it")

    # 7. Encryption roundtrip test
    try:
        from backend.utils.encryption import encrypt, decrypt
        test_val = "test_roundtrip_12345"
        encrypted = encrypt(test_val)
        decrypted = decrypt(encrypted)
        all_ok &= check_pass("Encryption roundtrip", decrypted == test_val,
                             f"Expected '{test_val}', got '{decrypted}'")
    except Exception as e:
        all_ok &= check_pass("Encryption roundtrip", False, str(e))

    # 8. LinkedIn credential decryption test
    if linkedin_creds.exists():
        try:
            from backend.automation.linkedin_login import load_credentials
            email, password = load_credentials()
            all_ok &= check_pass("LinkedIn credential decryption", bool(email) and bool(password),
                                 "Decrypted but got empty values")
            # Show masked email for confirmation
            if email:
                masked = email[:3] + "***" + email[email.index("@"):] if "@" in email else email[:3] + "***"
                print(f"         {CYAN}Email: {masked}{RESET}")
        except Exception as e:
            all_ok &= check_pass("LinkedIn credential decryption", False, str(e))

    # 9. Config loader
    try:
        from backend.utils.config_loader import load_config, get
        load_config()
        engine_enabled = get("engine.enabled")
        all_ok &= check_pass("Config loader (engine.enabled)", engine_enabled is not None,
                             "settings.yaml not loading properly")
    except Exception as e:
        all_ok &= check_pass("Config loader", False, str(e))

    # 10. Database init
    try:
        from backend.storage.database import init_db, get_db
        init_db()
        with get_db() as db:
            from backend.storage.models import Budget
            budgets = db.query(Budget).all()
        all_ok &= check_pass("Database init + budget seed", len(budgets) > 0,
                             f"Expected budget rows, got {len(budgets)}")
    except Exception as e:
        all_ok &= check_pass("Database init", False, str(e))

    return all_ok


# ── Test Runner ──────────────────────────────────────────────────────────

def run_pytest(test_files, label):
    banner(f"Running: {label}")
    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + test_files
    print(f"  Command: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode == 0


def run_all_tests(quick=False):
    results = {}

    # Unit tests (always run)
    unit_tests = [
        ("Utils (encryption, lock file)", ["tests/test_utils.py"]),
        ("Storage (DB, posts, budget, leads)", ["tests/test_storage.py"]),
        ("Feed Scanner", ["tests/test_feed_scanner.py"]),
        ("AI Client", ["tests/test_ai_client.py"]),
        ("Enrichment", ["tests/test_enrichment.py"]),
        ("Campaigns", ["tests/test_campaigns.py"]),
    ]

    for label, files in unit_tests:
        existing = [f for f in files if (PROJECT_ROOT / f).exists()]
        if existing:
            results[label] = run_pytest(existing, label)
        else:
            print(f"\n  {YELLOW}SKIP: {label} — test file not found{RESET}")
            results[label] = None

    # E2E tests (skip in quick mode)
    if not quick:
        e2e_tests = [
            ("E2E Pipeline + Budget Safety", ["tests/test_e2e.py"]),
        ]
        for label, files in e2e_tests:
            existing = [f for f in files if (PROJECT_ROOT / f).exists()]
            if existing:
                results[label] = run_pytest(existing, label)
            else:
                results[label] = None
    else:
        print(f"\n  {YELLOW}SKIP: E2E tests (--quick mode){RESET}")

    return results


# ── Summary ──────────────────────────────────────────────────────────────

def print_summary(config_ok, test_results):
    banner("Test Summary")

    print(f"  Configuration: {'  ' + GREEN + 'ALL PASS' + RESET if config_ok else '  ' + RED + 'ISSUES FOUND' + RESET}")
    print()

    total = passed = failed = skipped = 0
    for label, result in test_results.items():
        total += 1
        if result is True:
            passed += 1
            status = f"{GREEN}PASS{RESET}"
        elif result is False:
            failed += 1
            status = f"{RED}FAIL{RESET}"
        else:
            skipped += 1
            status = f"{YELLOW}SKIP{RESET}"
        print(f"  [{status}] {label}")

    print(f"\n  {BOLD}Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}{RESET}")

    if failed > 0 or not config_ok:
        print(f"\n  {RED}{BOLD}Some checks failed. Review output above for details.{RESET}")
        return 1
    else:
        print(f"\n  {GREEN}{BOLD}All checks passed!{RESET}")
        return 0


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BlogPilot Test Runner")
    parser.add_argument("--quick", action="store_true", help="Skip E2E tests")
    parser.add_argument("--check", action="store_true", help="Only check configuration")
    args = parser.parse_args()

    banner("BlogPilot — Master Test Runner")

    # Always check config
    config_ok = check_config()

    if args.check:
        sys.exit(0 if config_ok else 1)

    # Run tests
    test_results = run_all_tests(quick=args.quick)

    # Summary
    exit_code = print_summary(config_ok, test_results)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
