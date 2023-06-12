web: gunicorn app:app --worker-class eventlet -w 1
worker: python processing.py
worker: python assembler.py