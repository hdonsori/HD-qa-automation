def validate_status(response):

    assert 200 <= response.status < 300, \
        f"Unexpected status code: {response.status}"