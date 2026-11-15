"""Fixed lines the agent speaks when it cannot rely on the LLM.

These are used when a reply fails, a provider is down, or the call hits its time
limit, so they must not depend on the LLM. Have a native speaker review each
language before relying on them in production.
"""
from typing import Literal

MessageKey = Literal["repeat", "trouble", "time_warning", "time_goodbye"]

MESSAGES: dict[str, dict[MessageKey, str]] = {
    "en-IN": {
        "repeat": "Sorry, I had a small problem. Could you please say that again?",
        "trouble": "Sorry, I'm having technical trouble right now. Please call again in a little while.",
        "time_warning": "We have about thirty seconds left in this call.",
        "time_goodbye": "Our time for this call is up. Thank you for calling, please call again anytime.",
    },
    "hi-IN": {
        "repeat": "माफ़ कीजिए, थोड़ी दिक्कत हुई। क्या आप फिर से बता सकते हैं?",
        "trouble": "माफ़ कीजिए, अभी तकनीकी समस्या आ रही है। कृपया थोड़ी देर बाद फिर से कॉल करें।",
        "time_warning": "इस कॉल में लगभग तीस सेकंड बचे हैं।",
        "time_goodbye": "इस कॉल का समय पूरा हो गया है। कॉल करने के लिए धन्यवाद, आप कभी भी फिर से कॉल कर सकते हैं।",
    },
    "te-IN": {
        "repeat": "క్షమించండి, చిన్న సమస్య వచ్చింది. దయచేసి మళ్ళీ చెప్పగలరా?",
        "trouble": "క్షమించండి, ప్రస్తుతం సాంకేతిక సమస్య ఉంది. దయచేసి కొంతసేపటి తర్వాత మళ్ళీ కాల్ చేయండి.",
        "time_warning": "ఈ కాల్‌లో సుమారు ముప్పై సెకన్లు మాత్రమే మిగిలి ఉన్నాయి.",
        "time_goodbye": "ఈ కాల్ సమయం ముగిసింది. కాల్ చేసినందుకు ధన్యవాదాలు, ఎప్పుడైనా మళ్ళీ కాల్ చేయండి.",
    },
    "ta-IN": {
        "repeat": "மன்னிக்கவும், ஒரு சிறிய பிரச்சனை ஏற்பட்டது. தயவுசெய்து மீண்டும் சொல்ல முடியுமா?",
        "trouble": "மன்னிக்கவும், இப்போது தொழில்நுட்பப் பிரச்சனை உள்ளது. சிறிது நேரம் கழித்து மீண்டும் அழைக்கவும்.",
        "time_warning": "இந்த அழைப்பில் சுமார் முப்பது வினாடிகள் மட்டுமே உள்ளன.",
        "time_goodbye": "இந்த அழைப்பின் நேரம் முடிந்தது. அழைத்ததற்கு நன்றி, எப்போது வேண்டுமானாலும் மீண்டும் அழைக்கவும்.",
    },
    "kn-IN": {
        "repeat": "ಕ್ಷಮಿಸಿ, ಸಣ್ಣ ತೊಂದರೆ ಆಯಿತು. ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳುತ್ತೀರಾ?",
        "trouble": "ಕ್ಷಮಿಸಿ, ಈಗ ತಾಂತ್ರಿಕ ತೊಂದರೆ ಇದೆ. ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
        "time_warning": "ಈ ಕರೆಯಲ್ಲಿ ಸುಮಾರು ಮೂವತ್ತು ಸೆಕೆಂಡುಗಳು ಉಳಿದಿವೆ.",
        "time_goodbye": "ಈ ಕರೆಯ ಸಮಯ ಮುಗಿದಿದೆ. ಕರೆ ಮಾಡಿದ್ದಕ್ಕೆ ಧನ್ಯವಾದಗಳು, ಯಾವಾಗ ಬೇಕಾದರೂ ಮತ್ತೆ ಕರೆ ಮಾಡಿ.",
    },
    "ml-IN": {
        "repeat": "ക്ഷമിക്കണം, ചെറിയൊരു പ്രശ്നം ഉണ്ടായി. ദയവായി ഒന്നുകൂടി പറയാമോ?",
        "trouble": "ക്ഷമിക്കണം, ഇപ്പോൾ സാങ്കേതിക പ്രശ്നമുണ്ട്. കുറച്ചു കഴിഞ്ഞ് വീണ്ടും വിളിക്കൂ.",
        "time_warning": "ഈ കോളിൽ ഏകദേശം മുപ്പത് സെക്കൻഡ് മാത്രമേ ബാക്കിയുള്ളൂ.",
        "time_goodbye": "ഈ കോളിന്റെ സമയം കഴിഞ്ഞു. വിളിച്ചതിന് നന്ദി, എപ്പോൾ വേണമെങ്കിലും വീണ്ടും വിളിക്കൂ.",
    },
    "mr-IN": {
        "repeat": "माफ करा, थोडी अडचण आली. कृपया पुन्हा सांगाल का?",
        "trouble": "माफ करा, सध्या तांत्रिक अडचण आहे. कृपया थोड्या वेळाने पुन्हा कॉल करा.",
        "time_warning": "या कॉलमध्ये सुमारे तीस सेकंद उरले आहेत.",
        "time_goodbye": "या कॉलची वेळ संपली आहे. कॉल केल्याबद्दल धन्यवाद, कधीही पुन्हा कॉल करा.",
    },
    "pa-IN": {
        "repeat": "ਮਾਫ਼ ਕਰਨਾ, ਥੋੜ੍ਹੀ ਦਿੱਕਤ ਆਈ। ਕਿਰਪਾ ਕਰਕੇ ਦੁਬਾਰਾ ਦੱਸ ਸਕਦੇ ਹੋ?",
        "trouble": "ਮਾਫ਼ ਕਰਨਾ, ਇਸ ਵੇਲੇ ਤਕਨੀਕੀ ਸਮੱਸਿਆ ਹੈ। ਕਿਰਪਾ ਕਰਕੇ ਥੋੜ੍ਹੀ ਦੇਰ ਬਾਅਦ ਦੁਬਾਰਾ ਕਾਲ ਕਰੋ।",
        "time_warning": "ਇਸ ਕਾਲ ਵਿੱਚ ਲਗਭਗ ਤੀਹ ਸਕਿੰਟ ਬਾਕੀ ਹਨ।",
        "time_goodbye": "ਇਸ ਕਾਲ ਦਾ ਸਮਾਂ ਪੂਰਾ ਹੋ ਗਿਆ ਹੈ। ਕਾਲ ਕਰਨ ਲਈ ਧੰਨਵਾਦ, ਕਦੇ ਵੀ ਦੁਬਾਰਾ ਕਾਲ ਕਰੋ।",
    },
    "bn-IN": {
        "repeat": "দুঃখিত, একটু সমস্যা হয়েছে। আবার একবার বলবেন?",
        "trouble": "দুঃখিত, এখন প্রযুক্তিগত সমস্যা হচ্ছে। একটু পরে আবার কল করুন।",
        "time_warning": "এই কলে আর প্রায় তিরিশ সেকেন্ড বাকি আছে।",
        "time_goodbye": "এই কলের সময় শেষ। কল করার জন্য ধন্যবাদ, যেকোনো সময় আবার কল করবেন।",
    },
    "gu-IN": {
        "repeat": "માફ કરશો, થોડી તકલીફ થઈ. કૃપા કરીને ફરી કહેશો?",
        "trouble": "માફ કરશો, અત્યારે ટેકનિકલ સમસ્યા છે. કૃપા કરીને થોડી વાર પછી ફરી કૉલ કરો.",
        "time_warning": "આ કૉલમાં લગભગ ત્રીસ સેકન્ડ બાકી છે.",
        "time_goodbye": "આ કૉલનો સમય પૂરો થયો છે. કૉલ કરવા બદલ આભાર, ગમે ત્યારે ફરી કૉલ કરજો.",
    },
}


def call_message(key: MessageKey, language: str | None) -> str:
    """Return the line for language, falling back to English for unknown languages."""
    return MESSAGES.get(language or "", MESSAGES["en-IN"])[key]
