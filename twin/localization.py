COPY = {
    "en": {
        "title": "Digital Twin",
        "description": "Talk to my AI twin about my career",
        "back": "Back to website",
        "greeting": "Hi! I'm Borja's AI twin. Ask me about his experience, projects, and interests.",
        "placeholder": "Ask me about Borja...",
        "new_chat": "New conversation",
        "examples_label": "Try asking",
        "examples": [
            "Tell me about your background and experience.",
            "What kinds of projects are you working on now?",
            "What are your strongest technical skills?",
            "How can I get in touch with you?",
        ],
        "instruction": "Reply in English by default.",
        "incomplete": "I couldn't complete that reply. Please try again.",
        "failed": "I couldn't complete that request. Please try again.",
        "unavailable": "The twin is temporarily unavailable. Please try again later.",
    },
    "es": {
        "title": "Gemelo digital",
        "description": "Habla con mi gemelo digital sobre mi trayectoria",
        "back": "Volver a la web",
        "greeting": "¡Hola! Soy el gemelo digital de Borja. Puedes preguntarme sobre su experiencia, proyectos e intereses.",
        "placeholder": "Pregúntame sobre Borja...",
        "new_chat": "Nueva conversación",
        "examples_label": "Puedes preguntar",
        "examples": [
            "Cuéntame sobre tu trayectoria y experiencia.",
            "¿En qué proyectos estás trabajando ahora?",
            "¿Cuáles son tus principales habilidades técnicas?",
            "¿Cómo puedo contactar contigo?",
        ],
        "instruction": "Reply in Spanish by default.",
        "incomplete": "No he podido completar la respuesta. Inténtalo de nuevo.",
        "failed": "No he podido completar esa solicitud. Inténtalo de nuevo.",
        "unavailable": "El gemelo digital no está disponible temporalmente. Inténtalo más tarde.",
    },
}

SPANISH_ERRORS = {
    "Please enter a message.": "Escribe un mensaje.",
    "Please keep your message under 2,000 characters.": "Limita tu mensaje a 2.000 caracteres.",
    "Please start a new conversation to continue.": "Inicia una nueva conversación para continuar.",
    "Only text messages are supported.": "Solo se admiten mensajes de texto.",
    "Too many requests. Please try again later.": "Has enviado demasiados mensajes. Inténtalo de nuevo más tarde.",
    "The twin has reached today's usage limit. Please try again tomorrow.": "El gemelo digital ha alcanzado el límite de uso de hoy. Inténtalo de nuevo mañana.",
}


def normalize_language(language):
    if isinstance(language, str) and language.lower() in COPY:
        return language.lower()
    return "en"


def language_from_request(request):
    params = getattr(request, "query_params", None)
    return normalize_language(params.get("lang") if params is not None else None)


def initial_history(language):
    return [{"role": "assistant", "content": COPY[normalize_language(language)]["greeting"]}]


def language_instruction(language):
    return (
        COPY[normalize_language(language)]["instruction"]
        + " If the visitor explicitly asks to switch language, honor that request and continue "
        "in that language until asked otherwise. The opening assistant message already identifies "
        "you as Borja's AI twin; do not repeat the introduction in every reply."
    )


def error_text(message, language):
    if normalize_language(language) == "es":
        return SPANISH_ERRORS.get(message, COPY["es"]["unavailable"])
    return message
