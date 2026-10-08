package com.mistu.mffm;

import java.io.File;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

/**
 * Fast, pure-Java OpenType / TrueType font inspector.
 * Reads font metadata, variable axes, OpenType features, unitsPerEm,
 * and detects presence of centered clock colon without external libraries.
 */
public class FontInspector {

    public static class InspectionResult {
        public String fileName = "";
        public long fileSize = 0;
        public String familyName = "Font";
        public String styleName = "Regular";
        public String fullName = "Font Regular";
        public String postScriptName = "Font-Regular";
        public int unitsPerEm = 1000;
        public boolean isVariable = false;
        public List<String> variableAxes = new ArrayList<>();
        public boolean hasCenteredColon = false;
        public String centeredColonDetails = "";
        public List<FeatureInfo> features = new ArrayList<>();
        public Set<String> allFeatureTags = new TreeSet<>();
    }

    public static class FeatureInfo {
        public final String tag;
        public final String name;
        public final String category; // "SAFE", "CAUTION", "SYSTEM"
        public final String description;

        public FeatureInfo(String tag, String name, String category, String description) {
            this.tag = tag;
            this.name = name;
            this.category = category;
            this.description = description;
        }
    }

    private static class TableRecord {
        String tag;
        long offset;
        long length;
    }

    public static InspectionResult inspect(File fontFile) {
        InspectionResult res = new InspectionResult();
        if (fontFile == null || !fontFile.exists() || fontFile.length() < 32) {
            return res;
        }

        res.fileName = fontFile.getName();
        res.fileSize = fontFile.length();

        try (RandomAccessFile raf = new RandomAccessFile(fontFile, "r")) {
            long baseOffset = 0;
            int tag1 = raf.readInt();

            // Check for TrueType Collection ('ttcf')
            if (tag1 == 0x74746366) { // 'ttcf'
                raf.readInt(); // version
                int numFonts = raf.readInt();
                if (numFonts > 0) {
                    baseOffset = raf.readInt(); // offset to first font
                    raf.seek(baseOffset);
                    tag1 = raf.readInt();
                }
            }

            int numTables = raf.readUnsignedShort();
            raf.skipBytes(6); // searchRange, entrySelector, rangeShift

            Map<String, TableRecord> tables = new LinkedHashMap<>();
            for (int i = 0; i < numTables; i++) {
                byte[] tagBytes = new byte[4];
                raf.readFully(tagBytes);
                String tag = new String(tagBytes, StandardCharsets.ISO_8859_1);
                raf.readInt(); // checkSum
                long offset = raf.readInt() & 0xFFFFFFFFL;
                long length = raf.readInt() & 0xFFFFFFFFL;

                TableRecord rec = new TableRecord();
                rec.tag = tag;
                rec.offset = offset;
                rec.length = length;
                tables.put(tag, rec);
            }

            // 1. Parse 'head' table
            if (tables.containsKey("head")) {
                TableRecord head = tables.get("head");
                raf.seek(head.offset + 18);
                int upm = raf.readUnsignedShort();
                if (upm > 0) {
                    res.unitsPerEm = upm;
                }
            }

            // 2. Parse 'name' table
            if (tables.containsKey("name")) {
                parseNameTable(raf, tables.get("name"), res);
            }

            // 3. Parse 'fvar' table (Variable Fonts)
            if (tables.containsKey("fvar")) {
                parseFvarTable(raf, tables.get("fvar"), res);
            }

            // 4. Parse 'GSUB' table (OpenType Features)
            if (tables.containsKey("GSUB")) {
                parseGsubTable(raf, tables.get("GSUB"), res);
            }

            // 5. Parse 'cmap' table for clock codepoints (U+EE01, U+2236)
            boolean cmapHasClock = false;
            if (tables.containsKey("cmap")) {
                cmapHasClock = checkCmapForClock(raf, tables.get("cmap"));
            }

            // 6. Centered colon evaluation
            // A font has centered colon if:
            // - GSUB contains "case" (Case-Sensitive Forms, standard for clock 12:30 colons between digits)
            // - cmap contains U+EE01 (Android lockscreen clock PUA) or U+2236 (Ratio)
            if (res.allFeatureTags.contains("case") || cmapHasClock) {
                res.hasCenteredColon = true;
                if (res.allFeatureTags.contains("case") && cmapHasClock) {
                    res.centeredColonDetails = "Built-in Case-Sensitive Forms ('case') & Clock PUA (U+EE01) detected in font";
                } else if (res.allFeatureTags.contains("case")) {
                    res.centeredColonDetails = "Built-in Case-Sensitive Forms ('case' feature for 12:30) detected in font";
                } else {
                    res.centeredColonDetails = "Lockscreen Clock PUA (U+EE01) detected in font";
                }
            } else {
                res.hasCenteredColon = false;
                res.centeredColonDetails = "Standard baseline colon detected. Generating centered colon for lockscreen clock is recommended.";
            }

        } catch (Exception e) {
            // In case of any binary read issues, provide safe defaults
            if (res.familyName == null || res.familyName.equals("Font")) {
                String stem = fontFile.getName();
                if (stem.contains(".")) stem = stem.substring(0, stem.lastIndexOf('.'));
                res.familyName = stem;
            }
        }

        return res;
    }

