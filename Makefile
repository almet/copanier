serve:
	./venv/bin/copanier serve --reload
pserve:
	./venv/bin/gunicorn -k roll.worker.Worker copanier:app --bind 0.0.0.0:8000
