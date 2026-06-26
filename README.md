- 👋 Hi, I’m @ZeroXenon9
- 👀 I’m interested in learning how to code
- 🌱 I’m currently learning cpp
- 💞️ I’m looking to collaborate on nothing much hehe
- 📫 How to reach me facebook: Ivan How

<!---
ZeroXenon9/ZeroXenon9 is a ✨ special ✨ repository because its `README.md` (this file) appears on your GitHub profile.
You can click the Preview link to take a look at your changes.
--->

---

## FaceFilter — Delete Photos by Person

A simple web app to upload photos and remove all images of a specific person in one click.

### Features
- Upload any number of photos (JPG, PNG, WEBP, GIF)
- Pick a reference photo of the person you want to remove
- Scans your entire library using face recognition
- Delete all matches instantly with one button

### How to run

**Requirements:** Python 3.10+, cmake

```bash
# Install dependencies
pip install "setuptools<72"
pip install -r requirements.txt

# Start the app
python app.py
```

Then open **http://localhost:5000** in your browser.

### How to use

1. **Upload** your photos in Step 1
2. In Step 3, upload one clear front-facing photo of the person you want to remove
3. Click **Find This Person** — the app scans your entire library
4. Click **Delete All Matches** to remove every photo with that person

> All processing happens locally. No photos are sent anywhere.
