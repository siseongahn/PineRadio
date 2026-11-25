import re

"""Country / language lookup tables used by build_stations.py.

Keys are normalized playlist names: lowercase, with non-alphanumeric runs replaced by '_'.
"""

COUNTRIES = """
Afghanistan|Albania|Algeria|American Samoa|Andorra|Angola|Anguilla|Antigua and Barbuda|Argentina|Armenia|Aruba|
Australia|Austria|Azerbaijan|Bahamas|Bahrain|Bangladesh|Barbados|Belarus|Belgium|Belize|Benin|Bermuda|Bhutan|
Bolivia|Bonaire|Bosnia and Herzegovina|Botswana|Brazil|British Virgin Islands|Brunei|Bulgaria|Burkina Faso|Burundi|
Cambodia|Cameroon|Canada|Cape Verde|Cayman Islands|Central African Republic|Chad|Chile|China|Colombia|Comoros|
Congo|DR Congo|Cook Islands|Costa Rica|Croatia|Cuba|Curacao|Cyprus|Czech Republic|Denmark|Djibouti|Dominica|
Dominican Republic|Ecuador|Egypt|El Salvador|Equatorial Guinea|Eritrea|Estonia|Eswatini|Ethiopia|Falkland Islands|
Faroe Islands|Fiji|Finland|France|French Guiana|French Polynesia|Gabon|Gambia|Georgia|Germany|Ghana|Gibraltar|
Greece|Greenland|Grenada|Guadeloupe|Guam|Guatemala|Guernsey|Guinea|Guinea-Bissau|Guyana|Haiti|Honduras|Hong Kong|
Hungary|Iceland|India|Indonesia|Iran|Iraq|Ireland|Isle of Man|Israel|Italy|Ivory Coast|Jamaica|Japan|Jersey|Jordan|
Kazakhstan|Kenya|Kiribati|Kosovo|Kuwait|Kyrgyzstan|Laos|Latvia|Lebanon|Lesotho|Liberia|Libya|Liechtenstein|
Lithuania|Luxembourg|Macao|Madagascar|Malawi|Malaysia|Maldives|Mali|Malta|Marshall Islands|Martinique|Mauritania|
Mauritius|Mayotte|Mexico|Micronesia|Moldova|Monaco|Mongolia|Montenegro|Montserrat|Morocco|Mozambique|Myanmar|
Namibia|Nauru|Nepal|Netherlands|Netherlands Antilles|New Caledonia|New Zealand|Nicaragua|Niger|Nigeria|Niue|
North Korea|North Macedonia|Northern Mariana Islands|Norway|Oman|Pakistan|Palau|Palestine|Panama|Papua New Guinea|
Paraguay|Peru|Philippines|Poland|Portugal|Puerto Rico|Qatar|Reunion|Romania|Russia|Rwanda|Saint Barthelemy|
Saint Kitts and Nevis|Saint Lucia|Saint Martin|Saint Pierre and Miquelon|Saint Vincent and the Grenadines|Samoa|
San Marino|Sao Tome and Principe|Saudi Arabia|Senegal|Serbia|Seychelles|Sierra Leone|Singapore|Sint Maarten|
Slovakia|Slovenia|Solomon Islands|Somalia|South Africa|South Korea|South Sudan|Spain|Sri Lanka|Sudan|Suriname|
Svalbard|Sweden|Switzerland|Syria|Taiwan|Tajikistan|Tanzania|Thailand|Timor-Leste|Togo|Tokelau|Tonga|
Trinidad and Tobago|Tunisia|Turkey|Turkmenistan|Turks and Caicos Islands|Tuvalu|Uganda|Ukraine|United Arab Emirates|
United Kingdom|United States|Uruguay|US Virgin Islands|Uzbekistan|Vanuatu|Vatican|Venezuela|Vietnam|
Wallis and Futuna|Western Sahara|Yemen|Zambia|Zimbabwe
"""

