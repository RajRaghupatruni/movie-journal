// DEPRECATED MIGRATION REFERENCE: Geoapify-backed ProviderSearch is the active flow.
import React, { useState, useEffect } from "react";
import { legacyProviderRequest, legacyProviderSearchEnabled } from "../lib/legacyProviders";

const FoursquareSearch = ({ onSelect }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const [coords, setCoords] = useState(null); // { lat, lng }
  const [fallbackCity, setFallbackCity] = useState("New York");

  // Get geolocation on mount
  useEffect(() => {
    if (!legacyProviderSearchEnabled || !navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
      },
      (err) => {
        console.warn("Geolocation denied or unavailable:", err.message);
        setCoords(null); // fallback will kick in
      },
      { timeout: 5000 }
    );
  }, []);

  const handleSearch = async (input) => {
    if (!legacyProviderSearchEnabled || !input) return;

    setLoading(true);

    try {
      let url = `/places/search?query=${encodeURIComponent(input)}&limit=5`;

      if (coords) {
        url += `&ll=${coords.lat},${coords.lng}`;
      } else if (fallbackCity) {
        url += `&near=${encodeURIComponent(fallbackCity)}`;
      }

      const res = await legacyProviderRequest(url);

      if (!res.ok) {
        const errText = await res.text();
        console.error("Foursquare API error:", errText);
      }

      const data = await res.json();
      setResults(data.results || []);
    } catch (err) {
      console.error("Foursquare fetch error:", err);
    }

    setLoading(false);
  };

  useEffect(() => {
    const timeout = setTimeout(() => {
      handleSearch(query);
    }, 400);
    return () => clearTimeout(timeout);
  }, [query]);

  const handleSelect = (place) => {
    const location = {
      name: place.name,
      lat: place.geocodes.main.latitude,
      lng: place.geocodes.main.longitude,
      address: place.location.formatted_address || "",
      source: "foursquare",
    };
    onSelect(location);
    setQuery(place.name);
    setResults([]);
  };

  return (
    <div className="relative space-y-2">
      {!legacyProviderSearchEnabled && <p role="status" className="text-sm text-gray-400">Place search is temporarily unavailable.</p>}
      {!coords && (
        <input
          disabled={!legacyProviderSearchEnabled}
          value={fallbackCity}
          onChange={(e) => setFallbackCity(e.target.value)}
          placeholder="Enter city for search (e.g. Dallas)"
          className="w-full bg-zinc-700 p-2 rounded text-white"
        />
      )}

      <input
        disabled={!legacyProviderSearchEnabled}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a place..."
        className="w-full bg-zinc-800 p-2 rounded text-white"
      />

      {loading && <p className="text-sm text-gray-400">Searching...</p>}
      {!loading && query && results.length === 0 && (
        <p className="text-sm text-gray-400">No places found.</p>
      )}
      {results.length > 0 && (
        <ul className="absolute bg-zinc-800 w-full mt-1 rounded shadow-lg z-10 max-h-60 overflow-y-auto">
          {results.map((place) => (
            <li
              key={place.fsq_id}
              className="p-2 hover:bg-zinc-700 cursor-pointer text-sm"
              onClick={() => handleSelect(place)}
            >
              <div className="font-semibold">{place.name}</div>
              <div className="text-gray-400 text-xs">
                {place.location.formatted_address}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default FoursquareSearch;
