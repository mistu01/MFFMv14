# MFFMv14 স্ক্রিপ্ট ব্যবহার নির্দেশিকা (`build.py` ও `update.py`) - বাংলা সংস্করণ

এই নথিতে **MFFMv14**-এর পাইথন কম্পাইলেশন স্ক্রিপ্টগুলোর বিস্তারিত কমান্ড-লাইন রেফারেন্স, ইউনিভার্সাল ফিচার বিবরণী, নিরাপত্তা গাইডলাইন, ইনস্টলেশন প্রক্রিয়া এবং ব্যবহারের উদাহরণ প্রদান করা হলো:
১. `build.py`: যেকোনো সোর্স ফন্ট থেকে ফ্ল্যাশেবল Magisk/KernelSU/APatch ফন্ট মডিউল তৈরির মূল ইউনিভার্সাল কম্পাইলার।
২. `update.py`: পুরনো মডিউলগুলোকে MFFMv14 ইঞ্জিনে রূপান্তর করার ব্যাচ মাইগ্রেশন টুল।

---

## ০. পূর্বশর্ত ও ইনস্টলেশন

আপনার সিস্টেমে Python 3.9 বা তার পরবর্তী সংস্করণ ইনস্টল থাকা আবশ্যক। বিল্ড বা আপডেট স্ক্রিপ্ট চালানোর আগে টার্মিনালে নিচের কমান্ডটি দিয়ে প্রয়োজনীয় লাইব্রেরিগুলো ইনস্টল করুন:

```bash
pip install -r requirements.txt
```

### অন্তর্ভুক্ত ডিপেন্ডেন্সিসমূহ (`requirements.txt`)
- `fonttools>=4.55` (ফন্ট টেবিল পার্সিং ও মডিফিকেশন)
- `cryptography>=43.0` (সিকিউরিটি কি এবং ZIP সাইনিং)
- `brotli` (WOFF2 ফন্ট ডিকম্প্রেশন)
- `opentype-feature-freezer` (`pyftfeatfreeze` ফিচার ফ্রিজিং টুল)

*(ঐচ্ছিক alternative pipx এর মাধ্যমে)*:
```bash
pipx install opentype-feature-freezer
```

---

## ১. `build.py` — ইউনিভার্সাল ফন্ট মডিউল কম্পাইলার

### বিবরণ
`build.py` স্ক্রিপ্টটি `Fonts/` ডিরেক্টরিতে থাকা যেকোনো ফন্ট ফ্যামিলির (Roboto, Google Sans, Inter, Fira Code, JetBrains Mono, Atkinson ইত্যাদি) স্ট্যাটিক বা ভ্যারিয়েবল ফন্ট ফাইলগুলো (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) প্রসেস করে অ্যান্ড্রয়েডের জন্য ফ্ল্যাশেবল ফন্ট মডিউল তৈরি করে।

