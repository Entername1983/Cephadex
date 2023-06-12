web: gunicorn app:app --worker-class gevent -w 1
worker1: python processing.py
worker2: python assembler.py