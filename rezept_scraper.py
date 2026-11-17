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
    print(f"💾 [DB-Update] Neu gespeichert: '{titel}'")
  except Exception as e:
    print(f"❌ Fehler beim Speichern: {e}")
  finally:
    conn.close()


# --- 2. EINZELNES REZEPT SCRAPEN ---
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

# --- 3. ECHTER LIVE-WEB-FALLBACK (ULTRA-STRENG GEFILTERT) ---
def suche_und_scrape_im_web(suchbegriff):
  gefundene_rezepte = []
  query = quote_plus(suchbegriff)
  such_wort_clean = suchbegriff.lower()

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

    print(f"🌐 Durchsuche {portal_name} live nach '{suchbegriff}'...")

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

          # Nur Links aufnehmen, bei denen das Suchwort im Pfad steht
          if (
              such_wort_clean in voll_url.lower()
              and voll_url not in rezept_links
          ):
            rezept_links.append(voll_url)

      print(
          f"🔗 {len(rezept_links)} exakt passende Links auf {portal_name}"
          " gefunden."
      )

      for link in rezept_links[:2]:
        daten = lade_rezept_von_url(link)
        if daten:
          # Zusätzlicher Check: Kommt das Suchwort auch im Rezept-Titel vor?
          if such_wort_clean in daten["titel"].lower():
            speichere_rezept(daten["titel"], daten["url"], daten["zutaten"])
            gefundene_rezepte.append(
                (daten["titel"], daten["url"], ", ".join(daten["zutaten"]))
            )
          else:
            print(
                f"⏭️ Übersprungen (Titel passt nicht zu '{suchbegriff}'):"
                f" {daten['titel']}"
            )
    except Exception as e:
      print(f"⚠️ Hinweis bei Websuche auf {portal_name}: {e}")

  return gefundene_rezepte


# --- 4. LOKALES LLM (OLLAMA) ---
def frage_lokales_llm(prompt):
  url = "http://localhost:11434/api/generate"
  payload = {"model": "llama3", "prompt": prompt, "stream": False}

  try:
    response = requests.post(url, json=payload, timeout=180)
    response.raise_for_status()
    return response.json().get("response", "Keine Antwort erhalten.")
  except Exception as e:
    return f"❌ Fehler bei Ollama: {e}"


# --- 5. KI-GESTÜTZTE ANALYSE & TIPPFEHLER-KORREKTUR ---
def analysiere_eingabe_mit_ki(nutzer_input):
  """Nutzt Llama 3, um den Satz zu verstehen, Tippfehler zu korrigieren

  und die reinen Suchbegriffe zu extrahieren.
  """
  prompt = f"""
Analysiere die folgende Eingabe und gib NUR den Namen des Gerichts oder der Zutat aus. Schreib absolut keinen erklärenden Text, keine Einleitung und kein "Suchbegriffe:" vor die Antwort!
Eingabe: "{nutzer_input}"
Gericht/Zutat:
"""
  print("🧠 KI analysiert und korrigiert deine Eingabe...")
  ki_analyse = frage_lokales_llm(prompt).strip()

  # Sicherheitsnetz: Falls die KI trotz Verbot Text oder "Suchbegriffe:" mitschickt, schneiden wir es ab
  ki_analyse = re.sub(
      r"^(suchbegriffe:|gericht/zutat:|\s*-\s*)\s*",
      "",
      ki_analyse,
      flags=re.IGNORECASE,
  )

  saubere_begriffe = [
      b.strip() for b in ki_analyse.replace("\n", "").split(",") if b.strip()
  ]
  if not saubere_begriffe:
    saubere_begriffe = [nutzer_input]

  print(f"💡 Erkannte Suchbegriffe: {', '.join(saubere_begriffe)}")
  return saubere_begriffe


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


# --- 6. INTERAKTIVER SMART CHEF AGENT ---
def starte_koch_assistenten():
  erstelle_datenbank()
  print("\n==================================================")
  print("🧑‍🍳 Smart Chef Agent (mit KI-Tippfehler-Erkennung) bereit!")
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

    # 1. Schritt: Eingabe von Llama 3 analysieren & Tippfehler korrigieren lassen
    suchbegriffe = analysiere_eingabe_mit_ki(nutzer_input)

    # 2. Schritt: Lokal in SQLite suchen
    print(f"🔍 Prüfe lokale Datenbank...")
    treffer = suche_in_datenbank(suchbegriffe)

    # 3. Schritt: Fallback auf alle 3 Web-Portale, falls lokal nichts da ist
    if not treffer:
      print(
          "⚠️ Nichts Passendes lokal gefunden. Starte Live-Suche im Web auf"
          " Chefkoch, Essen & Trinken und DasKochrezept..."
      )
      such_query = " ".join(suchbegriffe)
      treffer = suche_und_scrape_im_web(such_query)

    if not treffer:
      print(
          "❌ Konnte im Web leider keine passenden Rezepte dazu automatisch"
          " finden."
      )
      continue

    # 4. Schritt: Kontext für Llama 3 zusammenbauen und Antwort generieren
    kontext_texte = []
    for titel, url, zutaten in treffer[:3]:
      kontext_texte.append(
          f"Rezept-Titel: {titel}\nLink: {url}\nZutaten: {zutaten}\n---"
      )

    gefundene_rezepte_text = "\n".join(kontext_texte)

    prompt = f"""
Du bist ein lockerer, kreativer deutscher Koch-Assistent.
Ursprüngliche Anfrage des Nutzers: "{nutzer_input}"
Extrahierte Suchbegriffe: {suchbegriffe}

Hier sind passende Rezepte aus der Datenbank:
{gefundene_rezepte_text}

AUFGABE:
1. Antworte AUSSCHLIESSLICH auf Deutsch!
2. Schlage 1 bis maximal 3 Gerichte aus den obigen Rezepten vor.
3. Nenne jeweils den Titel und den Link.
4. Wenn der Nutzer Zutaten aus seinem Vorrat genannt hat, erkläre kurz, was davon im Rezept vorkommt und was eventuell noch fehlt.
5. Erfinde keine eigenen Rezepte außerhalb der Liste.
"""

    print("🤖 Assistent kocht die Antwort...")
    ki_antwort = frage_lokales_llm(prompt)

    print("\n--- 🍽️ Deine Rezept-Vorschläge ---")
    print(ki_antwort)
    print("-------------------------------------")


if __name__ == "__main__":
  starte_koch_assistenten()