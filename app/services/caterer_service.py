from __future__ import annotations
from typing import Optional


class CatererService:
    def __init__(self, router) -> None:
        self.router = router

    def _build_prompt(self, destination: str, catering_cost: float, guest_count: int, currency: str = "INR") -> str:
        per_plate = int(catering_cost / guest_count) if guest_count > 0 else 2000
        return (
            f"Find 5 real catering companies available for weddings in {destination}.\n"
            f"For each caterer provide exactly in this format:\n"
            f"Caterer: <name>\n"
            f"Cuisine: <cuisine types>\n"
            f"Price per plate: <price in {currency}>\n"
            f"Rating: <Google rating out of 5>\n"
            f"Contact: <phone or website>\n"
            f"Why they fit: <one line reason>\n"
            f"---\n"
            f"The couple has a catering budget of {currency} {int(catering_cost):,} for {guest_count} guests "
            f"(approx {currency} {per_plate:,}/plate). Only suggest caterers whose price per plate fits this budget. "
            f"Focus on mid-range to premium caterers, NOT ultra-luxury 5-star hotel catering. "
            f"Suggest realistic options a wedding couple would actually book."
        )

    def _detect_currency(self, destination: str) -> str:
        """Detect currency based on destination country/city."""
        destination_lower = destination.lower()
        currency_map = {
            # India
            ("india", "goa", "jaipur", "mumbai", "delhi", "bangalore", "udaipur",
             "hyderabad", "chennai", "kolkata", "pune", "agra", "kerala"): "INR",
            # UAE
            ("dubai", "abu dhabi", "uae", "sharjah", "ajman"): "AED",
            # UK
            ("london", "uk", "england", "manchester", "edinburgh"): "GBP",
            # USA
            ("new york", "usa", "los angeles", "chicago", "miami", "las vegas"): "USD",
            # Europe
            ("paris", "france", "italy", "rome", "barcelona", "spain"): "EUR",
            # Singapore
            ("singapore",): "SGD",
            # Thailand
            ("thailand", "bangkok", "phuket"): "THB",
            # Maldives
            ("maldives",): "USD",
        }
        for keywords, currency in currency_map.items():
            if any(k in destination_lower for k in keywords):
                return currency
        return "USD"  # default fallback

    def fetch_caterers(self, destination: str, catering_cost: float, guest_count: int) -> list[dict]:
        currency = self._detect_currency(destination)
        prompt = self._build_prompt(destination, catering_cost, guest_count, currency)
        try:
            result = self.router.generate_text(prompt)
            print(f"[CatererService DEBUG] Raw response:\n{result}\n")
            return self._parse_caterers(result or "")
        except Exception as e:
            print(f"[CatererService] Could not fetch caterers: {e}")
            return []

    def _parse_caterers(self, raw: str) -> list[dict]:
        caterers = []
        blocks = raw.strip().split("---")
        for block in blocks:
            lines = block.strip().splitlines()
            c: dict = {}
            for line in lines:
                if line.startswith("Caterer:"):
                    c["name"] = line.replace("Caterer:", "").strip()
                elif line.startswith("Cuisine:"):
                    c["cuisine"] = line.replace("Cuisine:", "").strip()
                elif line.startswith("Price per plate:"):
                    c["price_per_plate"] = line.replace("Price per plate:", "").strip()
                elif line.startswith("Rating:"):
                    c["rating"] = line.replace("Rating:", "").strip()
                elif line.startswith("Contact:"):
                    c["contact"] = line.replace("Contact:", "").strip()
                elif line.startswith("Why they fit:"):
                    c["why"] = line.replace("Why they fit:", "").strip()
            if "name" in c:
                caterers.append(c)
        return caterers

    def prompt_user_selection(self, caterers: list[dict]) -> Optional[dict]:
        if not caterers:
            print("\n[!] No caterers found for your location and budget.")
            return None

        print("\n🍽️  Available Caterers in your area:\n")
        for i, c in enumerate(caterers, 1):
            print(f"  {i}. {c.get('name', 'N/A')}")
            print(f"     Cuisine    : {c.get('cuisine', 'N/A')}")
            print(f"     Per Plate  : {c.get('price_per_plate', 'N/A')}")
            print(f"     Rating     : {c.get('rating', 'N/A')} ⭐")
            print(f"     Contact    : {c.get('contact', 'N/A')}")
            print(f"     Note       : {c.get('why', '')}\n")

        while True:
            try:
                choice = int(input(f"👉 Select a caterer (1-{len(caterers)}): "))
                if 1 <= choice <= len(caterers):
                    selected = caterers[choice - 1]
                    print(f"\n✅ You selected: {selected['name']}\n")
                    return selected
                else:
                    print(f"Please enter a number between 1 and {len(caterers)}.")
            except ValueError:
                print("Please enter a valid number.")
