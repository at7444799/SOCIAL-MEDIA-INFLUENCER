# AI Influencer Auto Posting Bot

This bot posts influencer photo carousels automatically to:

- Instagram
- Facebook Page

It selects **2 photos per post** from category folders, generates a fresh caption using NVIDIA API, posts to both platforms, then deletes the used photos so they are never reused.

---

## 1. Folder Structure

Upload your photos into these folders:

```text
media/photos/morning/bed/
media/photos/morning/office/

media/photos/evening/nightlife/
media/photos/evening/club/

media/photos/weekend/travel/
media/photos/weekend/trip/
```

You can create more subfolders inside morning/evening/weekend.  
The bot searches subfolders automatically.

Examples:

```text
media/photos/morning/bed/photo1.jpg
media/photos/morning/bed/photo2.jpg

media/photos/evening/club/photo1.jpg
media/photos/evening/club/photo2.jpg

media/photos/weekend/travel/photo1.jpg
media/photos/weekend/trip/photo2.jpg
```

The bot needs at least **2 images** in the selected category.

---

## 2. Schedule

GitHub Actions runs automatically:

```text
Morning post: 8:30 AM India time
Evening post: 8:30 PM India time
Weekend post: 11:00 AM India time on Saturday and Sunday
```

Manual run is also available:

```text
GitHub → Actions → Auto Post Influencer Photos → Run workflow
```

Choose:

```text
auto
morning
evening
weekend
```

---

## 3. GitHub Secrets

Go to:

```text
GitHub repo → Settings → Secrets and variables → Actions → New repository secret
```

Add these:

```env
FB_PAGE_ID=your_facebook_page_id
FB_PAGE_ACCESS_TOKEN=your_page_access_token
IG_USER_ID=your_instagram_business_id
NVIDIA_API_KEY=your_nvidia_api_key
```

Optional:

```env
NVIDIA_MODEL=meta/llama-3.1-70b-instruct
```

---

## 4. Required Meta Permissions

For Facebook Page posting:

```text
pages_show_list
pages_read_engagement
pages_manage_posts
```

For Instagram posting:

```text
instagram_basic
instagram_content_publish
```

Useful/common:

```text
business_management
```

Use your regenerated Page Access Token after adding permissions.

---

## 5. Important

Your GitHub repository must be **public** because Instagram/Facebook need to fetch image URLs from GitHub raw URLs.

After successful posting, the bot deletes used images and commits that deletion back to GitHub.

---

## 6. Videos

Manual video folder is included:

```text
media/videos/manual/
```

This first version is for photo carousel posting. Video/Reels automation can be added after photo posting works.
