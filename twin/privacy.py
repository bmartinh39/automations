import re

PUBLIC_EMAIL = "borja@borjamartin.com"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[ .-]?)?(?:\d[ .()-]*){9,15}(?!\w)")


def public_reply(text, language):
    """Allow only the approved business email; suppress other contact details."""
    forbidden_email = any(match.group().lower() != PUBLIC_EMAIL for match in EMAIL.finditer(text))
    if forbidden_email or PHONE.search(text):
        email_link = f"[{PUBLIC_EMAIL}](mailto:{PUBLIC_EMAIL})"
        if language == "es":
            return f"Puedes escribir a Borja en {email_link} o contactar desde [su web](https://borjamartin.com/es/#contacto)."
        return f"You can email Borja at {email_link} or contact him through [his website](https://borjamartin.com/en/#contacto)."
    return text
