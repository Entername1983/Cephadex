web: gunicorn app:app --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1
worker1: python job_processing.py
