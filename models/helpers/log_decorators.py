
import functools
import logging
import time
import os

LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
logger = logging.getLogger('flask_app')
job_logger = logging.getLogger('job_processing')
subrollover_logger = logging.getLogger('subrollover')
## TO DO implement special logger for stripe payments
DEBUG_ARG_LENGTH = os.environ.get("DEBUG_ARG_LENGTH", 50)


logger.setLevel(logging.INFO)
def log_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            truncated_args = [
                f'{str(arg)[:DEBUG_ARG_LENGTH]}...' if len(str(arg)) > DEBUG_ARG_LENGTH else arg
                for arg in args
            ]
            truncated_kwargs = {
                k: f'{str(v)[:DEBUG_ARG_LENGTH]}...' if len(str(v)) > DEBUG_ARG_LENGTH else v
                for k, v in kwargs.items()
            }
            logger.info(f"Entering function {f.__name__} with args: {truncated_args} and kwargs: {truncated_kwargs}")
            result = f(*args, **kwargs)
            truncated_result = (
                f'{str(result)[:DEBUG_ARG_LENGTH]}...' if len(str(result)) > DEBUG_ARG_LENGTH else result
            )
            logger.info(f"Exiting function {f.__name__} with result: {truncated_result}")
            return result
        except Exception as e:
            extra_info = kwargs.get('extra_info', 'No extra info provided.')
            logger.error(f"Exception occurred in function {f.__name__}. Extra info: {extra_info}", exc_info=True)
            raise e
        finally:
            elapsed_time = time.time() - start_time
            logger.info(f"Function {f.__name__} took {elapsed_time:.4f} seconds")
    return wrapper


def job_log_decorator(f):
    @functools.wraps(f)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            truncated_args = [
                f'{str(arg)[:DEBUG_ARG_LENGTH]}...' if len(str(arg)) > DEBUG_ARG_LENGTH else arg
                for arg in args
            ]
            truncated_kwargs = {
                k: f'{str(v)[:DEBUG_ARG_LENGTH]}...' if len(str(v)) > DEBUG_ARG_LENGTH else v
                for k, v in kwargs.items()
            }
            job_logger.info(f"Entering function {f.__name__} with args: {truncated_args} and kwargs: {truncated_kwargs}")
            result = await f(*args, **kwargs)
            truncated_result = (
                f'{str(result)[:DEBUG_ARG_LENGTH]}...' if len(str(result)) > DEBUG_ARG_LENGTH else result
            )
            job_logger.info(f"Exiting function {f.__name__} with result: {truncated_result}")
            return result
        except Exception as e:
            extra_info = kwargs.get('extra_info', 'No extra info provided.')
            job_logger.error(f"Exception occurred in function {f.__name__}. Extra info: {extra_info}", exc_info=True)
            raise e
        finally:
            elapsed_time = time.time() - start_time
            job_logger.info(f"Function {f.__name__} took {elapsed_time:.4f} seconds")
    return wrapper


def subrollover_log_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            truncated_args = [
                f'{str(arg)[:DEBUG_ARG_LENGTH]}...' if len(str(arg)) > DEBUG_ARG_LENGTH else arg
                for arg in args
            ]
            truncated_kwargs = {
                k: f'{str(v)[:DEBUG_ARG_LENGTH]}...' if len(str(v)) > DEBUG_ARG_LENGTH else v
                for k, v in kwargs.items()
            }
            subrollover_logger.info(f"Entering function {f.__name__} with args: {truncated_args} and kwargs: {truncated_kwargs}")
            result = f(*args, **kwargs)
            truncated_result = (
                f'{str(result)[:DEBUG_ARG_LENGTH]}...' if len(str(result)) > DEBUG_ARG_LENGTH else result
            )
            subrollover_logger.info(f"Exiting function {f.__name__} with result: {truncated_result}")
            return result
        except Exception as e:
            extra_info = kwargs.get('extra_info', 'No extra info provided.')
            subrollover_logger.error(f"Exception occurred in function {f.__name__}. Extra info: {extra_info}", exc_info=True)
            raise e
        finally:
            elapsed_time = time.time() - start_time
            subrollover_logger.info(f"Function {f.__name__} took {elapsed_time:.4f} seconds")
    return wrapper