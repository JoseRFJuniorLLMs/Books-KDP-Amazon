# -*- coding: utf-8 -*-
"""
HUNTER.PY - Caçador de Livros em Domínio Público
================================================
Sistema AGRESSIVO que:
1. Mantém lista de autores em DOMÍNIO PÚBLICO
2. Busca em múltiplas fontes (Archive.org, Gutenberg, etc.)
3. Baixa EPUBs/PDFs automaticamente
4. Organiza em CALIBRE/Autor/Titulo.epub

FOCO: Autores clássicos, especialmente RUSSOS!

Fontes:
- Archive.org (Internet Archive)
- Project Gutenberg
- Standard Ebooks
- Feedbooks
- ManyBooks

DOMÍNIO PÚBLICO: Obras de autores mortos há mais de 70 anos (maioria dos países)
"""

import os
import re
import sys
import json
import time
import asyncio
import hashlib
import logging
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor

import requests
from tqdm import tqdm

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
CALIBRE_DIR = BASE_DIR.parent / "CALIBRE"
DOWNLOAD_DIR = CALIBRE_DIR  # Salva direto no CALIBRE
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "modelo" / "cache_hunter"

# Criar diretórios
CALIBRE_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# Headers para requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
}

# ============================================================================
# LOGGING
# ============================================================================

log_file = LOG_DIR / f"hunter_{datetime.now().strftime('%Y%m%d')}.log"
downloaded_log = LOG_DIR / "livros_baixados.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# AUTORES EM DOMÍNIO PÚBLICO
# ============================================================================

# Autores mortos há mais de 70 anos (domínio público na maioria dos países)
# Organizado por nacionalidade com foco especial em RUSSOS

