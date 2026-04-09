"""Comprehensive verification of Reddit Lead Hunter integration."""
import json
import os
import subprocess
import sys
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

errors = []

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

def check(name, ok):
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}")
    if not ok:
        errors.append(name)

# 1. Backend imports
print("=== 1. Backend Module Imports ===")
try:
    from jarvis.social.models import Lead, LeadStatus, ScanResult, LeadStats
    from jarvis.social.store import LeadStore
    from jarvis.social.scanner import RedditScanner, ScanConfig
    from jarvis.social.reply import ReplyPoster, ReplyMode, ReplyResult
    from jarvis.social.service import RedditLeadService
    from jarvis.mcp.reddit_tools import register_reddit_tools
    check("All social modules importable", True)
except Exception as e:
    check(f"Import failed: {e}", False)

# 2. Config
print("\n=== 2. Config ===")
from jarvis.config import JarvisConfig
cfg = JarvisConfig()
for f in ["reddit_scan_enabled", "reddit_subreddits", "reddit_min_score",
          "reddit_product_name", "reddit_product_description", "reddit_reply_tone", "reddit_auto_post"]:
    check(f"social.{f}", hasattr(cfg.social, f))

# 3. Gateway wiring
print("\n=== 3. Gateway Wiring ===")
adv = read("src/jarvis/gateway/phases/advanced.py")
check("RedditLeadService in advanced.py", "RedditLeadService" in adv)
tools = read("src/jarvis/gateway/phases/tools.py")
check("register_reddit_tools in tools.py", "register_reddit_tools" in tools)
gw = read("src/jarvis/gateway/gateway.py")
check("reddit_lead_scan cron in gateway.py", "reddit_lead_scan" in gw)
routes = read("src/jarvis/channels/config_routes.py")
check("_register_social_routes", "_register_social_routes" in routes)
for ep in ["/api/v1/leads/scan", "/api/v1/leads/stats", "/api/v1/leads/{lead_id}", "/api/v1/leads/{lead_id}/reply"]:
    check(f"Endpoint {ep}", ep in routes)

# 4. Skill file
print("\n=== 4. Skill File ===")
skill = read("data/procedures/reddit-lead-hunter.md")
check("trigger_keywords", "trigger_keywords" in skill)
check("reddit_scan tool", "reddit_scan" in skill)
check("Asks for product", "Produkt" in skill or "product" in skill.lower())

# 5. Version
print("\n=== 5. Version ===")
with open("pyproject.toml", "rb") as f:
    ver = tomllib.load(f)["project"]["version"]
init = read("src/jarvis/__init__.py")
check(f"Version {ver} consistent", f'__version__ = "{ver}"' in init)

# 6. Flutter files
print("\n=== 6. Flutter Files ===")
for f in [
    "flutter_app/lib/providers/reddit_leads_provider.dart",
    "flutter_app/lib/screens/reddit_leads_screen.dart",
    "flutter_app/lib/widgets/leads/lead_card.dart",
    "flutter_app/lib/widgets/leads/lead_detail_sheet.dart",
    "flutter_app/lib/screens/config/social_page.dart",
]:
    check(f, os.path.exists(f))

# 7. Flutter wiring
print("\n=== 7. Flutter Wiring ===")
main_dart = read("flutter_app/lib/main.dart")
shell = read("flutter_app/lib/screens/main_shell.dart")
api = read("flutter_app/lib/services/api_client.dart")
check("RedditLeadsProvider in main.dart", "RedditLeadsProvider" in main_dart)
check("RedditLeadsScreen in main_shell", "RedditLeadsScreen" in shell)
check("7th NavItem (redditLeads)", "redditLeads" in shell)
check("Ctrl+7 shortcut", "digit7" in shell)
check("scanRedditLeads in api_client", "scanRedditLeads" in api)
check("getRedditLeads in api_client", "getRedditLeads" in api)
check("replyToRedditLead in api_client", "replyToRedditLead" in api)
check("SocialPage in config_screen", "SocialPage" in read("flutter_app/lib/screens/config_screen.dart"))
check("Social in search index", "Social Listening" in read("flutter_app/lib/widgets/global_search_dialog.dart"))

# 8. i18n
print("\n=== 8. i18n ===")
with open("flutter_app/lib/l10n/app_en.arb", encoding="utf-8") as f:
    en = json.load(f)
en_keys = {k for k in en if not k.startswith("@") and k != "@@locale"}
for lang in ["de", "zh", "ar"]:
    with open(f"flutter_app/lib/l10n/app_{lang}.arb", encoding="utf-8") as f:
        loc = json.load(f)
    loc_keys = {k for k in loc if not k.startswith("@") and k != "@@locale"}
    missing = en_keys - loc_keys
    check(f"{lang}: {len(loc_keys)} keys, {len(missing)} missing", len(missing) == 0)

for k in ["redditLeads", "noLeadsFound", "scanNow", "leadNew", "postReply", "copyReply", "socialListening"]:
    check(f"i18n key: {k}", k in en_keys)

# 9. Tests
print("\n=== 9. Test Files ===")
for f in ["tests/test_social/test_models.py", "tests/test_social/test_store.py",
          "tests/test_social/test_scanner.py", "tests/test_social/test_reply.py",
          "tests/test_social/test_service.py", "tests/test_mcp/test_reddit_tools.py"]:
    check(f, os.path.exists(f))

# 10. Git
print("\n=== 10. Git Status ===")
result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
uncommitted = [l for l in result.stdout.strip().split("\n") if l.strip()]
if uncommitted:
    print(f"[WARN] {len(uncommitted)} uncommitted changes:")
    for l in uncommitted[:10]:
        print(f"  {l}")
else:
    check("Working tree clean", True)

# Summary
print("\n" + "=" * 60)
if errors:
    print(f"FOUND {len(errors)} ISSUES:")
    for e in errors:
        print(f"  - {e}")
else:
    print("ALL CHECKS PASSED - ZERO ISSUES")
print("=" * 60)