    private static void parseNameTable(RandomAccessFile raf, TableRecord nameRec, InspectionResult res) {
        try {
            raf.seek(nameRec.offset);
            int format = raf.readUnsignedShort();
            int count = raf.readUnsignedShort();
            int stringOffset = raf.readUnsignedShort();
            long storageBase = nameRec.offset + stringOffset;

            String famName1 = null;
            String famName16 = null;
            String subName2 = null;
            String subName17 = null;
            String fullName4 = null;
            String psName6 = null;

            for (int i = 0; i < count; i++) {
                raf.seek(nameRec.offset + 6 + i * 12);
                int platformID = raf.readUnsignedShort();
                int encodingID = raf.readUnsignedShort();
                int languageID = raf.readUnsignedShort();
                int nameID = raf.readUnsignedShort();
                int length = raf.readUnsignedShort();
                int offset = raf.readUnsignedShort();

                if (nameID == 1 || nameID == 2 || nameID == 4 || nameID == 6 || nameID == 16 || nameID == 17) {
                    raf.seek(storageBase + offset);
                    byte[] strBytes = new byte[length];
                    raf.readFully(strBytes);
                    String str;
                    if (platformID == 0 || platformID == 3) {
                        str = new String(strBytes, StandardCharsets.UTF_16BE).trim();
                    } else {
                        str = new String(strBytes, StandardCharsets.ISO_8859_1).trim();
                    }

                    if (!str.isEmpty()) {
                        switch (nameID) {
                            case 1:
                                if (famName1 == null || platformID == 3) famName1 = str;
                                break;
                            case 2:
                                if (subName2 == null || platformID == 3) subName2 = str;
                                break;
                            case 4:
                                if (fullName4 == null || platformID == 3) fullName4 = str;
                                break;
                            case 6:
                                if (psName6 == null || platformID == 3) psName6 = str;
                                break;
                            case 16:
                                if (famName16 == null || platformID == 3) famName16 = str;
                                break;
                            case 17:
                                if (subName17 == null || platformID == 3) subName17 = str;
                                break;
                        }
                    }
                }
            }

            if (famName16 != null) res.familyName = famName16;
            else if (famName1 != null) res.familyName = famName1;

            if (subName17 != null) res.styleName = subName17;
            else if (subName2 != null) res.styleName = subName2;

            if (fullName4 != null) res.fullName = fullName4;
            else res.fullName = res.familyName + " " + res.styleName;

            if (psName6 != null) res.postScriptName = psName6;
        } catch (Exception ignored) {}
    }