COUNTRY_ALIASES = {
    "usa": "United States", "us": "United States", "united_states_of_america": "United States", "america": "United States",
    "uk": "United Kingdom", "great_britain": "United Kingdom", "england": "United Kingdom", "scotland": "United Kingdom",
    "wales": "United Kingdom", "northern_ireland": "United Kingdom", "britain": "United Kingdom",
    "uae": "United Arab Emirates", "antigua": "Antigua and Barbuda", "bosnia": "Bosnia and Herzegovina",
    "saint_kitts_nevis": "Saint Kitts and Nevis", "saint_vincent": "Saint Vincent and the Grenadines",
    "trinidad_tobago": "Trinidad and Tobago", "slovak_republic": "Slovakia", "czechia": "Czech Republic",
    "macedonia": "North Macedonia", "macedonia_the_former_yugoslav_republic_of": "North Macedonia",
    "congo_the_democratic_republic_of_the": "DR Congo", "congo_the": "Congo", "democratic_republic_of_the_congo": "DR Congo",
    "gambia_the": "Gambia", "micronesia_the_federated_states_of": "Micronesia", "swaziland": "Eswatini",
    "cote_d_ivoire": "Ivory Coast", "korea": "South Korea", "republic_of_korea": "South Korea", "burma": "Myanmar",
    "virgin_islands_uk": "British Virgin Islands", "virgin_islands_us": "US Virgin Islands", "macau": "Macao",
    "holland": "Netherlands", "the_netherlands": "Netherlands", "russian_federation": "Russia", "turkiye": "Turkey",
    "viet_nam": "Vietnam", "cabo_verde": "Cape Verde", "east_timor": "Timor-Leste", "vatican_city": "Vatican",
    "francia": "France", "espana": "Spain", "deutschland": "Germany", "italia": "Italy", "brasil": "Brazil",
    "mexico_city": "Mexico", "berlin": "Germany", "republica_dominicana": "Dominican Republic",
    "washington_d_c": "United States", "hawaii": "United States", "alaska": "United States",
}

US_STATES = """
Alabama|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Idaho|Illinois|Indiana|Iowa|Kansas|
Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|
New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|
Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|
Wyoming
"""
# Georgia is deliberately left out: it is treated as the country.

