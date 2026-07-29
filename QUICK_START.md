# MFFMv14 Quick Start & Usage Guide

### What is MFFMv14?

**MFFMv14 (Magisk Flashable Font Module v14)** is an automated tool and template designed to build flashable Android font modules for **Magisk**, **KernelSU**, and **APatch**. It replaces default Android system fonts (like Roboto) with custom static or variable fonts while maintaining complete system compatibility.

---

### Main Features & Capabilities

- **Automatic Font Mode & Format Support**: Handles static (`.ttf`, `.otf`) and variable (`fvar` axes) fonts, including compressed webfont formats (`.woff`, `.woff2`).
- **OpenType Feature Freezer**: Lets you freeze specific stylistic alternates (e.g., open digits `ss01`, alternate letters `cv01`) directly into the font.
- **Dynamic Module Naming**: Automatically appends applied feature tags (e.g., `(ss02, cv11)`) to the module name in `module.prop` and the generated `.zip` filename.
- **Auto-Signing**: Automatically signs generated ZIP files so they are immediately ready to flash.
- **Batch Migration Tool**: Upgrades older MFFM font modules onto the new MFFMv14 template core.

---

### Prerequisites & Dependency Installation

Before running the scripts, make sure you have Python 3.9+ installed and run the following command in your terminal to install all required dependencies:

```bash
# Install Python dependencies from requirements.txt
pip install -r requirements.txt
```

*(Optional)* You can also install OpenType Feature Freezer globally via `pipx`:
```bash
pipx install opentype-feature-freezer
```

---

### Basic Usage Guide

- **Step 1: Install Dependencies**
  - Run `pip install -r requirements.txt`.

- **Step 2: Add Your Fonts**
  - Place your source font files (`.ttf`, `.otf`, `.ttc`, `.otc`, `.woff`, `.woff2`) inside the `Fonts/` folder.

- **Step 3: Build the Module (Interactive)**
  - Run the following command in your terminal:
    ```bash
    python build.py
    ```
  - Press `y` when prompted if you want to view and freeze any Stylistic Sets or Character Variants.

- **Step 4: Build Non-Interactively (Optional)**
  - To freeze specific features directly via command line:
    ```bash
    python build.py --features "ss02,ss03,cv11"
    ```

- **Step 5: Update Legacy Modules (Optional)**
  - Place older MFFM ZIP files inside `Old Modules/` and run:
    ```bash
    python update.py
    ```

- **Step 6: Flash**
  - Grab your finished flashable `.zip` from the `dist/` directory and flash it using Magisk, KernelSU, or APatch.
