package com.mistu.mffm;

import android.app.Activity;
import android.content.ClipData;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
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
import java.util.List;
import java.util.Map;
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

    // Primary Sans UI
    private Button btnBrowseSans;
    private LinearLayout layoutSansInfo;
    private TextView tvSansSummary;
    private TextView tvSansFiles;
    private Button btnClearSans;
    private TextView tvNoSans;

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

    // Builder Mode UI
    private RadioGroup rgMode;
    private RadioButton rbModeQuick;
    private RadioButton rbModeCustom;
    private LinearLayout layoutCustomOptions;

    private EditText etModuleName;
    private EditText etAuthor;
    private CheckBox cbCenteredColon;
    private CheckBox cbEqualizeDigits;
    private CheckBox cbPuaColon;
    private CheckBox cbSyntheticItalic;
    private RadioGroup rgMetrics;
    private RadioButton rbMetricsCompact;
    private RadioButton rbMetricsSafe;
    private RadioButton rbMetricsPreserve;
    private CheckBox cbSubset;
    private EditText etTracking;
    private EditText etFeatures;

    // Build Actions & Console
    private Button btnBuild;
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

    // State
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
        // Sans views
        btnBrowseSans = findViewById(R.id.btn_browse_sans);
        layoutSansInfo = findViewById(R.id.layout_sans_info);
        tvSansSummary = findViewById(R.id.tv_sans_summary);
        tvSansFiles = findViewById(R.id.tv_sans_files);
        btnClearSans = findViewById(R.id.btn_clear_sans);
        tvNoSans = findViewById(R.id.tv_no_sans);

        // Optional accordion views
        layoutOptionalToggle = findViewById(R.id.layout_optional_toggle);
        tvOptionalArrow = findViewById(R.id.tv_optional_arrow);
        layoutOptionalFamilies = findViewById(R.id.layout_optional_families);

        // Mono views
        btnBrowseMono = findViewById(R.id.btn_browse_mono);
        layoutMonoInfo = findViewById(R.id.layout_mono_info);
        tvMonoSummary = findViewById(R.id.tv_mono_summary);
        btnClearMono = findViewById(R.id.btn_clear_mono);

        // Serif views
        btnBrowseSerif = findViewById(R.id.btn_browse_serif);
        layoutSerifInfo = findViewById(R.id.layout_serif_info);
        tvSerifSummary = findViewById(R.id.tv_serif_summary);
        btnClearSerif = findViewById(R.id.btn_clear_serif);

        // Bengali views
        btnBrowseBengali = findViewById(R.id.btn_browse_bengali);
        layoutBengaliInfo = findViewById(R.id.layout_bengali_info);
        tvBengaliSummary = findViewById(R.id.tv_bengali_summary);
        btnClearBengali = findViewById(R.id.btn_clear_bengali);

        // Mode views
        rgMode = findViewById(R.id.rg_mode);
        rbModeQuick = findViewById(R.id.rb_mode_quick);
        rbModeCustom = findViewById(R.id.rb_mode_custom);
        layoutCustomOptions = findViewById(R.id.layout_custom_options);

        etModuleName = findViewById(R.id.et_module_name);
        etAuthor = findViewById(R.id.et_author);
        cbCenteredColon = findViewById(R.id.cb_centered_colon);
        cbEqualizeDigits = findViewById(R.id.cb_equalize_digits);
        cbPuaColon = findViewById(R.id.cb_pua_colon);
        cbSyntheticItalic = findViewById(R.id.cb_synthetic_italic);
        rgMetrics = findViewById(R.id.rg_metrics);
        rbMetricsCompact = findViewById(R.id.rb_metrics_compact);
        rbMetricsSafe = findViewById(R.id.rb_metrics_safe);
        rbMetricsPreserve = findViewById(R.id.rb_metrics_preserve);
        cbSubset = findViewById(R.id.cb_subset);
        etTracking = findViewById(R.id.et_tracking);
        etFeatures = findViewById(R.id.et_features);

        btnBuild = findViewById(R.id.btn_build);
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
        btnBrowseSans.setOnClickListener(v -> pickFonts(REQUEST_PICK_SANS));
        btnClearSans.setOnClickListener(v -> {
            sansFonts.clear();
            updateSansUI();
        });

        layoutOptionalToggle.setOnClickListener(v -> {
            if (layoutOptionalFamilies.getVisibility() == View.VISIBLE) {
                layoutOptionalFamilies.setVisibility(View.GONE);
                tvOptionalArrow.setText("▼");
            } else {
                layoutOptionalFamilies.setVisibility(View.VISIBLE);
                tvOptionalArrow.setText("▲");
            }
        });

        btnBrowseMono.setOnClickListener(v -> pickFonts(REQUEST_PICK_MONO));
        btnClearMono.setOnClickListener(v -> {
            monoFonts.clear();
            updateMonoUI();
        });

        btnBrowseSerif.setOnClickListener(v -> pickFonts(REQUEST_PICK_SERIF));
        btnClearSerif.setOnClickListener(v -> {
            serifFonts.clear();
            updateSerifUI();
        });

        btnBrowseBengali.setOnClickListener(v -> pickFonts(REQUEST_PICK_BENGALI));
        btnClearBengali.setOnClickListener(v -> {
            bengaliFonts.clear();
            updateBengaliUI();
        });

        rgMode.setOnCheckedChangeListener((group, checkedId) -> {
            if (checkedId == R.id.rb_mode_custom) {
                layoutCustomOptions.setVisibility(View.VISIBLE);
            } else {
                layoutCustomOptions.setVisibility(View.GONE);
            }
        });

        btnBuild.setOnClickListener(v -> startBuildProcess());
        btnOpenFolder.setOnClickListener(v -> openDownloadsFolder());
        btnShareModule.setOnClickListener(v -> shareGeneratedModule());
        btnFlashRoot.setOnClickListener(v -> flashModuleWithRoot());
    }

    private void pickFonts(int requestCode) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
        intent.setType("*/*");
        String[] mimeTypes = {"font/*", "application/x-font-ttf", "application/font-sfnt", "application/zip", "application/octet-stream"};
        intent.putExtra(Intent.EXTRA_MIME_TYPES, mimeTypes);
        startActivityForResult(intent, requestCode);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null) return;

        List<Uri> uris = new ArrayList<>();
        if (data.getClipData() != null) {
            ClipData clip = data.getClipData();
            for (int i = 0; i < clip.getItemCount(); i++) {
                ClipData.Item item = clip.getItemAt(i);
                if (item != null && item.getUri() != null) {
                    uris.add(item.getUri());
                }
            }
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }

        if (uris.isEmpty()) return;

        List<FontItem> items = new ArrayList<>();
        for (Uri uri : uris) {
            items.add(queryFileInfo(uri));
        }

        switch (requestCode) {
            case REQUEST_PICK_SANS:
                sansFonts.addAll(items);
                updateSansUI();
                if (!sansFonts.isEmpty()) {
                    String first = sansFonts.get(0).name;
                    String stem = first.contains(".") ? first.substring(0, first.lastIndexOf('.')) : first;
                    etModuleName.setHint(stem);
                }
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

    private void updateSansUI() {
        if (sansFonts.isEmpty()) {
            layoutSansInfo.setVisibility(View.GONE);
            tvNoSans.setVisibility(View.VISIBLE);
        } else {
            tvNoSans.setVisibility(View.GONE);
            layoutSansInfo.setVisibility(View.VISIBLE);
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
        }
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

    private void startBuildProcess() {
        if (sansFonts.isEmpty()) {
            Toast.makeText(this, "Please choose at least one Sans-serif font file!", Toast.LENGTH_SHORT).show();
            return;
        }

        btnBuild.setEnabled(false);
        layoutProgress.setVisibility(View.VISIBLE);
        layoutSuccess.setVisibility(View.GONE);
        layoutConsoleCard.setVisibility(View.VISIBLE);
        tvConsole.setText("");
        tvStatus.setText("Initializing standalone engine...");

        new Thread(() -> {
            try {
                runCompilation();
            } catch (Exception e) {
                appendLog("Error during build: " + e.getMessage());
                for (StackTraceElement ste : e.getStackTrace()) {
                    appendLog("  at " + ste.toString());
                }
                mainHandler.post(() -> {
                    btnBuild.setEnabled(true);
                    tvStatus.setText("Build failed: " + e.getMessage());
                    Toast.makeText(MainActivity.this, "Build failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
                });
            }
        }).start();
    }

    private void runCompilation() throws Exception {
        updateStatus("Unpacking standalone compiler...");
        File filesDir = getFilesDir();
        File engineDir = new File(filesDir, "engine");

        // 1. Unpack engine.zip if needed
        File marker = new File(engineDir, ".ready_v14");
        if (!marker.exists()) {
            appendLog("Extracting bundled standalone engine assets...");
            unzipAsset("engine.zip", engineDir);
            marker.createNewFile();
            appendLog("Engine assets extracted successfully.");
        }

        // 2. Locate python binary
        String pythonBin = getApplicationInfo().nativeLibraryDir + "/libmffm_python.so";
        File binFile = new File(pythonBin);
        if (!binFile.exists()) {
            File fallback = new File(engineDir, "bin/python3");
            if (fallback.exists()) {
                pythonBin = fallback.getAbsolutePath();
                fallback.setExecutable(true, false);
            } else {
                throw new IllegalStateException("Python binary not found at: " + pythonBin);
            }
        }
        binFile.setExecutable(true, false);

        // 3. Prepare workspace & copy fonts
        updateStatus("Copying font families into workspace...");
        File workDir = new File(getCacheDir(), "mffm_build");
        deleteRecursive(workDir);

        // Copy Sans fonts
        File fontsSans = new File(workDir, "Fonts/Sans");
        fontsSans.mkdirs();
        copyFontListToDir(sansFonts, fontsSans);
        appendLog("Staged " + sansFonts.size() + " Sans-serif font(s).");

        // Copy Monospace fonts if present
        if (!monoFonts.isEmpty()) {
            File fontsMono = new File(workDir, "Fonts/Monospace");
            fontsMono.mkdirs();
            copyFontListToDir(monoFonts, fontsMono);
            appendLog("Staged " + monoFonts.size() + " Monospace font(s).");
        }

        // Copy Serif fonts if present
        if (!serifFonts.isEmpty()) {
            File fontsSerif = new File(workDir, "Fonts/Serif");
            fontsSerif.mkdirs();
            copyFontListToDir(serifFonts, fontsSerif);
            appendLog("Staged " + serifFonts.size() + " Serif font(s).");
        }

        // Copy Bengali fonts if present
        if (!bengaliFonts.isEmpty()) {
            File fontsBengali = new File(workDir, "Fonts/Bengali");
            fontsBengali.mkdirs();
            copyFontListToDir(bengaliFonts, fontsBengali);
            appendLog("Staged " + bengaliFonts.size() + " Bengali font(s).");
        }

        // 4. Construct command line
        File buildScript = new File(engineDir, "scripts/build_standalone.py");
        File outDir = new File(workDir, "dist");
        outDir.mkdirs();

        List<String> cmd = new ArrayList<>();
        cmd.add(pythonBin);
        cmd.add("-B");
        cmd.add(buildScript.getAbsolutePath());
        cmd.add("--fonts-dir");
        cmd.add(new File(workDir, "Fonts").getAbsolutePath());
        cmd.add("--output-dir");
        cmd.add(outDir.getAbsolutePath());
        cmd.add("--no-interactive");

        boolean isCustom = rbModeCustom.isChecked();
        if (isCustom) {
            String name = etModuleName.getText().toString().trim();
            if (!name.isEmpty()) {
                cmd.add("--name");
                cmd.add(name);
            }

            if (cbCenteredColon.isChecked()) {
                cmd.add("--centered-colon");
            } else {
                cmd.add("--no-centered-colon");
            }

            if (cbEqualizeDigits.isChecked()) {
                cmd.add("--equalize-digits");
            }

            if (cbPuaColon.isChecked()) {
                cmd.add("--pua-colon");
            }

            if (cbSyntheticItalic.isChecked()) {
                cmd.add("--synthetic-italic");
            }

            if (rbMetricsSafe.isChecked()) {
                cmd.add("--metrics-mode");
                cmd.add("safe");
            } else if (rbMetricsPreserve.isChecked()) {
                cmd.add("--metrics-mode");
                cmd.add("preserve");
            } else {
                cmd.add("--metrics-mode");
                cmd.add("compact");
            }

            if (cbSubset.isChecked()) {
                cmd.add("--subset");
            } else {
                cmd.add("--no-subset");
            }

            String tracking = etTracking.getText().toString().trim();
            if (!tracking.isEmpty()) {
                cmd.add("--tracking");
                cmd.add(tracking);
            }

            String features = etFeatures.getText().toString().trim();
            if (!features.isEmpty()) {
                cmd.add("--features");
                cmd.add(features);
            }
        } else {
            // Quick mode: Best defaults
            cmd.add("--centered-colon");
            cmd.add("--equalize-digits");
            cmd.add("--pua-colon");
            cmd.add("--synthetic-italic");
            cmd.add("--metrics-mode");
            cmd.add("compact");
        }

        // 5. Execute compiler process
        updateStatus("Compiling typography & packaging module...");
        appendLog("Executing: " + cmd.get(0) + " " + cmd.get(2) + " [options]");

        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(new File(engineDir, "scripts"));
        Map<String, String> env = pb.environment();
        env.put("PYTHONHOME", engineDir.getAbsolutePath());
        env.put("PYTHONPATH", new File(engineDir, "lib/python3.11").getAbsolutePath() + ":" +
                new File(engineDir, "lib/python3.11/site-packages").getAbsolutePath());
        env.put("PATH", new File(engineDir, "scripts/.mffm-signer/bin").getAbsolutePath() + ":" + System.getenv("PATH"));
        env.put("HOME", filesDir.getAbsolutePath());
        env.put("TMPDIR", getCacheDir().getAbsolutePath());
        env.put("SOURCE_DATE_EPOCH", String.valueOf(System.currentTimeMillis() / 1000L));
        pb.redirectErrorStream(true);

        Process process = pb.start();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                appendLog(line);
                if (line.contains("Centered Colon")) {
                    updateStatus("Calculating centered colon alignment...");
                } else if (line.contains("Equalize")) {
                    updateStatus("Equalizing clock digits for wobble-free display...");
                } else if (line.contains("metrics")) {
                    updateStatus("Harmonizing vertical font metrics...");
                } else if (line.contains("Packaging")) {
                    updateStatus("Compressing & signing flashable ZIP...");
                }
            }
        }

        int exitCode = process.waitFor();
        if (exitCode != 0) {
            throw new RuntimeException("Compiler returned exit code " + exitCode);
        }

        // 6. Find generated ZIP
        File[] zips = outDir.listFiles((dir, name) -> name.endsWith(".zip"));
        if (zips == null || zips.length == 0) {
            throw new RuntimeException("No output ZIP archive was produced in dist/");
        }

        File generatedZip = zips[0];
        lastGeneratedZip = generatedZip;
        appendLog("Module created successfully: " + generatedZip.getName() + " (" + (generatedZip.length() / (1024 * 1024)) + " MB)");

        // 7. Save to Downloads
        updateStatus("Saving module to Downloads folder...");
        lastSavedDownloadUri = saveZipToDownloads(generatedZip);

        mainHandler.post(() -> {
            btnBuild.setEnabled(true);
            layoutProgress.setVisibility(View.GONE);
            layoutSuccess.setVisibility(View.VISIBLE);

            String sizeStr = String.format("%.2f MB", generatedZip.length() / (1024.0 * 1024.0));
            tvSuccessDetails.setText("File: " + generatedZip.getName() + "\nSize: " + sizeStr + "\nSaved to: Downloads folder");
            Toast.makeText(MainActivity.this, "Module built successfully!", Toast.LENGTH_SHORT).show();
        });
    }

    private void copyFontListToDir(List<FontItem> items, File targetDir) throws Exception {
        for (FontItem item : items) {
            if (item.name.toLowerCase().endsWith(".zip")) {
                // If user selected a zip pack containing fonts, extract fonts from it
                try (InputStream is = getContentResolver().openInputStream(item.uri);
                     ZipInputStream zis = new ZipInputStream(is)) {
                    ZipEntry entry;
                    byte[] buf = new byte[65536];
                    while ((entry = zis.getNextEntry()) != null) {
                        String name = new File(entry.getName()).getName();
                        String lower = name.toLowerCase();
                        if (lower.endsWith(".ttf") || lower.endsWith(".otf") || lower.endsWith(".ttc") || lower.endsWith(".woff") || lower.endsWith(".woff2")) {
                            File dest = new File(targetDir, name);
                            try (FileOutputStream fos = new FileOutputStream(dest)) {
                                int len;
                                while ((len = zis.read(buf)) > 0) {
                                    fos.write(buf, 0, len);
                                }
                            }
                        }
                        zis.closeEntry();
                    }
                }
            } else {
                File dest = new File(targetDir, item.name);
                try (InputStream in = getContentResolver().openInputStream(item.uri);
                     OutputStream out = new FileOutputStream(dest)) {
                    byte[] buf = new byte[65536];
                    int len;
                    while ((len = in.read(buf)) > 0) {
                        out.write(buf, 0, len);
                    }
                }
            }
        }
    }

    private Uri saveZipToDownloads(File zipFile) {
        String fileName = zipFile.getName();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.Downloads.DISPLAY_NAME, fileName);
            values.put(MediaStore.Downloads.MIME_TYPE, "application/zip");
            values.put(MediaStore.Downloads.IS_PENDING, 1);

            ContentResolver resolver = getContentResolver();
            Uri uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
            if (uri != null) {
                try (InputStream in = new FileInputStream(zipFile);
                     OutputStream out = resolver.openOutputStream(uri)) {
                    byte[] buf = new byte[65536];
                    int len;
                    while ((len = in.read(buf)) > 0) {
                        out.write(buf, 0, len);
                    }
                    values.clear();
                    values.put(MediaStore.Downloads.IS_PENDING, 0);
                    resolver.update(uri, values, null, null);
                    appendLog("Saved to Downloads via MediaStore: " + fileName);
                    return uri;
                } catch (Exception e) {
                    appendLog("Failed writing to MediaStore: " + e.getMessage());
                }
            }
        }

        // Fallback for Android 9 and older
        try {
            File publicDownloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
            publicDownloads.mkdirs();
            File dest = new File(publicDownloads, fileName);
            try (InputStream in = new FileInputStream(zipFile);
                 OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[65536];
                int len;
                while ((len = in.read(buf)) > 0) {
                    out.write(buf, 0, len);
                }
            }
            appendLog("Saved to public Downloads: " + dest.getAbsolutePath());
            return Uri.fromFile(dest);
        } catch (Exception e) {
            appendLog("Failed to write to public Downloads: " + e.getMessage());
            return Uri.fromFile(zipFile);
        }
    }

    private void openDownloadsFolder() {
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW);
            if (lastSavedDownloadUri != null) {
                intent.setDataAndType(lastSavedDownloadUri, "application/zip");
            } else {
                intent.setDataAndType(Uri.parse(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()), "*/*");
            }
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(this, "Find your module in the Downloads folder!", Toast.LENGTH_LONG).show();
        }
    }

    private void shareGeneratedModule() {
        if (lastGeneratedZip == null || !lastGeneratedZip.exists()) {
            Toast.makeText(this, "No module file available to share", Toast.LENGTH_SHORT).show();
            return;
        }

        try {
            Uri shareUri = Uri.parse("content://" + MffmFileProvider.AUTHORITY + "/" + lastGeneratedZip.getAbsolutePath());
            Intent intent = new Intent(Intent.ACTION_SEND);
            intent.setType("application/zip");
            intent.putExtra(Intent.EXTRA_STREAM, shareUri);
            intent.putExtra(Intent.EXTRA_SUBJECT, lastGeneratedZip.getName());
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(intent, "Share Flashable Module"));
        } catch (Exception e) {
            Toast.makeText(this, "Share failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void flashModuleWithRoot() {
        if (lastGeneratedZip == null || !lastGeneratedZip.exists()) {
            Toast.makeText(this, "No module available to flash", Toast.LENGTH_SHORT).show();
            return;
        }

        appendLog("\nAttempting root installation...");
        new Thread(() -> {
            try {
                String zipPath = lastGeneratedZip.getAbsolutePath();
                String script = "if command -v magisk >/dev/null 2>&1; then magisk --install-module '" + zipPath + "'; " +
                        "elif [ -f /data/adb/ksu/bin/ksud ]; then /data/adb/ksu/bin/ksud module install '" + zipPath + "'; " +
                        "elif [ -f /data/adb/ap/bin/apd ]; then /data/adb/ap/bin/apd module install '" + zipPath + "'; " +
                        "else echo 'No compatible root manager command found (Magisk/KSU/APatch)'; exit 1; fi";

                Process su = Runtime.getRuntime().exec(new String[]{"su", "-c", script});
                BufferedReader reader = new BufferedReader(new InputStreamReader(su.getInputStream()));
                String line;
                while ((line = reader.readLine()) != null) {
                    appendLog("[ROOT] " + line);
                }
                int code = su.waitFor();
                if (code == 0) {
                    mainHandler.post(() -> Toast.makeText(MainActivity.this, "Module flashed successfully! Reboot to apply.", Toast.LENGTH_LONG).show());
                } else {
                    mainHandler.post(() -> Toast.makeText(MainActivity.this, "Flashing failed or root denied.", Toast.LENGTH_LONG).show());
                }
            } catch (Exception e) {
                appendLog("[ROOT ERROR] " + e.getMessage());
                mainHandler.post(() -> Toast.makeText(MainActivity.this, "Root not available: " + e.getMessage(), Toast.LENGTH_SHORT).show());
            }
        }).start();
    }

    private void updateStatus(String status) {
        mainHandler.post(() -> tvStatus.setText(status));
    }

    private void appendLog(String message) {
        mainHandler.post(() -> {
            tvConsole.append(message + "\n");
            scrollConsole.post(() -> scrollConsole.fullScroll(View.FOCUS_DOWN));
        });
    }

    private void unzipAsset(String assetName, File destDir) throws Exception {
        destDir.mkdirs();
        try (InputStream is = getAssets().open(assetName);
             ZipInputStream zis = new ZipInputStream(is)) {
            ZipEntry entry;
            byte[] buffer = new byte[65536];
            while ((entry = zis.getNextEntry()) != null) {
                File file = new File(destDir, entry.getName());
                if (entry.isDirectory()) {
                    file.mkdirs();
                } else {
                    File parent = file.getParentFile();
                    if (parent != null && !parent.exists()) {
                        parent.mkdirs();
                    }
                    try (FileOutputStream fos = new FileOutputStream(file)) {
                        int len;
                        while ((len = zis.read(buffer)) > 0) {
                            fos.write(buffer, 0, len);
                        }
                    }
                    if (file.getName().endsWith(".sh") || file.getName().contains("python") || file.getName().contains("zipsignerust")) {
                        file.setExecutable(true, false);
                    }
                }
                zis.closeEntry();
            }
        }
    }

    private void deleteRecursive(File fileOrDirectory) {
        if (fileOrDirectory.isDirectory()) {
            File[] children = fileOrDirectory.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursive(child);
                }
            }
        }
        fileOrDirectory.delete();
    }
}
