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
    # Only apply an explicit override when the caller asks to speak/reply in a
    # named language; a passing mention of a language should not change TTS.
    text = text.casefold()
    request = re.search(r'\b(speak|reply|respond|answer|talk|say|bol|bolo|baat|mein|me|in)\b|बोल|बात|जवाब|उत्तर|में', text)
    if not request:
        return None
    matches = [code for code, names in LANGUAGES.items() if any(
        re.search(r'(?<!\w)' + re.escape(name.casefold()) + r'(?!\w)', text) for name in names[1:]
    )]
    return matches[0] if len(matches) == 1 else None


class TurnLanguage:
    def __init__(self):
        self.pending = None
        self.current = None
        self.pending_text = None

    def on_transcript(self, event):
        if event.is_final and event.transcript:
            self.pending = supported_language(event.language)
            self.pending_text = event.transcript.strip()

    def complete_turn(self, text):
        text = text or ''
        detected = self.pending if self.pending_text and self.pending_text in text else None
        self.current = requested_language(text) or detected
        self.pending = None
        self.pending_text = None
        return self.current
