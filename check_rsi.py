from curl_cffi import requests as _cffi_requests
_orig = _cffi_requests.Session.request
def _p(self, method, url, **kw):
    kw.setdefault("verify", False)
    return _orig(self, method, url, **kw)
_cffi_requests.Session.request = _p

import yfinance as yf

t = yf.Ticker("ASTS")
info = t.info
price  = info.get("currentPrice") or info.get("regularMarketPrice")
low52  = info.get("fiftyTwoWeekLow")
high52 = info.get("fiftyTwoWeekHigh")

pct_from_high = (price - high52) / high52 * 100
pct_above_low = (price - low52)  / low52  * 100

print(f"Precio actual   : ${price:.2f}")
print(f"52W Low         : ${low52:.2f}")
print(f"52W High        : ${high52:.2f}")
print(f"% desde 52W High: {pct_from_high:.1f}%")
print(f"% sobre 52W Low : +{pct_above_low:.1f}%")