PUBLIC_DOMAIN_AUTHORS = {
    # =========================================================================
    # RUSSOS - OS MELHORES! 🇷🇺
    # =========================================================================
    "russian": [
        # GIGANTES
        {"name": "Fyodor Dostoevsky", "alt": ["Dostoievski", "Dostoyevsky", "Dostoevskij"], "died": 1881,
         "works": ["Crime and Punishment", "The Brothers Karamazov", "The Idiot", "Notes from Underground", "Demons", "The Gambler"]},

        {"name": "Leo Tolstoy", "alt": ["Lev Tolstoi", "Tolstói", "Tolstoj"], "died": 1910,
         "works": ["War and Peace", "Anna Karenina", "The Death of Ivan Ilyich", "Resurrection", "Hadji Murat"]},

        {"name": "Anton Chekhov", "alt": ["Tchekhov", "Čechov", "Chekhov"], "died": 1904,
         "works": ["The Cherry Orchard", "Three Sisters", "The Seagull", "Uncle Vanya", "Ward No. 6"]},

        {"name": "Nikolai Gogol", "alt": ["Gogol", "Hohol"], "died": 1852,
         "works": ["Dead Souls", "The Overcoat", "The Nose", "Taras Bulba", "Diary of a Madman"]},

        {"name": "Ivan Turgenev", "alt": ["Turgueniev", "Turgenjev"], "died": 1883,
         "works": ["Fathers and Sons", "A Sportsman's Sketches", "Rudin", "On the Eve", "First Love"]},

        {"name": "Alexander Pushkin", "alt": ["Púchkin", "Puškin"], "died": 1837,
         "works": ["Eugene Onegin", "The Captain's Daughter", "Boris Godunov", "The Queen of Spades"]},

        {"name": "Mikhail Lermontov", "alt": ["Liérmontov"], "died": 1841,
         "works": ["A Hero of Our Time", "The Demon", "Mtsyri"]},

        {"name": "Maxim Gorky", "alt": ["Gorki", "Gorkij", "Maksim Gorky"], "died": 1936,
         "works": ["The Mother", "My Childhood", "The Lower Depths", "Twenty-Six Men and a Girl"]},

        {"name": "Ivan Bunin", "alt": ["Bunin"], "died": 1953,
         "works": ["The Village", "Dry Valley", "The Gentleman from San Francisco", "Dark Avenues"]},

        {"name": "Mikhail Bulgakov", "alt": ["Bulgákov"], "died": 1940,
         "works": ["The Master and Margarita", "Heart of a Dog", "The White Guard"]},

        {"name": "Leonid Andreyev", "alt": ["Andreev", "Andreiev"], "died": 1919,
         "works": ["The Seven Who Were Hanged", "He Who Gets Slapped", "The Red Laugh"]},

        {"name": "Alexander Kuprin", "alt": ["Kuprin"], "died": 1938,
         "works": ["The Duel", "Yama: The Pit", "The Garnet Bracelet"]},

        {"name": "Nikolai Leskov", "alt": ["Leskov"], "died": 1895,
         "works": ["Lady Macbeth of Mtsensk", "The Enchanted Wanderer", "The Steel Flea"]},

        # POETAS
        {"name": "Anna Akhmatova", "alt": ["Achmatova"], "died": 1966,  # Pode não estar em DP em alguns países
         "works": ["Requiem", "Poem Without a Hero"]},

        {"name": "Sergei Yesenin", "alt": ["Esenin", "Iessenin"], "died": 1925,
         "works": ["Confessions of a Hooligan", "Persian Motifs"]},

        {"name": "Vladimir Mayakovsky", "alt": ["Maiakovski", "Majakovsky"], "died": 1930,
         "works": ["A Cloud in Trousers", "The Bedbug", "The Bathhouse"]},
    ],

    # =========================================================================
    # FRANCESES
    # =========================================================================
    "french": [
        {"name": "Victor Hugo", "alt": ["Hugo"], "died": 1885,
         "works": ["Les Misérables", "The Hunchback of Notre-Dame", "Ninety-Three"]},

        {"name": "Alexandre Dumas", "alt": ["Dumas père"], "died": 1870,
         "works": ["The Count of Monte Cristo", "The Three Musketeers", "The Man in the Iron Mask"]},

        {"name": "Honoré de Balzac", "alt": ["Balzac"], "died": 1850,
         "works": ["Le Père Goriot", "Eugénie Grandet", "Lost Illusions", "Cousin Bette"]},

        {"name": "Gustave Flaubert", "alt": ["Flaubert"], "died": 1880,
         "works": ["Madame Bovary", "Sentimental Education", "Salammbô"]},

        {"name": "Émile Zola", "alt": ["Zola"], "died": 1902,
         "works": ["Germinal", "Nana", "L'Assommoir", "La Bête humaine"]},

        {"name": "Stendhal", "alt": ["Henri Beyle"], "died": 1842,
         "works": ["The Red and the Black", "The Charterhouse of Parma"]},

        {"name": "Guy de Maupassant", "alt": ["Maupassant"], "died": 1893,
         "works": ["Bel-Ami", "Pierre et Jean", "Une Vie"]},

        {"name": "Charles Baudelaire", "alt": ["Baudelaire"], "died": 1867,
         "works": ["Les Fleurs du mal", "Paris Spleen"]},

        {"name": "Marcel Proust", "alt": ["Proust"], "died": 1922,
         "works": ["In Search of Lost Time", "Swann's Way"]},

        {"name": "Jules Verne", "alt": ["Verne"], "died": 1905,
         "works": ["Twenty Thousand Leagues Under the Sea", "Around the World in Eighty Days", "Journey to the Center of the Earth"]},
    ],

    # =========================================================================
    # INGLESES E AMERICANOS
    # =========================================================================
    "english": [
        {"name": "William Shakespeare", "alt": ["Shakespeare"], "died": 1616,
         "works": ["Hamlet", "Macbeth", "Othello", "King Lear", "Romeo and Juliet"]},

        {"name": "Charles Dickens", "alt": ["Dickens"], "died": 1870,
         "works": ["Great Expectations", "Oliver Twist", "A Tale of Two Cities", "David Copperfield"]},

        {"name": "Jane Austen", "alt": ["Austen"], "died": 1817,
         "works": ["Pride and Prejudice", "Sense and Sensibility", "Emma", "Persuasion"]},

        {"name": "Oscar Wilde", "alt": ["Wilde"], "died": 1900,
         "works": ["The Picture of Dorian Gray", "The Importance of Being Earnest", "De Profundis"]},

        {"name": "Mark Twain", "alt": ["Samuel Clemens"], "died": 1910,
         "works": ["The Adventures of Tom Sawyer", "Adventures of Huckleberry Finn", "A Connecticut Yankee"]},

        {"name": "Edgar Allan Poe", "alt": ["Poe"], "died": 1849,
         "works": ["The Raven", "The Fall of the House of Usher", "The Tell-Tale Heart", "The Murders in the Rue Morgue"]},

        {"name": "Herman Melville", "alt": ["Melville"], "died": 1891,
         "works": ["Moby-Dick", "Bartleby, the Scrivener", "Billy Budd"]},

        {"name": "Henry James", "alt": ["James"], "died": 1916,
         "works": ["The Portrait of a Lady", "The Turn of the Screw", "The Wings of the Dove"]},

        {"name": "Joseph Conrad", "alt": ["Conrad"], "died": 1924,
         "works": ["Heart of Darkness", "Lord Jim", "Nostromo", "The Secret Agent"]},

        {"name": "H.G. Wells", "alt": ["Wells", "Herbert George Wells"], "died": 1946,
         "works": ["The Time Machine", "The War of the Worlds", "The Invisible Man", "The Island of Doctor Moreau"]},

        {"name": "Jack London", "alt": ["London"], "died": 1916,
         "works": ["The Call of the Wild", "White Fang", "Martin Eden", "The Sea-Wolf"]},

        {"name": "Arthur Conan Doyle", "alt": ["Conan Doyle", "Doyle"], "died": 1930,
         "works": ["A Study in Scarlet", "The Hound of the Baskervilles", "The Sign of the Four"]},

        {"name": "Robert Louis Stevenson", "alt": ["Stevenson"], "died": 1894,
         "works": ["Treasure Island", "Strange Case of Dr Jekyll and Mr Hyde", "Kidnapped"]},

        {"name": "Bram Stoker", "alt": ["Stoker"], "died": 1912,
         "works": ["Dracula", "The Lair of the White Worm"]},

        {"name": "Mary Shelley", "alt": ["Shelley"], "died": 1851,
         "works": ["Frankenstein", "The Last Man"]},

        {"name": "Emily Brontë", "alt": ["Bronte"], "died": 1848,
         "works": ["Wuthering Heights"]},

        {"name": "Charlotte Brontë", "alt": ["Bronte"], "died": 1855,
         "works": ["Jane Eyre", "Villette", "Shirley"]},

        {"name": "Thomas Hardy", "alt": ["Hardy"], "died": 1928,
         "works": ["Tess of the d'Urbervilles", "Jude the Obscure", "Far from the Madding Crowd"]},

        {"name": "Walt Whitman", "alt": ["Whitman"], "died": 1892,
         "works": ["Leaves of Grass", "Song of Myself"]},

        {"name": "Nathaniel Hawthorne", "alt": ["Hawthorne"], "died": 1864,
         "works": ["The Scarlet Letter", "The House of the Seven Gables"]},

        {"name": "F. Scott Fitzgerald", "alt": ["Fitzgerald"], "died": 1940,
         "works": ["The Great Gatsby", "Tender Is the Night", "This Side of Paradise"]},
    ],

    # =========================================================================
    # ALEMÃES
    # =========================================================================
    "german": [
        {"name": "Johann Wolfgang von Goethe", "alt": ["Goethe"], "died": 1832,
         "works": ["Faust", "The Sorrows of Young Werther", "Wilhelm Meister"]},

        {"name": "Friedrich Nietzsche", "alt": ["Nietzsche"], "died": 1900,
         "works": ["Thus Spoke Zarathustra", "Beyond Good and Evil", "The Birth of Tragedy", "Ecce Homo"]},

        {"name": "Franz Kafka", "alt": ["Kafka"], "died": 1924,
         "works": ["The Metamorphosis", "The Trial", "The Castle", "Amerika"]},

        {"name": "Thomas Mann", "alt": ["Mann"], "died": 1955,
         "works": ["The Magic Mountain", "Death in Venice", "Buddenbrooks"]},

        {"name": "Hermann Hesse", "alt": ["Hesse"], "died": 1962,  # Pode não estar em DP
         "works": ["Siddhartha", "Steppenwolf", "The Glass Bead Game", "Demian"]},

        {"name": "Arthur Schopenhauer", "alt": ["Schopenhauer"], "died": 1860,
         "works": ["The World as Will and Representation", "Essays and Aphorisms"]},

        {"name": "Friedrich Schiller", "alt": ["Schiller"], "died": 1805,
         "works": ["William Tell", "Mary Stuart", "Don Carlos"]},

        {"name": "Heinrich Heine", "alt": ["Heine"], "died": 1856,
         "works": ["Book of Songs", "Germany: A Winter's Tale"]},

        {"name": "E.T.A. Hoffmann", "alt": ["Hoffmann"], "died": 1822,
         "works": ["The Nutcracker", "The Sandman", "The Golden Pot"]},

        {"name": "Rainer Maria Rilke", "alt": ["Rilke"], "died": 1926,
         "works": ["Duino Elegies", "Letters to a Young Poet", "The Notebooks of Malte Laurids Brigge"]},
    ],

    # =========================================================================
    # ESPANHÓIS E PORTUGUESES
    # =========================================================================
    "iberian": [
        {"name": "Miguel de Cervantes", "alt": ["Cervantes"], "died": 1616,
         "works": ["Don Quixote", "Novelas ejemplares"]},

        {"name": "Fernando Pessoa", "alt": ["Pessoa"], "died": 1935,
         "works": ["The Book of Disquiet", "Message", "Poems of Fernando Pessoa"]},

        {"name": "José Saramago", "alt": ["Saramago"], "died": 2010,  # Não está em DP ainda
         "works": ["Blindness", "The Gospel According to Jesus Christ"]},

        {"name": "Eça de Queirós", "alt": ["Eça de Queiroz", "Queirós"], "died": 1900,
         "works": ["The Maias", "The Crime of Father Amaro", "Cousin Bazilio"]},

        {"name": "Machado de Assis", "alt": ["Machado"], "died": 1908,
         "works": ["The Posthumous Memoirs of Brás Cubas", "Dom Casmurro", "Quincas Borba"]},

        {"name": "Federico García Lorca", "alt": ["García Lorca", "Lorca"], "died": 1936,
         "works": ["Blood Wedding", "Poet in New York", "Romancero Gitano"]},
    ],

    # =========================================================================
    # ITALIANOS
    # =========================================================================
    "italian": [
        {"name": "Dante Alighieri", "alt": ["Dante"], "died": 1321,
         "works": ["Divine Comedy", "La Vita Nuova"]},

        {"name": "Giovanni Boccaccio", "alt": ["Boccaccio"], "died": 1375,
         "works": ["The Decameron"]},

        {"name": "Niccolò Machiavelli", "alt": ["Machiavelli"], "died": 1527,
         "works": ["The Prince", "Discourses on Livy"]},

        {"name": "Giacomo Leopardi", "alt": ["Leopardi"], "died": 1837,
         "works": ["Canti", "Zibaldone"]},

        {"name": "Luigi Pirandello", "alt": ["Pirandello"], "died": 1936,
         "works": ["Six Characters in Search of an Author", "One, No One and One Hundred Thousand"]},

        {"name": "Italo Svevo", "alt": ["Svevo"], "died": 1928,
         "works": ["Zeno's Conscience", "As a Man Grows Older"]},
    ],

    # =========================================================================
    # ESCANDINAVOS
    # =========================================================================
    "scandinavian": [
        {"name": "Henrik Ibsen", "alt": ["Ibsen"], "died": 1906,
         "works": ["A Doll's House", "Hedda Gabler", "Peer Gynt", "An Enemy of the People"]},

        {"name": "August Strindberg", "alt": ["Strindberg"], "died": 1912,
         "works": ["Miss Julie", "The Father", "A Dream Play"]},

        {"name": "Knut Hamsun", "alt": ["Hamsun"], "died": 1952,
         "works": ["Hunger", "Growth of the Soil", "Pan"]},

        {"name": "Selma Lagerlöf", "alt": ["Lagerlof"], "died": 1940,
         "works": ["The Wonderful Adventures of Nils", "Gösta Berling's Saga"]},

        {"name": "Hans Christian Andersen", "alt": ["Andersen"], "died": 1875,
         "works": ["Fairy Tales", "The Little Mermaid", "The Ugly Duckling", "The Snow Queen"]},
    ],

    # =========================================================================
    # OUTROS
    # =========================================================================
    "other": [
        {"name": "Homer", "alt": ["Homero"], "died": -800,
         "works": ["Iliad", "Odyssey"]},

        {"name": "Plato", "alt": ["Platão"], "died": -348,
         "works": ["The Republic", "Symposium", "Phaedo", "Apology"]},

        {"name": "Aristotle", "alt": ["Aristóteles"], "died": -322,
         "works": ["Nicomachean Ethics", "Politics", "Poetics", "Metaphysics"]},

        {"name": "Marcus Aurelius", "alt": ["Marco Aurélio"], "died": 180,
         "works": ["Meditations"]},

        {"name": "Sun Tzu", "alt": ["Sun Zi"], "died": -496,
         "works": ["The Art of War"]},

        {"name": "Lao Tzu", "alt": ["Laozi", "Lao Tse"], "died": -531,
         "works": ["Tao Te Ching"]},

        {"name": "Rabindranath Tagore", "alt": ["Tagore"], "died": 1941,
         "works": ["Gitanjali", "The Home and the World", "Gora"]},

        {"name": "Khalil Gibran", "alt": ["Gibran", "Kahlil Gibran"], "died": 1931,
         "works": ["The Prophet", "The Madman", "Sand and Foam"]},
    ],

    # =========================================================================
    # FILOSOFIA E ESPIRITUALIDADE
    # =========================================================================
    "philosophy": [
        {"name": "Baruch Spinoza", "alt": ["Spinoza"], "died": 1677,
         "works": ["Ethics", "Theological-Political Treatise"]},

        {"name": "Immanuel Kant", "alt": ["Kant"], "died": 1804,
         "works": ["Critique of Pure Reason", "Critique of Practical Reason"]},

        {"name": "Georg Wilhelm Friedrich Hegel", "alt": ["Hegel"], "died": 1831,
         "works": ["Phenomenology of Spirit", "Philosophy of Right"]},

        {"name": "Søren Kierkegaard", "alt": ["Kierkegaard"], "died": 1855,
         "works": ["Either/Or", "Fear and Trembling", "The Sickness Unto Death"]},

        {"name": "William James", "alt": ["James"], "died": 1910,
         "works": ["The Varieties of Religious Experience", "Pragmatism", "The Principles of Psychology"]},

        {"name": "Henri Bergson", "alt": ["Bergson"], "died": 1941,
         "works": ["Creative Evolution", "Matter and Memory", "Time and Free Will"]},

        {"name": "P.D. Ouspensky", "alt": ["Ouspensky", "Uspensky"], "died": 1947,
         "works": ["In Search of the Miraculous", "Tertium Organum", "A New Model of the Universe"]},

        {"name": "G.I. Gurdjieff", "alt": ["Gurdjieff", "Gurdjiev"], "died": 1949,
         "works": ["Beelzebub's Tales to His Grandson", "Meetings with Remarkable Men"]},
    ],
}

