# MFFMv14 স্ক্রিপ্ট ব্যবহার নির্দেশিকা (`build.py` ও `update.py`) - বাংলা সংস্করণ

এই নথিতে **MFFMv14**-এর পাইথন কম্পাইলেশন স্ক্রিপ্টগুলোর বিস্তারিত কমান্ড-লাইন রেফারেন্স, ফিচার বিবরণী, ফ্ল্যাগ আর্গুমেন্ট তালিকা, ইনস্টলেশন প্রক্রিয়া এবং ব্যবহারের উদাহরণ প্রদান করা হলো:
১. `build.py`: সোর্স ফন্ট থেকে ফ্ল্যাশেবল Magisk/KernelSU/APatch ফন্ট মডিউল তৈরির মূল কম্পাইলার।
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

## ১. `build.py` — ফন্ট মডিউল কম্পাইলার

### বিবরণ
`build.py` স্ক্রিপ্টটি `Fonts/` ডিরেক্টরিতে থাকা স্ট্যাটিক বা ভ্যারিয়েবল ফন্ট ফাইলগুলো (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) প্রসেস করে অ্যান্ড্রয়েডের জন্য ফ্ল্যাশেবল ফন্ট মডিউল তৈরি করে।

### প্রধান সুবিধাসমূহ
- **অটো-ডিটেকশন**: ইনপুট ফন্টগুলো স্ট্যাটিক নাকি ভ্যারিয়েবল (`fvar` টেবিল উপস্থিতি) তা স্বয়ংক্রিয়ভাবে শনাক্ত করে।
- **ওপেনটাইপ ফিচার ফ্রিজার (`pyftfeatfreeze`)**: ফন্টে থাকা Stylistic Sets (`ss01`–`ss20`) এবং Character Variants (`cv01`–`cv99`) টার্মিনালে তালিকা আকারে দেখায়, ভিজ্যুয়াল প্রিভিউ দেখার জন্য লিংক (https://www.adamjagosz.com/bulletproof/lettering) প্রদান করে এবং ব্যবহারকারীর পছন্দের ফিচারগুলো ফন্টে স্থায়ীভাবে ফ্রিজ করে।
- **ডাইনামিক ফাইলিং ও মেটাডাটা ট্যাগিং**: মডিউলে প্রয়োগ করা ফিচার ট্যাগগুলো (যেমন `(ss02, cv11)`) `module.prop`-এর নাম এবং আউটপুট `.zip` ফাইলনেমে স্বয়ংক্রিয়ভাবে যুক্ত করে।
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
| `--features` | `<TAGS>` | কমা দ্বারা পৃথক করা ফ্রিজ করার ফিচার ট্যাগ (যেমন `'ss01,cv01'`) | None |
| `--interactive` | *Flag* | জোরপূর্বক ইন্টারেক্টিভ প্রম্পট চালু রাখা | False |
| `--no-interactive` | *Flag* | ইন্টারেক্টিভ প্রম্পট বন্ধ রাখা | False |
| `--keep-hinting` | *Flag* | মূল ট্রুটাইপ হিন্টিং টেবিলগুলো (`cvt`, `fpgm` ইত্যাদি) বজায় রাখা | False (হিন্টিং রিমুভ করা হয়) |
| `--no-prefix` | *Flag* | ইন্টারনাল ফন্ট ফ্যামিলি নামের আগে `MFFM` যুক্ত না করা | False (`MFFM` যুক্ত করা হয়) |
| `--no-zip` | *Flag* | জিপ না বানিয়ে `Files/` ফোল্ডারে পেলোড ফাইল প্রস্তুত করা | False |
| `--no-sign` | *Flag* | আনসাইনড ডিবাগিং ZIP তৈরি করা | False (সাইন করা হয়) |

---

### `build.py` ব্যবহারের উদাহরণ

#### উদাহরণ ১: স্ট্যান্ডার্ড ইন্টারেক্টিভ বিল্ড
ডিপেন্ডেন্সি ইনস্টল করার পর কোনো ফ্ল্যাগ ছাড়া সরাসরি চালান:
```bash
pip install -r requirements.txt
python build.py
```
**টার্মিনাল প্রম্পট আউটপুট:**
```text
------------------------------------------------------------
OpenType Feature Freezer Tool Integration
------------------------------------------------------------
Do you want to use any Stylistic Sets (for example ss01 Open digits), or Character Variants (for example cv01 Alternate One)? (y/N): y

Available Stylistic Sets and Character Variants:
  cv01  -  Alternate one
  cv11  -  Single-story a
  ss01  -  Open digits
  ss02  -  Disambiguation

[Visual Preview]
For visual representation of available sets, visit:
https://www.adamjagosz.com/bulletproof/lettering and upload your font.
------------------------------------------------------------

Enter your desired entries (comma or space separated, e.g. ss01, cv01): ss02, cv11
Selected features to freeze: ss02, cv11
Successfully froze features [ss02,cv11] in InterVariable.ttf
Detected mode : variable
Font family   : Inter Variable
Freezer sets  : ss02, cv11
Source faces  : 2
Payload fonts : DroidSans.ttf, DroidSans-Bold.ttf
Signature     : verified
Output        : C:\Users\Admin\Desktop\MFFMv14\dist\mffm14-Inter-Variable-VF-ss02-cv11-2026.07.30.zip
```

#### উদাহরণ ২: নির্দিষ্ট ফিচারসহ নন-ইন্টারেক্টিভ বিল্ড
সরাসরি ফ্ল্যাগ ব্যবহার করে কমান্ড লাইনের মাধ্যমে বিল্ড করতে:
```bash
python build.py --features "ss02,ss03,cv11"
```
**আউটপুট ফাইল:** `dist/mffm14-Inter-Variable-VF-ss02-ss03-cv11-YYYY.MM.DD.zip`

#### উদাহরণ ৩: কাস্টম নাম, ভার্সন ও আনসাইনড বিল্ড
```bash
python build.py --name "Custom Sans" --version "1.0.0" --version-code 100 --no-sign
```

---

## ২. `update.py` — পুরনো মডিউল মাইগ্রেশন টুল

### বিবরণ
`update.py` ডিরেক্টরি `Old Modules/`-এ থাকা পুরনো MFFM জিপ মডিউলগুলোকে এক্সট্র্যাক্ট করে নতুন MFFMv14 কোরে আপডেট করে এবং `Updated Modules/` ফোল্ডারে সাইন করা নতুন ZIP আউটপুট দেয়।

---

### কমান্ড-লাইন আর্গুমেন্ট ও ফ্ল্যাগসমূহ

| ফ্ল্যাগ (Flag) | আর্গুমেন্ট | বিবরণ | ডিফল্ট |
| :--- | :--- | :--- | :--- |
| `--old-dir` | `<PATH>` | পুরনো জিপ মডিউল থাকা ডিরেক্টরি | `Old Modules/` |
| `--output-dir` | `<PATH>` | আপডেট করা মডিউল সংরক্ষণের ডিরেক্টরি | `Updated Modules/` |
| `--mode` | `auto`, `static`, `variable` | ফন্ট কম্পাইলেশন মোড | `auto` |
| `--name` | `<STRING>` | আপডেট করা মডিউলগুলোর কাস্টম নাম | পুরনো মডিউলের নাম |
| `--version` | `<STRING>` | কাস্টম ভার্সন স্ট্রিং | বর্তমান তারিখ |
| `--version-code` | `<NUMBER>` | কাস্টম নিউমেরিক `versionCode` | বর্তমান টাইমস্ট্যাম্প |
| `--no-sign` | *Flag* | আনসাইনড জিপ তৈরি করা | False (সাইন করা হয়) |
| `--keep-hinting` | *Flag* | সোর্স ফন্টের হিন্টিং সরিয়ে না ফেলা | False |
| `--no-prefix` | *Flag* | ফ্যামিলি নেমে `MFFM` প্রিফিক্স না দেওয়া | False |
| `--force` | *Flag* | আগের আউটপুট জিপ ফাইল ওভাররাইট করা | False |
| `--keep-temp` | *Flag* | পরীক্ষার জন্য অস্থায়ী ডিরেক্টরি মুছে না ফেলা | False |

---

### `update.py` ব্যবহারের উদাহরণ

#### উদাহরণ ১: ব্যাচ মাইগ্রেশন
`Old Modules/` ফোল্ডারে পুরনো জিপ ফাইল রেখে চালান:
```bash
python update.py
```
**আউটপুট:**
```text
Updated old-font-module.zip
  mode   : variable
  family : Roboto Flex VF
  output : C:\Users\Admin\Desktop\MFFMv14\Updated Modules\mffm14-Roboto-Flex-VF-2026.07.30.zip
Updated 1 module(s).
```

#### উদাহরণ ২: ওভাররাইটসহ মাইগ্রেশন
```bash
python update.py --force
```

---

## ৩. সংক্ষেপে কমান্ড ওভারভিউ

```bash
# ০. প্রয়োজনীয় ডিপেন্ডেন্সি ইনস্টল করা
pip install -r requirements.txt

# ১. ইন্টারেক্টিভ বিল্ড
python build.py

# ২. ফিচার ফ্রিজ করে সরাসরি বিল্ড করা
python build.py --features "ss01,cv01"

# ৩. ডিবাগিংয়ের জন্য আনসাইনড বিল্ড করা
python build.py --no-sign

# ৪. পুরনো জিপ মডিউল মাইগ্রেশন করা
python update.py
```
