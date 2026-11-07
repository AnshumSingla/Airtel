"""Reason sentences: server templates (EN / HI / Hinglish) and the guard for LLM sentences.

POLICIES.md §5.4 and §14: product names, quantities and prices are rendered by
the server from IDs. A reason sentence may only restate its reason code. The
LLM may rephrase a sentence, but only through ``guard_sentences``, which falls
back to the template for any sentence that adds a claim.
"""

from __future__ import annotations

import re

from app.catalogue.models import Catalogue
from app.catalogue.recommend import Reason

SEGMENT_LABEL = {
    "en": {"micro": "shops like yours", "prof": "professional offices",
           "multi": "multi-outlet businesses", "mfg": "manufacturers"},
    "hi": {"micro": "आप जैसी दुकानें", "prof": "प्रोफेशनल ऑफिस", "multi": "कई आउटलेट वाले बिज़नेस",
           "mfg": "मैन्युफैक्चरिंग यूनिट"},
    "hinglish": {"micro": "aap jaisi dukaanein", "prof": "professional offices",
                 "multi": "multi-outlet businesses", "mfg": "manufacturing units"},
}

NEED_LABEL = {
    "en": {"P19": "billing and UPI/card payments", "P23": "CCTV", "P10": "to manage all sites centrally",
           "P15": "WhatsApp for customers", "P14": "SMS alerts", "P16": "business email",
           "P20": "antivirus protection", "P21": "a firewall", "P09": "a backup internet link",
           "P18": "a website", "P22": "Wi-Fi for customers", "P17": "data backup",
           "P12": "business phone lines", "P13": "a toll-free number", "P24": "machine monitoring",
           "P25": "vehicle tracking", "P11": "a static IP"},
    "hi": {"P19": "बिलिंग और UPI/कार्ड पेमेंट", "P23": "CCTV", "P10": "सभी जगहों को एक जगह से संभालना",
           "P15": "ग्राहकों के लिए WhatsApp", "P14": "SMS अलर्ट", "P16": "बिज़नेस ईमेल",
           "P20": "एंटीवायरस सुरक्षा", "P21": "फ़ायरवॉल", "P09": "बैकअप इंटरनेट", "P18": "वेबसाइट",
           "P22": "ग्राहकों के लिए Wi-Fi", "P17": "डेटा बैकअप", "P12": "बिज़नेस फ़ोन लाइनें",
           "P13": "टोल-फ़्री नंबर", "P24": "मशीन मॉनिटरिंग", "P25": "गाड़ियों की ट्रैकिंग", "P11": "स्टैटिक IP"},
    "hinglish": {"P19": "billing aur UPI/card payments", "P23": "CCTV", "P10": "saari jagah ek jagah se manage karna",
                 "P15": "customers ke liye WhatsApp", "P14": "SMS alerts", "P16": "business email",
                 "P20": "antivirus suraksha", "P21": "firewall", "P09": "backup internet", "P18": "website",
                 "P22": "customers ke liye Wi-Fi", "P17": "data backup", "P12": "business phone lines",
                 "P13": "toll-free number", "P24": "machine monitoring", "P25": "gaadiyon ki tracking",
                 "P11": "static IP"},
}

_TEMPLATES = {
    "en": {
        "every": "Chosen by every one of the {seg} we've served ({n}).",
        "most": "Most {seg} choose this ({pct}% of {n} we've served).",
        "half": "About half of {seg} add this ({pct}% of {n} we've served).",
        "top": "The option {seg} choose most often ({pct}% of {n} we've served).",
        "target": "Listed by Accel for {seg}.",
        "need": "You told us you need {need}.",
        "qty": "{qty} to start with; change it on the quote.",
    },
    "hi": {
        "every": "हमारे सभी {seg} ({n}) ने इसे चुना है।",
        "most": "ज़्यादातर {seg} इसे चुनते हैं ({n} में से {pct}%)।",
        "half": "लगभग आधे {seg} इसे लेते हैं ({n} में से {pct}%)।",
        "top": "{seg} सबसे ज़्यादा यही चुनते हैं ({n} में से {pct}%)।",
        "target": "Accel ने इसे {seg} के लिए रखा है।",
        "need": "आपने बताया कि आपको {need} चाहिए।",
        "qty": "शुरुआत के लिए {qty}; कोटेशन पर बदल सकते हैं।",
    },
    "hinglish": {
        "every": "Humare sabhi {seg} ({n}) ne yeh chuna hai.",
        "most": "Zyadatar {seg} yeh chunte hain ({n} mein se {pct}%).",
        "half": "Lagbhag aadhe {seg} yeh lete hain ({n} mein se {pct}%).",
        "top": "{seg} sabse zyada yahi chunte hain ({n} mein se {pct}%).",
        "target": "Accel ne yeh {seg} ke liye rakha hai.",
        "need": "Aapne bataya ki aapko {need} chahiye.",
        "qty": "Shuruaat ke liye {qty}; quote par badal sakte hain.",
    },
}

