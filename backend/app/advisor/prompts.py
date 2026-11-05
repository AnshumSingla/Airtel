"""Question texts, buttons and LLM instructions for the advisor (EN / HI / Hinglish)."""

from __future__ import annotations

REQUIRED_SLOTS = ("segment", "city_tier", "employees", "sites", "has_gstin")

QUESTIONS = {
    "en": {
        "segment": "What kind of business do you run? (for example: clinic, kirana store, restaurant chain, factory)",
        "city_tier": "Which city is the business in?",
        "employees": "How many people work there, roughly?",
        "sites": "How many locations (shops, branches, outlets) do you have?",
        "has_gstin": "Does the business have a GSTIN? (yes or no is enough; don't type the number here)",
        "needs": "Anything specific you need? For example billing and UPI, CCTV, WhatsApp for customers, Wi-Fi, email.",
        "confirm": "Here is what I understood. Please check it, edit anything that's wrong, then confirm.",
        "unclear": "Sorry, I didn't catch that. You can tap an option below.",
        "too_many_turns": "I still need a few details. I can show a quote with typical values filled in, or someone can call you.",
        "gstin_consent": "I won't store or send that number. If you want, tap below and we'll check it with your permission.",
    },
    "hi": {
        "segment": "आपका बिज़नेस किस तरह का है? (जैसे: क्लिनिक, किराना दुकान, रेस्टोरेंट, फ़ैक्ट्री)",
        "city_tier": "आपका बिज़नेस किस शहर में है?",
        "employees": "वहाँ लगभग कितने लोग काम करते हैं?",
        "sites": "आपकी कितनी जगहें (दुकान, ब्रांच, आउटलेट) हैं?",
        "has_gstin": "क्या बिज़नेस का GSTIN है? (हाँ या नहीं बताइए; नंबर यहाँ न लिखें)",
        "needs": "कुछ खास चाहिए? जैसे बिलिंग और UPI, CCTV, ग्राहकों के लिए WhatsApp, Wi-Fi, ईमेल।",
        "confirm": "मैंने यह समझा है। जाँच लीजिए, कुछ गलत हो तो बदलिए, फिर कन्फ़र्म कीजिए।",
        "unclear": "माफ़ कीजिए, समझ नहीं पाया। नीचे से कोई विकल्प चुन सकते हैं।",
        "too_many_turns": "अभी कुछ जानकारी बाकी है। मैं आम वैल्यू के साथ कोटेशन दिखा सकता हूँ, या कोई आपको कॉल कर सकता है।",
        "gstin_consent": "मैं यह नंबर न सेव करूँगा न कहीं भेजूँगा। चाहें तो नीचे टैप करें, आपकी अनुमति से हम इसे जाँचेंगे।",
    },
    "hinglish": {
        "segment": "Aapka business kis type ka hai? (jaise: clinic, kirana dukaan, restaurant, factory)",
        "city_tier": "Aapka business kis shehar mein hai?",
        "employees": "Wahan lagbhag kitne log kaam karte hain?",
        "sites": "Aapki kitni jagah (dukaan, branch, outlet) hain?",
        "has_gstin": "Kya business ka GSTIN hai? (haan ya nahi bataiye; number yahan mat likhiye)",
        "needs": "Kuch khaas chahiye? Jaise billing aur UPI, CCTV, customers ke liye WhatsApp, Wi-Fi, email.",
        "confirm": "Maine yeh samjha hai. Check kar lijiye, kuch galat ho to badaliye, phir confirm kijiye.",
        "unclear": "Maaf kijiye, samajh nahi paaya. Neeche se koi option chun sakte hain.",
        "too_many_turns": "Abhi kuch details baaki hain. Main typical values ke saath quote dikha sakta hoon, ya koi aapko call kar sakta hai.",
        "gstin_consent": "Main yeh number na save karunga na kahin bhejunga. Chahein to neeche tap karein, aapki permission se hum ise check karenge.",
    },
}

