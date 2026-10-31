# Websites

Front-end work: plain HTML, CSS and JavaScript, no build step. Open any `index.html` /
`.html` file in a browser, or serve the folder with `python -m http.server`.

| Project | What it is |
|---|---|
| [ozone-booking](ozone-booking/) | Marketing site and booking system for a Cairo recording studio: two rooms with their own calendars and time slots, beat store, team and gear pages, WhatsApp hand-off, and a staff **admin panel** (bookings dashboard, status changes). Firebase Auth + Firestore. See [PRODUCT.md](ozone-booking/PRODUCT.md) and [DESIGN.md](ozone-booking/DESIGN.md). |
| [tourism-templates](tourism-templates/) | Two travel templates: **Voyago** (trips) and **Auriga** (coastal hotel and private suites). |

## Ozone booking: Firebase

The real project's Firebase config has been replaced with placeholders. To run bookings
and sign-in, create a Firebase project (Auth with email/password + Google, and Firestore),
paste its web config into `ozone-booking/assets/firebase-init.js`, and set the admin email
in `ozone-booking/script.js` and `ozone-booking/admin/admin.js`. Without it the site still
renders; only the live booking/auth calls fail.

Run it locally with `start-ozone.bat` (or `python -m http.server 5174`), then open
http://localhost:5174/ and http://localhost:5174/admin/.
