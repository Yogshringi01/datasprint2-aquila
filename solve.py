import glob
import math
import os
import re
from fractions import Fraction as F
import pandas as pd

DEFAULT_BASE = '/kaggle/input/competitions/the-procurement-desk'
BASE = DEFAULT_BASE if os.path.exists(DEFAULT_BASE) else '.'
PB = (
    f'{BASE}/playbook/playbook'
    if os.path.exists(f'{BASE}/playbook/playbook')
    else f'{BASE}/playbook'
)
OUT_DIR = '/kaggle/working' if os.path.exists('/kaggle/working') else '.'

rd = lambda p: open(p, encoding='utf-8').read()
num = lambda s: int(F(s.replace(',', '')))

# 1. Dynamically parse Categories
CATEGORIES, NAME2SLUG = {}, {}
for f in glob.glob(f'{PB}/categories/*.md'):
  t, slug = rd(f), os.path.basename(f)[:-3]
  NAME2SLUG[re.search(r'# Category:\s*(.+)', t).group(1).strip().lower()] = slug
  g = lambda k: re.search(rf'\*\*{k}[^*]*:\*\*\s*₹?([\d,\.]+)', t).group(1)
  unit = re.search(r'\*\*Normalized unit:\*\*\s*(.+)', t).group(1)
  CATEGORIES[slug] = dict(
      gst=str(F(re.search(r'\*\*GST rate:\*\*\s*([\d\.]+)%', t).group(1)) / 100),
      target=num(g('Target price')),
      walkaway=num(g('Walk-away price')),
      R=num(g(r'Negotiation rounds \(R\)')),
      beta=num(g(r'Concession exponent \(β\)')),
      limit=num(g('Approval limit')),
      sub=bool(re.search(r'per (month|year)', unit)),
  )

# 2. Dynamically parse Amendments
FIELD = {
    'target price': 'target',
    'walk-away price': 'walkaway',
    'approval limit': 'limit',
}
AMENDMENTS = []
for f in sorted(glob.glob(f'{PB}/amendments/*.md')):
  t = rd(f)
  date = re.search(r'Effective from:\*\*\s*(\d{4}-\d{2}-\d{2})', t).group(1)
  m = re.search(
      r'the (target price|walk-away price|approval limit) for (.+?) is now'
      r' ₹([\d,\.]+)',
      t,
  )
  AMENDMENTS.append((
      date,
      NAME2SLUG[m.group(2).strip().lower()],
      FIELD[m.group(1)],
      num(m.group(3)),
  ))
AMENDMENTS.sort(key=lambda a: (a[0]))

# 3. Dynamically parse Suppliers (supports multiple caps/fx per supplier)
SUPPLIERS = {}
for f in glob.glob(f'{PB}/suppliers/*.md'):
  t = rd(f)
  name = re.search(r'# Supplier:\s*(.+)', t).group(1).strip()
  st = re.search(r'\*\*Status:\*\*\s*(\w+)', t).group(1).upper()
  info = {
      'status': (
          'BLACKLISTED'
          if st == 'BLACKLISTED'
          else 'PROBATION' if st == 'PROBATION' else 'Approved'
      ),
      'caps': {
          NAME2SLUG[m.group(1).strip().lower()]: num(m.group(2))
          for m in re.finditer(r'price cap for (.+?) of ₹([\d,\.]+)', t)
      },
      'fx': {
          m.group(1): m.group(2).replace(',', '')
          for m in re.finditer(
              r'invoices in (\w+) are converted at ₹([\d,\.]+)', t
          )
      },
  }
  SUPPLIERS[name] = info

print(
    f'Parsed: {len(CATEGORIES)} categories, {len(AMENDMENTS)} amendments,'
    f' {len(SUPPLIERS)} suppliers'
)

W = dict(
    zero=0,
    one=1,
    two=2,
    three=3,
    four=4,
    five=5,
    six=6,
    seven=7,
    eight=8,
    nine=9,
    ten=10,
    eleven=11,
    twelve=12,
    thirteen=13,
    fourteen=14,
    fifteen=15,
    sixteen=16,
    seventeen=17,
    eighteen=18,
    nineteen=19,
    twenty=20,
    thirty=30,
    forty=40,
    fifty=50,
    sixty=60,
    seventy=70,
    eighty=80,
    ninety=90,
)
SC = {
    'thousand': 10**3,
    'lakh': 10**5,
    'lakhs': 10**5,
    'lac': 10**5,
    'lacs': 10**5,
    'crore': 10**7,
}


def words_to_num(s):
  tokens = [
      w for w in re.split(r'[\s-]+', s.lower().strip()) if w and w != 'and'
  ]
  if not tokens:
    return None
  total = cur = 0
  for w in tokens:
    if w in W:
      cur += W[w]
    elif w == 'hundred':
      cur = (cur or 1) * 100
    elif w in SC:
      total += (cur or 1) * SC[w]
      cur = 0
    else:
      return None
  return total + cur


