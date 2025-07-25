// src/firebase.js
import { initializeApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

// Your Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyB6glH7pERFXc8Cqk_Qv3mdqwmmx0YAN2g",
  authDomain: "movie-journal-6e7f5.firebaseapp.com",
  projectId: "movie-journal-6e7f5",
  storageBucket: "movie-journal-6e7f5.appspot.com", // <- fixed .app typo
  messagingSenderId: "128353456086",
  appId: "1:128353456086:web:3b9f24df922932721a5e77"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// ✅ Export Firestore database
export const db = getFirestore(app);
