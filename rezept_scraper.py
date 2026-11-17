import json
import re
import sqlite3
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
}


# --- 1. DATENBANK ---
def erstelle_datenbank():
  conn = sqlite3.connect("rezepte.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS rezepte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titel TEXT,
            url TEXT UNIQUE,
            zutaten TEXT
        )
    """)
  conn.commit()
  conn.close()


def speichere_rezept(titel, url, zutaten):
  conn = sqlite3.connect("rezepte.db")
  cursor = conn.cursor()
  zutaten_text = ", ".join(zutaten) if isinstance(zutaten, list) else zutaten
  try:
    cursor.execute(
        "INSERT OR IGNORE INTO rezepte (titel, url, zutaten) VALUES (?, ?, ?)",
        (titel, url, zutaten_text),
    )
    conn.commit()
    print(f"📝 Hab ich mir direkt für nächstes Mal notiert: '{titel}'")
  except Exception as e:
    print(f"❌ Mir ist mein Stift kaputt gegangen: {e}")
  finally:
    conn.close()


def suche_in_datenbank(suchbegriffe):
  conn = sqlite3.connect("rezepte.db")
  cursor = conn.cursor()

  bedingungen = []
  parameter = []
  for wort in suchbegriffe:
    bedingungen.append("(LOWER(zutaten) LIKE ? OR LOWER(titel) LIKE ?)")
    parameter.extend([f"%{wort.lower()}%", f"%{wort.lower()}%"])

  sql = f"SELECT titel, url, zutaten FROM rezepte WHERE {' OR '.join(bedingungen)}"
  cursor.execute(sql, parameter)
  treffer = cursor.fetchall()
  conn.close()
  return treffer


# --- 2. WEB-SCRAPING & LIVE-FALLBACK ---
def lade_rezept_von_url(url):
  try:
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    json_ld_tags = soup.find_all("script", type="application/ld+json")

    for tag in json_ld_tags:
      try:
        if not tag.string:
          continue
        data = json.loads(tag.string)
        items = (
            data["@graph"]
            if isinstance(data, dict) and "@graph" in data
            else (data if isinstance(data, list) else [data])
        )
        for item in items:
          if isinstance(item, dict):
            typ = item.get("@type", "")
            if typ == "Recipe" or (isinstance(typ, list) and "Recipe" in typ):
              titel = item.get("name", "Unbekannter Titel")
              zutaten = item.get("recipeIngredient", [])
              if zutaten:
                return {"titel": titel, "url": url, "zutaten": zutaten}
      except (json.JSONDecodeError, TypeError):
        continue
    return None
  except Exception:
    return None


def suche_und_scrape_im_web(suchbegriff):
  gefundene_rezepte = []
  query = quote_plus(suchbegriff)
  such_woerter = [w.lower() for w in suchbegriff.split() if len(w) > 2]

  such_urls = [
      f"https://www.essen-und-trinken.de/suche?q={query}",
      f"https://www.chefkoch.de/rs/s0/{query}/Rezepte.html",
      f"https://www.daskochrezept.de/suche?q={query}",
  ]

  for such_url in such_urls:
    if "chefkoch.de" in such_url:
      portal_name = "Chefkoch"
    elif "daskochrezept.de" in such_url:
      portal_name = "DasKochrezept"
    else:
      portal_name = "Essen & Trinken"

    print(f"👨‍🍳 Ich Schaue mal bei {portal_name} vorbei wegen '{suchbegriff}'...")

    try:
      res = requests.get(such_url, headers=HEADERS, timeout=15)
      res.raise_for_status()
      soup = BeautifulSoup(res.text, "html.parser")

      rezept_links = []
      for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/rezepte/" in href and href.endswith(".html"):
          if href.startswith("http"):
            voll_url = href
          elif "chefkoch.de" in such_url:
            voll_url = f"https://www.chefkoch.de{href}"
          elif "daskochrezept.de" in such_url:
            voll_url = f"https://www.daskochrezept.de{href}"
          else:
            voll_url = f"https://www.essen-und-trinken.de{href}"

          url_lower = voll_url.lower()
          if all(wort in url_lower for wort in such_woerter):
            if voll_url not in rezept_links:
              rezept_links.append(voll_url)

      print(f"🔗 {len(rezept_links)} passende Links auf {portal_name} gefunden.")

      # Pro Suchbegriff maximal 1-2 Top-Treffer laden, damit es bei mehreren Gerichten schnell bleibt
      for link in rezept_links[:2]:
        daten = lade_rezept_von_url(link)
        if daten:
          titel_lower = daten["titel"].lower()
          if any(wort in titel_lower for wort in such_woerter):
            speichere_rezept(daten["titel"], daten["url"], daten["zutaten"])
            gefundene_rezepte.append(
                (daten["titel"], daten["url"], ", ".join(daten["zutaten"]))
            )
          else:
            print(f"⏭️ Übersprungen (Titel passt nicht): {daten['titel']}")
    except Exception as e:
      print(f"⚠️ Hinweis bei Websuche auf {portal_name}: {e}")

  return gefundene_rezepte


# --- 3. LOKALES LLM (OLLAMA) ---
def frage_lokales_llm(prompt, temperatur=0.7):
  url = "http://localhost:11434/api/generate"
  payload = {
      "model": "llama3",
      "prompt": prompt,
      "stream": False,
      "options": {"temperature": temperatur},
  }

  try:
    response = requests.post(url, json=payload, timeout=180)
    response.raise_for_status()
    return response.json().get("response", "Keine Antwort erhalten.")
  except Exception as e:
    return f"❌ Fehler bei Ollama: {e}"


# --- 4. INTELLIGENTE EINGABE-ANALYSE (GERICHTE, ZUTATEN & LANDESKÜCHEN) ---
def analysiere_eingabe_mit_ki(nutzer_input):
  prompt = f"""
