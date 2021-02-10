import base64
import re

def get_china_phone_verifier():
    prefixes_china_telecom = \
        ['133', '153', '173', '177', '180', '181', '189', '191', '193',
         '199']
    prefixes_china_unicom  = \
        ['130', '131', '132', '155', '156', '166', '175', '176', '185',
         '186','166']
    prefixes_china_mobile  = \
        ['134', '135', '136', '137', '138', '139', '147', '150', '151',
         '152', '157', '158', '159', '172', '178', '182', '183', '184',
         '187', '188', '198']
    prefixes = prefixes_china_mobile  \
             + prefixes_china_unicom  \
             + prefixes_china_telecom
    pattern  = r'^\s*(?:\+?0{0,2}86\s*-?\s*)?((?:' \
             + '|'.join(prefixes)                  \
             + r')\d{8})\s*$'
    return re.compile(pattern).match

def get_email_verifier():
    pattern = base64.b64decode(
        'XlxzKigoPzpbYS16MC05ISMkJSYnKisvPT9eX2B7fH1+LV0rKD86XC5bYS16M'
        'C05ISMkJSYnKisvPT9eX2B7fH1+LV0rKSp8Iig/OlsBLQgLDA4tHyEjLVtdLX'
        '9dfFxbAS0JCwwOLX9dKSoiKUAoPzooPzpbYS16MC05XSg/OlthLXowLTktXSp'
        'bYS16MC05XSk/XC4pK1thLXowLTldKD86W2EtejAtOS1dKlthLXowLTldKT98'
        'XFsoPzooPzooMig1WzAtNV18WzAtNF1bMC05XSl8MVswLTldWzAtOV18WzEtO'
        'V0/WzAtOV0pKVwuKXszfSg/OigyKDVbMC01XXxbMC00XVswLTldKXwxWzAtOV'
        '1bMC05XXxbMS05XT9bMC05XSl8W2EtejAtOS1dKlthLXowLTldOig/OlsBLQg'
        'LDA4tHyEtWlMtf118XFsBLQkLDA4tf10pKylcXSkpXHMqJA==').decode()
    return re.compile(pattern).match

is_china_phone = get_china_phone_verifier()
is_email       = get_email_verifier()