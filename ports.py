"""Where she says she is bound, as a person would say it.

AIS destination is 20 characters of free text typed on the bridge: 'USOAK', 'US OAK',
'CAPRR>USSFO', 'OAKLAND CA', 'JP_TYO'. The code is a UN/LOCODE (country + place) when the
crew follows the rules. The table is our own short list, the places ships off this coast
really name, plus what the crews call them. Anything we cannot read comes back as "Sea",
which the caption leaves out: a code nobody can read is not a destination, and a guess is
worse. Add a line when the log shows one worth having."""
import re

_BY_COUNTRY = {
 "US": "OAK Oakland,SFO San Francisco,LAX Los Angeles,LGB Long Beach,PDX Portland,SEA Seattle,TIW Tacoma,TCM Tacoma,"
       "RCH Richmond,SCK Stockton,BEN Benicia,BNC Benicia,HUM Humboldt Bay,CEC Crescent City,COS Coos Bay,OOS Coos Bay,"
       "AST Astoria,MTY Monterey,HNL Honolulu,MRZ Martinez,ELS El Segundo,SAN San Diego,KAM Kalama,FDT Ferndale,"
       "SAC Sacramento,LOG Longview,PBG Pittsburg,VDZ Valdez,OTS Anacortes,ANA Anacortes,CRM Crockett,CP4 Cherry Point,ANZ Antioch,"
       "CLM Port Angeles,ITO Hilo,VAN Vancouver Wa,BLI Bellingham,OLM Olympia,EVT Everett,FRD Friday Harbor,"
       "RWC Redwood City,SEL Selby,EKA Eureka,GHR Grays Harbor,NTD Port Hueneme,KTN Ketchikan,ANC Anchorage,"
       "DUT Dutch Harbor,KDK Kodiak,OGG Kahului,HIL Hilo",
 "CA": "VAN Vancouver,PRR Prince Rupert,TLB Tilbury,PMA Port McNeill,NWE New Westminster,STW Stewart,KTM Kitimat,"
       "NNO Nanaimo,SQA Squamish,VIC Victoria,RCH Richmond Bc,RTB Roberts Bank,ROB Roberts Bank",
 "MX": "ZLO Manzanillo,LZC Lazaro Cardenas,SRL Santa Rosalia,ESE Ensenada,GYM Guaymas,MZT Mazatlan,TPB Topolobampo",
 "PA": "BLB Balboa,MIT Manzanillo Pa,PCN Panama Canal,ROD Rodman,CTB Cristobal",
 "GT": "PRQ Puerto Quetzal", "SV": "AQJ Acajutla", "NI": "CIO Corinto", "PE": "CLL Callao", "CO": "BUN Buenaventura",
 "EC": "LLD La Libertad,GYE Guayaquil,ESM Esmeraldas", "CL": "QTV Quintero,SAI San Antonio,VAP Valparaiso,MJS Mejillones",
 "CN": "SHA Shanghai,SHG Shanghai,NGB Ningbo,NBO Ningbo,TAO Qingdao,QDG Qingdao,YTN Yantian,TXG Tianjin Xingang,XGA Tianjin Xingang,"
       "TAG Taicang,XMN Xiamen,SHK Shekou,ZOS Zhoushan,LYG Lianyungang,DLC Dalian,ZJG Zhangjiagang,CFD Caofeidian",
 "HK": "HKG Hong Kong", "TW": "KHH Kaohsiung,KEL Keelung,TXG Taichung", "SG": "SIN Singapore",
 "KR": "PUS Busan,USN Ulsan,YOS Yeosu,INC Incheon,KAN Gwangyang,PTK Pyeongtaek,ONS Onsan",
 "JP": "TYO Tokyo,YOK Yokohama,NGO Nagoya,UKB Kobe,THS Toyohashi,MYJ Matsuyama,HIJ Hiroshima,KWS Kawasaki,CHB Chiba,"
       "OSA Osaka,MIZ Mizushima,SMZ Shimizu,TOY Toyama",
 "VN": "VUT Vung Tau,SGN Ho Chi Minh City", "PH": "MNL Manila,BTG Batangas", "TH": "LCH Laem Chabang",
 "MY": "PKG Port Klang,TPP Tanjung Pelepas", "ID": "BPN Balikpapan,DUM Dumai", "IN": "VTZ Visakhapatnam,SIK Sikka",
 "AU": "BNE Brisbane,NTL Newcastle,SYD Sydney,GLT Gladstone,MEL Melbourne", "RU": "VVO Vladivostok,NJK Nakhodka",
 "NZ": "AKL Auckland,TRG Tauranga,MAP Marsden Point,NPE Napier"}