# Language names and adjectives. vTuner uses ISO 639-2/B codes (lang-xxx).
LANGUAGES = {
    "English": "english|eng", "Spanish": "spanish|spa|espanol|castellano", "French": "french|fre|fra|francais|chansons_francaises",
    "German": "german|ger|deu|deutsch", "Italian": "italian|ita|italiano|italian_music", "Portuguese": "portuguese|por|portugues",
    "Dutch": "dutch|dut|nld|nederlands", "Russian": "russian|rus|russkiy", "Ukrainian": "ukrainian|ukr", "Polish": "polish|pol",
    "Czech": "czech|cze|ces", "Slovak": "slovak|slo", "Slovenian": "slovenian|slv", "Croatian": "croatian|scr|hrv",
    "Serbian": "serbian|scc|srp", "Bosnian": "bosnian|bos", "Macedonian": "macedonian|mac", "Bulgarian": "bulgarian|bul",
    "Romanian": "romanian|rum|ron|moldovan|mol", "Hungarian": "hungarian|hun", "Greek": "greek|gre|ell",
    "Albanian": "albanian|alb|sqi", "Turkish": "turkish|tur|turk", "Arabic": "arabic|ara|arabic_music",
    "Hebrew": "hebrew|heb", "Persian": "persian|per|fas|farsi", "Kurdish": "kurdish|kur", "Armenian": "armenian|arm|hye",
    "Georgian": "georgian|geo", "Azerbaijani": "azerbaijani|aze|azeri", "Kazakh": "kazakh|kaz", "Kyrgyz": "kyrgyz|kir",
    "Uzbek": "uzbek|uzb", "Tajik": "tajik|tgk", "Turkmen": "turkmen|tuk", "Mongolian": "mongolian|mon",
    "Swedish": "swedish|swe", "Norwegian": "norwegian|nor", "Danish": "danish|dan", "Finnish": "finnish|fin",
    "Icelandic": "icelandic|ice|isl", "Faroese": "faroese|fao", "Estonian": "estonian|est", "Latvian": "latvian|lav",
    "Lithuanian": "lithuanian|lit", "Belarusian": "belarusian|bel", "Irish": "irish|gle|gaelic", "Scottish Gaelic": "gla|scottish_gaelic",
    "Welsh": "welsh|wel|cym", "Breton": "breton|bre", "Basque": "basque|baq|eus", "Catalan": "catalan|cat",
    "Galician": "galician|glg", "Frisian": "frisian|fry", "Romansh": "romansh|roh", "Maltese": "maltese|mlt",
    "Luxembourgish": "luxembourgish|ltz", "Sorbian": "sorbian", "Esperanto": "esperanto|epo", "Bashkir": "bashkir|bak",
    "Chinese": "chinese|chi|zho|mandarin|cantonese", "Japanese": "japanese|jpn", "Korean": "korean|kor",
    "Vietnamese": "vietnamese|vie", "Thai": "thai|tha", "Khmer": "khmer|khm", "Lao": "lao|lao_language",
    "Burmese": "burmese|bur|mya", "Malay": "malay|may|msa", "Indonesian": "indonesian|ind|bahasa",
    "Filipino": "filipino|tagalog|pinoy|phi|fil|tgl", "Hindi": "hindi|hin", "Urdu": "urdu|urd", "Bengali": "bengali|ben|bangla",
    "Punjabi": "punjabi|pan", "Tamil": "tamil|tam", "Telugu": "telugu|tel", "Kannada": "kannada|kan",
    "Malayalam": "malayalam|mal", "Marathi": "marathi|mar", "Gujarati": "gujarati|guj", "Odia": "odia|oriya|ori",
    "Assamese": "assamese|asm", "Konkani": "konkani|kok", "Kashmiri": "kashmiri|kas", "Sindhi": "sindhi|snd",
    "Nepali": "nepali|nep", "Sinhala": "sinhala|sinhalese|sin", "Pashto": "pashto|pus", "Tibetan": "tibetan|tib|bod",
    "Meitei": "meitei", "Swahili": "swahili|swa", "Amharic": "amharic|amh", "Somali": "somali|som", "Hausa": "hausa|hau",
    "Yoruba": "yoruba|yor", "Igbo": "igbo|ibo", "Akan": "akan|twi", "Lingala": "lingala|lin", "Kinyarwanda": "kinyarwanda|kin",
    "Luganda": "luganda|lug", "Shona": "shona|sna", "Xhosa": "xhosa|xho", "Zulu": "zulu|zul", "Afrikaans": "afrikaans|afr",
    "Malagasy": "malagasy|mlg", "Berber": "berber|ber|amazigh", "Haitian Creole": "haitian|hat|kreyol", "Creole": "creole",
    "Papiamento": "papiamento|pap", "Samoan": "samoan|smo", "Hawaiian": "hawaiian_language|haw", "Multilingual": "mul|multilingual",
}


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _split(block):
    return [x.strip() for x in block.replace("\n", "").split("|") if x.strip()]


COUNTRY_MAP = {norm(c): c for c in _split(COUNTRIES)}
COUNTRY_MAP.update({norm(s): "United States" for s in _split(US_STATES)})
COUNTRY_MAP.update(COUNTRY_ALIASES)
COUNTRY_MAP["guinea_bissau"] = "Guinea-Bissau"
COUNTRY_MAP["timor_leste"] = "Timor-Leste"

LANG_MAP = {}
for lang, keys in LANGUAGES.items():
    for k in keys.split("|"):
        LANG_MAP[k] = lang
        LANG_MAP["lang_" + k] = lang
# 3-letter ISO codes are only matched behind the vTuner 'lang_' prefix, so bare names like 'mal' or 'ben' don't clash.
LANG_BARE = {k: v for k, v in LANG_MAP.items() if not k.startswith("lang_") and len(k) > 3}
LANG_BARE.update({"thai": "Thai", "lao": "Lao", "akan": "Akan", "twi": "Akan"})
LANG_PREFIXED = {k: v for k, v in LANG_MAP.items() if k.startswith("lang_")}


def country_of(n):
    return COUNTRY_MAP.get(n)


def language_of(n):
    if n.startswith("lang_"):
        return LANG_PREFIXED.get(n)
    return LANG_BARE.get(n) or LANG_BARE.get(n.removesuffix("_music"))


