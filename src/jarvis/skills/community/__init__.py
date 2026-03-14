"""Community Skill Marketplace — architektonisch malware-sicher.

Skills sind Daten (Markdown + YAML), kein Code.  Die Sicherheitskette:

  1. Skill = Markdown + YAML-Frontmatter (kein import, kein eval)
  2. Planner liest den Skill und erzeugt PlannedAction-Objekte
  3. ToolEnforcer prüft: nur in tools_required deklarierte Tools erlaubt
  4. Gatekeeper prüft: Standard-Evaluation (Pfade, Patterns, Risk)
  5. Executor führt nur genehmigte Actions aus

Bible reference: §6.2 (Prozedurale Skills), §11 (Security)
"""

from jarvis.skills.community.client import CommunityRegistryClient, InstallResult, RegistryEntry
from jarvis.skills.community.publisher import PublisherIdentity, PublisherVerifier, TrustLevel
from jarvis.skills.community.sync import RegistrySync, SyncResult
from jarvis.skills.community.tool_enforcer import ToolEnforcementResult, ToolEnforcer
from jarvis.skills.community.validator import CheckResult, SkillValidator, ValidationResult

__all__ = [
    "CheckResult",
    # client
    "CommunityRegistryClient",
    "InstallResult",
    # publisher
    "PublisherIdentity",
    "PublisherVerifier",
    "RegistryEntry",
    # sync
    "RegistrySync",
    # validator
    "SkillValidator",
    "SyncResult",
    "ToolEnforcementResult",
    # tool_enforcer
    "ToolEnforcer",
    "TrustLevel",
    "ValidationResult",
]
