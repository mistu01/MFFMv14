package com.mistu.mffm;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

public class MainActivity extends Activity {
    private static final int REQUEST_PICK_SANS = 1001;
    private static final int REQUEST_PICK_MONO = 1002;
    private static final int REQUEST_PICK_SERIF = 1003;
    private static final int REQUEST_PICK_BENGALI = 1004;

    static class FontItem {
        final Uri uri;
        final String name;
        final long size;

        FontItem(Uri uri, String name, long size) {
            this.uri = uri;
            this.name = name;
            this.size = size;
        }
    }

    // Selected Fonts per category
    private final List<FontItem> sansFonts = new ArrayList<>();
    private final List<FontItem> monoFonts = new ArrayList<>();
    private final List<FontItem> serifFonts = new ArrayList<>();
    private final List<FontItem> bengaliFonts = new ArrayList<>();

    // Primary Sans UI (Step 1)
    private Button btnBrowseSans;
    private LinearLayout layoutSansInfo;
    private TextView tvSansSummary;
    private TextView tvSansFiles;
    private Button btnClearSans;
    private TextView tvNoSans;
    private LinearLayout layoutInspectionBadge;
    private TextView tvInspectFamily;
    private TextView tvInspectDetails;

    // Optional Families Accordion
    private LinearLayout layoutOptionalToggle;
    private TextView tvOptionalArrow;
    private LinearLayout layoutOptionalFamilies;

    // Monospace UI
    private Button btnBrowseMono;
    private LinearLayout layoutMonoInfo;
    private TextView tvMonoSummary;
    private Button btnClearMono;

    // Serif UI
    private Button btnBrowseSerif;
    private LinearLayout layoutSerifInfo;
    private TextView tvSerifSummary;
    private Button btnClearSerif;

    // Bengali UI
    private Button btnBrowseBengali;
    private LinearLayout layoutBengaliInfo;
    private TextView tvBengaliSummary;
    private Button btnClearBengali;

    // Unlocked Steps Container
    private LinearLayout layoutUnlockedSteps;

    // Step 2: Centered Clock Colon & Live Preview
    private LinearLayout layoutColonDetectionBadge;
    private TextView tvColonBadgeTitle;
    private TextView tvColonBadgeDesc;
    private CheckBox cbCenteredColon;
    private LinearLayout layoutColonControls;
    private RadioGroup rgColonAlignment;
    private RadioButton rbAlignCenter;
    private RadioButton rbAlignCap;
    private RadioButton rbAlignX;
    private RadioGroup rgColonRule;
    private RadioButton rbRuleBetween;
    private RadioButton rbRuleAfter;
    private RadioButton rbRuleAlways;
    private TextView tvColonOffsetVal;
    private SeekBar seekColonOffset;
    private Button btnOffsetMinus10;
    private Button btnOffsetMinus2;
    private Button btnOffsetReset;
    private Button btnOffsetPlus2;
    private Button btnOffsetPlus10;

    // Live Clock Preview
    private Button btnTime1230;
    private Button btnTime1008;
    private Button btnTime0715;
    private Button btnTime2359;
    private TextView tvClockHour;
    private TextView tvClockColon;
    private TextView tvClockMinute;
    private TextView tvSampleText;

    // Step 3: OpenType Feature Freezer
    private LinearLayout layoutFeatureChips;
    private TextView tvNoFeatures;
    private EditText etFeatures;

    // Step 4: Harmonization & Metrics
    private CheckBox cbEqualizeDigits;
    private CheckBox cbPuaColon;
    private CheckBox cbSyntheticItalic;
    private RadioGroup rgMetrics;
    private RadioButton rbMetricsCompact;
    private RadioButton rbMetricsSafe;
    private RadioButton rbMetricsPreserve;
    private CheckBox cbSubset;
    private TextView tvTrackingVal;
    private SeekBar seekTracking;

    // Step 5: Module Metadata & Build
    private EditText etModuleName;
    private EditText etAuthor;
    private Button btnBuild;

    // Progress & Success & Console
    private LinearLayout layoutProgress;
    private ProgressBar progressBar;
    private TextView tvStatus;
    private LinearLayout layoutSuccess;
    private TextView tvSuccessDetails;
    private Button btnOpenFolder;
    private Button btnShareModule;
    private Button btnFlashRoot;
    private LinearLayout layoutConsoleCard;
    private ScrollView scrollConsole;
    private TextView tvConsole;