    private static void parseFvarTable(RandomAccessFile raf, TableRecord fvarRec, InspectionResult res) {
        try {
            raf.seek(fvarRec.offset);
            raf.readUnsignedShort(); // major
            raf.readUnsignedShort(); // minor
            int axesArrayOffset = raf.readUnsignedShort();
            raf.readUnsignedShort(); // reserved
            int axisCount = raf.readUnsignedShort();
            int axisSize = raf.readUnsignedShort();

            if (axisCount > 0) {
                res.isVariable = true;
                for (int i = 0; i < axisCount; i++) {
                    raf.seek(fvarRec.offset + axesArrayOffset + i * axisSize);
                    byte[] tagBytes = new byte[4];
                    raf.readFully(tagBytes);
                    String tag = new String(tagBytes, StandardCharsets.ISO_8859_1);
                    float minVal = raf.readInt() / 65536.0f;
                    float defVal = raf.readInt() / 65536.0f;
                    float maxVal = raf.readInt() / 65536.0f;

                    String axisStr = String.format(Locale.US, "%s: %.0f..%.0f (default %.0f)", tag, minVal, maxVal, defVal);
                    res.variableAxes.add(axisStr);
                }
            }
        } catch (Exception ignored) {}
    }

    private static void parseGsubTable(RandomAccessFile raf, TableRecord gsubRec, InspectionResult res) {
        try {
            raf.seek(gsubRec.offset);
            raf.readUnsignedShort(); // major
            raf.readUnsignedShort(); // minor
            raf.readUnsignedShort(); // scriptListOffset
            int featureListOffset = raf.readUnsignedShort();

            long featListBase = gsubRec.offset + featureListOffset;
            raf.seek(featListBase);
            int featureCount = raf.readUnsignedShort();

            Set<String> uniqueTags = new TreeSet<>();
            for (int i = 0; i < featureCount; i++) {
                raf.seek(featListBase + 2 + i * 6);
                byte[] tagBytes = new byte[4];
                raf.readFully(tagBytes);
                String tag = new String(tagBytes, StandardCharsets.ISO_8859_1).trim();
                if (tag.length() == 4) {
                    uniqueTags.add(tag);
                }
            }

            res.allFeatureTags.addAll(uniqueTags);

            for (String tag : uniqueTags) {
                FeatureInfo info = describeFeature(tag);
                if (info != null) {
                    res.features.add(info);
                }
            }
        } catch (Exception ignored) {}
    }

    private static boolean checkCmapForClock(RandomAccessFile raf, TableRecord cmapRec) {
        try {
            raf.seek(cmapRec.offset);
            raf.readUnsignedShort(); // version
            int numSubtables = raf.readUnsignedShort();

            for (int i = 0; i < numSubtables; i++) {
                raf.seek(cmapRec.offset + 4 + i * 8);
                int platformID = raf.readUnsignedShort();
                int encodingID = raf.readUnsignedShort();
                long subOffset = raf.readInt() & 0xFFFFFFFFL;

                raf.seek(cmapRec.offset + subOffset);
                int format = raf.readUnsignedShort();

                if (format == 4) {
                    int length = raf.readUnsignedShort();
                    raf.readUnsignedShort(); // language
                    int segCountX2 = raf.readUnsignedShort();
                    int segCount = segCountX2 / 2;
                    raf.skipBytes(6); // searchRange, entrySelector, rangeShift

                    int[] endCode = new int[segCount];
                    for (int s = 0; s < segCount; s++) {
                        endCode[s] = raf.readUnsignedShort();
                    }
                    raf.skipBytes(2); // reservedPad
                    int[] startCode = new int[segCount];
                    for (int s = 0; s < segCount; s++) {
                        startCode[s] = raf.readUnsignedShort();
                    }

                    for (int s = 0; s < segCount; s++) {
                        // Check if 0xEE01 (Android clock colon) is inside this segment
                        if (startCode[s] <= 0xEE01 && 0xEE01 <= endCode[s]) {
                            return true;
                        }
                        // Check if 0x2236 (Ratio) is inside this segment
                        if (startCode[s] <= 0x2236 && 0x2236 <= endCode[s]) {
                            return true;
                        }
                    }
                } else if (format == 12) {
                    raf.readUnsignedShort(); // reserved
                    raf.readInt(); // length
                    raf.readInt(); // language
                    int numGroups = raf.readInt();
                    for (int g = 0; g < numGroups; g++) {
                        long start = raf.readInt() & 0xFFFFFFFFL;
                        long end = raf.readInt() & 0xFFFFFFFFL;
                        raf.readInt(); // startGlyphID
                        if (start <= 0xEE01 && 0xEE01 <= end) return true;
                        if (start <= 0x2236 && 0x2236 <= end) return true;
                    }
                }
            }
        } catch (Exception ignored) {}
        return false;
    }

