# dev_tools/

These scripts are **development and debugging utilities** — they are NOT part of:
- The production application
- The CI/CD pipeline (Jenkinsfile)
- The Django application (INSTALLED_APPS)

They can be run manually by developers for diagnostics:

| Script | Purpose |
|--------|---------|
| debug_*.py | Runtime debugging helpers |
| audit_*.py | One-time database audit scripts |
| check_*.py | Environment/configuration checks |
| fix_all.py | One-time data fix script |
| inspect_admin.py | Admin site inspection |
| mlops_audit.py | MLOps data integrity check |
| verify_api_contracts.py | API contract verification |

They are excluded from SonarQube analysis (see sonar-project.properties).