_BUTTONS = {
    "en": {
        "segment": [("Shop or small service (kirana, salon, pharmacy)", "__set:segment=micro"),
                    ("Professional office (clinic, CA, coaching)", "__set:segment=prof"),
                    ("Several outlets or branches", "__set:segment=multi"),
                    ("Factory or workshop", "__set:segment=mfg")],
        "city_tier": [("Big city (metro)", "__set:city_tier=1"), ("Smaller city", "__set:city_tier=2")],
        "employees": [("1-5", "__set:employees=3"), ("6-20", "__set:employees=12"), ("21-50", "__set:employees=35"),
                      ("More than 50", "__set:employees=60")],
        "sites": [("1", "__set:sites=1"), ("2-3", "__set:sites=2"), ("4-10", "__set:sites=5")],
        "has_gstin": [("Yes", "__set:has_gstin=true"), ("No", "__set:has_gstin=false")],
        "needs": [("Billing and UPI", "__need:P19"), ("CCTV", "__need:P23"), ("WhatsApp for customers", "__need:P15"),
                  ("Wi-Fi for customers", "__need:P22"), ("Email", "__need:P16"), ("No, that's all", "__need:none")],
        "too_many_turns": [("Show a quote anyway", "__partial"), ("Ask someone to call me", "__handoff")],
    },
    "hi": {
        "segment": [("दुकान या छोटी सर्विस", "__set:segment=micro"), ("प्रोफेशनल ऑफिस (क्लिनिक, CA)", "__set:segment=prof"),
                    ("कई आउटलेट/ब्रांच", "__set:segment=multi"), ("फ़ैक्ट्री या वर्कशॉप", "__set:segment=mfg")],
        "city_tier": [("बड़ा शहर (मेट्रो)", "__set:city_tier=1"), ("छोटा शहर", "__set:city_tier=2")],
        "employees": [("1-5", "__set:employees=3"), ("6-20", "__set:employees=12"), ("21-50", "__set:employees=35"),
                      ("50 से ज़्यादा", "__set:employees=60")],
        "sites": [("1", "__set:sites=1"), ("2-3", "__set:sites=2"), ("4-10", "__set:sites=5")],
        "has_gstin": [("हाँ", "__set:has_gstin=true"), ("नहीं", "__set:has_gstin=false")],
        "needs": [("बिलिंग और UPI", "__need:P19"), ("CCTV", "__need:P23"), ("WhatsApp", "__need:P15"),
                  ("ग्राहकों के लिए Wi-Fi", "__need:P22"), ("ईमेल", "__need:P16"), ("नहीं, बस इतना", "__need:none")],
        "too_many_turns": [("फिर भी कोटेशन दिखाएँ", "__partial"), ("कोई मुझे कॉल करे", "__handoff")],
    },
}
_BUTTONS["hinglish"] = {
    **_BUTTONS["en"],
    "has_gstin": [("Haan", "__set:has_gstin=true"), ("Nahi", "__set:has_gstin=false")],
    "needs": [("Billing aur UPI", "__need:P19"), ("CCTV", "__need:P23"), ("WhatsApp", "__need:P15"),
              ("Customers ke liye Wi-Fi", "__need:P22"), ("Email", "__need:P16"), ("Nahi, bas itna", "__need:none")],
}


def question(slot: str, language: str) -> str:
    return QUESTIONS.get(language, QUESTIONS["en"])[slot]


def buttons(slot: str, language: str) -> list[dict]:
    table = _BUTTONS.get(language, _BUTTONS["en"])
    return [{"label": label, "value": value} for label, value in table.get(slot, [])]


# ---------------------------------------------------------------- LLM instructions (sent with gated payloads only)

NEED_CODES = {"billing": "P19", "cctv": "P23", "whatsapp": "P15", "sms": "P14", "email": "P16",
              "antivirus": "P20", "firewall": "P21", "backup_internet": "P09", "central_management": "P10",
              "website": "P18", "wifi": "P22", "data_backup": "P17", "phone_lines": "P12",
              "toll_free": "P13", "machine_monitoring": "P24", "vehicle_tracking": "P25", "static_ip": "P11"}

EXTRACT_SYSTEM = (
    "You help a telecom bundle advisor read a small-business owner's message. Unknown words have been "
    "replaced by [?] for privacy; never guess what they were. Return only facts the message clearly "
    "states, as JSON. Omit any field that isn't stated. Never return names, addresses or numbers other "
    "than the counts asked for. Segments: micro = shop or small service, prof = professional office, "
    "multi = several outlets, mfg = factory or workshop."
)

EXTRACT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "segment": {"type": "STRING", "enum": ["micro", "prof", "multi", "mfg"]},
        "city_tier": {"type": "INTEGER", "enum": [1, 2]},
        "employees": {"type": "INTEGER"},
        "sites": {"type": "INTEGER"},
        "has_gstin": {"type": "BOOLEAN"},
        "needs": {"type": "ARRAY", "items": {"type": "STRING", "enum": sorted(NEED_CODES)}},
    },
}

EXPLAIN_SYSTEM = (
    "For each reason in the input, write one short, friendly sentence (under 160 characters) in the "
    "requested language saying why the product fits. Use only the reason code and the coarse facts given. "
    "No numbers, prices, percentages, speeds, guarantees, savings claims, or names of other products. "
    "Return a JSON object keyed exactly by '<product_id>:<code>'."
)


def explain_schema(keys: list[str]) -> dict:
    return {"type": "OBJECT", "properties": {k: {"type": "STRING"} for k in keys}, "required": keys}