    private static FeatureInfo describeFeature(String tag) {
        String lower = tag.toLowerCase(Locale.US);

        // Safe & Recommended
        if (lower.startsWith("ss") && lower.length() == 4) {
            try {
                int num = Integer.parseInt(lower.substring(2));
                return new FeatureInfo(tag, "Stylistic Set " + num, "SAFE", "Alternate letterforms (ss" + String.format("%02d", num) + ")");
            } catch (Exception ignored) {}
        }
        if (lower.startsWith("cv") && lower.length() == 4) {
            try {
                int num = Integer.parseInt(lower.substring(2));
                return new FeatureInfo(tag, "Character Variant " + num, "SAFE", "Glyph alternate (cv" + String.format("%02d", num) + ")");
            } catch (Exception ignored) {}
        }
        if ("zero".equals(lower)) return new FeatureInfo(tag, "Slashed Zero", "SAFE", "Render slashed/dotted 0 instead of plain 0");
        if ("tnum".equals(lower)) return new FeatureInfo(tag, "Tabular Numbers", "SAFE", "Fixed-width digits for clocks & lists");
        if ("pnum".equals(lower)) return new FeatureInfo(tag, "Proportional Numbers", "SAFE", "Proportionally spaced digits");
        if ("lnum".equals(lower)) return new FeatureInfo(tag, "Lining Figures", "SAFE", "Full-height numbers matching capital letters");
        if ("salt".equals(lower)) return new FeatureInfo(tag, "Stylistic Alternates", "SAFE", "Secondary glyph design alternatives");
        if ("swsh".equals(lower)) return new FeatureInfo(tag, "Swashes", "SAFE", "Decorative swash glyph variants");
        if ("smcp".equals(lower)) return new FeatureInfo(tag, "Small Capitals", "SAFE", "Small capital letters for lowercase");
        if ("c2sc".equals(lower)) return new FeatureInfo(tag, "Capitals to Small Caps", "SAFE", "Small capitals from uppercase");

        // Caution
        if ("frac".equals(lower)) return new FeatureInfo(tag, "Fractions", "CAUTION", "Shrinks number sequences globally (e.g. 1/2)");
        if ("numr".equals(lower)) return new FeatureInfo(tag, "Numerators", "CAUTION", "Shrinks letters/numbers into superior position");
        if ("dnom".equals(lower)) return new FeatureInfo(tag, "Denominators", "CAUTION", "Shrinks letters/numbers into inferior position");
        if ("subs".equals(lower)) return new FeatureInfo(tag, "Subscript", "CAUTION", "Shrinks text into lower subscript position");
        if ("sups".equals(lower)) return new FeatureInfo(tag, "Superscript", "CAUTION", "Shrinks text into upper superscript position");
        if ("sinf".equals(lower)) return new FeatureInfo(tag, "Scientific Inferiors", "CAUTION", "Shrinks numbers to bottom baseline");
        if ("ordn".equals(lower)) return new FeatureInfo(tag, "Ordinals", "CAUTION", "Raised ordinal indicators (1st, 2nd)");
        if ("onum".equals(lower)) return new FeatureInfo(tag, "Oldstyle Figures", "CAUTION", "Varying baseline numbers (some with descenders)");

        // System
        if ("case".equals(lower)) return new FeatureInfo(tag, "Case-Sensitive Forms", "SYSTEM", "Centered punctuation and clock colons");
        if ("kern".equals(lower)) return new FeatureInfo(tag, "Kerning", "SYSTEM", "Character pair spacing adjustments");
        if ("liga".equals(lower)) return new FeatureInfo(tag, "Standard Ligatures", "SYSTEM", "Standard letter pairs (fi, fl)");
        if ("calt".equals(lower)) return new FeatureInfo(tag, "Contextual Alternates", "SYSTEM", "Context-dependent glyph substitution");

        return null;
    }
}
