import uuid

def generate_payment_reference(prefix="CHAP"):
    """
    Generate a unique payment reference.

    Args:
        prefix (str): Optional prefix to identify the payment system or app.

    Returns:
        str: A unique payment reference string.
    """
    
    
    unique_id = uuid.uuid4().hex[:12].upper() 
    return f"{prefix}-{unique_id}"