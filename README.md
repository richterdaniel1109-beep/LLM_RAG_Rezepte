# 🧑‍🍳 Smart Chef Agent ("Chef Rémy")

Ein autonomer, interaktiver Koch-Assistent, der eine lokale SQLite-Rezeptdatenbank mit einem lokalen LLM (**Llama 3 via Ollama**) und einem intelligenten, gefilterten Web-Scraper-Fallback kombiniert. 

Das Projekt demonstriert eine datenschutzfreundliche RAG-Architektur (Retrieval-Augmented Generation) komplett auf dem eigenen Rechner – ganz ohne Cloud-Abhängigkeiten oder externe API-Keys.

---

## 🚀 Features

* **🧠 Intelligenter Query-Übersetzer:** Nutzt Llama 3 als Vorfilter, um Tippfehler zu korrigieren und Nutzeranfragen flexibel zu interpretieren:
  * *Konkrete Gerichte/Zutaten:* Werden direkt gesucht (z. B. "Wiener Schnitzel").
  * *Oberbegriffe:* Erweitert automatisch um bekannte Varianten (z. B. "Pizza" $\rightarrow$ *Pizza, Pizza Margherita, Pizza Salami*).
  * *Landesküchen & Kategorien:* Übersetzt Stimmungen oder Länder sofort in konkrete, typische Hauptgerichte (z. B. "Spanisch" $\rightarrow$ *Paella, Tortilla, Albondigas*).
* **⚡ Lokaler RAG-Workflow:** Sucht blitzschnell in einer lokalen SQLite-Datenbank (`rezepte.db`) nach passenden Rezepten.
* **🌐 Multi-Portal Live-Web-Scraping:** Greift als automatischer Fallback auf drei große Koch-Portale (*Chefkoch*, *Essen & Trinken* und *DasKochrezept*) zu.
* **🛡️ Strenger Qualitäts- und URL-Schutz:** Verhindert Fehltreffer durch mehrstufige Wort-Validierung. LLMs erhalten ausschließlich Platzhalter-IDs (`[R1], [R2]`), wodurch halluzinierte oder kaputte URLs im Code technisch ausgeschlossen sind.
* **💾 Automatisches Caching:** Frisch gescrapte Rezepte werden im selben Moment lokal in SQLite hinterlegt – für ultraschnelle Wiederholungsabfragen.
* **🔒 100% Privat & Offline:** Läuft vollständig lokal über Ollama und benötigt keine kommerziellen Cloud-APIs oder Passwörter.

---

## 🛠️ Tech Stack

* **Python** (Core Logic, Regex, JSON)
* **SQLite** (Lokale relationale Datenbank)
* **Ollama / Llama 3** (Lokales LLM für Query-Understanding & RAG-Antworten mit variabler Temperatur)
* **BeautifulSoup4 & Requests** (Web-Scraping & HTML-Parsing)

---

## ⚙️ Installation & Start

1. **Voraussetzungen:**
   * Python (3.x) ist installiert.
   * [Ollama](https://ollama.com/) läuft lokal im Hintergrund mit dem Modell `llama3` (`ollama run llama3`).

2. **Repository klonen / Ordner öffnen:**
   ```bash
   cd LLM_RAG_Rezepte