# ISO 3166-1 alpha-2 -> country
ISO2 = {
    "af": "Afghanistan",
    "al": "Albania",
    "dz": "Algeria",
    "as": "American Samoa",
    "ad": "Andorra",
    "ao": "Angola",
    "ai": "Anguilla",
    "ag": "Antigua and Barbuda",
    "ar": "Argentina",
    "am": "Armenia",
    "aw": "Aruba",
    "au": "Australia",
    "at": "Austria",
    "az": "Azerbaijan",
    "bs": "Bahamas",
    "bh": "Bahrain",
    "bd": "Bangladesh",
    "bb": "Barbados",
    "by": "Belarus",
    "be": "Belgium",
    "bz": "Belize",
    "bj": "Benin",
    "bm": "Bermuda",
    "bt": "Bhutan",
    "bo": "Bolivia",
    "bq": "Bonaire",
    "ba": "Bosnia and Herzegovina",
    "bw": "Botswana",
    "br": "Brazil",
    "vg": "British Virgin Islands",
    "bn": "Brunei",
    "bg": "Bulgaria",
    "bf": "Burkina Faso",
    "bi": "Burundi",
    "kh": "Cambodia",
    "cm": "Cameroon",
    "ca": "Canada",
    "cv": "Cape Verde",
    "ky": "Cayman Islands",
    "cf": "Central African Republic",
    "td": "Chad",
    "cl": "Chile",
    "cn": "China",
    "co": "Colombia",
    "km": "Comoros",
    "cg": "Congo",
    "cd": "DR Congo",
    "ck": "Cook Islands",
    "cr": "Costa Rica",
    "hr": "Croatia",
    "cu": "Cuba",
    "cw": "Curacao",
    "cy": "Cyprus",
    "cz": "Czech Republic",
    "dk": "Denmark",
    "dj": "Djibouti",
    "dm": "Dominica",
    "do": "Dominican Republic",
    "ec": "Ecuador",
    "eg": "Egypt",
    "sv": "El Salvador",
    "gq": "Equatorial Guinea",
    "er": "Eritrea",
    "ee": "Estonia",
    "sz": "Eswatini",
    "et": "Ethiopia",
    "fk": "Falkland Islands",
    "fo": "Faroe Islands",
    "fj": "Fiji",
    "fi": "Finland",
    "fr": "France",
    "gf": "French Guiana",
    "pf": "French Polynesia",
    "ga": "Gabon",
    "gm": "Gambia",
    "ge": "Georgia",
    "de": "Germany",
    "gh": "Ghana",
    "gi": "Gibraltar",
    "gr": "Greece",
    "gl": "Greenland",
    "gd": "Grenada",
    "gp": "Guadeloupe",
    "gu": "Guam",
    "gt": "Guatemala",
    "gg": "Guernsey",
    "gn": "Guinea",
    "gw": "Guinea-Bissau",
    "gy": "Guyana",
    "ht": "Haiti",
    "hn": "Honduras",
    "hk": "Hong Kong",
    "hu": "Hungary",
    "is": "Iceland",
    "in": "India",
    "id": "Indonesia",
    "ir": "Iran",
    "iq": "Iraq",
    "ie": "Ireland",
    "im": "Isle of Man",
    "il": "Israel",
    "it": "Italy",
    "ci": "Ivory Coast",
    "jm": "Jamaica",
    "jp": "Japan",
    "je": "Jersey",
    "jo": "Jordan",
    "kz": "Kazakhstan",
    "ke": "Kenya",
    "ki": "Kiribati",
    "xk": "Kosovo",
    "kw": "Kuwait",
    "kg": "Kyrgyzstan",
    "la": "Laos",
    "lv": "Latvia",
    "lb": "Lebanon",
    "ls": "Lesotho",
    "lr": "Liberia",
    "ly": "Libya",
    "li": "Liechtenstein",
    "lt": "Lithuania",
    "lu": "Luxembourg",
    "mo": "Macao",
    "mg": "Madagascar",
    "mw": "Malawi",
    "my": "Malaysia",
    "mv": "Maldives",
    "ml": "Mali",
    "mt": "Malta",
    "mh": "Marshall Islands",
    "mq": "Martinique",
    "mr": "Mauritania",
    "mu": "Mauritius",
    "yt": "Mayotte",
    "mx": "Mexico",
    "fm": "Micronesia",
    "md": "Moldova",
    "mc": "Monaco",
    "mn": "Mongolia",
    "me": "Montenegro",
    "ms": "Montserrat",
    "ma": "Morocco",
    "mz": "Mozambique",
    "mm": "Myanmar",
    "na": "Namibia",
    "nr": "Nauru",
    "np": "Nepal",
    "nl": "Netherlands",
    "an": "Netherlands Antilles",
    "nc": "New Caledonia",
    "nz": "New Zealand",
    "ni": "Nicaragua",
    "ne": "Niger",
    "ng": "Nigeria",
    "nu": "Niue",
    "kp": "North Korea",
    "mk": "North Macedonia",
    "mp": "Northern Mariana Islands",
    "no": "Norway",
    "om": "Oman",
    "pk": "Pakistan",
    "pw": "Palau",
    "ps": "Palestine",
    "pa": "Panama",
    "pg": "Papua New Guinea",
    "py": "Paraguay",
    "pe": "Peru",
    "ph": "Philippines",
    "pl": "Poland",
    "pt": "Portugal",
    "pr": "Puerto Rico",
    "qa": "Qatar",
    "re": "Reunion",
    "ro": "Romania",
    "ru": "Russia",
    "rw": "Rwanda",
    "bl": "Saint Barthelemy",
    "kn": "Saint Kitts and Nevis",
    "lc": "Saint Lucia",
    "mf": "Saint Martin",
    "pm": "Saint Pierre and Miquelon",
    "vc": "Saint Vincent and the Grenadines",
    "ws": "Samoa",
    "sm": "San Marino",
    "st": "Sao Tome and Principe",
    "sa": "Saudi Arabia",
    "sn": "Senegal",
    "rs": "Serbia",
    "sc": "Seychelles",
    "sl": "Sierra Leone",
    "sg": "Singapore",
    "sx": "Sint Maarten",
    "sk": "Slovakia",
    "si": "Slovenia",
    "sb": "Solomon Islands",
    "so": "Somalia",
    "za": "South Africa",
    "kr": "South Korea",
    "ss": "South Sudan",
    "es": "Spain",
    "lk": "Sri Lanka",
    "sd": "Sudan",
    "sr": "Suriname",
    "sj": "Svalbard",
    "se": "Sweden",
    "ch": "Switzerland",
    "sy": "Syria",
    "tw": "Taiwan",
    "tj": "Tajikistan",
    "tz": "Tanzania",
    "th": "Thailand",
    "tl": "Timor-Leste",
    "tg": "Togo",
    "tk": "Tokelau",
    "to": "Tonga",
    "tt": "Trinidad and Tobago",
    "tn": "Tunisia",
    "tr": "Turkey",
    "tm": "Turkmenistan",
    "tc": "Turks and Caicos Islands",
    "tv": "Tuvalu",
    "ug": "Uganda",
    "ua": "Ukraine",
    "ae": "United Arab Emirates",
    "gb": "United Kingdom",
    "uk": "United Kingdom",
    "us": "United States",
    "um": "United States",
    "uy": "Uruguay",
    "vi": "US Virgin Islands",
    "uz": "Uzbekistan",
    "vu": "Vanuatu",
    "va": "Vatican",
    "ve": "Venezuela",
    "vn": "Vietnam",
    "wf": "Wallis and Futuna",
    "eh": "Western Sahara",
    "ye": "Yemen",
    "zm": "Zambia",
    "zw": "Zimbabwe",
}

