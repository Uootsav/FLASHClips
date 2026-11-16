# How to publish FLASHClips on GitHub (step by step)

## 1. One-time setup
1. Create a free account at https://github.com
2. Install **Git**: https://git-scm.com/download/win
3. Create your support page at https://www.buymeacoffee.com (free)
4. Replace these placeholders (search "YOUR_"):
   - `flashclips/config.py` → `SUPPORT_URL` and `GITHUB_URL`
   - `README.md` → `YOUR_NAME` and `YOUR_USERNAME`

## 2. Create the repository
1. GitHub → **+** (top right) → **New repository**
2. Name: `FLASHClips` · **Public** · do NOT add a README (you already have one) → **Create**

## 3. Upload the code (in the FLASHClips folder, open a terminal)
```bash
git init
git add .
git commit -m "FLASHClips v1.0.0"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/FLASHClips.git
git push -u origin main
```

## 4. Build the Windows app automatically and publish the Release
```bash
git tag v1.0.0
git push origin v1.0.0
```
GitHub Actions (the **Actions** tab) now builds `FLASHClips-Setup.exe` and the portable zip
on GitHub's Windows servers (~10–15 min) and attaches them to a new **Release**. Users download from
`https://github.com/YOUR_USERNAME/FLASHClips/releases/latest`.

To test a build without releasing: **Actions → Build & Release FLASHClips → Run workflow**.

## 5. Show the coffee button on GitHub
Create `.github/FUNDING.yml` containing:
```yaml
buy_me_a_coffee: YOUR_NAME
```
GitHub then shows a **Sponsor** button on your repo.

## 6. When YouTube downloads stop working
YouTube changes things sometimes and yt-dlp fixes them within days. Just release a new version:
1. Change `__version__` in `flashclips/__init__.py` (e.g. "1.0.1")
2. `git commit -am "v1.0.1" && git tag v1.0.1 && git push && git push origin v1.0.1`

The build installs the newest yt-dlp, and existing users get an "update available" popup.

## 7. Tips to get users
- Add screenshots/GIF to the README · topics: `ai`, `shorts`, `tiktok`, `video-editor`, `whisper`
- Post on Reddit (r/NewTubers, r/opensource, r/SideProject), Product Hunt and YouTube
- Windows SmartScreen may warn about the unsigned .exe at first ("More info → Run anyway").
  This goes away as downloads grow, or with a code-signing certificate.

## 8. Microsoft Store (later)
Register at https://partner.microsoft.com (individual developer account), package the built
app as MSIX with the free **MSIX Packaging Tool**, and submit. Free apps are allowed.
