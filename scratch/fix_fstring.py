"""
Fix f-string backslash escape issues in the Section 9 patch.
Replaces the two problematic f-string lines that use '\u2014' inside format specs.
"""
PATH = r"c:\Users\Mahi\major\core\professional_report_generator.py"
EM = "\u2014"  # em-dash

with open(PATH, encoding="utf-8") as f:
    content = f.read()

# The two problematic lines as they appear in the file (with the escaped unicode):
# Note: in the file text, the unicode is stored as the actual character \u2014 (the em-dash)
# because the patch script wrote it as chr(0x2014) equivalent.
# Let's find and replace both f-string lines.

BAD_SD = (
    "            f\"  {'Selective disclosure':<24} {_sd_present:<14} {'" + EM + "':<8} {_sd_evidence:<32}\""
)
GOOD_SD = (
    "            \"  \" + f\"{'Selective disclosure':<24} {_sd_present:<14} \" + \"" + EM + "      \" + f\" {_sd_evidence:<32}\""
)

BAD_CTV = (
    "            f\"  {'Carbon tunnel vision':<24} {_ctv_present:<14} {'" + EM + "':<8} {_ctv_evidence:<32}\""
)
GOOD_CTV = (
    "            \"  \" + f\"{'Carbon tunnel vision':<24} {_ctv_present:<14} \" + \"" + EM + "      \" + f\" {_ctv_evidence:<32}\""
)

# Better fix: just assign the em-dash to a simple variable before the table block.
# Insert _EM_DASH = "\u2014" right before the tactic table comment and use it.
# Actually simplest: just replace the f-string expressions to avoid the issue entirely.

# Replace with plain string concatenation using a pre-set variable that's already in scope.
# We'll use a different approach: remove the format spec from the em-dash literal.
# Format the em-dash as a plain 8-char padded string outside the f-string.

GOOD_SD2 = (
    "            \"  \" + \"%-24s\" % \"Selective disclosure\" + \" \"\n"
    "            + \"%-14s\" % _sd_present + \" \"\n"
    "            + \"%-8s\" % \"\u2014\" + \" \"\n"
    "            + \"%-32s\" % _sd_evidence"
)

GOOD_CTV2 = (
    "            \"  \" + \"%-24s\" % \"Carbon tunnel vision\" + \" \"\n"
    "            + \"%-14s\" % _ctv_present + \" \"\n"
    "            + \"%-8s\" % \"\u2014\" + \" \"\n"
    "            + \"%-32s\" % _ctv_evidence"
)

count = 0

if BAD_SD in content:
    content = content.replace(BAD_SD, GOOD_SD2)
    count += 1
    print("Fixed selective disclosure row")
else:
    print("WARNING: selective disclosure bad pattern not found, searching raw...")
    # Try to print context
    idx = content.find("Selective disclosure")
    if idx >= 0:
        print(repr(content[idx-20:idx+120]))

if BAD_CTV in content:
    content = content.replace(BAD_CTV, GOOD_CTV2)
    count += 1
    print("Fixed carbon tunnel vision row")
else:
    print("WARNING: carbon tunnel vision bad pattern not found")
    idx = content.find("Carbon tunnel vision")
    if idx >= 0:
        print(repr(content[idx-20:idx+120]))

if count > 0:
    with open(PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Saved {count} fix(es) to file.")
else:
    print("No changes saved — all patterns already correct or not found.")
