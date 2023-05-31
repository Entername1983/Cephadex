
from functools import wraps
   
  

def exception(logger):
      
    # logger is the logging object
    # exception is the decorator objects 
    # that logs every exception into log file
    def decorator(func):
          
        @wraps(func)
        def wrapper(*args, **kwargs):
              
            try:
                return func(*args, **kwargs)
              
            except Exception:
                issue = f"exception in {func.__name__}" + "\n"
                issue = issue+"-------------------------\
                ------------------------------------------------\n"
                logger.exception(issue)
            raise
               
          
        return wrapper
    return decorator