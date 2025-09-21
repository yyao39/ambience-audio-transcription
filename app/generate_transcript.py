import functions_framework

@functions_framework.http
def generate_transcript(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)

    if not request_json:
        print("request json is empty")
        return "request json is empty"

    name = "world"
    
    return 'Hello {}!'.format(name)
