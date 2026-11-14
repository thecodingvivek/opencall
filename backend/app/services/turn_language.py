"""Per-call language hints derived from final speech transcripts."""
import re

LANGUAGES = {
    'en-IN': ('English', 'english', 'अंग्रेजी', 'अंग्रेज़ी'),
    'hi-IN': ('Hindi', 'hindi', 'हिन्दी', 'हिंदी'),
    'te-IN': ('Telugu', 'telugu', 'తెలుగు'),
    'ta-IN': ('Tamil', 'tamil', 'தமிழ்'),
    'kn-IN': ('Kannada', 'kannada', 'ಕನ್ನಡ'),
    'ml-IN': ('Malayalam', 'malayalam', 'മലയാളം'),
    'mr-IN': ('Marathi', 'marathi', 'मराठी'),
    'pa-IN': ('Punjabi', 'punjabi', 'ਪੰਜਾਬੀ'),
    'bn-IN': ('Bengali', 'bengali', 'বাংলা'),
    'gu-IN': ('Gujarati', 'gujarati', 'ગુજરાતી'),
}


def supported_language(value):
    return value if isinstance(value, str) and value in LANGUAGES else None


def requested_language(text):
    """Recognize a request to change language, not mentions of places or crops."""
    text = text.casefold().strip()
    if not text:
        return None
    # Require an imperative or polite request and a language next to the action.
    lead = r"(?:^|[.!?।]\s*)(?:please\s+|(?:can|could|would) you\s+)?"
    verb = r"(?:speak|reply|respond|answer|talk|say|bol|bolo|boliye)"
    for code, names in LANGUAGES.items():
        for name in names[1:]:
            language = re.escape(name.casefold())
            english_request = lead + verb + r"\s+(?:to me\s+)?(?:in\s+)?" + language + r"(?![\w])"
            hindi_request = language + r"\s*(?:में|me|mein)\s*(?:बोल(?:ो|िए|ें)?|बात|जवाब|उत्तर|bol(?:o|iye)?|baat)"
            telugu_request = language + r"\s*(?:లో|lo)\s*(?:మాట్లాడు|మాట్లాడండి|చెప్పండి|matladu|matladandi)"
            if re.search(english_request, text) or re.search(hindi_request, text) or re.search(telugu_request, text):
                return code
    return None


class TurnLanguage:
    def __init__(self):
        self.pending = None
        self.current = None
        self.preferred = None
        self.pending_text = None

    def on_transcript(self, event):
        if event.is_final and event.transcript:
            self.pending = supported_language(event.language)
            self.pending_text = event.transcript.strip()

    def complete_turn(self, text):
        text = text or ''
        detected = self.pending if self.pending_text and self.pending_text in text else None
        requested = requested_language(text)
        if requested:
            self.preferred = requested
        self.current = self.preferred or detected
        self.pending = None
        self.pending_text = None
        return self.current
