"""
Script to generate the Gold Standard for Wikipedia in English.
Generates 80-100 unique questions with answers extracted directly from the articles.
Author: Auto-generated for TFG
Date: 2026-04-17
"""
import json
import re
import random
from collections import Counter, defaultdict
from pathlib import Path
random.seed(42)
# ─────────────────────────────────────────────
# 1. LOAD ALL ARTICLES
# ─────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[3]
WIKI_DIR = ROOT / "data" / "wikipedia" / "en" / "json"
OUTPUT_DIR = ROOT / "src" / "test" / "gold_standard_data"
articles = {}
for f in sorted(WIKI_DIR.glob("*.json")):
    with open(f, encoding="utf-8") as fh:
        art = json.load(fh)
        articles[art["titulo"]] = art
print(f"Loaded {len(articles)} articles")
# ─────────────────────────────────────────────
# 2. BUILD INDEXES
# ─────────────────────────────────────────────
idx_category = defaultdict(list)
for title, art in articles.items():
    for cat in art.get("categorias", []):
        cat_clean = cat.replace("Category:", "").strip()
        # Skip internal Wikipedia categories
        if not any(cat_clean.startswith(p) for p in ["Wikipedia:", "Articles ", "All ", "Short description", "Commons",
                                                       "CS1 ", "Webarchive", "Use ", "Pages ", "Accuracy"]):
            idx_category[cat_clean].append(title)
def get_sections(content):
    return re.findall(r'^={2,3}\s*(.+?)\s*={2,3}', content, re.MULTILINE)
def get_first_sentence(content):
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f]', '', content)
    match = re.match(r'^(.+?\.)\s', clean)
    if match:
        return match.group(1).strip()
    return clean[:200].strip()
def count_words(content):
    return len(content.split())
def search_content(keyword):
    result = []
    for title, art in articles.items():
        if keyword.lower() in art["contenido"].lower():
            result.append(title)
    return result
def search_by_category(cat_keyword):
    result = []
    for cat, titles in idx_category.items():
        if cat_keyword.lower() in cat.lower():
            result.extend(titles)
    return sorted(set(result))
words_per_article = {t: count_words(a["contenido"]) for t, a in articles.items()}
sections_per_article = {t: get_sections(a["contenido"]) for t, a in articles.items()}
n_sections = {t: len(s) for t, s in sections_per_article.items()}
n_categories = {t: len([c for c in a.get("categorias", [])
                        if not any(c.replace("Category:", "").strip().startswith(p)
                                   for p in ["Wikipedia:", "Articles ", "All ", "Short description",
                                             "Commons", "CS1 ", "Webarchive", "Use ", "Pages ", "Accuracy"])])
                for t, a in articles.items()}
titles_list = list(articles.keys())
random.shuffle(titles_list)
t_iter = iter(titles_list)
def next_art():
    t = next(t_iter)
    return t, articles[t]
# ─────────────────────────────────────────────
# 3. GENERATE QUESTIONS
# ─────────────────────────────────────────────
preguntas = []
q_id = 0
def add_q(cat, question, answer, tipo="text"):
    global q_id
    q_id += 1
    entry = {"id": q_id, "categoria": cat, "pregunta": question, "tipo_respuesta": tipo}
    if isinstance(answer, list):
        try:
            entry["respuesta"] = sorted(answer)
        except TypeError:
            entry["respuesta"] = answer
        entry["num_resultados"] = len(answer)
    else:
        entry["respuesta"] = answer
    preguntas.append(entry)
