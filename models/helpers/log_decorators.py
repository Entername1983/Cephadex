
import functools
import logging
# import time

logger = logging.getLogger('flask_app')
job_logger = logging.getLogger('job_processing')


def log_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # start_time = time.time()
        try:
            logger.info(f"Entering function {f.__name__}")
            result = f(*args, **kwargs)
            logger.info(f"Exiting function {f.__name__}")
            return result
        except Exception as e:
            logger.error(f"Exception occurred in function {f.__name__}", exc_info=True)
            raise e
        # finally:
        #     elapsed_time = time.time() - start_time
        #     logger.info(f"Function {f.__name__} took {elapsed_time:.4f} seconds")
    return wrapper



def job_log_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        # start_time = time.time()
        try:
            job_logger.info(f"Entering function {f.__name__}")
            result = f(*args, **kwargs)
            job_logger.info(f"Exiting function {f.__name__}")
            return result
        except Exception as e:
            job_logger.error(f"Exception occurred in function {f.__name__}", exc_info=True)
            raise e
        # finally:
        #     elapsed_time = time.time() - start_time
        #     job_logger.info(f"Function {f.__name__} took {elapsed_time:.4f} seconds")
    return wrapper