Du bist ein kulinarischer Such-Übersetzer für eine deutsche Rezeptdatenbank (wie Chefkoch).
Deine Aufgabe: Wandle die Anfrage des Nutzers in 1 bis 3 gute Suchbegriffe um.

VORGEHEN:
- Ignoriere Füllwörter und Floskeln ("ich habe Hunger auf", "mir steht der Sinn nach",
  "ich hab Lust auf", "typisch", "original", "irgendwas mit").
- Korrigiere Tippfehler und Schreibvarianten. Erkenne dabei auch Getränke und Cocktails
  (z. B. "Mai Thai" -> "Mai Tai", "Mohito" -> "Mojito").

REGELN:
1. Konkretes Gericht, Zutat oder Getränk: Gib nur den bereinigten Begriff aus.
2. Allgemeiner Oberbegriff (z. B. Burger, Pizza, Pasta, Suppe, Salat, Kuchen, Curry):
   Gib den Oberbegriff plus bis zu 2 sehr bekannte Varianten aus.
3. Landesküche, Region oder Kategorie (z. B. "Spanisch", "Serbisch", "Deutsch"):
   Gib 3 berühmte, typische Hauptgerichte dieser Küche aus (deutsche Namen, wie auf Chefkoch).
4. Mehrere genannte Zutaten (Vorrat): Gib alle Zutaten aus, maximal 4, die wichtigste zuerst.
5. Vage Wünsche ("was Leckeres", "was Schnelles", "was Vegetarisches"):
   Gib 3 beliebte Klassiker passend zur Stimmung aus,
   z. B. "Schnelle Gerichte" -> Spaghetti Aglio e Olio, Rührei, Omelett.
6. Gib niemals mehr als 3 Begriffe aus (bei Regel 4 maximal 4).
7. Antworte AUSSCHLIESSLICH mit den Suchbegriffen, durch Komma getrennt.
   Keine Sätze, keine Erklärungen, keine Anführungszeichen, keine Aufzählungszeichen.

BEISPIELE:
Eingabe: "ich hab hunger auf hünchn"
Antwort: Hühnchen