AMT = re.compile(
    r'(?<![A-Za-z])(?P<cur>US\$|\$|₹|Rs\.?|INR|USD|€|EUR|£|GBP)\s*'
    r'(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<suf>lakhs?|lacs?|crore|k)?(?![A-Za-z])',
    re.I,
)
SUF = {
    'lakh': 10**5,
    'lakhs': 10**5,
    'lac': 10**5,
    'lacs': 10**5,
    'crore': 10**7,
    'k': 1000,
}
CODE = {
    '₹': 'INR',
    'RS': 'INR',
    'INR': 'INR',
    '$': 'USD',
    'US$': 'USD',
    'USD': 'USD',
    '€': 'EUR',
    'EUR': 'EUR',
    '£': 'GBP',
    'GBP': 'GBP',
}
TABLE = {'INR': F(1), 'USD': F('84.5'), 'EUR': F(91), 'GBP': F(106)}
UNSUPPORTED = re.compile(
    r'(?<![A-Za-z])(?:S|A|C|NZ|HK)\$|[¥₩₽]|\b(?:SGD|AUD|CAD|JPY|AED|CHF|CNY|RMB|SEK|NZD|HKD|ZAR|KRW|NOK|DKK|MYR|THB|IDR|SAR|QAR|BRL|MXN|PLN|TRY|RUB)\b'
)
WORD_RUPEES = re.compile(
    r'\b((?:(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|lakhs?|lacs?|crore|and)[\s-]+)+)rupees\b',
    re.I,
)
DEVANAGARI = re.compile(r'[\u0900-\u097F]')


def amt_inr(m, sup_info):
  code = CODE[m.group('cur').upper().rstrip('.')]
  rate = (
      F(sup_info['fx'][code])
      if code in sup_info.get('fx', {})
      else TABLE[code]
  )
  return (
      F(m.group('num').replace(',', ''))
      * SUF.get((m.group('suf') or '').lower(), 1)
      * rate
  )


def get_latest_message(thread_text):
  marker = '[Latest message'
  if marker in thread_text:
    idx = thread_text.rfind(marker)
    nl = thread_text.find('\n', idx)
    return thread_text[nl + 1 :].strip() if nl != -1 else thread_text[idx:]
  return thread_text.strip()


def get_previous_supplier_quotes(thread_text, supplier):
  blocks = re.split(r'\[Earlier message\s*[—-]\s*', thread_text)
  quotes = []
  for b in blocks[1:]:
    if b.startswith(supplier):
      nl = b.find('\n')
      quotes.append(b[nl + 1 :].split('[')[0].strip())
  return quotes


def L_exact(cfg, rnd, probation):
  t, w = F(cfg['target']), F(cfg['walkaway'])
  if probation:
    return t
  ratio = min(F(1), F(rnd - 1, cfg['R'] - 1))
  return t + (w - t) * ratio ** cfg['beta']


def round_half_up(x):
  return math.floor(x + F(1, 2))


