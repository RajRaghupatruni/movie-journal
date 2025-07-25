// src/firebaseHelpers.js
import {
  collection,
  addDoc,
  getDocs,
  deleteDoc,
  doc,
} from "firebase/firestore";
import { db } from "./firebase";

const MOVIES_COLLECTION = "watchedMovies";

export const fetchMovies = async () => {
  const snapshot = await getDocs(collection(db, MOVIES_COLLECTION));
  return snapshot.docs.map((doc) => ({ id: doc.id, ...doc.data() }));
};

export const addMovie = async (movie) => {
  await addDoc(collection(db, MOVIES_COLLECTION), movie);
};

export const deleteMovie = async (firebaseId) => {
  await deleteDoc(doc(db, MOVIES_COLLECTION, firebaseId));
};