    // State & Font Inspection Cache
    private FontInspector.InspectionResult currentInspection = null;
    private Typeface currentTypeface = null;
    private File previewFontFile = null;
    private File lastGeneratedZip = null;
    private Uri lastSavedDownloadUri = null;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        setupListeners();
    }

    private void initViews() {
        // Step 1: Fonts
        btnBrowseSans = findViewById(R.id.btn_browse_sans);
        layoutSansInfo = findViewById(R.id.layout_sans_info);
        tvSansSummary = findViewById(R.id.tv_sans_summary);
        tvSansFiles = findViewById(R.id.tv_sans_files);
        btnClearSans = findViewById(R.id.btn_clear_sans);
        tvNoSans = findViewById(R.id.tv_no_sans);
        layoutInspectionBadge = findViewById(R.id.layout_inspection_badge);
        tvInspectFamily = findViewById(R.id.tv_inspect_family);
        tvInspectDetails = findViewById(R.id.tv_inspect_details);

        layoutOptionalToggle = findViewById(R.id.layout_optional_toggle);
        tvOptionalArrow = findViewById(R.id.tv_optional_arrow);
        layoutOptionalFamilies = findViewById(R.id.layout_optional_families);

        btnBrowseMono = findViewById(R.id.btn_browse_mono);
        layoutMonoInfo = findViewById(R.id.layout_mono_info);
        tvMonoSummary = findViewById(R.id.tv_mono_summary);
        btnClearMono = findViewById(R.id.btn_clear_mono);

        btnBrowseSerif = findViewById(R.id.btn_browse_serif);
        layoutSerifInfo = findViewById(R.id.layout_serif_info);
        tvSerifSummary = findViewById(R.id.tv_serif_summary);
        btnClearSerif = findViewById(R.id.btn_clear_serif);

        btnBrowseBengali = findViewById(R.id.btn_browse_bengali);
        layoutBengaliInfo = findViewById(R.id.layout_bengali_info);
        tvBengaliSummary = findViewById(R.id.tv_bengali_summary);
        btnClearBengali = findViewById(R.id.btn_clear_bengali);

        // Unlocked Container
        layoutUnlockedSteps = findViewById(R.id.layout_unlocked_steps);

        // Step 2: Colon & Preview
        layoutColonDetectionBadge = findViewById(R.id.layout_colon_detection_badge);
        tvColonBadgeTitle = findViewById(R.id.tv_colon_badge_title);
        tvColonBadgeDesc = findViewById(R.id.tv_colon_badge_desc);
        cbCenteredColon = findViewById(R.id.cb_centered_colon);
        layoutColonControls = findViewById(R.id.layout_colon_controls);
        rgColonAlignment = findViewById(R.id.rg_colon_alignment);
        rbAlignCenter = findViewById(R.id.rb_align_center);
        rbAlignCap = findViewById(R.id.rb_align_cap);
        rbAlignX = findViewById(R.id.rb_align_x);
        rgColonRule = findViewById(R.id.rg_colon_rule);
        rbRuleBetween = findViewById(R.id.rb_rule_between);
        rbRuleAfter = findViewById(R.id.rb_rule_after);
        rbRuleAlways = findViewById(R.id.rb_rule_always);
        tvColonOffsetVal = findViewById(R.id.tv_colon_offset_val);
        seekColonOffset = findViewById(R.id.seek_colon_offset);
        btnOffsetMinus10 = findViewById(R.id.btn_offset_minus10);
        btnOffsetMinus2 = findViewById(R.id.btn_offset_minus2);
        btnOffsetReset = findViewById(R.id.btn_offset_reset);
        btnOffsetPlus2 = findViewById(R.id.btn_offset_plus2);
        btnOffsetPlus10 = findViewById(R.id.btn_offset_plus10);

        btnTime1230 = findViewById(R.id.btn_time_1230);
        btnTime1008 = findViewById(R.id.btn_time_1008);
        btnTime0715 = findViewById(R.id.btn_time_0715);
        btnTime2359 = findViewById(R.id.btn_time_2359);
        tvClockHour = findViewById(R.id.tv_clock_hour);
        tvClockColon = findViewById(R.id.tv_clock_colon);
        tvClockMinute = findViewById(R.id.tv_clock_minute);
        tvSampleText = findViewById(R.id.tv_sample_text);

        // Step 3: Features
        layoutFeatureChips = findViewById(R.id.layout_feature_chips);
        tvNoFeatures = findViewById(R.id.tv_no_features);
        etFeatures = findViewById(R.id.et_features);

        // Step 4: Harmonization & Metrics
        cbEqualizeDigits = findViewById(R.id.cb_equalize_digits);
        cbPuaColon = findViewById(R.id.cb_pua_colon);
        cbSyntheticItalic = findViewById(R.id.cb_synthetic_italic);
        rgMetrics = findViewById(R.id.rg_metrics);
        rbMetricsCompact = findViewById(R.id.rb_metrics_compact);
        rbMetricsSafe = findViewById(R.id.rb_metrics_safe);
        rbMetricsPreserve = findViewById(R.id.rb_metrics_preserve);
        cbSubset = findViewById(R.id.cb_subset);
        tvTrackingVal = findViewById(R.id.tv_tracking_val);
        seekTracking = findViewById(R.id.seek_tracking);

        // Step 5: Module & Build
        etModuleName = findViewById(R.id.et_module_name);
        etAuthor = findViewById(R.id.et_author);
        btnBuild = findViewById(R.id.btn_build);

        // Progress & Success & Console
        layoutProgress = findViewById(R.id.layout_progress);
        progressBar = findViewById(R.id.progress_bar);
        tvStatus = findViewById(R.id.tv_status);
        layoutSuccess = findViewById(R.id.layout_success);
        tvSuccessDetails = findViewById(R.id.tv_success_details);
        btnOpenFolder = findViewById(R.id.btn_open_folder);
        btnShareModule = findViewById(R.id.btn_share_module);
        btnFlashRoot = findViewById(R.id.btn_flash_root);
        layoutConsoleCard = findViewById(R.id.layout_console_card);
        scrollConsole = findViewById(R.id.scroll_console);
        tvConsole = findViewById(R.id.tv_console);
    }

    private void setupListeners() {
        // Step 1: Browse Sans
        btnBrowseSans.setOnClickListener(v -> openFontPicker(REQUEST_PICK_SANS));
        btnClearSans.setOnClickListener(v -> {
            sansFonts.clear();
            currentInspection = null;
            currentTypeface = null;
            updateSansUI();
        });

        // Companion accordion toggle
        layoutOptionalToggle.setOnClickListener(v -> {
            if (layoutOptionalFamilies.getVisibility() == View.VISIBLE) {
                layoutOptionalFamilies.setVisibility(View.GONE);
                tvOptionalArrow.setText("▼");
            } else {
                layoutOptionalFamilies.setVisibility(View.VISIBLE);
                tvOptionalArrow.setText("▲");
            }
        });

        btnBrowseMono.setOnClickListener(v -> openFontPicker(REQUEST_PICK_MONO));
        btnClearMono.setOnClickListener(v -> {
            monoFonts.clear();
            updateMonoUI();
        });

        btnBrowseSerif.setOnClickListener(v -> openFontPicker(REQUEST_PICK_SERIF));
        btnClearSerif.setOnClickListener(v -> {
            serifFonts.clear();
            updateSerifUI();
        });

        btnBrowseBengali.setOnClickListener(v -> openFontPicker(REQUEST_PICK_BENGALI));
        btnClearBengali.setOnClickListener(v -> {
            bengaliFonts.clear();
            updateBengaliUI();
        });

        // Step 2: Centered Colon controls
        cbCenteredColon.setOnCheckedChangeListener((buttonView, isChecked) -> {
            layoutColonControls.setVisibility(isChecked ? View.VISIBLE : View.GONE);
            updateColonVisualShift();
        });

        seekColonOffset.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                updateColonVisualShift();
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // Steppers
        btnOffsetMinus10.setOnClickListener(v -> adjustColonOffset(-10));
        btnOffsetMinus2.setOnClickListener(v -> adjustColonOffset(-2));
        btnOffsetReset.setOnClickListener(v -> seekColonOffset.setProgress(80));
        btnOffsetPlus2.setOnClickListener(v -> adjustColonOffset(2));
        btnOffsetPlus10.setOnClickListener(v -> adjustColonOffset(10));

        // Time presets
        btnTime1230.setOnClickListener(v -> setClockPreviewTime("12", "30"));
        btnTime1008.setOnClickListener(v -> setClockPreviewTime("10", "08"));
        btnTime0715.setOnClickListener(v -> setClockPreviewTime("07", "15"));
        btnTime2359.setOnClickListener(v -> setClockPreviewTime("23", "59"));

        // Step 4: Tracking SeekBar
        seekTracking.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                int tracking = progress - 40; // -40 to +60
                String label = tracking == 0 ? "0 ‰ em (Default)" : String.format("%+d ‰ em", tracking);
                tvTrackingVal.setText(label);
                if (tvSampleText != null) {
                    tvSampleText.setLetterSpacing(tracking / 1000f);
                }
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {}

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // Step 5: Build
        btnBuild.setOnClickListener(v -> startBuildProcess());

        // Success buttons
        btnOpenFolder.setOnClickListener(v -> openDownloadsFolder());
        btnShareModule.setOnClickListener(v -> shareGeneratedZip());
        btnFlashRoot.setOnClickListener(v -> flashWithRoot());
    }

    private void adjustColonOffset(int delta) {
        int newProgress = Math.max(0, Math.min(160, seekColonOffset.getProgress() + delta));
        seekColonOffset.setProgress(newProgress);
    }

    private void setClockPreviewTime(String hour, String minute) {
        tvClockHour.setText(hour);
        tvClockMinute.setText(minute);
    }

    private void updateColonVisualShift() {
        int offset = seekColonOffset.getProgress() - 80; // range: -80 to +80
        String label = (offset == 0) ? "0 font units (Center)" : String.format("%+d font units", offset);
        tvColonOffsetVal.setText(label);

        if (!cbCenteredColon.isChecked()) {
            tvClockColon.setTranslationY(0f);
            return;
        }

        int upm = (currentInspection != null && currentInspection.unitsPerEm > 0) ? currentInspection.unitsPerEm : 2048;
        // In typography, positive shift moves the colon upwards toward cap-height
        float textSizePx = tvClockColon.getTextSize();
        float shiftPx = -(offset / (float) upm) * textSizePx * 1.5f;
        tvClockColon.setTranslationY(shiftPx);
    }

    private void openFontPicker(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        String[] mimeTypes = {
                "font/ttf", "font/otf", "font/woff", "font/woff2",
                "application/x-font-ttf", "application/x-font-otf",
                "application/zip", "application/octet-stream"
        };
        intent.putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes);
        startActivityForResult(intent, requestCode);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) return;

        List<FontItem> items = new ArrayList<>();
        if (data.getClipData() != null) {
            ClipData clip = data.getClipData();
            for (int i = 0; i < clip.getItemCount(); i++) {
                Uri uri = clip.getItemAt(i).getUri();
                items.add(queryFileInfo(uri));
            }
        } else if (data.getData() != null) {
            items.add(queryFileInfo(data.getData()));
        }

        if (items.isEmpty()) return;

        switch (requestCode) {
            case REQUEST_PICK_SANS:
                sansFonts.addAll(items);
                inspectAndApplySansFont();
                break;
            case REQUEST_PICK_MONO:
                monoFonts.addAll(items);
                updateMonoUI();
                break;
            case REQUEST_PICK_SERIF:
                serifFonts.addAll(items);
                updateSerifUI();
                break;
            case REQUEST_PICK_BENGALI:
                bengaliFonts.addAll(items);
                updateBengaliUI();
                break;
        }
    }

    private FontItem queryFileInfo(Uri uri) {
        String name = "font.ttf";
        long size = 0;
        try (Cursor cursor = getContentResolver().query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIdx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (nameIdx >= 0) name = cursor.getString(nameIdx);
                int sizeIdx = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (sizeIdx >= 0) size = cursor.getLong(sizeIdx);
            }
        } catch (Exception ignored) {}
        return new FontItem(uri, name, size);
    }

    private void inspectAndApplySansFont() {
        if (sansFonts.isEmpty()) {
            updateSansUI();
            return;
        }

        // Cache first sans font file to local cache for instant inspection & Typeface loading
        FontItem primary = sansFonts.get(0);
        previewFontFile = new File(getCacheDir(), "preview_sans_" + primary.name);

        try (InputStream in = getContentResolver().openInputStream(primary.uri);
             FileOutputStream out = new FileOutputStream(previewFontFile)) {
            byte[] buf = new byte[8192];
            int len;
            while ((len = in.read(buf)) != -1) {
                out.write(buf, 0, len);
            }
        } catch (Exception e) {
            previewFontFile = null;
        }

        if (previewFontFile != null && previewFontFile.exists()) {
            currentInspection = FontInspector.inspect(previewFontFile);
            try {
                currentTypeface = Typeface.createFromFile(previewFontFile);
            } catch (Exception e) {
                currentTypeface = Typeface.DEFAULT;
            }
        }

        updateSansUI();
    }

    private void updateSansUI() {
        if (sansFonts.isEmpty()) {
            layoutSansInfo.setVisibility(View.GONE);
            tvNoSans.setVisibility(View.VISIBLE);
            layoutUnlockedSteps.setVisibility(View.GONE);
            return;
        }

        tvNoSans.setVisibility(View.GONE);
        layoutSansInfo.setVisibility(View.VISIBLE);
        layoutUnlockedSteps.setVisibility(View.VISIBLE);

        long totalSize = 0;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < sansFonts.size(); i++) {
            FontItem item = sansFonts.get(i);
            totalSize += item.size;
            if (i > 0) sb.append(", ");
            sb.append(item.name);
        }
        String sizeStr = String.format("%.2f MB", totalSize / (1024.0 * 1024.0));
        tvSansSummary.setText(sansFonts.size() + " Sans-serif font(s) selected (" + sizeStr + ")");
        tvSansFiles.setText(sb.toString());

        // Step 1: Update Inspection Card
        if (currentInspection != null) {
            String fontType = currentInspection.isVariable ? "Variable Font" : "Static Font";
            tvInspectFamily.setText("Family: " + currentInspection.familyName + " (" + fontType + ")");

            StringBuilder details = new StringBuilder();
            details.append("UPM: ").append(currentInspection.unitsPerEm);
            details.append(" | Style: ").append(currentInspection.styleName);
            if (!currentInspection.variableAxes.isEmpty()) {
                details.append("\nAxes: ").append(String.join(", ", currentInspection.variableAxes));
            }
            tvInspectDetails.setText(details.toString());
            layoutInspectionBadge.setVisibility(View.VISIBLE);

            etModuleName.setHint(currentInspection.familyName);

            // Step 2: Centered Clock Colon Status
            if (currentInspection.hasCenteredColon) {
                layoutColonDetectionBadge.setBackgroundResource(R.drawable.badge_green);
                tvColonBadgeTitle.setText("✓ Centered Clock Colon Detected in Font");
                tvColonBadgeTitle.setTextColor(getResources().getColor(R.color.badge_green_text));
                tvColonBadgeDesc.setText(currentInspection.centeredColonDetails);
                cbCenteredColon.setChecked(true);
            } else {
                layoutColonDetectionBadge.setBackgroundResource(R.drawable.badge_yellow);
                tvColonBadgeTitle.setText("⚠️ No Centered Clock Colon Detected");
                tvColonBadgeTitle.setTextColor(getResources().getColor(R.color.badge_yellow_text));
                tvColonBadgeDesc.setText(currentInspection.centeredColonDetails);
                cbCenteredColon.setChecked(true);
            }

            // Apply Typeface to Live Clock and Sample Preview
            if (currentTypeface != null) {
                tvClockHour.setTypeface(currentTypeface);
                tvClockColon.setTypeface(currentTypeface);
                tvClockMinute.setTypeface(currentTypeface);
                tvSampleText.setTypeface(currentTypeface);
            }

            updateColonVisualShift();

            // Step 3: Populate OpenType Layout Features Chips
            populateFeatureChips();

            // Step 4: Suggest subsetting if total size > 1MB
            if (totalSize > 1024 * 1024) {
                cbSubset.setChecked(true);
            }
        }
    }

    private void populateFeatureChips() {
        layoutFeatureChips.removeAllViews();
        if (currentInspection == null || currentInspection.features.isEmpty()) {
            tvNoFeatures.setVisibility(View.VISIBLE);
            return;
        }

        tvNoFeatures.setVisibility(View.GONE);

        for (FontInspector.FeatureInfo feat : currentInspection.features) {
            CheckBox chip = new CheckBox(this);
            String label = feat.tag + " — " + feat.name;
            chip.setText(label);
            chip.setTextSize(12);

            if ("SAFE".equals(feat.category)) {
                chip.setTextColor(getResources().getColor(R.color.accent));
            } else if ("CAUTION".equals(feat.category)) {
                chip.setTextColor(getResources().getColor(R.color.warning));
            } else {
                chip.setTextColor(getResources().getColor(R.color.text_secondary));
            }

            chip.setOnCheckedChangeListener((buttonView, isChecked) -> {
                updateFeatureTagsFromChips();
            });

            layoutFeatureChips.addView(chip);
        }
    }

    private void updateFeatureTagsFromChips() {
        Set<String> selected = new LinkedHashSet<>();

        for (int i = 0; i < layoutFeatureChips.getChildCount(); i++) {
            View v = layoutFeatureChips.getChildAt(i);
            if (v instanceof CheckBox) {
                CheckBox cb = (CheckBox) v;
                if (cb.isChecked()) {
                    String text = cb.getText().toString();
                    if (text.contains(" — ")) {
                        String tag = text.substring(0, text.indexOf(" — ")).trim();
                        selected.add(tag);
                    }
                }
            }
        }

        // Also preserve any custom tags user typed
        String current = etFeatures.getText().toString().trim();
        if (!current.isEmpty()) {
            String[] parts = current.split("[,\\s]+");
            for (String p : parts) {
                if (!p.isEmpty()) selected.add(p);
            }
        }

        etFeatures.setText(String.join(", ", selected));
    }

    private void updateMonoUI() {
        if (monoFonts.isEmpty()) {
            layoutMonoInfo.setVisibility(View.GONE);
        } else {
            layoutMonoInfo.setVisibility(View.VISIBLE);
            tvMonoSummary.setText("Monospace: " + monoFonts.size() + " font file(s) attached");
        }
    }

    private void updateSerifUI() {
        if (serifFonts.isEmpty()) {
            layoutSerifInfo.setVisibility(View.GONE);
        } else {
            layoutSerifInfo.setVisibility(View.VISIBLE);
            tvSerifSummary.setText("Serif: " + serifFonts.size() + " font file(s) attached");
        }
    }

    private void updateBengaliUI() {
        if (bengaliFonts.isEmpty()) {
            layoutBengaliInfo.setVisibility(View.GONE);
        } else {
            layoutBengaliInfo.setVisibility(View.VISIBLE);
            tvBengaliSummary.setText("Bengali: " + bengaliFonts.size() + " font file(s) attached");
        }
    }

    // =========================================================================
    // BUILD EXECUTION PIPELINE
    // =========================================================================

    private void startBuildProcess() {
        if (sansFonts.isEmpty()) {
            Toast.makeText(this, "Please select at least one Sans-serif font.", Toast.LENGTH_SHORT).show();
            return;
        }

        btnBuild.setEnabled(false);
        layoutProgress.setVisibility(View.VISIBLE);
        layoutSuccess.setVisibility(View.GONE);
        layoutConsoleCard.setVisibility(View.VISIBLE);
        tvConsole.setText("");
        tvStatus.setText("Extracting engine assets and preparing build...");

        new Thread(this::runBuildPipeline).start();
    }

    private void runBuildPipeline() {
        try {
            File filesDir = getFilesDir();
            File engineDir = new File(filesDir, "engine");

            // 1. Unpack engine.zip if needed
            File marker = new File(engineDir, ".ready_v14_2");
            if (!marker.exists()) {
                appendLog("Extracting bundled standalone engine assets...");
                unzipAsset("engine.zip", engineDir);
                File[] scripts = new File(engineDir, "scripts").listFiles();
                if (scripts != null) {
                    for (File s : scripts) s.setExecutable(true, false);
                }
                marker.createNewFile();
                appendLog("Engine assets initialized successfully.");
            }

            // 2. Prepare Fonts workspace directory
            File fontsDir = new File(filesDir, "Fonts");
            deleteDir(fontsDir);
            fontsDir.mkdirs();

            File sansDir = new File(fontsDir, "Sans");
            sansDir.mkdirs();
            appendLog("Staging Sans-serif fonts (" + sansFonts.size() + " files)...");
            for (FontItem item : sansFonts) {
                stageFontItem(item, sansDir);
            }

            if (!monoFonts.isEmpty()) {
                File monoDir = new File(fontsDir, "Monospace");
                monoDir.mkdirs();
                appendLog("Staging Monospace fonts (" + monoFonts.size() + " files)...");
                for (FontItem item : monoFonts) stageFontItem(item, monoDir);
            }

            if (!serifFonts.isEmpty()) {
                File serifDir = new File(fontsDir, "Serif");
                serifDir.mkdirs();
                appendLog("Staging Serif fonts (" + serifFonts.size() + " files)...");
                for (FontItem item : serifFonts) stageFontItem(item, serifDir);
            }

            if (!bengaliFonts.isEmpty()) {
                File bengaliDir = new File(fontsDir, "Bengali");
                bengaliDir.mkdirs();
                appendLog("Staging Bengali fonts (" + bengaliFonts.size() + " files)...");
                for (FontItem item : bengaliFonts) stageFontItem(item, bengaliDir);
            }

            // 3. Locate python native binary
            File pythonBin = new File(getApplicationInfo().nativeLibraryDir, "libmffm_python.so");
            if (!pythonBin.exists()) {
                throw new RuntimeException("Python binary not found at " + pythonBin.getAbsolutePath());
            }
            pythonBin.setExecutable(true, false);

            File outputDir = new File(filesDir, "dist");
            deleteDir(outputDir);
            outputDir.mkdirs();

            // 4. Assemble command line options exactly matching user choices
            List<String> cmd = new ArrayList<>();
            cmd.add(pythonBin.getAbsolutePath());
            cmd.add(new File(engineDir, "scripts/build_standalone.py").getAbsolutePath());
            cmd.add("--fonts-dir");
            cmd.add(fontsDir.getAbsolutePath());
            cmd.add("--output-dir");
            cmd.add(outputDir.getAbsolutePath());

            // Module Name
            String modName = etModuleName.getText().toString().trim();
            if (modName.isEmpty() && currentInspection != null) {
                modName = currentInspection.familyName;
            }
            if (!modName.isEmpty()) {
                cmd.add("--name");
                cmd.add(modName);
            }

            // Centered Colon & Shift
            if (cbCenteredColon.isChecked()) {
                cmd.add("--centered-colon");
                int offset = seekColonOffset.getProgress() - 80;
                cmd.add("--colon-offset");
                cmd.add(String.valueOf(offset));

                // Alignment
                String alignment = "center";
                if (rbAlignCap.isChecked()) alignment = "cap_height";
                else if (rbAlignX.isChecked()) alignment = "x_height";
                cmd.add("--colon-alignment");
                cmd.add(alignment);

                // Rule
                String rule = "between_digits";
                if (rbRuleAfter.isChecked()) rule = "after_digit";
                else if (rbRuleAlways.isChecked()) rule = "always";
                cmd.add("--colon-rule");
                cmd.add(rule);
            } else {
                cmd.add("--no-centered-colon");
            }

            // Digit Equalization & PUA Colon
            if (cbEqualizeDigits.isChecked()) {
                cmd.add("--equalize-digits");
            }
            if (cbPuaColon.isChecked()) {
                cmd.add("--pua-colon");
            }

            // Synthetic Italic
            if (cbSyntheticItalic.isChecked()) {
                cmd.add("--synthetic-italic");
            }

            // Metrics mode
            String metrics = "compact";
            if (rbMetricsSafe.isChecked()) metrics = "safe";
            else if (rbMetricsPreserve.isChecked()) metrics = "preserve";
            cmd.add("--metrics-mode");
            cmd.add(metrics);

            // Subsetting
            if (cbSubset.isChecked()) {
                cmd.add("--subset");
            } else {
                cmd.add("--no-subset");
            }

            // Tracking
            int tracking = seekTracking.getProgress() - 40;
            if (tracking != 0) {
                cmd.add("--tracking");
                cmd.add(String.valueOf(tracking));
            }

            // OpenType Features
            String feats = etFeatures.getText().toString().trim();
            if (!feats.isEmpty()) {
                cmd.add("--features");
                cmd.add(feats);
            }

            // Never prompt interactively on Android
            cmd.add("--no-interactive");

            appendLog("Launching MFFM Standalone Engine: " + String.join(" ", cmd));

            ProcessBuilder pb = new ProcessBuilder(cmd);
            pb.directory(new File(engineDir, "scripts"));
            Map<String, String> env = pb.environment();
            env.put("PYTHONHOME", engineDir.getAbsolutePath());
            env.put("PYTHONPATH", new File(engineDir, "lib/python3.11").getAbsolutePath() + ":" +
                    new File(engineDir, "lib/python3.11/site-packages").getAbsolutePath());
            env.put("PATH", new File(engineDir, "scripts/.mffm-signer/bin").getAbsolutePath() + ":" + System.getenv("PATH"));
            File zipsignerLib = new File(getApplicationInfo().nativeLibraryDir, "libzipsignerust.so");
            if (zipsignerLib.exists()) {
                zipsignerLib.setExecutable(true, false);
                env.put("ZIPSIGNER_BIN", zipsignerLib.getAbsolutePath());
            }
            env.put("HOME", filesDir.getAbsolutePath());
            env.put("TMPDIR", getCacheDir().getAbsolutePath());
            env.put("SOURCE_DATE_EPOCH", String.valueOf(System.currentTimeMillis() / 1000L));
            pb.redirectErrorStream(true);

            updateStatus("Compiling typography & generating font module...");
            Process process = pb.start();

            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    appendLog(line);
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                throw new RuntimeException("Compiler returned exit code " + exitCode + ". Check console for details.");
            }

            // Find generated ZIP
            File[] zips = outputDir.listFiles((dir, name) -> name.endsWith(".zip"));
            if (zips == null || zips.length == 0) {
                throw new RuntimeException("Compilation completed but output ZIP was not found in " + outputDir);
            }
            lastGeneratedZip = zips[0];
            appendLog("Generated flashable module: " + lastGeneratedZip.getName() + " (" + (lastGeneratedZip.length() / 1024) + " KB)");

            // Copy to public Downloads directory
            lastSavedDownloadUri = exportZipToDownloads(lastGeneratedZip);

            mainHandler.post(() -> onBuildSuccess(lastGeneratedZip));

        } catch (Exception e) {
            String err = e.getMessage() != null ? e.getMessage() : e.toString();
            appendLog("[ERROR] " + err);
            mainHandler.post(() -> onBuildFailure(err));
        }
    }

    private void stageFontItem(FontItem item, File targetDir) throws Exception {
        if (item.name.toLowerCase().endsWith(".zip")) {
            appendLog("Extracting font package: " + item.name);
            try (InputStream in = getContentResolver().openInputStream(item.uri);
                 ZipInputStream zin = new ZipInputStream(in)) {
                ZipEntry entry;
                while ((entry = zin.getNextEntry()) != null) {
                    String n = entry.getName().toLowerCase();
                    if (!entry.isDirectory() && (n.endsWith(".ttf") || n.endsWith(".otf") || n.endsWith(".woff") || n.endsWith(".woff2") || n.endsWith(".ttc"))) {
                        File out = new File(targetDir, new File(entry.getName()).getName());
                        try (FileOutputStream fos = new FileOutputStream(out)) {
                            byte[] b = new byte[8192];
                            int r;
                            while ((r = zin.read(b)) != -1) fos.write(b, 0, r);
                        }
                    }
                    zin.closeEntry();
                }
            }
        } else {
            File out = new File(targetDir, item.name);
            try (InputStream in = getContentResolver().openInputStream(item.uri);
                 FileOutputStream fos = new FileOutputStream(out)) {
                byte[] b = new byte[8192];
                int r;
                while ((r = in.read(b)) != -1) fos.write(b, 0, r);
            }
        }
    }

    private Uri exportZipToDownloads(File zipFile) {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.MediaColumns.DISPLAY_NAME, zipFile.getName());
                values.put(MediaStore.MediaColumns.MIME_TYPE, "application/zip");
                values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);

                ContentResolver resolver = getContentResolver();
                Uri uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
                if (uri != null) {
                    try (OutputStream out = resolver.openOutputStream(uri);
                         FileInputStream in = new FileInputStream(zipFile)) {
                        byte[] buf = new byte[8192];
                        int len;
                        while ((len = in.read(buf)) != -1) out.write(buf, 0, len);
                    }
                    appendLog("Exported module to Downloads: " + zipFile.getName());
                    return uri;
                }
            } else {
                File downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                File dest = new File(downloadsDir, zipFile.getName());
                try (FileInputStream in = new FileInputStream(zipFile);
                     FileOutputStream out = new FileOutputStream(dest)) {
                    byte[] buf = new byte[8192];
                    int len;
                    while ((len = in.read(buf)) != -1) out.write(buf, 0, len);
                }
                appendLog("Saved module to: " + dest.getAbsolutePath());
                return Uri.fromFile(dest);
            }
        } catch (Exception e) {
            appendLog("Warning: Could not export to public Downloads: " + e.getMessage());
        }
        return null;
    }

    private void onBuildSuccess(File zip) {
        layoutProgress.setVisibility(View.GONE);
        btnBuild.setEnabled(true);
        layoutSuccess.setVisibility(View.VISIBLE);

        String msg = "Flashable module ready: " + zip.getName() + " (" + (zip.length() / 1024) + " KB)\n" +
                "Saved automatically to your device's Downloads folder.";
        tvSuccessDetails.setText(msg);
        Toast.makeText(this, "Module built successfully!", Toast.LENGTH_LONG).show();
    }

    private void onBuildFailure(String error) {
        layoutProgress.setVisibility(View.GONE);
        btnBuild.setEnabled(true);
        Toast.makeText(this, "Build failed: " + error, Toast.LENGTH_LONG).show();
    }

    private void openDownloadsFolder() {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW);
            if (lastSavedDownloadUri != null) {
                intent.setDataAndType(lastSavedDownloadUri, "application/zip");
            } else {
                intent.setDataAndType(Uri.parse(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).toURI().toString()), "*/*");
            }
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(this, "Module is located in Downloads: " + (lastGeneratedZip != null ? lastGeneratedZip.getName() : ""), Toast.LENGTH_LONG).show();
        }
    }

    private void shareGeneratedZip() {
        if (lastGeneratedZip == null || !lastGeneratedZip.exists()) {
            Toast.makeText(this, "No built module available to share.", Toast.LENGTH_SHORT).show();
            return;
        }
        try {
            Uri contentUri;
            if (lastSavedDownloadUri != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                contentUri = lastSavedDownloadUri;
            } else {
                contentUri = MffmFileProvider.getUriForFile(this, "com.mistu.mffm.fileprovider", lastGeneratedZip);
            }
            Intent shareIntent = new Intent(Intent.ACTION_SEND);
            shareIntent.setType("application/zip");
            shareIntent.putExtra(Intent.EXTRA_STREAM, contentUri);
            shareIntent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(shareIntent, "Share MFFM Font Module"));
        } catch (Exception e) {
            Toast.makeText(this, "Could not share module: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void flashWithRoot() {
        if (lastGeneratedZip == null || !lastGeneratedZip.exists()) {
            Toast.makeText(this, "No module found to flash.", Toast.LENGTH_SHORT).show();
            return;
        }

        layoutProgress.setVisibility(View.VISIBLE);
        tvStatus.setText("Flashing module via Root (su)...");

        new Thread(() -> {
            try {
                appendLog("Requesting root permissions to flash module...");
                Process su = Runtime.getRuntime().exec("su");
                OutputStream out = su.getOutputStream();
                String zipPath = lastGeneratedZip.getAbsolutePath();

                // Detect Magisk / KernelSU / APatch flash command
                String cmd = "magisk --install-module \"" + zipPath + "\" || " +
                        "ksud module install \"" + zipPath + "\" || " +
                        "apatch module install \"" + zipPath + "\"\n";

                out.write(cmd.getBytes());
                out.flush();
                out.write("exit\n".getBytes());
                out.flush();

                BufferedReader reader = new BufferedReader(new InputStreamReader(su.getInputStream()));
                String line;
                while ((line = reader.readLine()) != null) {
                    appendLog("[ROOT] " + line);
                }

                int code = su.waitFor();
                mainHandler.post(() -> {
                    layoutProgress.setVisibility(View.GONE);
                    if (code == 0) {
                        Toast.makeText(MainActivity.this, "Module flashed successfully! Reboot to apply.", Toast.LENGTH_LONG).show();
                    } else {
                        Toast.makeText(MainActivity.this, "Root flash exited with code " + code + ". You can install it manually from Magisk/KernelSU app.", Toast.LENGTH_LONG).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> {
                    layoutProgress.setVisibility(View.GONE);
                    Toast.makeText(MainActivity.this, "Root access unavailable or denied: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private void appendLog(String line) {
        mainHandler.post(() -> {
            if (tvConsole != null) {
                tvConsole.append(line + "\n");
                scrollConsole.post(() -> scrollConsole.fullScroll(View.FOCUS_DOWN));
            }
        });
    }

    private void updateStatus(String status) {
        mainHandler.post(() -> {
            if (tvStatus != null) tvStatus.setText(status);
        });
    }

    private void unzipAsset(String assetName, File destDir) throws Exception {
        destDir.mkdirs();
        try (InputStream is = getAssets().open(assetName);
             ZipInputStream zis = new ZipInputStream(is)) {
            ZipEntry entry;
            while ((entry = zis.getNextEntry()) != null) {
                File file = new File(destDir, entry.getName());
                if (entry.isDirectory()) {
                    file.mkdirs();
                } else {
                    file.getParentFile().mkdirs();
                    try (FileOutputStream fos = new FileOutputStream(file)) {
                        byte[] buf = new byte[8192];
                        int count;
                        while ((count = zis.read(buf)) != -1) fos.write(buf, 0, count);
                    }
                }
                zis.closeEntry();
            }
        }
    }

    private void deleteDir(File dir) {
        if (dir.isDirectory()) {
            File[] children = dir.listFiles();
            if (children != null) {
                for (File child : children) deleteDir(child);
            }
        }
        dir.delete();
    }
}