### প্রধান সুবিধাসমূহ
- **ইউনিভার্সাল ফন্ট সাপোর্ট**: যেকোনো ফন্টের স্ট্যাটিক বা ভ্যারিয়েবল মোড স্বয়ংক্রিয়ভাবে শনাক্ত ও রূপান্তর করে।
- **সম্পূর্ণ ওপেনটাইপ লেআউট ফিচার ফ্রিজার (`pyftfeatfreeze`)**: ফন্টে থাকা **সকল** ওপেনটাইপ লেআউট ফিচার (Stylistic Sets `ss01`–`ss20`, Character Variants `cv01`–`cv99`, `zero` Slashed Zero, `tnum` Tabular Figures, `pnum`, `salt`, `case`, `dlig` ইত্যাদি) স্বয়ংক্রিয়ভাবে খুঁজে বের করে ৩টি নিরাপত্তা বিভাগে বিভক্ত করে প্রদর্শন করে, প্রিভিউ লিংক (https://www.adamjagosz.com/bulletproof/lettering ও https://wakamaifondue.com/) প্রদান করে এবং ফন্টে স্থায়ীভাবে ফ্রিজ করে:
  - **[RECOMMENDED / SAFE TO FREEZE] (ব্যবহার করা সম্পূর্ণ নিরাপদ)**: Stylistic Sets (`ss01`..`ss20`), Character Variants (`cv01`..`cv99`), Slashed Zero (`zero`), Tabular Figures (`tnum`), Proportional Figures (`pnum`), Stylistic Alternates (`salt`), Case-Sensitive Forms (`case`), Discretionary Ligatures (`dlig`)।
  - **[CAUTION - USE WITH CARE] (সাবধানতার সাথে ব্যবহার্য)**: পজিশন বা লেআউট ফিচার (`frac` ভগ্নাংশ, `numr`, `dnom`, `subs`, `sups`, `sinf`, `ordn`) যা চালু করলে সমগ্র সিস্টেম লেখার সকল সংখ্যা ছোট হয়ে বা সাবস্ক্রিপ্ট/ভগ্নাংশে পরিণত হয়ে যেতে পারে!
  - **[NOT RECOMMENDED / UNSAFE & SYSTEM FEATURES] (ব্যবহার না করার পরামর্শ)**: মাস্টার ওভাররাইড ফিচার যেমন `aalt` (Access All Alternates - যা একসাথে সকল বিকল্প ফন্ট স্টাইল এলোমেলোভাবে সক্রিয় করে দেয়) এবং লেআউট ইঞ্জিনের ডিফল্ট ফিচারসমূহ (`calt`, `kern`, `liga`, `ccmp`, `locl`)।
- **সেন্টার্ড কোলন ফিচার শনাক্তকরণ ও জেনারেশন**: ইনপুট ফন্টে ঘড়ি বা সময় প্রদর্শনের (যেমন `12:30`) জন্য সেন্টার্ড কোলন (`colon.case`) ফিচার আছে কিনা স্বয়ংক্রিয়ভাবে পরীক্ষা করে। অনুপস্থিত থাকলে ব্যবহারকারীকে তা যুক্ত করার প্রস্তাব দেয়।
- **ডাইনামিক ফাইলিং ও মেটাডাটা ট্যাগিং**: মডিউলে প্রয়োগ করা ফিচার ট্যাগগুলো (যেমন `(ss02, cv11)`, `(zero, tnum)`) `module.prop`-এর নাম এবং আউটপুট `.zip` ফাইলনেমে স্বয়ংক্রিয়ভাবে যুক্ত করে।
- **অটো-সাইনিং**: তৈরি হওয়া ZIP ফাইলগুলো `zipsigner_auto.py`-এর মাধ্যমে স্বয়ংক্রিয়ভাবে সাইন করে।

---

### কমান্ড-লাইন আর্গুমেন্ট ও ফ্ল্যাগসমূহ

| ফ্ল্যাগ (Flag) | আর্গুমেন্ট | বিবরণ | ডিফল্ট |
| :--- | :--- | :--- | :--- |
| `--fonts-dir` | `<PATH>` | সোর্স ফন্ট ফোল্ডারের পাথ (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) | `Fonts/` |
| `--mode` | `auto`, `static`, `variable` | ফন্ট কম্পাইলেশন মোড | `auto` |
| `--name` | `<STRING>` | মডিউলের কাস্টম ডিসপ্লে নাম | ফন্ট থেকে এক্সট্র্যাক্ট করা নাম |
| `--version` | `<STRING>` | কাস্টম ভার্সন স্ট্রিং | বর্তমান তারিখ `YYYY.MM.DD` |
| `--version-code` | `<NUMBER>` | কাস্টম নিউমেরিক `versionCode` | `YYYYMMDDHHMM` |
| `--output-dir` | `<PATH>` | আউটপুট `.zip` ফাইল সংরক্ষণের ডিরেক্টরি | `dist/` |
| `--features` | `<TAGS>` | কমা দ্বারা পৃথক করা ফ্রিজ করার ফিচার ট্যাগ (যেমন `'zero,tnum,ss01,cv01'`) | None |
| `--centered-colon` | *Flag* | সময় বা ঘড়ি প্রদর্শনের জন্য সেন্টার্ড কোলন (`12:30`) ইনজেক্ট করা | False |
| `--no-centered-colon` | *Flag* | সেন্টার্ড কোলন ইনজেকশন বন্ধ রাখা | False |
| `--interactive` | *Flag* | জোরপূর্বক ইন্টারেক্টিভ প্রম্পট চালু রাখা | False |
| `--no-interactive` | *Flag* | ইন্টারেক্টিভ প্রম্পট বন্ধ রাখা | False |
| `--keep-hinting` | *Flag* | মূল ট্রুটাইপ হিন্টিং টেবিলগুলো (`cvt`, `fpgm` ইত্যাদি) বজায় রাখা | False (হিন্টিং রিমুভ করা হয়) |
| `--no-prefix` | *Flag* | ইন্টারনাল ফন্ট ফ্যামিলি নামের আগে `MFFM` যুক্ত না করা | False (`MFFM` যুক্ত করা হয়) |
| `--no-zip` | *Flag* | জিপ না বানিয়ে `Files/` ফোল্ডারে পেলোড ফাইল প্রস্তুত করা | False |
| `--no-sign` | *Flag* | আনসাইনড ডিবাগিং ZIP তৈরি করা | False (সাইন করা হয়) |

---

### `build.py` ব্যবহারের উদাহরণ

#### উদাহরণ ১: স্ট্যান্ডার্ড ইন্টারেক্টিভ বিল্ড
ডিপেন্ডেন্সি ইনস্টল করার পর যেকোনো ফন্ট `Fonts/` ফোল্ডারে রেখে চালান:
```bash
pip install -r requirements.txt
python build.py
```
**টার্মিনাল প্রম্পট আউটপুট:**
```text
------------------------------------------------------------
OpenType Feature Freezer Tool Integration
------------------------------------------------------------
Do you want to freeze any OpenType layout features (Stylistic Sets, Character Variants, Slashed Zero, Tabular Figures, etc.)? (y/N): y

Available OpenType Layout Features:

  [RECOMMENDED / SAFE TO FREEZE] (Stylistic & Character Alternates, Digit Toggles):
    case   - Case-Sensitive Forms
    cv01   - Alternate one
    ss01   - Open digits
    ss02   - Disambiguation
    tnum   - Tabular Figures
    zero   - Slashed Zero

  [CAUTION - USE WITH CARE] (Layout/Position features - shrinks/repositions text globally):
    dnom   - Denominators (Shrinks all numbers into denominators)
    frac   - Fractions (Shrinks and repositions all numbers into fraction form)

  [NOT RECOMMENDED / SYSTEM & MASTER ALTERNATE FEATURES]:
    aalt   - Access All Alternates (UNSAFE: Enables multiple/all alternate glyphs simultaneously across font)
    calt   - Contextual Alternates (Enabled by default in font layout engines)

[Visual Preview]
For visual representation of available sets, visit:
https://www.adamjagosz.com/bulletproof/lettering and upload your font.
------------------------------------------------------------

Enter your desired entries (comma or space separated, e.g. ss01, cv01, zero, tnum): zero, tnum, ss01
Selected features to freeze: zero, tnum, ss01
Successfully froze features [zero,tnum,ss01] in YourFont.ttf
Detected mode : variable
Font family   : Your Font Family
Freezer sets  : zero, tnum, ss01
Source faces  : 1
Payload fonts : DroidSans.ttf
Signature     : verified
Output        : dist/mffm14-Your-Font-Family-zero-tnum-ss01-YYYY.MM.DD.zip
```

#### উদাহরণ ২: নির্দিষ্ট ফিচারসহ নন-ইন্টারেক্টিভ বিল্ড
সরাসরি ফ্ল্যাগ ব্যবহার করে কমান্ড লাইনের মাধ্যমে বিল্ড করতে:
```bash
python build.py --features "zero,tnum,ss01"
```
**আউটপুট ফাইল:** `dist/mffm14-Your-Font-Family-zero-tnum-ss01-YYYY.MM.DD.zip`

---

## ২. সংক্ষেপে কমান্ড ওভারভিউ

```bash
# ০. প্রয়োজনীয় ডিপেন্ডেন্সি ইনস্টল করা
pip install -r requirements.txt

# ১. যেকোনো ফন্টের জন্য ইন্টারেক্টিভ বিল্ড
python build.py

# ২. স্ল্যাশড জিরো (zero), টেবুলার ফিগার (tnum) ও স্টাইলিস্টিক ফিচার নিয়ে বিল্ড করা
python build.py --features "zero,tnum,ss01,cv01"

# ৩. ডিবাগিংয়ের জন্য আনসাইনড বিল্ড করা
python build.py --no-sign

# ৪. পুরনো জিপ মডিউল মাইগ্রেশন করা
python update.py
```