Eingabe: "ich habe hunger auf original Wiener Schnitzel"
Antwort: Wiener Schnitzel

Eingabe: "Ich habe Hunger auf typische Burger"
Antwort: Burger, Cheeseburger, Hamburger

Eingabe: "mir steht der Sinn nach Pizza"
Antwort: Pizza, Pizza Margherita, Pizza Salami

Eingabe: "Ich hab lust auf einen Mai Thai"
Antwort: Mai Tai

Eingabe: "Ich habe Hunger auf typisch Spanisches Essen"
Antwort: Paella, Tortilla, Albondigas

Eingabe: "was leckeres serbisches"
Antwort: Cevapcici, Pljeskavica, Djuvec Reis

Eingabe: "ich hab nur noch Reis, Eier und Paprika da"
Antwort: Reis, Eier, Paprika

Eingabe: "irgendwas schnelles für abends"
Antwort: Spaghetti Aglio e Olio, Rührei, Omelett

Jetzt bist du dran:
Eingabe: "{nutzer_input}"
Antwort:
"""
  print("🧑‍🍳 Chef Rémy schaut kurz in seine Rezeptkiste, bin gleich zurück...")
  ki_analyse = frage_lokales_llm(prompt, temperatur=0.1).strip()

  # Super-Sicherheitsnetz in Python: Falls die KI Text wie "Antwort:" oder Ausrufezeichen einbaut,
  # nehmen wir zur Not nur das letzte Wort oder bereinigen es radikal.
  if "Antwort:" in ki_analyse:
    ki_analyse = ki_analyse.split("Antwort:")[-1].strip()

  # Alles entfernen, was nicht zum Suchbegriff gehört (Satzzeichen am Anfang etc.)
  ki_analyse = re.sub(
      r"^[^a-zA-ZäöüÄÖÜß0-9]+", "", ki_analyse
  )  # Führende Sonderzeichen weg

  saubere_begriffe = [
      b.strip() for b in ki_analyse.replace("\n", "").split(",") if b.strip()
  ]
  if not saubere_begriffe:
    saubere_begriffe = [nutzer_input]

  saubere_begriffe = saubere_begriffe[:3]

  print(f"💡 Konkrete Suchbegriffe: {', '.join(saubere_begriffe)}")
  return saubere_begriffe


# --- 5. ANTWORT-GENERIERUNG (CHEF RÉMY) ---
def generiere_chef_remy_antwort(nutzer_input, suchbegriffe, treffer):
  kontext_texte = []
  # Doppelte URLs herausfiltern, falls ein Rezept über mehrere Begriffe gefunden wurde
  eindeutige_treffer = []
  gesehene_urls = set()
  for titel, url, zutaten in treffer:
    if url not in gesehene_urls:
      gesehene_urls.add(url)
      eindeutige_treffer.append((titel, url, zutaten))

  for i, (titel, url, zutaten) in enumerate(eindeutige_treffer[:3], 1):
    kontext_texte.append(
        f"ID: [R{i}]\nTitel: {titel}\nZutaten: {zutaten}\n---"
    )

  gefundene_rezepte_text = "\n".join(kontext_texte)

  prompt = f"""
Du bist "Chef Rémy", ein leidenschaftlicher Hobby- und Profikoch mit 20 Jahren Küchenerfahrung. Du sprichst, wie du in einer offenen Küche mit einem Freund redest: herzlich, direkt, mit Humor und Appetit auf gutes Essen. Du duzt den Nutzer.

STIL:
- Schreibe ausschließlich auf Deutsch, in natürlicher Umgangssprache.
- Keine Floskeln wie "Gerne helfe ich dir weiter" oder "Hier sind einige Vorschläge".
- Steig direkt mit einer kurzen, persönlichen Reaktion auf die Anfrage ein.
- Beschreibe Gerichte sinnlich, aber kurz (z. B. Textur, Geschmack, Gefühl), ohne zu übertreiben.
- Maximal 1-2 passende Emojis pro Antwort, keine Emoji-Flut.
- Kurze Sätze, kein Marketing-Ton, keine Aufzählungsorgie.