# ISO 639-1 -> language
ISO639_1 = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese",
    "nl": "Dutch", "ru": "Russian", "uk": "Ukrainian", "pl": "Polish", "cs": "Czech", "sk": "Slovak", "sl": "Slovenian",
    "hr": "Croatian", "sr": "Serbian", "bs": "Bosnian", "mk": "Macedonian", "bg": "Bulgarian", "ro": "Romanian",
    "hu": "Hungarian", "el": "Greek", "sq": "Albanian", "tr": "Turkish", "ar": "Arabic", "he": "Hebrew", "fa": "Persian",
    "ku": "Kurdish", "hy": "Armenian", "ka": "Georgian", "az": "Azerbaijani", "kk": "Kazakh", "ky": "Kyrgyz",
    "uz": "Uzbek", "tg": "Tajik", "tk": "Turkmen", "mn": "Mongolian", "sv": "Swedish", "no": "Norwegian", "nb": "Norwegian",
    "nn": "Norwegian", "da": "Danish", "fi": "Finnish", "is": "Icelandic", "fo": "Faroese", "et": "Estonian",
    "lv": "Latvian", "lt": "Lithuanian", "be": "Belarusian", "ga": "Irish", "gd": "Scottish Gaelic", "cy": "Welsh",
    "br": "Breton", "eu": "Basque", "ca": "Catalan", "gl": "Galician", "fy": "Frisian", "rm": "Romansh", "mt": "Maltese",
    "lb": "Luxembourgish", "eo": "Esperanto", "ba": "Bashkir", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "vi": "Vietnamese", "th": "Thai", "km": "Khmer", "lo": "Lao", "my": "Burmese", "ms": "Malay", "id": "Indonesian",
    "tl": "Filipino", "fil": "Filipino", "hi": "Hindi", "ur": "Urdu", "bn": "Bengali", "pa": "Punjabi", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi", "gu": "Gujarati", "or": "Odia", "as": "Assamese",
    "ks": "Kashmiri", "sd": "Sindhi", "ne": "Nepali", "si": "Sinhala", "ps": "Pashto", "bo": "Tibetan", "sw": "Swahili",
    "am": "Amharic", "so": "Somali", "ha": "Hausa", "yo": "Yoruba", "ig": "Igbo", "ak": "Akan", "ln": "Lingala",
    "rw": "Kinyarwanda", "lg": "Luganda", "sn": "Shona", "xh": "Xhosa", "zu": "Zulu", "af": "Afrikaans", "mg": "Malagasy",
    "ht": "Haitian Creole", "pap": "Papiamento", "sm": "Samoan", "la": "Latin", "oc": "Occitan", "co": "Corsican",
}

