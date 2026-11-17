# 🧑‍🍳 Smart Chef Agent

Ein autonomer, interaktiver Koch-Assistent, der eine lokale SQLite-Rezeptdatenbank mit einem lokalen LLM (**Llama 3 via Ollama**) und einem intelligenten, gefilterten Web-Scraper-Fallback kombiniert. 

Das Projekt demonstriert eine datenschutzfreundliche RAG-Architektur (Retrieval-Augmented Generation) komplett auf dem eigenen Rechner – ganz ohne Cloud-Abhängigkeiten oder externe API-Keys.

---

## 🚀 Features

* **🧠 KI-gestützte Eingabe-Analyse:** Nutzt Llama 3 als Vorfilter, um Tippfehler zu korrigieren, Umgangssprache zu verstehen und saubere Suchbegriffe zu extrahieren.
* **⚡ Lokaler RAG-Workflow:** Sucht blitzschnell in einer lokalen SQLite-Datenbank (`rezepte.db`) nach passenden Rezepten anhand von Titeln und Zutaten.
* **🌐 Multi-Portal Live-Web-Scraping:** Greift als automatischer Fallback auf drei große Koch-Portale (*Chefkoch*, *Essen & Trinken* und *DasKochrezept*) zu.
* **🛡️ Strenger Qualitätsfilter:** Verhindert Fehltreffer durch URL- und Titel-Validierung vor dem Speichern.
* **💾 Automatisches Caching:** Frisch gescrapte Rezepte werden im selben Moment lokal in SQLite hinterlegt – für ultraschnelle Wiederholungsabfragen.
* **🔒 100% Privat & Offline:** Läuft vollständig lokal über Ollama und benötigt keine kommerziellen Cloud-APIs oder Passwörter.

---

## 🛠️ Tech Stack

* **Python** (Core Logic, Regex, JSON)
* **SQLite** (Lokale relationale Datenbank)
* **Ollama / Llama 3** (Lokales LLM für Query-Understanding & RAG-Antworten)
* **BeautifulSoup4 & Requests** (Web-Scraping & HTML-Parsing)

---

## ⚙️ Installation & Start

1. **Voraussetzungen:**
   * Python (3.x) ist installiert.
   * [Ollama](https://ollama.com/) läuft lokal im Hintergrund mit dem Modell `llama3` (`ollama run llama3`).

2. **Repository klonen / Ordner öffnen:**
   ```bash
   cd LLM_RAG_Rezepte