EXCLUSION_TEXT = {
    "en": {"EXCL_TIER": "Not available in your city yet.",
           "EXCL_MIN_EMP": "Offered from a larger team size.",
           "EXCL_MIN_SITES": "Offered for businesses with more sites.",
           "EXCL_GSTIN_MISSING": "Needs an active GSTIN.",
           "EXCL_GSTIN_UNKNOWN": "Needs an active GSTIN; we check it at KYC, or now if you choose.",
           "EXCL_GSTIN_INACTIVE": "Needs an active GSTIN; yours shows as inactive in the (mock) registry.",
           "EXCL_DEP_UNRESOLVED": "Needs a connection we can't add for you automatically; our team can help."},
    "hi": {"EXCL_TIER": "आपके शहर में अभी उपलब्ध नहीं।",
           "EXCL_MIN_EMP": "बड़ी टीम के लिए उपलब्ध।",
           "EXCL_MIN_SITES": "ज़्यादा जगहों वाले बिज़नेस के लिए उपलब्ध।",
           "EXCL_GSTIN_MISSING": "इसके लिए सक्रिय GSTIN चाहिए।",
           "EXCL_GSTIN_UNKNOWN": "इसके लिए सक्रिय GSTIN चाहिए; KYC पर या अभी चाहें तो जाँचेंगे।",
           "EXCL_GSTIN_INACTIVE": "इसके लिए सक्रिय GSTIN चाहिए; (मॉक) रजिस्ट्री में आपका GSTIN सक्रिय नहीं दिखता।",
           "EXCL_DEP_UNRESOLVED": "इसके लिए एक कनेक्शन चाहिए जो हम अपने-आप नहीं जोड़ सकते; हमारी टीम मदद करेगी।"},
    "hinglish": {"EXCL_TIER": "Aapke shehar mein abhi available nahi.",
                 "EXCL_MIN_EMP": "Badi team ke liye available.",
                 "EXCL_MIN_SITES": "Zyada jagah wale business ke liye available.",
                 "EXCL_GSTIN_MISSING": "Iske liye active GSTIN chahiye.",
                 "EXCL_GSTIN_UNKNOWN": "Iske liye active GSTIN chahiye; KYC par ya abhi chahein to check karenge.",
                 "EXCL_GSTIN_INACTIVE": "Iske liye active GSTIN chahiye; (mock) registry mein aapka GSTIN active nahi dikhta.",
                 "EXCL_DEP_UNRESOLVED": "Iske liye ek connection chahiye jo hum khud nahi jod sakte; humari team madad karegi."},
}


def _lang(language: str) -> str:
    return language if language in _TEMPLATES else "en"


def template_sentence(reason: Reason, segment: str, language: str, product_id: str) -> str:
    text = _template_sentence(reason, segment, language, product_id)
    return text[:1].upper() + text[1:]


def _template_sentence(reason: Reason, segment: str, language: str, product_id: str) -> str:
    lang = _lang(language)
    t = _TEMPLATES[lang]
    seg = SEGMENT_LABEL[lang][segment]
    if reason.tag == "YOU_TOLD_US":
        return t["need"].format(need=NEED_LABEL[lang].get(product_id, product_id))
    if reason.tag == "QTY_DEFAULT":
        return t["qty"].format(qty=reason.data["quantity"])
    if reason.tag == "CATALOGUE_TARGET":
        return t["target"].format(seg=seg)
    share, n = reason.data["share"], reason.data["n"]
    key = "every" if share >= 0.995 else "most" if share > 0.5 else "half" if share >= 0.45 else "top"
    return t[key].format(seg=seg, pct=round(share * 100), n=n)


def exclusion_sentence(codes: list[str], language: str) -> str:
    texts = EXCLUSION_TEXT[_lang(language)]
    return " ".join(texts.get(c, c) for c in codes)


# ---------------------------------------------------------------- guard for LLM sentences

MAX_SENTENCE = 160
_BANNED = re.compile(
    r"[0-9०-९₹%]|\b(rupees?|rupaye|rs|inr|uptime|sla|guarantee[ds]?|guaranteed|assured|"
    r"mbps|gbps|fastest|never down|always on|free|discount|save|saving)\b|रुपये|रुपए|गारंटी|मुफ़्त|मुफ्त|बचत",
    re.I,
)


def _product_aliases(cat: Catalogue) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    for pid, p in cat.items():
        names = {p.name.lower()}
        first = p.name.lower().split()
        if len(first) > 1:
            names.add(" ".join(first[:2]))
        aliases[pid] = names
    extra = {"P01": {"फाइबर 100"}, "P02": {"फाइबर 300"}, "P03": {"फाइबर 1g"}, "P04": {"airfiber", "एयरफाइबर"},
             "P15": {"व्हाट्सएप एपीआई", "whatsapp api"}, "P23": {"सीसीटीवी"}, "P22": {"वाई-फाई"}}
    for pid, words in extra.items():
        aliases[pid] |= words
    return aliases


def guard_sentences(cat: Catalogue, proposed: dict, expected: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Keep each LLM sentence only if it passes; otherwise use the template.

    ``expected`` maps key "P02:MOST_CHOSEN_IN_SEGMENT" -> template sentence.
    Returns (final sentences, list of keys that fell back).
    """
    aliases = _product_aliases(cat)
    final: dict[str, str] = {}
    fallbacks: list[str] = []
    if not isinstance(proposed, dict) or set(proposed) != set(expected):
        return dict(expected), sorted(expected)
    for key, template in expected.items():
        sentence = proposed.get(key)
        pid = key.split(":")[0]
        ok = isinstance(sentence, str) and 0 < len(sentence) <= MAX_SENTENCE and not _BANNED.search(sentence)
        if ok:
            low = sentence.lower()
            ok = not any(a in low for other, names in aliases.items() if other != pid for a in names)
        final[key] = sentence if ok else template
        if not ok:
            fallbacks.append(key)
    return final, fallbacks
