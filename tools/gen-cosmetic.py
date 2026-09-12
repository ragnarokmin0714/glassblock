#!/usr/bin/env python3
"""Extract the generic element-hiding rules from Adblock Plus filter lists and
emit them as a plain CSS stylesheet.

Usage:
    python3 tools/gen-cosmetic.py easylist.txt easylistchina.txt > hide-generic.css

Only *generic* cosmetic rules are usable here: a rule written as `##selector`,
with no domain prefix, applies everywhere, which is exactly what a static
stylesheet injected on <all_urls> can express. Domain-scoped rules
(`example.com##selector`) and uBlock's procedural extensions (`:has-text()`,
`:upward()`, ...) are skipped -- the first would need a per-site stylesheet, the
second a DOM engine and the page-reading permission this extension refuses to
ask for.

Two details that matter:

  * A CSS selector list is all-or-nothing. One malformed selector invalidates
    the entire rule it sits in, so selectors are validated against a
    conservative grammar first and then emitted in small chunks, which bounds
    the blast radius of anything that slips through to one chunk.
  * `#@#` un-hide exceptions cannot be expressed in a static global stylesheet
    (they re-show an element on specific domains only). Selectors carrying such
    an exception anywhere in the lists are dropped entirely, which errs toward
    showing an ad rather than breaking a page.
"""

import re
import sys

CHUNK_SIZE = 100

# uBlock/ABP procedural extensions: not plain CSS, cannot be expressed here.
PROCEDURAL = re.compile(
    r":(?:-abp-)?(?:has|has-text|contains|matches-css|matches-path|matches-attr|"
    r"xpath|upward|remove|style|nth-ancestor|min-text-length|watch-attr|others)\b"
)

# Conservative CSS3 selector grammar. Anything outside this is dropped rather
# than risk emitting a rule Chrome will reject.
SAFE_SELECTOR = re.compile(
    r"""^(?:
          [A-Za-z0-9_\-\#\.\*\[\]\=\"\'\^\$\|\~\+\>\,\:\(\)\s/%!?&;@]
        )+$""",
    re.VERBOSE,
)


def balanced(sel):
    """Reject selectors with unbalanced brackets or quotes."""
    if sel.count('"') % 2 or sel.count("'") % 2:
        return False
    depth = {"[": 0, "(": 0}
    pairs = {"]": "[", ")": "("}
    for ch in sel:
        if ch in depth:
            depth[ch] += 1
        elif ch in pairs:
            depth[pairs[ch]] -= 1
            if depth[pairs[ch]] < 0:
                return False
    return not any(depth.values())


def usable(sel):
    if not sel or len(sel) > 400:
        return False
    if PROCEDURAL.search(sel):
        return False
    if sel.startswith("^") or sel.startswith("+js") or "{" in sel or "}" in sel:
        return False
    if not SAFE_SELECTOR.match(sel):
        return False
    if not balanced(sel):
        return False
    # A bare tag name would hide half the web; require some specificity.
    if re.fullmatch(r"[A-Za-z0-9]+", sel):
        return False
    return True


def collect(paths):
    generic, excepted = set(), set()
    stats = {"generic": 0, "domain_scoped": 0, "exception": 0,
             "procedural": 0, "rejected": 0}

    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("!"):
                    continue
                if "#@#" in line:
                    _, _, sel = line.partition("#@#")
                    if sel:
                        excepted.add(sel.strip())
                        stats["exception"] += 1
                    continue
                if "##" not in line:
                    continue
                prefix, _, sel = line.partition("##")
                sel = sel.strip()
                if prefix:
                    stats["domain_scoped"] += 1
                    continue
                if PROCEDURAL.search(sel) or sel.startswith("^"):
                    stats["procedural"] += 1
                    continue
                if not usable(sel):
                    stats["rejected"] += 1
                    continue
                generic.add(sel)
                stats["generic"] += 1

    generic -= excepted
    return sorted(generic), stats


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    selectors, stats = collect(sys.argv[1:])

    out = sys.stdout
    out.write("/*\n")
    out.write(" * GENERATED FILE -- do not edit by hand.\n")
    out.write(" * Regenerate with tools/update-lists.sh (or tools/gen-cosmetic.py).\n")
    out.write(" *\n")
    out.write(" * Generic element-hiding rules from EasyList / EasyList China, the ones\n")
    out.write(" * written without a domain prefix so they apply everywhere. Hand-written\n")
    out.write(" * selectors live in hide-ads.css; site-scoped ones in their own files.\n")
    out.write(f" *\n * {len(selectors)} selectors, emitted in chunks of {CHUNK_SIZE} so that one\n")
    out.write(" * selector Chrome dislikes costs a chunk rather than the whole sheet.\n")
    out.write(" */\n\n")

    for i in range(0, len(selectors), CHUNK_SIZE):
        chunk = selectors[i:i + CHUNK_SIZE]
        out.write(",\n".join(chunk))
        out.write("{display:none!important}\n\n")

    print(f"gen-cosmetic: {len(selectors)} generic selectors -> stdout; "
          f"skipped {stats['domain_scoped']} domain-scoped, "
          f"{stats['procedural']} procedural, {stats['rejected']} rejected, "
          f"{stats['exception']} exceptions honoured", file=sys.stderr)


if __name__ == "__main__":
    main()
