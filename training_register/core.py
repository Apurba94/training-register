"""Training records: did people learn, and can a certificate be trusted?

Certificates carry a short code made with a keyed hash (HMAC) of their details. Changing a
name or a date changes the code, and nobody can make a valid code without the secret key.
"""
import hashlib
import hmac
import math
import secrets

ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"     # no 0, O, 1, I, L or U, so a code is easy to read aloud


def new_secret():
    return secrets.token_hex(32)


def certificate_code(secret, name, course, day, length=12):
    """A readable code, tied to these exact details."""
    text = "\x1f".join((name.strip().lower(), course.strip().lower(), day))
    digest = hmac.new(secret.encode(), text.encode(), hashlib.sha256).digest()
    n = int.from_bytes(digest, "big")
    out = ""
    for _ in range(length):
        n, r = divmod(n, len(ALPHABET))
        out += ALPHABET[r]
    return "-".join(out[i:i + 4] for i in range(0, length, 4))


def clean_code(text):
    return "".join(c for c in text.upper() if c in ALPHABET)


def verify(secret, code, name, course, day):
    return hmac.compare_digest(clean_code(certificate_code(secret, name, course, day)), clean_code(code))


def mean(v):
    return sum(v) / len(v)


def learning_gain(pre, post, top=100):
    """Hake's normalised gain: the share of the possible improvement achieved."""
    if not 0 <= pre <= top or not 0 <= post <= top:
        raise ValueError("scores must be within the test range")
    return None if pre >= top else (post - pre) / (top - pre)


def t_cdf(t, df):
    """Student's t distribution by numerical integration, which is accurate enough for reports."""
    if df < 1:
        return 0.5
    c = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
    a, steps = abs(t), 2000
    if a == 0:
        return 0.5
    h = a / steps
    f = lambda x: c * (1 + x * x / df) ** (-(df + 1) / 2)
    area = f(0) + f(a) + sum((4 if i % 2 else 2) * f(i * h) for i in range(1, steps))
    p = 0.5 + area * h / 3
    return p if t > 0 else 1 - p


def paired_summary(pairs, top=100):
    """pairs: [(pre, post)]. The evidence a donor report needs, with honest caveats built in."""
    n = len(pairs)
    if n == 0:
        return None
    diffs = [b - a for a, b in pairs]
    d = mean(diffs)
    out = {"n": n, "pre": mean([a for a, _ in pairs]), "post": mean([b for _, b in pairs]), "change": d, "improved": sum(1 for x in diffs if x > 0) / n}
    gains = [g for g in (learning_gain(a, b, top) for a, b in pairs) if g is not None]
    out["gain"] = mean(gains) if gains else None
    if n >= 2:
        sd = math.sqrt(sum((x - d) ** 2 for x in diffs) / (n - 1))
        if sd > 0:
            t = d / (sd / math.sqrt(n))
            out["t"] = t
            out["p"] = 2 * (1 - t_cdf(abs(t), n - 1))
            out["effect"] = d / sd
    return out


def gain_label(g):
    if g is None:
        return "n/a"
    return "high" if g >= 0.7 else "medium" if g >= 0.3 else "low"


def outcome(attended, sessions, post, pass_mark=60, attendance=0.8):
    """Whether a participant earns a certificate, with the reason if not."""
    if sessions == 0:
        return False, "no sessions recorded"
    if attended / sessions < attendance:
        return False, f"attended {attended} of {sessions} sessions"
    if post is None:
        return False, "no final score"
    if post < pass_mark:
        return False, f"scored {post:g}, below {pass_mark:g}"
    return True, "completed"


def reach(rows):
    """rows: dicts with sex, age_group and group. Counts for reports, split as donors usually ask."""
    out = {"total": len(rows), "by_sex": {}, "by_age": {}, "by_group": {}}
    for r in rows:
        for key, field in (("by_sex", "sex"), ("by_age", "age_group"), ("by_group", "group")):
            v = r.get(field) or "unknown"
            out[key][v] = out[key].get(v, 0) + 1
    return out
