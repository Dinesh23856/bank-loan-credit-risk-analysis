train:
	python -m src.train
api:
	python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
ui:
	cd frontend && npm run dev
build-ui:
	cd frontend && npm run build
test:
	PYTHONPATH=. pytest -q
