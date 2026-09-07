PYTHON := .venv/bin/python

.PHONY: check demo-data init-db backend frontend test frontend-install

check:
	env -u PYTHONPATH $(PYTHON) scripts/check_demo_setup.py

demo-data:
	env -u PYTHONPATH $(PYTHON) scripts/build_demo_dataset.py

init-db:
	env -u PYTHONPATH $(PYTHON) scripts/init_db.py

backend:
	env -u PYTHONPATH $(PYTHON) -m uvicorn customer_support_agent.api.main:app --app-dir src --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

frontend-install:
	cd frontend && npm ci

test:
	env -u PYTHONPATH $(PYTHON) -m pytest -q
	cd frontend && npm test
