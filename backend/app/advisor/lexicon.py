"""Vocabulary for the local slot parser and the privacy gate (POLICIES.md §4, §5.2).

Business types and cities come from the synthetic leads data (each business
type maps to exactly one segment, each city to one tier and state). Aliases,
needs keywords and function words are hand-written for English, Hindi in
Devanagari, and Hinglish (Hindi in Latin script).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import Engine, select

from app.catalogue.models import SEGMENT_CODES
from app.data.schema import historical_leads

# ---------------------------------------------------------------- numbers
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

NUMBER_WORDS: dict[str, int] = {
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "hundred": 100, "single": 1,
    # Hinglish
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "chhah": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "baarah": 12,
    "terah": 13, "chaudah": 14, "pandrah": 15, "bees": 20, "pachees": 25, "tees": 30,
    "chalis": 40, "pachas": 50, "sau": 100,
    # Hindi (Devanagari)
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
    "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "पंद्रह": 15, "बीस": 20, "पच्चीस": 25,
    "तीस": 30, "चालीस": 40, "पचास": 50, "सौ": 100,
}

# ---------------------------------------------------------------- slot words
PEOPLE_WORDS = {"log", "logon", "logo", "people", "persons", "staff", "employees", "employee",
                "workers", "worker", "members", "karmchari", "aadmi", "लोग", "लोगों", "कर्मचारी",
                "स्टाफ", "आदमी"}
SITE_WORDS = {"branch", "branches", "site", "sites", "outlet", "outlets", "location", "locations",
              "store", "stores", "shops", "jagah", "jagahon", "jagah", "centre", "centres", "center",
              "centers", "unit", "units", "शाखा", "शाखाएं", "जगह", "जगहों", "ब्रांच", "आउटलेट", "दुकानें"}
ONLY_WORDS = {"hi", "only", "just", "सिर्फ", "ही", "bas", "sirf"}

YES_WORDS = {"yes", "haan", "han", "ha", "hai", "hain", "have", "got", "registered", "हां", "हाँ", "है", "हैं"}
NO_WORDS = {"no", "nahi", "nahin", "nahee", "not", "dont", "don't", "without", "नहीं", "नही", "ना"}
GSTIN_WORDS = {"gst", "gstin", "जीएसटी"}
BUDGET_WORDS = {"budget", "बजट", "kharcha", "max", "maximum", "upto", "tak"}

# Aliases -> canonical business type in the leads data.
BUSINESS_ALIASES: dict[str, str] = {
    "dental": "Dental clinic", "dentist": "Dental clinic", "clinic": "Dental clinic",
    "दांत": "Dental clinic", "डेंटल": "Dental clinic", "क्लिनिक": "Dental clinic", "दवाखाना": "Dental clinic",
    "physio": "Physiotherapy clinic", "physiotherapy": "Physiotherapy clinic",
    "lab": "Diagnostic lab", "diagnostic": "Diagnostic lab", "pathology": "Diagnostic lab",
    "ca": "CA firm", "accountant": "CA firm", "chartered": "CA firm",
    "coaching": "Coaching centre", "tuition": "Coaching centre", "कोचिंग": "Coaching centre",
    "lawyer": "Law office", "advocate": "Law office", "law": "Law office", "वकील": "Law office",
    "insurance": "Insurance agency", "travel": "Travel agency", "architect": "Architecture studio",
    "property": "Real estate agency", "estate": "Real estate agency",
    "kirana": "Kirana store", "grocery": "Kirana store", "किराना": "Kirana store",
    "salon": "Salon", "parlour": "Salon", "parlor": "Salon", "सैलून": "Salon", "पार्लर": "Salon",
    "pharmacy": "Pharmacy", "chemist": "Pharmacy", "medical": "Pharmacy", "दवा": "Pharmacy",
    "बेकरी": "Bakery", "bakery": "Bakery", "mithai": "Sweet shop", "sweets": "Sweet shop",
    "halwai": "Sweet shop", "मिठाई": "Sweet shop", "boutique": "Boutique", "बुटीक": "Boutique",
    "stationery": "Stationery shop", "hardware": "Hardware store", "optician": "Optician",
    "optical": "Optician", "chashma": "Optician", "mobile repair": "Mobile repair shop",
    "restaurant": "Restaurant chain", "रेस्टोरेंट": "Restaurant chain", "dhaba": "Restaurant chain",
    "hotel": "Budget hotel group", "होटल": "Budget hotel group", "gym": "Gym chain",
    "preschool": "Pre-school chain", "pre-school": "Pre-school chain", "playschool": "Pre-school chain",
    "textile": "Textile unit", "kapda": "Textile unit", "printing": "Printing press",
    "press": "Printing press", "packaging": "Packaging unit", "furniture": "Furniture workshop",
    "auto-parts": "Auto-parts unit", "auto parts": "Auto-parts unit", "plastic": "Plastic moulding unit",
    "factory": "Food processing unit", "food processing": "Food processing unit",
    "फैक्ट्री": "Food processing unit",
}

CITY_ALIASES: dict[str, str] = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru", "बेंगलुरु": "Bengaluru", "बैंगलोर": "Bengaluru",
    "bombay": "Mumbai", "मुंबई": "Mumbai", "दिल्ली": "Delhi", "new delhi": "Delhi", "पुणे": "Pune",
    "poona": "Pune", "चेन्नई": "Chennai", "madras": "Chennai", "कोलकाता": "Kolkata", "calcutta": "Kolkata",
    "हैदराबाद": "Hyderabad", "अहमदाबाद": "Ahmedabad", "जयपुर": "Jaipur", "लखनऊ": "Lucknow",
    "भोपाल": "Bhopal", "इंदौर": "Indore", "नागपुर": "Nagpur", "नासिक": "Nashik", "पटना": "Patna",
    "सूरत": "Surat", "वडोदरा": "Vadodara", "baroda": "Vadodara", "लुधियाना": "Ludhiana",
    "कोच्चि": "Kochi", "cochin": "Kochi", "mysore": "Mysuru", "vizag": "Visakhapatnam",
    "coimbatore": "Coimbatore",
}

# Need keyword -> product id. Multi-word phrases are matched before single words.
NEED_PHRASES: dict[str, str] = {
    "backup internet": "P09", "backup link": "P09", "failover": "P09", "internet backup": "P09",
    "data backup": "P17", "cloud backup": "P17", "backup of data": "P17",
    "static ip": "P11", "toll free": "P13", "toll-free": "P13", "call recording": "P12",
    "phone lines": "P12", "guest wifi": "P22", "guest wi-fi": "P22",
    "manage all": "P10", "manage centrally": "P10", "central management": "P10",
}
NEED_WORDS: dict[str, str] = {
    "upi": "P19", "card": "P19", "pos": "P19", "billing": "P19", "payments": "P19", "payment": "P19",
    "बिलिंग": "P19", "भुगतान": "P19", "whatsapp": "P15", "व्हाट्सएप": "P15", "sms": "P14",
    "cctv": "P23", "camera": "P23", "cameras": "P23", "सीसीटीवी": "P23", "कैमरा": "P23",
    "email": "P16", "e-mail": "P16", "ईमेल": "P16", "antivirus": "P20", "ransomware": "P20",
    "virus": "P20", "firewall": "P21", "centrally": "P10", "central": "P10", "sdwan": "P10",
    "sd-wan": "P10", "website": "P18", "वेबसाइट": "P18", "wifi": "P22", "wi-fi": "P22",
    "ivr": "P12", "telephony": "P12", "iot": "P24", "machines": "P24", "sensors": "P24",
    "fleet": "P25", "vehicles": "P25", "gps": "P25", "trucks": "P25",
}

# Words that carry no personal information, allowed through the privacy gate.
FUNCTION_WORDS = set("""
a an the and or but if so to of in on at for from with by as is are was were be been am i we you
they he she it my our your their this that these those there here have has had do does did not no
yes ok okay please thanks thank want need needs would like can could will should also just only
about around approx approximately more less than per each every all some any many much few one
what which who how when where why hi hello sir madam total our us me mine business shop office
store company firm internet connection wifi broadband fibre fiber mobile phone line lines sim sims
plan plans speed fast slow good cheap price cost monthly month months year years currently current
use using used now new old existing provider pay paying spend spending rupees rs inr lakh lakhs
thousand hundred
hai hain tha thi the ho hoga hogi haan han nahi nahin na mera meri mere hamara hamari hamare apna
apni apne aap tum main hum ka ki ke ko se mein me par pe aur ya bhi hi toh to kya kaun kitna kitne
kitni kaise kab kahan yahan wahan wala wali wale chahiye chahte chahta chahti karna karte karti
karta kar ho raha rahe rahi abhi bas sirf lagbhag kareeb takriban kuch bahut zyada kam accha achha
paas saath liye lie wajah sab sabhi har koi dono pehle baad near nearby
theek thik dukaan dukan kaam kaamkaj log logon jagah ek do teen char paanch das bees
है हैं था थी थे हो होगा हां हाँ नहीं ना मेरा मेरी मेरे हमारा हमारी हमारे अपना अपनी आप तुम मैं हम
का की के को से में पर और या भी ही तो क्या कौन कितना कितने कैसे कब कहाँ यहाँ वाला वाली वाले चाहिए
करना करते करता कर रहा रहे रही अभी बस सिर्फ लगभग कुछ बहुत ज़्यादा कम अच्छा ठीक दुकान काम लोग
जगह इंटरनेट फ़ोन फोन मोबाइल
""".split())


@dataclass(frozen=True)
class Lexicon:
    business_types: dict[str, str]          # lower-case business type -> canonical
    business_segment: dict[str, str]        # canonical business type -> segment code
    cities: dict[str, tuple[str, int, str]]  # lower-case city -> (canonical, tier, state)

    def allowed_tokens(self) -> set[str]:
        """Every token the privacy gate may let through (lower-case)."""
        words: set[str] = set(FUNCTION_WORDS) | PEOPLE_WORDS | SITE_WORDS | ONLY_WORDS
        words |= YES_WORDS | NO_WORDS | GSTIN_WORDS | BUDGET_WORDS | set(NUMBER_WORDS)
        for phrase in list(self.business_types) + list(BUSINESS_ALIASES) + list(self.cities) \
                + list(CITY_ALIASES) + list(NEED_PHRASES) + list(NEED_WORDS):
            words |= set(tokenize(phrase))
        return words


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens, keeping Devanagari words (with their vowel signs) intact."""
    return re.findall(r"[\wऀ-ॿ'-]+", text.lower())


def build_lexicon(engine: Engine) -> Lexicon:
    with engine.connect() as conn:
        rows = conn.execute(select(historical_leads.c.business_type, historical_leads.c.segment,
                                   historical_leads.c.city, historical_leads.c.city_tier,
                                   historical_leads.c.state).distinct()).all()
    business_segment: dict[str, str] = {}
    cities: dict[str, tuple[str, int, str]] = {}
    for btype, segment, city, tier, state in rows:
        business_segment[btype] = SEGMENT_CODES[segment]
        cities[city.lower()] = (city, int(tier), state)
    for alias, canonical in CITY_ALIASES.items():
        cities.setdefault(alias, cities[canonical.lower()])
    return Lexicon({b.lower(): b for b in business_segment}, business_segment, cities)