PORTS = {cc + e[:3]: e[4:] for cc, row in _BY_COUNTRY.items() for e in row.split(",")}
# what crews type instead
NICK = {"SFO": "San Francisco", "SF": "San Francisco", "SAN FRAN": "San Francisco", "SF BAY": "San Francisco",
        "LAX": "Los Angeles", "LA": "Los Angeles", "LB": "Long Beach", "LGB": "Long Beach", "LA LB": "Los Angeles", "LB LA": "Los Angeles", "EUREKA CHEV": "Eureka",
        "PDX": "Portland", "OAK": "Oakland", "SEA": "Seattle", "HUENEME": "Port Hueneme", "ESMT": "El Segundo",
        "TACOMA WA": "Tacoma", "ORDERS": "Orders", "FOR ORDERS": "Orders", "TO ORDER": "Orders"}
NOBODY = {"SEA", "AT SEA", "FISHING", "NONE", "NA", "N A", "TBA", "TBN", "UNKNOWN", "HOME", "HERE", "TEST"}
# these say what she is about, not where she is bound
JOB = {"CABLE OPERATION", "CABLE RECOVERY", "CABLE LAYING", "CABLE REPAIR", "RESEARCH", "SURVEY", "TRAINING", "PATROL"}
_STATE = r"(?:CA|CALIF|CALIFORNIA|WA|OR|0R|AK|HI|BC|USA?|U S A?|CHILE|MEXICO|JAPAN|CHINA|KOREA|CANADA|PANAMA)"


def _leg(t):
    """One place, or None if it cannot be read."""
    t = re.sub(r"\(.*", "", t)                                   # 'US RCH(FRANCISCO PS)'
    t = " ".join(re.sub(r"[_,./\\*=:;]+", " ", t).split())
    if not re.search(r"[A-Z]", t) or t in NOBODY:
        return None
    if t in NICK:
        return NICK[t]
    if t in JOB:
        return t.title()
    words = t.split()
    code = t.replace(" ", "")
    if len(code) == 5 and code in PORTS:
        return PORTS[code]
    if code[:3] == "USA" and "US" + code[3:] in PORTS:           # 'USA OAK'
        return PORTS["US" + code[3:]]
    # 'USSCK STOCKTON', 'US OAK MH', 'USSFOA9': a good code with something after it
    if words[0] in PORTS:
        return PORTS[words[0]]
    if len(words) >= 2 and words[0] + words[1] in PORTS:
        return PORTS[words[0] + words[1]]
    if re.fullmatch(r"(US)?SFOA?\d{1,2}", code):                 # an anchorage in the bay
        return "San Francisco"
    if code[:2] in _BY_COUNTRY and len(code) == 6 and code[2:] in NICK:     # 'US ESMT'
        return NICK[code[2:]]
    plain = re.sub(r"(\s+" + _STATE + r")+$", "", t)
    if words[0] in _BY_COUNTRY and len(words) == 2 and len(words[1]) >= 5:  # 'US ASTORIA'
        plain = words[1]
    if plain in NICK:
        return NICK[plain]
    # a name in words: letters only, no leftover berth numbers, long enough not to be a code
    if re.fullmatch(r"[A-Z]{2} [A-Z]{3}", plain):                # 'UX OAK': a code with a slip in it
        return None
    if re.fullmatch(r"[A-Z][A-Z' -]{3,}", plain) and re.search(r"[AEIOUY]", plain) \
            and not (len(plain.replace(" ", "")) == 5 and plain.replace(" ", "")[:2] in _BY_COUNTRY and (" " in plain or plain not in WORDS5)):
        return plain.strip().title()
    return None


# five-letter place names that happen to begin like a country code
WORDS5 = {"TOKYO", "BUSAN", "RODEO", "CHIBA", "ULSAN", "KOBE", "INCHON", "COOS", "USHUA", "CAIRO", "PALAU", "PATEA", "IDAHO", "AUKRA", "CALLAO"}


def clean_dest(raw):
    """The place she is bound for, or "Sea" when she has not said in a way anyone could read."""
    if not raw or not isinstance(raw, str):
        return "Sea"
    t = raw.upper().replace("=>", ">").strip("* >")
    if ">" not in t and re.fullmatch(r"[A-Z]{2}[ _]?[A-Z]{3}\s*-\s*[A-Z]{2}[ _]?[A-Z]{3}", t):
        t = t.replace("-", ">")                                  # 'US LGB-CA RTB'
    t = t.split(">")[-1].strip()                                 # keep the *to* leg of A>B
    if t.startswith("FOR ") and t != "FOR ORDERS":               # the caption already says FOR
        t = t[4:].strip()
    return _leg(t) or "Sea"
