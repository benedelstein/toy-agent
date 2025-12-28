def greet(name):
    """A simple greeting function"""
    import logging
    logging.info(f"Greeting {name}")
    message = f"Hello, {name}!"
    print(message)
    return message

def calculate_sum(a, b):
    """Calculate the sum of two numbers"""
    # Added input validation
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        raise TypeError("Both arguments must be numbers")
    result = a + b
    return result

if __name__ == "__main__":
    greet("User")
    print(calculate_sum(5, 3))