COUNTRY_MAP.update({
    "unitedstatesofamerica": "United States", "united_states_of_america": "United States", "mex": "Mexico",
    "the_united_kingdom_of_great_britain_and_northern_ireland": "United Kingdom", "unitedkingdom": "United Kingdom",
    "unitedarabemirates": "United Arab Emirates", "nederland": "Netherlands", "belgie": "Belgium", "belgique": "Belgium",
    "land_islands": "Finland", "aland_islands": "Finland", "osterreich": "Austria", "schweiz": "Switzerland",
    "chicago": "United States", "washington_dc": "United States", "los_angeles": "United States", "atlanta": "United States",
    "boston": "United States", "philadelphia": "United States", "detroit": "United States", "dallas_fort_worth": "United States",
    "phoenix": "United States", "new_york_city": "United States", "houston": "United States", "miami": "United States",
    "san_francisco": "United States", "seattle": "United States", "denver": "United States", "npr": "United States",
    "uk_radio_fm_online": "United Kingdom", "london": "United Kingdom", "paris": "France", "madrid": "Spain",
    "toronto": "Canada", "montreal": "Canada", "vancouver": "Canada", "sydney": "Australia", "melbourne": "Australia",
})
LANG_BARE.update({"haitian_creole": "Haitian Creole", "espanish": "Spanish", "spanish_castilian": "Spanish",
                  "tagalog_filipino": "Filipino", "castilian": "Spanish"})

DEMONYMS = {
    "brazilian": "Brazil", "mexican": "Mexico", "eeuu": "United States", "american": "United States",
    "argentinian": "Argentina", "argentine": "Argentina", "colombian": "Colombia", "chilean": "Chile", "peruvian": "Peru",
    "venezuelan": "Venezuela", "cuban": "Cuba", "canadian": "Canada", "australian": "Australia", "british": "United Kingdom",
    "austrian": "Austria", "swiss": "Switzerland", "belgian": "Belgium", "nigerian": "Nigeria", "ghanaian": "Ghana",
    "kenyan": "Kenya", "egyptian": "Egypt", "moroccan": "Morocco", "algerian": "Algeria", "tunisian": "Tunisia",
    "lebanese": "Lebanon", "israeli": "Israel", "iranian": "Iran", "iraqi": "Iraq", "syrian": "Syria", "saudi": "Saudi Arabia",
    "pakistani": "Pakistan", "taiwanese": "Taiwan", "jamaican": "Jamaica", "haitian_country": "Haiti", "puerto_rican": "Puerto Rico",
    "dominican": "Dominican Republic", "ecuadorian": "Ecuador", "bolivian": "Bolivia", "uruguayan": "Uruguay",
    "paraguayan": "Paraguay", "guatemalan": "Guatemala", "honduran": "Honduras", "salvadoran": "El Salvador",
    "nicaraguan": "Nicaragua", "panamanian": "Panama", "costa_rican": "Costa Rica",
}
# only used for the country part of "<language>_<country>" names, e.g. english_canadian, english_indian
SUFFIX_DEMONYMS = {**DEMONYMS, "indian": "India", "filipino": "Philippines", "castilian": "Spain"}

