// =============================================================
// OZONE STUDIOS — Firebase initialisation
// Loaded as an ES module from index.html and admin/index.html.
// Exposes a window.ozFB API that classic scripts can use.
// =============================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js";
import {
  getFirestore,
  collection,
  doc,
  addDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  getDoc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp
} from "https://www.gstatic.com/firebasejs/11.0.2/firebase-firestore.js";
import {
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  updateProfile,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as fbSignOut
} from "https://www.gstatic.com/firebasejs/11.0.2/firebase-auth.js";

const firebaseConfig = {
  apiKey: "YOUR_FIREBASE_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT",
  storageBucket: "YOUR_PROJECT.firebasestorage.app",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);

// ---------- Bookings (sessions + service requests) ----------
async function addBooking(record) {
  // Compose a browsable doc ID: <email>_<iso-timestamp>. The timestamp ensures
  // uniqueness for repeat bookings by the same customer. If no email is
  // supplied, fall back to "anon".
  const safeEmail = (record.email && record.email.trim()) || "anon";
  const id = safeEmail + "_" + new Date().toISOString();
  await setDoc(doc(db, "bookings", id), {
    ...record,
    createdAt: serverTimestamp()
  });
  return { id };
}
function watchBookings(cb) {
  const q = query(collection(db, "bookings"), orderBy("createdAt", "desc"));
  return onSnapshot(q, (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}
async function updateBookingStatus(id, status) {
  return updateDoc(doc(db, "bookings", id), { status });
}
async function deleteBooking(id) {
  return deleteDoc(doc(db, "bookings", id));
}

// ---------- Slot reservations (public-readable, admin-writeable) ----------
// A tiny doc per confirmed session: { studio, date, time, bookingId, customerName }.
// Keyed by "<studio>_<date>_<time>" so confirming the same slot twice overwrites.
function slotKey(studio, date, time) {
  return studio + "_" + date + "_" + time;
}
function watchSlotReservations(cb) {
  return onSnapshot(collection(db, "slotReservations"), (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}
async function setSlotReservation(data) {
  const key = slotKey(data.studio, data.date, data.time);
  return setDoc(doc(db, "slotReservations", key), {
    studio: data.studio,
    date: data.date,
    time: data.time,
    bookingId: data.bookingId || "",
    customerName: data.customerName || "",
    reservedAt: serverTimestamp()
  });
}
async function clearSlotReservation(studio, date, time) {
  return deleteDoc(doc(db, "slotReservations", slotKey(studio, date, time)));
}

// ---------- Beats ----------
function watchBeats(cb) {
  const q = query(collection(db, "beats"), orderBy("createdAt", "asc"));
  return onSnapshot(q, (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}
async function addBeat(record) {
  return addDoc(collection(db, "beats"), {
    ...record,
    createdAt: serverTimestamp()
  });
}
async function updateBeat(id, patch) {
  return updateDoc(doc(db, "beats", id), patch);
}
async function deleteBeat(id) {
  return deleteDoc(doc(db, "beats", id));
}

// ---------- Offers ----------
function watchOffers(cb) {
  const q = query(collection(db, "offers"), orderBy("createdAt", "desc"));
  return onSnapshot(q, (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}
async function addOffer(record) {
  return addDoc(collection(db, "offers"), {
    ...record,
    active: record.active !== false,
    createdAt: serverTimestamp()
  });
}
async function updateOffer(id, patch) {
  return updateDoc(doc(db, "offers", id), patch);
}
async function deleteOffer(id) {
  return deleteDoc(doc(db, "offers", id));
}

// ---------- Users (signed-up customers) — admin only via rules ----------
function watchUsers(cb) {
  return onSnapshot(collection(db, "users"), (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}

// ---------- Team ----------
function watchTeam(cb) {
  const q = query(collection(db, "team"), orderBy("order", "asc"));
  return onSnapshot(q, (snap) => {
    cb(snap.docs.map((d) => ({ id: d.id, ...d.data() })));
  });
}
async function addTeamMember(record) {
  return addDoc(collection(db, "team"), {
    ...record,
    createdAt: serverTimestamp()
  });
}
async function updateTeamMember(id, patch) {
  return updateDoc(doc(db, "team", id), patch);
}
async function deleteTeamMember(id) {
  return deleteDoc(doc(db, "team", id));
}

// ---------- Auth ----------
async function signIn(email, password) {
  return signInWithEmailAndPassword(auth, email, password);
}
async function signUp(email, password, profile) {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  if (cred.user) {
    if (profile && profile.displayName) {
      try { await updateProfile(cred.user, { displayName: profile.displayName }); }
      catch (err) { console.warn("[ozone] updateProfile failed:", err); }
    }
    // Mirror profile into Firestore keyed by the user's email (browsable in the
    // Firestore console). Auth itself doesn't store phone for password users.
    try {
      const docKey = cred.user.email || email;
      await setDoc(doc(db, "users", docKey), {
        uid: cred.user.uid,
        firstName: profile?.firstName || "",
        lastName: profile?.lastName || "",
        displayName: profile?.displayName || "",
        email: cred.user.email || email,
        phone: profile?.phone || "",
        createdAt: serverTimestamp()
      });
    } catch (err) {
      console.error("[ozone] users/{email} profile write failed:", err);
    }
  }
  return cred;
}
// Returns a merged profile for the currently signed-in user:
//   - the Firestore doc at users/{email}, if it exists
//   - falling back to whatever Firebase Auth knows
async function getMyProfile() {
  const user = auth.currentUser;
  if (!user) {
    console.warn("[ozone-profile] getMyProfile called with no auth user");
    return null;
  }
  const isGoogle = (user.providerData || []).some((p) => p.providerId === "google.com");
  let firestoreData = null;
  if (user.email) {
    const lookupKey = user.email;
    console.log("[ozone-profile] looking up users/" + lookupKey, {
      authEmail: user.email,
      tokenEmail: (await user.getIdTokenResult()).claims.email
    });
    try {
      const snap = await getDoc(doc(db, "users", lookupKey));
      if (snap.exists()) {
        firestoreData = snap.data();
        console.log("[ozone-profile] doc FOUND for", lookupKey, firestoreData);
      } else {
        console.warn("[ozone-profile] doc NOT FOUND at users/" + lookupKey + " — falling back to Auth-only data");
      }
    } catch (err) {
      console.error("[ozone-profile] read failed for users/" + lookupKey + ":", err);
    }
  }
  const parts = (user.displayName || "").trim().split(/\s+/);
  return {
    uid: user.uid,
    firstName: firestoreData?.firstName || parts[0] || "",
    lastName:  firestoreData?.lastName  || parts.slice(1).join(" "),
    displayName: firestoreData?.displayName || user.displayName || "",
    email:    firestoreData?.email   || user.email || "",
    phone:    firestoreData?.phone   || user.phoneNumber || "",
    photoURL: firestoreData?.photoURL || user.photoURL || "",
    provider: firestoreData?.provider || (isGoogle ? "google" : "password")
  };
}

// Add/overwrite fields on the current user's profile doc.
async function updateMyProfile(patch) {
  const user = auth.currentUser;
  if (!user || !user.email) return;
  try {
    await setDoc(doc(db, "users", user.email), { ...patch, email: user.email }, { merge: true });
  } catch (_) {}
}

async function signInWithGoogle() {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  const cred = await signInWithPopup(auth, provider);
  // Mirror the Google profile into our users collection (merge: don't overwrite
  // a phone the customer may have entered earlier via the email signup form).
  if (cred && cred.user) {
    const u = cred.user;
    const userEmail = u.email || "";
    if (userEmail) {
      const parts = (u.displayName || "").trim().split(/\s+/);
      const firstName = parts[0] || "";
      const lastName = parts.slice(1).join(" ");
      try {
        await setDoc(doc(db, "users", userEmail), {
          uid: u.uid,
          firstName,
          lastName,
          displayName: u.displayName || "",
          email: userEmail,
          phone: u.phoneNumber || "",
          photoURL: u.photoURL || "",
          provider: "google",
          createdAt: serverTimestamp()
        }, { merge: true });
      } catch (_) {}
    }
  }
  return cred;
}
async function signOut() {
  return fbSignOut(auth);
}
function onAuth(cb) {
  return onAuthStateChanged(auth, cb);
}

// ---------- Expose to classic scripts ----------
window.ozFB = {
  app,
  db,
  auth,
  // bookings
  addBooking,
  watchBookings,
  updateBookingStatus,
  deleteBooking,
  // slot reservations (sessions only)
  watchSlotReservations,
  setSlotReservation,
  clearSlotReservation,
  // users (signed-up customers)
  watchUsers,
  // beats
  watchBeats,
  addBeat,
  updateBeat,
  deleteBeat,
  // offers
  watchOffers,
  addOffer,
  updateOffer,
  deleteOffer,
  // team
  watchTeam,
  addTeamMember,
  updateTeamMember,
  deleteTeamMember,
  // auth
  signIn,
  signUp,
  signInWithGoogle,
  signOut,
  onAuth,
  getMyProfile,
  updateMyProfile,
  ready: true
};

// Dispatch a ready event so anything that wants to wait can listen
window.dispatchEvent(new CustomEvent("oz-firebase-ready"));