# ============================================================================
# FONTES DE DOWNLOAD
# ============================================================================

@dataclass
class BookResult:
    title: str
    author: str
    url: str
    format: str  # epub, pdf, etc.
    source: str  # archive.org, gutenberg, etc.
    language: str = "en"
    size: int = 0
    year: int = 0

@dataclass
class DownloadResult:
    success: bool
    path: Optional[Path]
    error: Optional[str] = None

# ============================================================================
# ARCHIVE.ORG API
# ============================================================================

class ArchiveOrgSearcher:
    """Busca livros no Internet Archive (archive.org)"""

    BASE_URL = "https://archive.org"
    SEARCH_URL = f"{BASE_URL}/advancedsearch.php"
    DOWNLOAD_URL = f"{BASE_URL}/download"

    def search_author(self, author_name: str, limit: int = 50) -> List[BookResult]:
        """Busca livros de um autor específico."""
        results = []

        # Formata query
        query = f'creator:"{author_name}" AND mediatype:texts AND (format:epub OR format:pdf)'

        params = {
            'q': query,
            'fl[]': ['identifier', 'title', 'creator', 'format', 'language', 'year'],
            'sort[]': 'downloads desc',
            'rows': limit,
            'page': 1,
            'output': 'json'
        }

        try:
            logger.info(f"Buscando no Archive.org: {author_name}")
            response = requests.get(self.SEARCH_URL, params=params, headers=HEADERS, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Archive.org retornou status {response.status_code}")
                return results

            data = response.json()
            docs = data.get('response', {}).get('docs', [])

            for doc in docs:
                identifier = doc.get('identifier', '')
                title = doc.get('title', 'Unknown')
                creator = doc.get('creator', author_name)
                if isinstance(creator, list):
                    creator = creator[0]

                formats = doc.get('format', [])
                if isinstance(formats, str):
                    formats = [formats]

                # Prioriza EPUB
                book_format = 'pdf'
                if any('epub' in f.lower() for f in formats):
                    book_format = 'epub'

                language = doc.get('language', 'en')
                if isinstance(language, list):
                    language = language[0] if language else 'en'

                year = doc.get('year', 0)
                if isinstance(year, list):
                    year = year[0] if year else 0
                try:
                    year = int(year)
                except:
                    year = 0

                results.append(BookResult(
                    title=title,
                    author=creator,
                    url=f"{self.DOWNLOAD_URL}/{identifier}",
                    format=book_format,
                    source="archive.org",
                    language=language,
                    year=year
                ))

            logger.info(f"Encontrados {len(results)} resultados no Archive.org")

        except Exception as e:
            logger.error(f"Erro ao buscar no Archive.org: {e}")

        return results

    def get_download_url(self, identifier: str, preferred_format: str = "epub") -> Optional[str]:
        """Obtém URL direta de download para um item."""
        try:
            # Busca metadados do item
            metadata_url = f"{self.BASE_URL}/metadata/{identifier}"
            response = requests.get(metadata_url, headers=HEADERS, timeout=30)

            if response.status_code != 200:
                return None

            data = response.json()
            files = data.get('files', [])

            # Procura arquivo no formato preferido
            for f in files:
                name = f.get('name', '').lower()
                if preferred_format in name:
                    return f"{self.DOWNLOAD_URL}/{identifier}/{f.get('name')}"

            # Fallback para PDF
            for f in files:
                name = f.get('name', '').lower()
                if '.pdf' in name and 'bw' not in name:  # Evita versões "black & white"
                    return f"{self.DOWNLOAD_URL}/{identifier}/{f.get('name')}"

        except Exception as e:
            logger.error(f"Erro ao obter URL de download: {e}")

        return None

# ============================================================================
# PROJECT GUTENBERG
# ============================================================================

class GutenbergSearcher:
    """Busca livros no Project Gutenberg"""

    # API do Gutendex (mirror da API do Gutenberg)
    SEARCH_URL = "https://gutendex.com/books"

    def search_author(self, author_name: str, limit: int = 50) -> List[BookResult]:
        """Busca livros de um autor."""
        results = []

        params = {
            'search': author_name,
            'page': 1
        }

        try:
            logger.info(f"Buscando no Gutenberg: {author_name}")
            response = requests.get(self.SEARCH_URL, params=params, headers=HEADERS, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Gutenberg retornou status {response.status_code}")
                return results

            data = response.json()
            books = data.get('results', [])

            for book in books[:limit]:
                title = book.get('title', 'Unknown')
                authors = book.get('authors', [])
                author = authors[0].get('name', author_name) if authors else author_name

                # Busca formatos
                formats = book.get('formats', {})

                # Prioriza EPUB
                url = None
                book_format = None

                for fmt, link in formats.items():
                    if 'epub' in fmt.lower() and 'images' not in fmt.lower():
                        url = link
                        book_format = 'epub'
                        break

                if not url:
                    for fmt, link in formats.items():
                        if 'epub' in fmt.lower():
                            url = link
                            book_format = 'epub'
                            break

                if not url:
                    # Tenta PDF ou texto
                    for fmt, link in formats.items():
                        if 'pdf' in fmt.lower():
                            url = link
                            book_format = 'pdf'
                            break

                if not url:
                    continue

                languages = book.get('languages', ['en'])

                results.append(BookResult(
                    title=title,
                    author=author,
                    url=url,
                    format=book_format,
                    source="gutenberg",
                    language=languages[0] if languages else 'en'
                ))

            logger.info(f"Encontrados {len(results)} resultados no Gutenberg")

        except Exception as e:
            logger.error(f"Erro ao buscar no Gutenberg: {e}")

        return results

# ============================================================================
# STANDARD EBOOKS
# ============================================================================

class StandardEbooksSearcher:
    """Busca livros no Standard Ebooks (alta qualidade)"""

    OPDS_URL = "https://standardebooks.org/opds/all"
    BASE_URL = "https://standardebooks.org"

    def search_author(self, author_name: str, limit: int = 50) -> List[BookResult]:
        """Busca livros de um autor."""
        results = []

        try:
            logger.info(f"Buscando no Standard Ebooks: {author_name}")

            # Standard Ebooks usa OPDS feed
            response = requests.get(self.OPDS_URL, headers=HEADERS, timeout=30)

            if response.status_code != 200:
                logger.warning(f"Standard Ebooks retornou status {response.status_code}")
                return results

            # Parse XML (OPDS é baseado em Atom)
            from xml.etree import ElementTree as ET
            root = ET.fromstring(response.content)

            # Namespace do Atom
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            author_lower = author_name.lower()

            for entry in root.findall('.//atom:entry', ns):
                # Verifica autor
                author_elem = entry.find('atom:author/atom:name', ns)
                if author_elem is None:
                    continue

                entry_author = author_elem.text or ""

                if author_lower not in entry_author.lower():
                    continue

                title_elem = entry.find('atom:title', ns)
                title = title_elem.text if title_elem is not None else "Unknown"

                # Busca link do EPUB
                for link in entry.findall('atom:link', ns):
                    href = link.get('href', '')
                    link_type = link.get('type', '')

                    if 'epub' in link_type.lower():
                        if not href.startswith('http'):
                            href = f"{self.BASE_URL}{href}"

                        results.append(BookResult(
                            title=title,
                            author=entry_author,
                            url=href,
                            format='epub',
                            source="standardebooks",
                            language='en'
                        ))
                        break

                if len(results) >= limit:
                    break

            logger.info(f"Encontrados {len(results)} resultados no Standard Ebooks")

        except Exception as e:
            logger.error(f"Erro ao buscar no Standard Ebooks: {e}")

        return results

# ============================================================================
# DOWNLOADER
# ============================================================================

class BookDownloader:
    """Gerencia downloads de livros"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_downloaded()

    def _load_downloaded(self):
        """Carrega lista de livros já baixados."""
        self.downloaded = set()
        if downloaded_log.exists():
            with open(downloaded_log, 'r', encoding='utf-8') as f:
                for line in f:
                    self.downloaded.add(line.strip())

    def _mark_downloaded(self, book_id: str, path: Path):
        """Marca livro como baixado."""
        with open(downloaded_log, 'a', encoding='utf-8') as f:
            f.write(f"{book_id}|{path}|{datetime.now().isoformat()}\n")
        self.downloaded.add(book_id)

    def _sanitize_filename(self, name: str) -> str:
        """Remove caracteres inválidos de nomes de arquivo."""
        # Remove caracteres inválidos
        invalid = '<>:"/\\|?*'
        for char in invalid:
            name = name.replace(char, '')
        # Remove espaços múltiplos
        name = re.sub(r'\s+', ' ', name).strip()
        # Limita tamanho
        return name[:100]

    def _get_book_id(self, book: BookResult) -> str:
        """Gera ID único para o livro."""
        return hashlib.md5(f"{book.author}|{book.title}|{book.source}".encode()).hexdigest()[:16]

    def download(self, book: BookResult) -> DownloadResult:
        """Baixa um livro."""
        book_id = self._get_book_id(book)

        # Verifica se já foi baixado
        if book_id in self.downloaded:
            logger.info(f"Já baixado: {book.title}")
            return DownloadResult(success=True, path=None, error="Já baixado anteriormente")

        # Prepara diretórios
        author_clean = self._sanitize_filename(book.author)
        title_clean = self._sanitize_filename(book.title)

        author_dir = self.output_dir / author_clean
        author_dir.mkdir(exist_ok=True)

        # Nome do arquivo
        filename = f"{title_clean}.{book.format}"
        output_path = author_dir / filename

        # Evita sobrescrever
        if output_path.exists():
            logger.info(f"Arquivo já existe: {output_path}")
            self._mark_downloaded(book_id, output_path)
            return DownloadResult(success=True, path=output_path)

        logger.info(f"Baixando: {book.title} ({book.source})")
        logger.info(f"URL: {book.url}")

        try:
            # Download com progresso
            response = requests.get(book.url, headers=HEADERS, stream=True, timeout=120)

            if response.status_code != 200:
                return DownloadResult(
                    success=False,
                    path=None,
                    error=f"Status {response.status_code}"
                )

            # Tamanho total
            total_size = int(response.headers.get('content-length', 0))

            # Salva arquivo
            with open(output_path, 'wb') as f:
                if total_size > 0:
                    with tqdm(total=total_size, unit='B', unit_scale=True, desc=title_clean[:30]) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                pbar.update(len(chunk))
                else:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            # Verifica se o arquivo foi criado
            if output_path.exists() and output_path.stat().st_size > 0:
                self._mark_downloaded(book_id, output_path)
                logger.info(f"✓ Salvo: {output_path}")
                return DownloadResult(success=True, path=output_path)
            else:
                output_path.unlink(missing_ok=True)
                return DownloadResult(success=False, path=None, error="Arquivo vazio ou inválido")

        except Exception as e:
            logger.error(f"Erro ao baixar {book.title}: {e}")
            output_path.unlink(missing_ok=True)
            return DownloadResult(success=False, path=None, error=str(e))

# ============================================================================
# HUNTER PRINCIPAL
# ============================================================================

class BookHunter:
    """Caçador principal de livros"""

    def __init__(self, output_dir: Path = CALIBRE_DIR):
        self.output_dir = output_dir
        self.downloader = BookDownloader(output_dir)

        # Inicializa buscadores
        self.searchers = [
            GutenbergSearcher(),      # Prioridade 1: Gutenberg (mais limpo)
            StandardEbooksSearcher(), # Prioridade 2: Standard Ebooks (alta qualidade)
            ArchiveOrgSearcher(),     # Prioridade 3: Archive.org (mais variedade)
        ]

    def get_all_authors(self) -> List[Dict]:
        """Retorna lista de todos os autores."""
        all_authors = []
        for category, authors in PUBLIC_DOMAIN_AUTHORS.items():
            for author in authors:
                author['category'] = category
                all_authors.append(author)
        return all_authors

    def search_author(self, author_info: Dict, limit_per_source: int = 20) -> List[BookResult]:
        """Busca livros de um autor em todas as fontes."""
        results = []

        author_name = author_info['name']
        alt_names = author_info.get('alt', [])

        # Busca pelo nome principal e alternativos
        search_names = [author_name] + alt_names

        for searcher in self.searchers:
            for name in search_names:
                try:
                    found = searcher.search_author(name, limit=limit_per_source)
                    results.extend(found)

                    if found:
                        break  # Se encontrou com esse nome, não tenta alternativos

                except Exception as e:
                    logger.error(f"Erro ao buscar {name} em {type(searcher).__name__}: {e}")

                time.sleep(1)  # Rate limiting

        # Remove duplicatas (mesmo título, mesmo autor)
        seen = set()
        unique_results = []
        for book in results:
            key = f"{book.author.lower()}|{book.title.lower()}"
            if key not in seen:
                seen.add(key)
                unique_results.append(book)

        return unique_results

    def hunt_category(self, category: str, limit_per_author: int = 10) -> Dict:
        """Caça livros de uma categoria específica."""
        if category not in PUBLIC_DOMAIN_AUTHORS:
            logger.error(f"Categoria desconhecida: {category}")
            return {"success": 0, "failed": 0}

        authors = PUBLIC_DOMAIN_AUTHORS[category]
        stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"\n{'='*60}")
        logger.info(f"CAÇANDO CATEGORIA: {category.upper()}")
        logger.info(f"Autores: {len(authors)}")
        logger.info(f"{'='*60}\n")

        for author in authors:
            logger.info(f"\n--- {author['name']} ---")

            try:
                # Busca livros
                books = self.search_author(author, limit_per_source=limit_per_author)

                if not books:
                    logger.warning(f"Nenhum livro encontrado para {author['name']}")
                    continue

                logger.info(f"Encontrados {len(books)} livros")

                # Baixa cada livro
                for book in books[:limit_per_author]:
                    result = self.downloader.download(book)

                    if result.success:
                        stats["success"] += 1
                    elif result.error == "Já baixado anteriormente":
                        stats["skipped"] += 1
                    else:
                        stats["failed"] += 1

                    time.sleep(2)  # Rate limiting entre downloads

            except Exception as e:
                logger.error(f"Erro ao processar {author['name']}: {e}")
                stats["failed"] += 1

            time.sleep(3)  # Rate limiting entre autores

        return stats

    def hunt_all(self, limit_per_author: int = 5, categories: List[str] = None):
        """Caça livros de todas as categorias."""
        if categories is None:
            categories = list(PUBLIC_DOMAIN_AUTHORS.keys())

        total_stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info("="*60)
        logger.info("INICIANDO CAÇA GERAL DE LIVROS")
        logger.info(f"Categorias: {categories}")
        logger.info("="*60)

        for category in categories:
            stats = self.hunt_category(category, limit_per_author)

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

        logger.info("\n" + "="*60)
        logger.info("CAÇA CONCLUÍDA!")
        logger.info(f"Sucesso: {total_stats['success']}")
        logger.info(f"Falhas: {total_stats['failed']}")
        logger.info(f"Já baixados: {total_stats['skipped']}")
        logger.info("="*60)

        return total_stats

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="HUNTER - Caçador de Livros em Domínio Público",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python hunter.py --list                    # Lista todos os autores
  python hunter.py --category russian        # Baixa apenas autores russos
  python hunter.py --author "Dostoevsky"     # Baixa apenas Dostoevsky
  python hunter.py --all --limit 5           # Baixa 5 livros por autor
  python hunter.py --russians                # Atalho para autores russos
        """
    )

    parser.add_argument('--list', '-l', action='store_true', help='Lista todos os autores disponíveis')
    parser.add_argument('--category', '-c', type=str, help='Categoria específica (russian, french, english, etc.)')
    parser.add_argument('--author', '-a', type=str, help='Autor específico')
    parser.add_argument('--all', action='store_true', help='Baixa de todas as categorias')
    parser.add_argument('--russians', '-r', action='store_true', help='Atalho para baixar autores russos')
    parser.add_argument('--limit', type=int, default=5, help='Limite de livros por autor (padrão: 5)')
    parser.add_argument('--output', '-o', type=Path, default=CALIBRE_DIR, help='Diretório de saída')

    args = parser.parse_args()

    hunter = BookHunter(output_dir=args.output)

    # Lista autores
    if args.list:
        print("\n" + "="*60)
        print("AUTORES EM DOMÍNIO PÚBLICO")
        print("="*60)

        for category, authors in PUBLIC_DOMAIN_AUTHORS.items():
            print(f"\n--- {category.upper()} ({len(authors)} autores) ---")
            for author in authors:
                works = ", ".join(author.get('works', [])[:3])
                print(f"  • {author['name']} (†{author['died']})")
                if works:
                    print(f"    Obras: {works}...")

        total = sum(len(a) for a in PUBLIC_DOMAIN_AUTHORS.values())
        print(f"\nTotal: {total} autores")
        return 0

    # Baixa autores russos
    if args.russians:
        hunter.hunt_category("russian", limit_per_author=args.limit)
        return 0

    # Baixa categoria específica
    if args.category:
        hunter.hunt_category(args.category, limit_per_author=args.limit)
        return 0

    # Baixa autor específico
    if args.author:
        # Procura autor na lista
        found = None
        for category, authors in PUBLIC_DOMAIN_AUTHORS.items():
            for author in authors:
                if args.author.lower() in author['name'].lower():
                    found = author
                    break
                for alt in author.get('alt', []):
                    if args.author.lower() in alt.lower():
                        found = author
                        break
            if found:
                break

        if found:
            logger.info(f"Buscando livros de: {found['name']}")
            books = hunter.search_author(found, limit_per_source=args.limit)

            for book in books:
                hunter.downloader.download(book)
                time.sleep(2)
        else:
            logger.error(f"Autor não encontrado: {args.author}")
            return 1

        return 0

    # Baixa tudo
    if args.all:
        hunter.hunt_all(limit_per_author=args.limit)
        return 0

    # Sem argumentos, mostra ajuda
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