def extract_offer_price(msg, cat, qty, sup_info, prev_quotes=None):
  m_corr = re.search(r'should\s+read\s+([^\n]+)', msg, re.I)
  price_text = re.split(r',?\s+not\s', m_corr.group(1))[0] if m_corr else msg
  if UNSUPPORTED.search(price_text):
    return None, 'UNSUPPORTED_CURRENCY'

  m_prev = re.search(
      r'(\d+(?:\.\d+)?)\s*%\s*(?:off|discount\s+on)\s+our\s+previous\s+quote',
      price_text,
      re.I,
  )
  if m_prev and prev_quotes:
    disc = F(m_prev.group(1)) / 100
    prev_p, _ = extract_offer_price(
        prev_quotes[-1], cat, qty, sup_info, prev_quotes[:-1]
    )
    if prev_p is not None:
      return prev_p * (1 - disc), None

  amts = list(AMT.finditer(price_text))
  if re.search(r'\bbetween\b', price_text, re.I) and len(amts) >= 2:
    p = max(amt_inr(amts[0], sup_info), amt_inr(amts[1], sup_info))
  else:
    m_list = re.search(
        r'(\d+(?:\.\d+)?)\s*%\s*(?:discount\s+on|off)\s+(?:our\s+)?list\s+price\s+of\s+',
        price_text,
        re.I,
    )
    if m_list and amts:
      p = amt_inr(amts[0], sup_info) * (1 - F(m_list.group(1)) / 100)
    else:
      m_tier = re.search(
          r'for\s+orders\s+of\s+up\s+to\s+(\d+)', price_text, re.I
      )
      if m_tier and len(amts) >= 2:
        p = (
            amt_inr(amts[0], sup_info)
            if qty <= int(m_tier.group(1))
            else amt_inr(amts[1], sup_info)
        )
      else:
        m_tot = re.search(r'in\s+total\s+for\s+all\s+(\d+)', price_text, re.I)
        if m_tot and amts:
          p = amt_inr(amts[0], sup_info) / int(m_tot.group(1))
        elif amts:
          p = amt_inr(amts[0], sup_info)
        else:
          m_words = WORD_RUPEES.search(price_text)
          val = words_to_num(m_words.group(1)) if m_words else None
          if not val or val <= 0:
            return None, 'NO_PRICE'
          p = F(val)

  m_free = re.search(
      r'plus\s+(\d+|[a-z]+)\s+free\s+\w+\s+for\s+every\s+(\d+|[a-z]+)\s+you\s+pay\s+for',
      msg,
      re.I,
  )
  if m_free:
    k_free = (
        int(m_free.group(1))
        if m_free.group(1).isdigit()
        else words_to_num(m_free.group(1))
    )
    n_pay = (
        int(m_free.group(2))
        if m_free.group(2).isdigit()
        else words_to_num(m_free.group(2))
    )
    if k_free and n_pay:
      p = p * F(n_pay, n_pay + k_free)

  m_vol = re.search(
      r'further\s+(\d+(?:\.\d+)?)\s*%\s*off\s+for\s+orders\s+of\s+(\d+)(?:\s+\w+)?\s+or\s+more',
      msg,
      re.I,
  )
  if m_vol and qty >= int(m_vol.group(2)):
    p = p * (1 - F(m_vol.group(1)) / 100)

  if re.search(
      r'(?:inclusive\s+of\s+(?:\d+%\s+)?GST|including\s+(?:\d+%\s+)?GST|inc\.?\s*GST|incl\.?\s*GST|\(GST\s+included\)|GST\s+included)',
      msg,
      re.I,
  ):
    p = p / (1 + F(CATEGORIES[cat]['gst']))

  if CATEGORIES[cat]['sub']:
    has_month = bool(re.search(r'per\s+mo(?:nth)?|/mo(?:nth)?|monthly', msg, re.I))
    has_year = bool(
        re.search(
            r'per\s+year|/year|/yr|yearly|annually|per\s+annum|p\.a\.', msg, re.I
        )
    )
    if not has_month and not has_year:
      return None, 'MISSING_PERIOD'
    if (
        cat in ['cloud-servers', 'crm-licenses', 'design-software']
        and has_month
    ):
      p *= 12
    elif cat in ['cleaning', 'security-guards'] and has_year:
      p /= 12

  m_pack_n = re.search(r'per\s+pack\s+of\s+(\d+)', msg, re.I)
  m_per_n = re.search(
      r'per\s+(\d+)\s+(?:shipments?|meals?|fixtures?|chairs?|phones?|monitors?|laptops?|headsets?|participants?|boxs?|boxes?)',
      msg,
      re.I,
  )
  if m_pack_n:
    p /= int(m_pack_n.group(1))
  elif m_per_n:
    p /= int(m_per_n.group(1))
  elif re.search(r'per\s+dozen', msg, re.I):
    p /= 12
  elif cat == 'led-lighting' and re.search(r'per\s+pack', msg, re.I):
    p /= 4
  elif cat == 'printer-paper' and re.search(r'per\s+ream', msg, re.I):
    p *= 10

  return p, None


def percents(s):
  out = [
      float(x)
      for x in re.findall(r'(\d+(?:\.\d+)?)\s*(?:%|per\s?cent|percent)', s)
  ]
  for m in re.finditer(
      r'([a-z]+(?:[\s-][a-z]+)?)\s+(?:per\s?cent|percent)', s
  ):
    v = words_to_num(m.group(1)) or words_to_num(m.group(1).split()[-1])
    if v is not None:
      out.append(float(v))
  return out


def check_banned_terms(latest):
  t = latest.lower()
  t = re.sub(
      r'\b(no|not|without|never)\s+(any\s+)?(automatic(ally)?[\s-]*renew\w*|auto[\s-]*renew\w*)',
      ' ',
      t,
  )
  t = re.sub(r'renewal\s+only\s+(if|by|with|upon)[^.;\n]*', ' ', t)
  t = re.sub(r'(not\s+asking\s+for|no|without)\s+(any\s+)?exclusiv\w*', ' ', t)
  if re.search(
      r'auto[\s-]*renew|automatic(ally)?\s+renew|renew\w*\s+automatic|renews?\s+on\s+its\s+own|(continues?|rolls?\s+over|extends?)\s+(from\s+)?year[\s-]to[\s-]year|evergreen',
      t,
  ):
    return True
  if re.search(
      r'exclusiv|sole\s+supplier|buy\s+only\s+from|only\s+from\s+us|buy\s+these\s+items\s+only\s+from\s+us',
      t,
  ):
    return True
  if re.search(
      r'unlimited\s+liab|liab\w*\s+(is|shall\s+be)\s+unlimited|uncapped\s+liab|liability\s+under\s+this\s+contract\s+shall\s+be\s+unlimited',
      t,
  ):
    return True
  for sent in re.split(r'(?<=[.;])\s+|\n', t):
    if re.search(r'advance|up[\s-]?front|prepay', sent):
      if any(p > 30 for p in percents(sent)) or re.search(
          r'\b(full|entire|half|whole)\b', sent
      ):
        return True
  return False


