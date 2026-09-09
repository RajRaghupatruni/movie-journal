> Historical planning notes. Follow `docs/TARGET_ARCHITECTURE.md` and the ordered migration tasks in `docs/REPOSITORY_AUDIT.md`; the old feature prompts below are not current instructions.

Got it. If typing real place names like "Starbucks" or "Empire State Building" isn't returning results even after setting `near=New York`, we’ll address that in the next patch. But before that, let’s organize our **remaining steps for Module 3** so you have a clear picture.

---

## ✅ **Module 3: Collaborative Event Tracking (Places, Movies, Activities)**

You’ve completed:

| Step    | Feature                                               |
| ------- | ----------------------------------------------------- |
| **3.1** | Add Event Modal UI                                    |
| **3.2** | Firestore Save (tandems → events subcollection)       |
| **3.3** | Timeline View showing added events                    |
| **3.4** | Place Search using Foursquare API (buggy, will patch) |

---

## 🔜 Remaining Steps in **Module 3**

### 🔹 **3.5: Fix Place Search Issues (Foursquare)**

* ✅ Show UI and query works.
* 🛠 Patch needed: `near=New York` alone often fails. Better options:

  * Use `ll=latitude,longitude` from browser geolocation (accurate).
  * Fallback: Add `location` input box (user types city).
* ✅ Optional: Show categories/tags of places.

➡️ **Next step:** Patch 3.5 with real geolocation or manual fallback.

---

### 🔹 **3.6: Add Event Preview Before Saving**

* Preview event details in a card below the modal before pressing "Save".
* Gives users confirmation before writing to Firestore.

---

### 🔹 **3.7: Display Events for Logged-in User or Shared Group Only**

* For now, you’re using a placeholder `tandemId = test-tandem-id`.
* This will be replaced with:

  * Authenticated user’s ID (once login added in Module 6).
  * Group-based Tandem IDs (Module 2).

---

### 🔹 **3.8: Add Edit/Delete Functionality**

* Allow editing events.
* Allow deleting an event from the timeline.

---

### 🔹 **3.9: Filter/Sort Events in Timeline**

* By category (Movie / Place / Trip / Activity)
* By date (newest → oldest, oldest → newest)
* Optional: Filter by rating or participant name

---

### 🔹 **3.10: Optional UX Upgrades**

* 🧭 Location preview map (via static image from Google Maps / Mapbox)
* 📷 Upload a photo with the event
* 🕘 Time of day selection (currently only date)

---

## ⚡ What You Should Do Now

1. ✅ Let’s **fix place search (3.5)** using browser geolocation (best fix).
2. Then implement **event preview (3.6)** before save.
3. Then move to **edit/delete (3.8)**.

---

Would you like to proceed with patching **3.5** (fixing place search with geolocation or fallback input)? I can prepare the complete working `FoursquareSearch.jsx` for you.