# ═══════════════════════════════════════════════
# CAT 1: DEFINITION / ARTICLE CONTENT (30)
# ═══════════════════════════════════════════════
t, a = next_art()
add_q("definition", f"What is {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Define the concept of {t}.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What is the article about {t} about?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Briefly explain what {t} is.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Give me a description of {t}.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"How is {t} defined according to available information?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"I need to know what {t} is. Can you explain?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Summarize the topic of {t} in one sentence.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What concept does the term {t} designate?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What does {t} consist of?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Provide the definition of {t}.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What does the concept of {t} refer to?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Tell me about {t}. What is it exactly?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What is the meaning of {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"If I look up {t}, what information do I find?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Could you tell me what {t} is in a concise manner?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Describe the concept covered under the name {t}.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"I want to understand what {t} is. Summarize it.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What information is available about {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Explain the topic of {t} in a few words.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What do we understand by {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Talk to me about {t}.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"I am interested in knowing what {t} is. Give me an introduction.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What can you tell me about {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"How would you define {t} based on the data?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"What is known about {t}?", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Do you have information about {t}? Summarize it.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"Give a brief summary of what {t} is.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"I would like you to clarify what {t} is.", get_first_sentence(a["contenido"]))
t, a = next_art()
add_q("definition", f"In what context does {t} appear and what does it mean?", get_first_sentence(a["contenido"]))
# ═══════════════════════════════════════════════
# CAT 2: ARTICLE SECTIONS (20)
# ═══════════════════════════════════════════════
arts_with_sections = [(t, a) for t, a in articles.items() if len(get_sections(a["contenido"])) >= 2]
random.shuffle(arts_with_sections)
sec_iter = iter(arts_with_sections)
def next_art_sec():
    return next(sec_iter)
t, a = next_art_sec()
add_q("sections", f"What sections does the article about {t} have?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"list the sections of the article on {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What topics are covered in the article about {t}?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Into what parts is the content of {t} divided?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Give me the structure of the article about {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What subtopics does the article on {t} address?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Show the headings of the article about {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What does each part of the article on {t} discuss?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Show me the table of contents of the article about {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What aspects does the article on {t} cover?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Enumerate the sections that make up the article on {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"How many sections does {t} have and what are they?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Break down the thematic structure of {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What points are developed in the article about {t}?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Give me the title of each section of {t}.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"What is the table of contents for the article on {t}?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Review the article on {t} and tell me its main sections.", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"How many parts is the article on {t} organized into?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"How is the content of {t} structured?", get_sections(a["contenido"]), "section_list")
t, a = next_art_sec()
add_q("sections", f"Detail the organization of the article about {t}.", get_sections(a["contenido"]), "section_list")
# ═══════════════════════════════════════════════
# CAT 3: ARTICLE CATEGORIES (15)
# ═══════════════════════════════════════════════
def get_clean_cats(art):
    return [c.replace("Category:", "").strip() for c in art.get("categorias", [])
            if not any(c.replace("Category:", "").strip().startswith(p)
                       for p in ["Wikipedia:", "Articles ", "All ", "Short description",
                                 "Commons", "CS1 ", "Webarchive", "Use ", "Pages ", "Accuracy"])]
t, a = next_art()
add_q("article_categories", f"What categories does the article on {t} belong to?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Tell me the categories of the article about {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Under what thematic classification is {t} filed?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"In which categories is the article on {t} placed?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"list the classification tags for article {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"What topics does the article on {t} cover based on its categories?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Look up the categories assigned to {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"How is the article about {t} classified?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Indicate the thematic categories of {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Within what areas is {t} classified?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Extract the categories from article {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"What classification labels does {t} have?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"What subjects is the article {t} related to?", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"Show me the thematic classification of {t}.", get_clean_cats(a), "category_list")
t, a = next_art()
add_q("article_categories", f"What fields of knowledge does {t} belong to?", get_clean_cats(a), "category_list")
# ═══════════════════════════════════════════════
# CAT 4: SEARCH BY CATEGORY (20)
# ═══════════════════════════════════════════════
cat_keys = [c for c, arts in idx_category.items() if 2 <= len(arts) <= 50]
random.shuffle(cat_keys)
cat_iter = iter(cat_keys)
def next_cat():
    return next(cat_iter)
c = next_cat(); add_q("search_by_category", f"What articles belong to the category {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"list all articles classified under {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Which are the articles in the category {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Give me the articles that are in the category {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"What topics fall under the classification of {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Search for articles in the category {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"How many and which articles are under {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Show me all articles in {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"What content is categorized as {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Find the articles belonging to {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Enumerate the articles classified within {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Can you list the articles tagged as {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"What articles are related to the category {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Identify the articles that belong to {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Filter articles by the category {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Within {c}, what articles do we have available?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Review the category {c} and tell me what articles it contains.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"What articles share the category {c}?", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Give me an inventory of articles in {c}.", idx_category[c], "article_list")
c = next_cat(); add_q("search_by_category", f"Select from the database the articles in category {c}.", idx_category[c], "article_list")
# ═══════════════════════════════════════════════
# CAT 5: SEARCH BY CONTENT / KEYWORD (25)
# ═══════════════════════════════════════════════
kw_searches = [
    ("poetry", "Which articles mention poetry?"),
    ("novel", "In which articles does the word novel appear?"),
    ("surrealism", "What articles discuss or mention surrealism?"),
    ("romanticism", "Which articles make reference to romanticism?"),
    ("metaphor", "In which articles is the metaphor mentioned?"),
    ("narrative", "Which articles address the topic of narrative?"),
    ("Aristotle", "What articles refer to Aristotle?"),
    ("verse", "Identify articles that contain information about verse."),
    ("short story", "In which articles is the short story mentioned as a genre?"),
    ("realism", "Give me articles that deal with realism."),
    ("feminism", "What articles contain the word feminism?"),
    ("theater", "Show me articles that talk about theater."),
    ("rhyme", "What articles address the concept of rhyme?"),
    ("fiction", "Search for articles that mention fiction."),
    ("French", "In which articles is France or French mentioned?"),
    ("writer", "Which articles refer to the figure of the writer?"),
    ("Nobel Prize", "What articles mention the Nobel Prize?"),
    ("Shakespeare", "In which articles does Shakespeare appear?"),
    ("essay", "Which articles contain information about the essay as a genre?"),
    ("modernism", "What articles discuss modernism?"),
    ("avant-garde", "list articles that mention the avant-garde."),
    ("allegory", "Which articles reference allegory?"),
    ("postmodernism", "In which articles is postmodernism discussed?"),
    ("Gothic", "What articles mention Gothic literature or the Gothic?"),
    ("colonialism", "Which articles reference colonialism?"),
]
for kw, question in kw_searches:
    r = search_content(kw)
    add_q("search_by_content", question, r, "article_list")
# ═══════════════════════════════════════════════
# CAT 6: METADATA (15)
# ═══════════════════════════════════════════════
t, a = next_art()
add_q("metadata", f"What is the URL of the article about {t}?", a["url"], "text")
t, a = next_art()
add_q("metadata", f"What page ID does the article on {t} have?", a["pageid"], "number")
t, a = next_art()
add_q("metadata", f"In what language is the article on {t}?", a["idioma"], "text")
t, a = next_art()
add_q("metadata", f"When was the article about {t} downloaded?", a["fecha_descarga"], "text")
t, a = next_art()
add_q("metadata", f"Give me the URL of article {t}.", a["url"], "text")
t, a = next_art()
add_q("metadata", f"What is the page ID of the article on {t}?", a["pageid"], "number")
t, a = next_art()
add_q("metadata", f"What is the download date for the article {t}?", a["fecha_descarga"], "text")
t, a = next_art()
add_q("metadata", f"Point me to the original link for {t}.", a["url"], "text")
t, a = next_art()
add_q("metadata", f"How many categories does the article {t} have assigned?", len(a.get("categorias", [])), "number")
t, a = next_art()
add_q("metadata", f"Approximately how many words does the article on {t} have?", words_per_article[t], "number")
t, a = next_art()
add_q("metadata", f"How many sections does the article about {t} contain?", n_sections.get(t, 0), "number")
t, a = next_art()
add_q("metadata", f"Give me the metadata for article {t}: URL and page ID.", {"url": a["url"], "pageid": a["pageid"]}, "object")
t, a = next_art()
add_q("metadata", f"What is the exact title of the article with page ID {a['pageid']}?", t, "text")
t, a = next_art()
add_q("metadata", f"Provide the download date and language of the article about {t}.", {"fecha_descarga": a["fecha_descarga"], "idioma": a["idioma"]}, "object")
t, a = next_art()
add_q("metadata", f"How many non-internal categories does the article on {t} have?", n_categories.get(t, 0), "number")
# ═══════════════════════════════════════════════
# CAT 7: COUNTING AND STATISTICS (20)
# ═══════════════════════════════════════════════
add_q("counting", "How many articles are there in total in the database?", len(articles), "number")
add_q("counting", "How many distinct categories exist across all articles?", len(idx_category), "number")
longest = max(words_per_article.items(), key=lambda x: x[1])
add_q("counting", "Which is the longest article (most words)?", {"article": longest[0], "words": longest[1]}, "object")
shortest = min(words_per_article.items(), key=lambda x: x[1])
add_q("counting", "Which is the shortest article (fewest words)?", {"article": shortest[0], "words": shortest[1]}, "object")
avg_words = round(sum(words_per_article.values()) / len(words_per_article), 1)
add_q("counting", "What is the average number of words per article?", avg_words, "number")
most_sections = max(n_sections.items(), key=lambda x: x[1])
add_q("counting", "Which article has the most sections?", {"article": most_sections[0], "sections": most_sections[1]}, "object")
most_cats_art = max(n_categories.items(), key=lambda x: x[1])
add_q("counting", "Which article has the most categories assigned?", {"article": most_cats_art[0], "categories": most_cats_art[1]}, "object")
add_q("counting", "How many articles have more than 1000 words?",
      len([t for t, w in words_per_article.items() if w > 1000]), "number")
add_q("counting", "How many articles have fewer than 500 words?",
      len([t for t, w in words_per_article.items() if w < 500]), "number")
top5_cats = Counter({c: len(arts) for c, arts in idx_category.items()}).most_common(5)
add_q("counting", "What are the 5 categories with the most articles?",
      [{"category": c, "num_articles": n} for c, n in top5_cats], "ranking")
add_q("counting", "How many articles mention the word 'poetry' in their content?",
      len(search_content("poetry")), "number")
add_q("counting", "How many articles mention 'novel'?",
      len(search_content("novel")), "number")
add_q("counting", "How many articles mention 'romanticism'?",
      len(search_content("romanticism")), "number")
avg_sec = round(sum(n_sections.values()) / len(n_sections), 1)
add_q("counting", "What is the average number of sections per article?", avg_sec, "number")
add_q("counting", "How many articles have no sections at all?",
      len([t for t, n in n_sections.items() if n == 0]), "number")
avg_cats = round(sum(n_categories.values()) / len(n_categories), 1)
add_q("counting", "What is the average number of categories per article?", avg_cats, "number")
total_words = sum(words_per_article.values())
add_q("counting", "How many words are there in total across all articles?", total_words, "number")
add_q("counting", "How many articles mention 'avant-garde'?",
      len(search_content("avant-garde")), "number")
add_q("counting", "How many articles contain the word 'realism'?",
      len(search_content("realism")), "number")
add_q("counting", "How many articles discuss literary movements (mention 'literary movement')?",
      len(search_content("literary movement")), "number")
# ═══════════════════════════════════════════════
# CAT 8: EXISTENCE (15)
# ═══════════════════════════════════════════════
add_q("existence", "Is there an article about magical realism?",
      {"exists": "Magical realism" in articles or "Magic realism" in articles,
       "title": "Magical realism" if "Magical realism" in articles else ("Magic realism" if "Magic realism" in articles else None)}, "boolean")
add_q("existence", "Is there an article dedicated to the Beat Generation?",
      {"exists": "Beat Generation" in articles,
       "title": "Beat Generation" if "Beat Generation" in articles else None}, "boolean")
add_q("existence", "Do we have an article about poetry?",
      {"exists": "Poetry" in articles,
       "title": "Poetry" if "Poetry" in articles else None}, "boolean")
add_q("existence", "Is there any article dealing with naturalism?",
      {"exists": any("naturalism" in t.lower() for t in articles),
       "articles": [t for t in articles if "naturalism" in t.lower()]}, "boolean")
add_q("existence", "Is there an article about imagism?",
      {"exists": "Imagism" in articles,
       "title": "Imagism" if "Imagism" in articles else None}, "boolean")
add_q("existence", "Is Shakespeare mentioned in any of the articles?",
      {"exists": len(search_content("Shakespeare")) > 0,
       "articles": search_content("Shakespeare")}, "boolean")
add_q("existence", "Are there articles that mention Pablo Neruda?",
      {"exists": len(search_content("Neruda")) > 0,
       "articles": search_content("Neruda")}, "boolean")
add_q("existence", "Is there an article about concrete poetry?",
      {"exists": "Concrete poetry" in articles,
       "title": "Concrete poetry" if "Concrete poetry" in articles else None}, "boolean")
add_q("existence", "Are there articles containing the word 'Quixote'?",
      {"exists": len(search_content("Quixote")) > 0,
       "articles": search_content("Quixote")}, "boolean")
add_q("existence", "Is Freud referenced in any article?",
      {"exists": len(search_content("Freud")) > 0,
       "articles": search_content("Freud")}, "boolean")
add_q("existence", "Is there an article about Dadaism?",
      {"exists": any("dada" in t.lower() for t in articles),
       "articles": [t for t in articles if "dada" in t.lower()]}, "boolean")
add_q("existence", "Do we have articles that mention surrealism?",
      {"exists": len(search_content("surrealism")) > 0,
       "articles": search_content("surrealism")}, "boolean")
add_q("existence", "Is there an article about literary modernism?",
      {"exists": any("modernism" in t.lower() for t in articles),
       "articles": [t for t in articles if "modernism" in t.lower()]}, "boolean")
add_q("existence", "Is there information about the Harlem Renaissance?",
      {"exists": any("harlem" in t.lower() for t in articles),
       "articles": [t for t in articles if "harlem" in t.lower()]}, "boolean")
add_q("existence", "Are haikus mentioned in any article in the database?",
      {"exists": len(search_content("haiku")) > 0,
       "articles": search_content("haiku")}, "boolean")
# ═══════════════════════════════════════════════
# CAT 9: FULL ARTICLE LISTING (10)
# ═══════════════════════════════════════════════
add_q("listing", "Give me the complete list of all available articles.", sorted(articles.keys()), "article_list")
add_q("listing", "What are all the article titles in the database?", sorted(articles.keys()), "article_list")
add_q("listing", "Enumerate all the articles we have.", sorted(articles.keys()), "article_list")
add_q("listing", "I need to see the full catalogue of articles. Which ones are there?", sorted(articles.keys()), "article_list")
add_q("listing", "Show me a list of all available articles in English.", sorted(articles.keys()), "article_list")
arts_P = sorted([t for t in articles if t.startswith("P")])
add_q("listing", "Which articles start with the letter P?", arts_P, "article_list")
arts_L = sorted([t for t in articles if t.startswith("L")])
add_q("listing", "list the articles whose title starts with L.", arts_L, "article_list")
arts_S = sorted([t for t in articles if t.startswith("S")])
add_q("listing", "Which articles begin with the letter S?", arts_S, "article_list")
arts_R = sorted([t for t in articles if t.startswith("R")])
add_q("listing", "Find articles whose name starts with R.", arts_R, "article_list")
arts_M = sorted([t for t in articles if t.startswith("M")])
add_q("listing", "What articles do we have that start with M?", arts_M, "article_list")
# ═══════════════════════════════════════════════
# CAT 10: COMPARISONS AND RELATIONSHIPS (30)
# ═══════════════════════════════════════════════
cat_pairs = [(c, arts) for c, arts in idx_category.items() if 2 <= len(arts) <= 10]
random.shuffle(cat_pairs)
cp_iter = iter(cat_pairs)
c, arts = next(cp_iter)
add_q("relationships", f"Which articles share the category '{c}'?", arts, "article_list")
c, arts = next(cp_iter)
add_q("relationships", f"Give me the articles that have the category {c} in common.", arts, "article_list")
c, arts = next(cp_iter)
add_q("relationships", f"Which articles are related by belonging to {c}?", arts, "article_list")
c, arts = next(cp_iter)
add_q("relationships", f"Identify the articles that coincide in category {c}.", arts, "article_list")
c, arts = next(cp_iter)
add_q("relationships", f"What topics are linked through the category {c}?", arts, "article_list")
# Articles that mention another article
mention_pairs = []
titles_sorted = sorted(articles.keys())
for t1 in titles_sorted:
    for t2 in titles_sorted:
        if t1 != t2 and t2.lower() in articles[t1]["contenido"].lower() and len(t2) > 5:
            mention_pairs.append((t1, t2))
random.shuffle(mention_pairs)
if len(mention_pairs) >= 10:
    mp_iter = iter(mention_pairs[:30])
    t1, t2 = next(mp_iter)
    add_q("relationships", f"Does the article on {t1} mention {t2}?", True, "boolean_simple")
    t1, t2 = next(mp_iter)
    add_q("relationships", f"Is there a reference to {t2} within the article on {t1}?", True, "boolean_simple")
    t1, t2 = next(mp_iter)
    add_q("relationships", f"Is there any connection between the articles on {t1} and {t2}?", True, "boolean_simple")
    t1, t2 = next(mp_iter)
    add_q("relationships", f"Is {t2} mentioned in the content of {t1}?", True, "boolean_simple")
    t1, t2 = next(mp_iter)
    add_q("relationships", f"Is there any relationship between {t1} and {t2} according to the articles?", True, "boolean_simple")
# Longest and shortest articles
top5_long = sorted(words_per_article.items(), key=lambda x: -x[1])[:5]
add_q("relationships", "Which are the 5 most extensive articles?",
      [{"article": t, "words": w} for t, w in top5_long], "ranking")
top5_short = sorted(words_per_article.items(), key=lambda x: x[1])[:5]
add_q("relationships", "Which are the 5 shortest articles?",
      [{"article": t, "words": w} for t, w in top5_short], "ranking")
movements = search_content("literary movement")
add_q("relationships", "What articles discuss literary movements?", movements, "article_list")
poetry_arts = search_by_category("Poetry")
if poetry_arts:
    add_q("relationships", "What articles are classified in categories related to poetry?", poetry_arts, "article_list")
lit_20th = search_by_category("20th century")
if not lit_20th:
    lit_20th = search_by_category("20th-century")
if lit_20th:
    add_q("relationships", "What articles belong to categories about the 20th century?", lit_20th, "article_list")
genres = search_content("literary genre")
add_q("relationships", "What articles refer to literary genres?", genres, "article_list")
cats_shared = [(c, len(arts)) for c, arts in idx_category.items() if len(arts) >= 3]
cats_shared.sort(key=lambda x: -x[1])
add_q("relationships", "Which categories group the most articles?",
      [{"category": c, "num_articles": n} for c, n in cats_shared[:10]], "ranking")
no_sections = [t for t, n in n_sections.items() if n == 0]
add_q("relationships", "Which articles have no internal sections?", sorted(no_sections), "article_list")
top5_sec = sorted(n_sections.items(), key=lambda x: -x[1])[:5]
add_q("relationships", "Which are the 5 articles with the most sections?",
      [{"article": t, "sections": n} for t, n in top5_sec], "ranking")
narrative = search_content("narrative")
add_q("relationships", "Which articles address narrative?", narrative, "article_list")
arts_england = search_content("England")
add_q("relationships", "What articles mention England?", arts_england, "article_list")
arts_america = search_content("America")
add_q("relationships", "In which articles is America mentioned?", arts_america, "article_list")
arts_germany = search_content("Germany")
add_q("relationships", "Which articles make reference to Germany?", arts_germany, "article_list")
arts_italy = search_content("Italy")
add_q("relationships", "In which articles is Italy mentioned?", arts_italy, "article_list")
arts_russia = search_content("Russia")
add_q("relationships", "What articles reference Russia?", arts_russia, "article_list")
top5_cats_art = sorted(n_categories.items(), key=lambda x: -x[1])[:5]
add_q("relationships", "Which are the 5 articles with the most categories assigned?",
      [{"article": t, "categories": n} for t, n in top5_cats_art], "ranking")
arts_19th = search_content("19th century")
add_q("relationships", "What articles make reference to the 19th century?", arts_19th, "article_list")
arts_english_lit = search_content("English literature")
add_q("relationships", "What articles mention English literature?", arts_english_lit, "article_list")
arts_latin = search_content("Latin")
add_q("relationships", "Which articles reference Latin?", arts_latin, "article_list")
arts_philosophy = search_content("philosophy")
add_q("relationships", "What articles mention philosophy?", arts_philosophy, "article_list")
# ═══════════════════════════════════════════════
# CAT 11: CROSS-DOCUMENT (Knowledge Graph required)
# ═══════════════════════════════════════════════
# These questions are deliberately designed to FAIL with basic vector RAG that
# retrieves chunks independently. They REQUIRE synthesising information from
# 2+ different articles (multi-hop reasoning, shared entities, bidirectional
# references, chains of mentions). A knowledge graph (GraphRAG) should
# clearly outperform basic RAG on them.
# --- Detect proper-noun entities mentioned across multiple articles ---
_proper_re = re.compile(
    r"\b((?:[A-Z][a-zà-ÿ]+(?:\s+(?:de|von|van|der|del|du|la|le|d['’]))?\s+){1,3}[A-Z][a-zà-ÿ]+)\b"
)
_entity_articles = defaultdict(set)
_blacklist = {
    "United States", "European Union", "World War", "Middle Ages", "New York",
    "Latin American", "South American", "North American", "English Literature",
    "French Literature", "World Literature", "Western Canon", "Common Era",
    "Holy Spirit", "American Civil", "United Kingdom", "Roman Empire",
}
for _t, _a in articles.items():
    _seen_here = set()
    for _m in _proper_re.finditer(_a["contenido"]):
        _name = _m.group(1).strip()
        if _name in _blacklist or _name in articles:
            continue
        if any(_name.startswith(p) for p in ("The ", "This ", "That ", "Some ", "Many ", "Most ", "Other ", "Several ")):
            continue
        if len(_name) < 6:
            continue
        _seen_here.add(_name)
    for _name in _seen_here:
        _entity_articles[_name].add(_t)
_entities_multi = sorted(
    ((n, ts) for n, ts in _entity_articles.items() if len(ts) >= 3),
    key=lambda x: (-len(x[1]), x[0]),
)
# Q1-Q3: list of articles mentioning a shared entity (KG must aggregate across docs)
for _idx, _slot in enumerate(_entities_multi[:3]):
    _name, _arts = _slot
    if _idx == 0:
        add_q("cross_document",
              f"list every article in our corpus that mentions {_name}.",
              sorted(_arts), "article_list")
    elif _idx == 1:
        add_q("cross_document",
              f"Which articles reference {_name}? Provide the complete list, not just one example.",
              sorted(_arts), "article_list")
    else:
        add_q("cross_document",
              f"How many distinct articles mention {_name}, and which are they?",
              {"count": len(_arts), "articles": sorted(_arts)}, "object")
# Q4: counting question over a shared entity (basic RAG can't aggregate)
if len(_entities_multi) >= 4:
    _name, _arts = _entities_multi[3]
    add_q("cross_document",
          f"How many articles in total mention {_name}?",
          len(_arts), "number")
# --- Bidirectional references: A mentions B AND B mentions A ---
_outgoing = defaultdict(set)
for _a, _b in mention_pairs:
    _outgoing[_a].add(_b)
_bidir = sorted({tuple(sorted([_a, _b])) for _a, _b in mention_pairs if _a in _outgoing[_b]})
# Q5-Q6: mutual reference between two articles (basic RAG often retrieves only one)
for _idx, _pair in enumerate(_bidir[:2]):
    _a, _b = _pair
    if _idx == 0:
        add_q("cross_document",
              f"Describe the mutual relationship between the articles on {_a} and {_b}: explain how each one references the other.",
              {"mutual_reference": True, "articles": [_a, _b]}, "object")
    else:
        add_q("cross_document",
              f"Are the articles on {_a} and {_b} bidirectionally connected? If so, justify by indicating that each one cites the other.",
              {"mutual_reference": True, "articles": [_a, _b]}, "object")
# Q7: total count of mutual-reference pairs (requires scanning ALL pairs)
add_q("cross_document",
      "How many pairs of articles in the corpus reference each other (mutual references)?",
      len(_bidir), "number")
# --- 3-hop chains: A → B → C where A does NOT directly mention C ---
_chains = []
for _a, _bs in _outgoing.items():
    for _b in _bs:
        for _c in _outgoing.get(_b, ()):
            if _c != _a and _c not in _outgoing.get(_a, set()):
                _chains.append((_a, _b, _c))
_chains = sorted(set(_chains))
# Q8-Q9: multi-hop reasoning (3 articles required)
for _idx, _chain in enumerate(_chains[:2]):
    _a, _b, _c = _chain
    if _idx == 0:
        add_q("cross_document",
              f"Find an article that bridges {_a} to {_c}: identify an intermediate article mentioned by {_a} that itself references {_c}.",
              {"intermediate": _b, "chain": [_a, _b, _c]}, "object")
    else:
        add_q("cross_document",
              f"Through which intermediate article is {_a} indirectly connected to {_c}?",
              {"intermediate": _b, "chain": [_a, _b, _c],
               "explanation": f"{_a} mentions {_b}, and {_b} mentions {_c}"}, "object")
# --- Strongly related pairs: articles sharing 2+ categories ---
_pair_shared = defaultdict(list)
for _cat, _arts in idx_category.items():
    if 2 <= len(_arts) <= 8:
        for _i, _x in enumerate(_arts):
            for _y in _arts[_i + 1:]:
                _pair_shared[tuple(sorted([_x, _y]))].append(_cat)
_strong_pairs = sorted(((p, cs) for p, cs in _pair_shared.items() if len(cs) >= 2),
                       key=lambda x: (-len(x[1]), x[0]))
# Q10-Q11: ALL shared categories between two articles (basic RAG misses some)
for _idx, _slot in enumerate(_strong_pairs[:2]):
    (_x, _y), _cats = _slot
    if _idx == 0:
        add_q("cross_document",
              f"list ALL categories that the articles {_x} and {_y} have in common.",
              sorted(_cats), "category_list")
    else:
        add_q("cross_document",
              f"What classification labels are shared between the articles {_x} and {_y}? Provide every common category.",
              sorted(_cats), "category_list")
# Q12: bridge entity between two specific articles
_bridge_candidates = sorted(((n, list(ts)) for n, ts in _entity_articles.items() if len(ts) == 2),
                            key=lambda x: x[0])
if _bridge_candidates:
    _name_b, _arts_b = _bridge_candidates[0]
    _arts_b_sorted = sorted(_arts_b)
    add_q("cross_document",
          f"What proper-noun entity is referenced in BOTH the article '{_arts_b_sorted[0]}' and the article '{_arts_b_sorted[1]}'?",
          _name_b, "text")
# ═══════════════════════════════════════════════
# FILTER: REDUCE TO 80-100 QUESTIONS
# ═══════════════════════════════════════════════
from difflib import SequenceMatcher as _SM
def _sim(a, b):
    return _SM(None, a.lower(), b.lower()).ratio()
def _remove_similar(qs, field, threshold=0.6):
    kept = []
    for q in qs:
        if not any(_sim(q[field], k[field]) > threshold for k in kept):
            kept.append(q)
    return kept
_TARGET = 90
_by_cat = defaultdict(list)
for q in preguntas:
    _by_cat[q["categoria"]].append(q)
_filtered = {}
for cat, qs in _by_cat.items():
    if cat == "cross_document":
        # Always keep ALL cross-document questions: this is the KG-evaluation set.
        _filtered[cat] = qs
    else:
        _filtered[cat] = _remove_similar(qs, "pregunta")
_total_f = sum(len(v) for k, v in _filtered.items() if k != "cross_document") or 1
_selected = []
for cat, qs in sorted(_filtered.items()):
    if cat == "cross_document":
        _selected.extend(qs)  # keep all KG-evaluation questions
    else:
        n = max(2, round(len(qs) / _total_f * _TARGET))
        _selected.extend(qs[:n])
if len(_selected) > 100:
    _selected = _selected[:100]
elif len(_selected) < 80:
    _remaining = [q for cat, qs in sorted(_filtered.items()) for q in qs if q not in _selected]
    _selected.extend(_remaining[:80 - len(_selected)])
_selected.sort(key=lambda q: q["id"])
for i, q in enumerate(_selected, 1):
    q["id"] = i
print(f"\n→ Reduced from {len(preguntas)} to {len(_selected)} questions (target: 80-100)")
preguntas = _selected
# ═══════════════════════════════════════════════
# VERIFICATION AND EXPORT
# ═══════════════════════════════════════════════
texts = [q["pregunta"] for q in preguntas]
if len(texts) != len(set(texts)):
    dupes = set([t for t in texts if texts.count(t) > 1])
    print(f"WARNING: {len(dupes)} duplicate questions:")
    for d in dupes:
        print(f"  - {d}")
else:
    print("OK All questions are unique")
print(f"Total questions generated: {len(preguntas)}")
cat_counts = Counter(q["categoria"] for q in preguntas)
print("\nDistribution by category:")
for cat, cnt in sorted(cat_counts.items()):
    print(f"  {cat}: {cnt}")
gold_standard = {
    "gold_standard": {
        "caso_uso": "wikipedia",
        "idioma": "en",
        "total_preguntas": len(preguntas),
        "total_articulos_analizados": len(articles),
        "generation_date": "2026-04-17",
        "categories": dict(sorted(cat_counts.items())),
        "description": "Gold standard for evaluating a RAG system on English Wikipedia articles "
                       "(topic: literature and literary movements). Contains definition questions, "
                       "sections, categories, content search, metadata, counting, existence, "
                       "listings, and relationships between articles. Includes a 'cross_document' "
                       "category with multi-hop questions (shared entities, bidirectional and chain "
                       "references) designed to expose the limits of basic vector RAG and to be "
                       "answerable by a knowledge graph. All answers computed from data.",
        "preguntas": preguntas
    }
}
output_path = OUTPUT_DIR / "gold_standard_wikipedia_en.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gold_standard, f, ensure_ascii=False, indent=2)
print(f"\nOK Gold standard saved to: {output_path}")
