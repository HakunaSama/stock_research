"""Production web application layer for the stock-research agent.

This package turns the dependency-light research engine (``stock_agent``) into a
deployable website:

    db.py      — stdlib sqlite3 data layer (users / sessions / research_jobs /
                 credits / orders / ledger)
    auth.py    — registration, login, HTTP-only cookie sessions, route guards
    billing.py — credit plans, research pricing, pluggable payment provider (stub)
    jobs.py    — background worker queue for user-initiated ODR research runs,
                 with free-daily-quota-then-credits charging + auto-refund
    admin.py   — admin-only management API (users, balances, orders, ledger)
    app.py     — FastAPI application wiring all of the above together

It deliberately keeps the ODR engine untouched — the webapp only *drives* it.
"""
