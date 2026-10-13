"""Seams for later phases. Nothing here is wired to an API endpoint in v1.

* ``payslip``: PDF payslip -> suggested net pay (phase 2).
* ``bank_import``: bank statement rows -> deduplicated expense drafts (phase 2).
* ``assistant``: read-only finance snapshot for a local LLM via Ollama (phase 3).

Every integration ends in the existing services (``record_salary``,
``create_expense``), so all money rules keep living in one place.
"""