KONTEXT:
- Anfrage des Nutzers: "{nutzer_input}"
- Abgeleitete Gerichte / Suchbegriffe: {suchbegriffe}
- Gefundene Rezepte (deine einzige Quelle):
{gefundene_rezepte_text}

AUFGABE:
1. Wähle die 1 bis 3 besten Treffer aus der Liste, nicht zwingend alle. Ist nur einer wirklich passend, schlage auch nur einen vor.
2. Für jedes Gericht: **Titel** (fett) und eine Zeile, warum es zur Anfrage passt.
3. Falls der Nutzer Zutaten genannt hat: Was hat er davon schon, was fehlt noch? Nenne nur Zutaten, die tatsächlich im Rezepttext stehen.
4. Setze den Link-Platzhalter exakt im Format: 👉 [R1] (nutze die jeweilige ID aus der Liste, erfinde niemals eigene URLs!).
5. Schließe mit einem kurzen Satz oder Profi-Tipp ab, der zur Auswahl passt.

HARTE REGELN:
- Verwende ausschließlich Rezepte aus der Liste oben. Erfinde nichts dazu, weder Rezepte noch Zutaten, Mengen oder URLs.
- Passt kein Rezept auch nur ansatzweise, sag das ehrlich und kurz ("Dazu hab ich leider nichts Passendes gefunden") und schlage vor, die Suche anders zu formulieren.
- Gib niemals Mengen oder Garzeiten an, die nicht im Rezepttext stehen.
"""

  print("🍳 Einen Moment, ich richte das kurz für dich an...")
  antwort = frage_lokales_llm(prompt, temperatur=0.7)

  for i, (titel, url, zutaten) in enumerate(eindeutige_treffer[:3], 1):
    antwort = antwort.replace(f"[R{i}]", url)

  return antwort


# --- 6. HAUPTSCHLEIFE (SMART CHEF AGENT) ---
def starte_koch_assistenten():
  erstelle_datenbank()
  print("\n==================================================")
  print("🧑‍🍳 Chef Rémy – Dein lokaler Küchen-Assistent ist bereit!")
  print("Sag mir, worauf du Hunger hast oder was du da hast.")
  print("Beenden mit 'exit'.")
  print("==================================================")

  while True:
    nutzer_input = input(
        "\n🛒 Was hast du da oder wonach steht dir der Sinn? > "
    ).strip()

    if nutzer_input.lower() in ["exit", "quit", "ende"]:
      print("\n👋 Guten Appetit und bis zum nächsten Mal!")
      break
    if not nutzer_input:
      continue

    # Schritt 1: Eingabe analysieren (erkennt Gerichte, Zutaten & Landesküchen)
    suchbegriffe = analysiere_eingabe_mit_ki(nutzer_input)

    # Schritt 2: Lokal in SQLite suchen
    print("📖 Ich blättere kurz durch mein eigenes Kochbuch...")
    treffer = suche_in_datenbank(suchbegriffe)

    # Schritt 3: Web-Fallback
    if not treffer:
      print(
          "🤷‍♂️ Hab ich gerade nicht griffbereit. Ich frag mal schnell bei den"
          " Kollegen im Netz nach..."
      )
      treffer = []
      for begriff in suchbegriffe:
        neue_treffer = suche_und_scrape_im_web(begriff)
        treffer.extend(neue_treffer)

    if not treffer:
      print(
          "😅 Tut mir leid, dazu hab ich heute nichts Vernünftiges gefunden."
          " Versuch mal, deinen Wunsch etwas einfacher zu formulieren!"
      )
      continue

    # Schritt 4: Antwort von Chef Rémy generieren & anzeigen
    ki_antwort = generiere_chef_remy_antwort(nutzer_input, suchbegriffe, treffer)

    print("\n--- 🍽️ Chef Rémys Empfehlung ---")
    print(ki_antwort)
    print("---------------------------------")


if __name__ == "__main__":
  starte_koch_assistenten()