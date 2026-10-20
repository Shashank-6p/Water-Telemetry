install:
	pip install -r requirements.txt

pipeline:
	python -m src.run_pipeline

test:
	pytest -q

app:
	streamlit run app/streamlit_app.py