# names that carry no country/language/genre information
NOISE = {"other", "music", "entertainment", "culture", "education", "internet_only", "radio", "local", "europe",
         "european", "international", "misc", "general", "stations", "online", "web", "live", "recommended", "early_access"}

_TRAIL = re.compile(r"(?:_?\d+|_lang|_language|_music|_radio|_stations?)$")


def classify_name(n):
    """normalized playlist name -> list of (kind, value), kind in {'country','language'}; [] if neither."""
    n = n.strip("_")
    prev = None
    while prev != n:
        prev, n = n, _TRAIL.sub("", n).strip("_")
    if not n or n in NOISE:
        return []
    m = re.match(r"^(lang|loca|country|language)_([a-z]{2,3})$", n)
    if m:
        if m.group(1) in ("lang", "language"):
            lang = ISO639_1.get(m.group(2)) or LANG_PREFIXED.get("lang_" + m.group(2))
            return [("language", lang)] if lang else []
        c = ISO2.get(m.group(2))
        return [("country", c)] if c else []
    if len(n) == 2:
        c = ISO2.get(n)
        return [("country", c)] if c else []
    c = COUNTRY_MAP.get(n) or DEMONYMS.get(n)
    if c:
        return [("country", c)]
    lang = language_of(n)
    if lang:
        return [("language", lang)]
    # "<language>_<country>"  e.g. portuguese_brazil, english_u_s, spanish_argentina, english_uk
    parts = n.split("_")
    for k in range(1, len(parts)):
        left, right = "_".join(parts[:k]), "_".join(parts[k:])
        lang = LANG_BARE.get(left)
        if not lang:
            continue
        right_c = (COUNTRY_MAP.get(right) or COUNTRY_MAP.get(right.replace("_", "")) or ISO2.get(right.replace("_", ""))
                   or SUFFIX_DEMONYMS.get(right))
        return [("language", lang), ("country", right_c)] if right_c else [("language", lang)]
    return []


# ccTLDs commonly sold as generic domains — not evidence of location
GENERIC_TLDS = {"fm", "am", "tv", "io", "me", "ws", "to", "ly", "co", "cc", "nu", "la", "gg", "ai", "eu", "tk", "ml",
                "ga", "cf", "gq", "su", "st", "sh", "ac", "vc", "mu", "dj", "lu_", "pw", "in_", "is_", "it_", "re_", "ag", "sc"}


def country_from_host(host):
    host = host.split("@")[-1].split(":")[0].rstrip(".")
    if not host or host.replace(".", "").isdigit():
        return None
    tld = host.rsplit(".", 1)[-1]
    if len(tld) != 2 or tld in GENERIC_TLDS:
        return None
    return ISO2.get(tld)


# reverse lookups (canonical name -> code) for display-name localization in the web player
_PREFER_ISO2 = {"United Kingdom": "GB", "United States": "US"}
COUNTRY_CODE = {}
for _code, _name in ISO2.items():
    COUNTRY_CODE.setdefault(_name, _code.upper())
COUNTRY_CODE.update(_PREFER_ISO2)

_PREFER_LANG = {"Norwegian": "no", "Filipino": "fil"}
LANGUAGE_CODE = {}
for _code, _name in ISO639_1.items():
    LANGUAGE_CODE.setdefault(_name, _code)
LANGUAGE_CODE.update(_PREFER_LANG)
LANGUAGE_CODE.update({"Konkani": "kok", "Berber": "ber", "Sorbian": "hsb", "Meitei": "mni", "Hawaiian": "haw", "Multilingual": "mul"})
