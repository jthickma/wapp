import os
from redis import Redis
from rq import Worker, Connection, Queue
from config import REDIS_URL

listen = ['downloads'] # Listen to the 'downloads' queue, same as in app.py

if __name__ == '__main__':
    redis_conn = Redis.from_url(REDIS_URL)
    with Connection(redis_conn):
        worker = Worker(map(Queue, listen))
        print(f"RQ Worker started, listening on queues: {', '.join(listen)}")
        worker.work(with_scheduler=False) # Set with_scheduler=True if using RQ Scheduler
        