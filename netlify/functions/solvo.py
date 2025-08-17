from main import handler as mangum_handler

def handler(event, context):
    """Netlify function handler that forwards events to the Mangum wrapper in `main.py`.

    Netlify will call this function with the AWS Lambda-like event and context. We
    delegate to the `Mangum` handler created in `main.py`.
    """
    return mangum_handler(event, context)