INJ = [
    r'system\s+note\s+to\s+ai',
    r'language\s+model',
    r'<!--\s*assistant',
    r'pre-?approved',
    r'output\s+accept',
    r'without\s+escalation',
    r'approval\s+already\s+granted',
    r'ignore\s+(?:your\s+|all\s+)?previous\s+instructions',
    r'admin\s+override',
    r'\boverride\b',
    r'skip\s+the\s+playbook',
    r'review(?:ing|er)\s+assistant',
    r'\bbot\b',
    r'automated\s+system',
    r'already\s+signed\s+off',
    r'record\s+the\s+decision',
    r'mark\s+(?:it|this)\b[^.\n]{0,40}accept',
]


def check_prompt_injection(full_thread):
  return bool(DEVANAGARI.search(full_thread)) or any(
      re.search(p, full_thread, re.I) for p in INJ
  )


def solve_row(row):
  cat, sup, date, qty, rnd = (
      row['category'],
      row['supplier'],
      str(row['date']),
      int(row['quantity']),
      int(row['round']),
  )
  msg_full = str(row['supplier_message'])
  latest = get_latest_message(msg_full)
  prev_quotes = get_previous_supplier_quotes(msg_full, sup)

  cfg = dict(CATEGORIES[cat])
  for eff_date, a_cat, field, val in AMENDMENTS:
    if a_cat == cat and eff_date <= date:
      cfg[field] = val

  sup_info = SUPPLIERS.get(sup, {'status': 'Approved', 'caps': {}, 'fx': {}})
  if cat in sup_info.get('caps', {}):
    cfg['walkaway'] = sup_info['caps'][cat]

  p, err = extract_offer_price(latest, cat, qty, sup_info, prev_quotes)
  if err is not None or p is None:
    return 'ESCALATE:MISSING_INFO:'
  if sup_info['status'] == 'BLACKLISTED':
    return 'REJECT:BLACKLISTED_SUPPLIER:'
  if check_prompt_injection(msg_full):
    return 'ESCALATE:PROMPT_INJECTION:'
  if check_banned_terms(latest):
    return 'ESCALATE:BANNED_TERM:'

  L_r = L_exact(cfg, rnd, sup_info['status'] == 'PROBATION')
  if p <= L_r:
    return (
        'ESCALATE:OVER_APPROVAL_LIMIT:'
        if p * qty > F(cfg['limit'])
        else 'ACCEPT:ACCEPTABLE_PRICE:'
    )
  return (
      'REJECT:ABOVE_WALKAWAY:'
      if rnd >= cfg['R']
      else f'COUNTER:COUNTER_OFFER:{round_half_up(L_r)}'
  )


if __name__ == '__main__':
  st = pd.read_csv(f'{BASE}/sample_threads.csv')
  sa = pd.read_csv(f'{BASE}/sample_answers.csv')
  df_val = st.merge(sa, on='thread_id')
  print(
      'SAMPLE ACCURACY:'
      f" {(df_val.apply(solve_row, axis=1) == df_val['label']).sum()} / 40"
  )

  threads = pd.read_csv(f'{BASE}/threads.csv')
  threads['label'] = threads.apply(solve_row, axis=1)
  out_path = os.path.join(OUT_DIR, 'submission.csv')
  threads[['thread_id', 'label']].to_csv(out_path, index=False)

  bad = []
  for _, r in threads.iterrows():
    if r.label.startswith(('ESCALATE:MISSING', 'REJECT:BLACK')):
      continue
    p, _ = extract_offer_price(
        get_latest_message(r.supplier_message),
        r.category,
        int(r.quantity),
        SUPPLIERS.get(r.supplier, {'status': 'Approved', 'caps': {}, 'fx': {}}),
        get_previous_supplier_quotes(r.supplier_message, r.supplier),
    )
    t = CATEGORIES[r.category]['target']
    if p is not None and not (0.6 * t <= p <= 2.5 * t):
      bad.append((r.thread_id, r.category, float(p)))

  print('OUT-OF-RANGE PARSES:', len(bad))
  print(threads.label.str.split(':').str[:2].str.join(':').value_counts())
  print('DONE! Saved', out_path, 'with', len(threads), 'rows.')