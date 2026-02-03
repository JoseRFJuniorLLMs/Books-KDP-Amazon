# -*- coding: utf-8 -*-
"""
API.PY - API REST e Dashboard Web para BooksKDP
================================================
Servidor Flask com:
- API REST para consultar/atualizar livros
- Dashboard HTML para visualizar a base de dados
- Estatísticas em tempo real
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from functools import wraps

# Flask
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash

# Configurações
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    DATABASE_PATH, TEMPLATES_DIR, STATIC_DIR,
    API_HOST, API_PORT, API_DEBUG
)
from database import BooksDatabase

# ============================================================================
# APP FLASK
# ============================================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR)
)
app.secret_key = os.urandom(24)

# ============================================================================
# HELPERS
# ============================================================================

def get_db():
    """Retorna instância conectada do banco."""
    db = BooksDatabase()
    db.connect()
    return db


def json_response(data, status=200):
    """Helper para respostas JSON."""
    return jsonify(data), status

# ============================================================================
# ROTAS - DASHBOARD HTML
# ============================================================================

@app.route('/')
def index():
    """Página principal - Dashboard."""
    with get_db() as db:
        stats = db.get_stats()
        recent_processed = db.search_books(processed=True, limit=10)
        pending = db.get_pending_books(limit=10)
        languages = db.get_languages()[:15]

    return render_template('dashboard.html',
                          stats=stats,
                          recent_processed=recent_processed,
                          pending=pending,
                          languages=languages)


@app.route('/books')
def books_page():
    """Página de listagem de livros."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    query = request.args.get('q', '')
    language = request.args.get('language', '')
    status = request.args.get('status', '')  # all, processed, pending

    processed = None
    if status == 'processed':
        processed = True
    elif status == 'pending':
        processed = False

    offset = (page - 1) * per_page

    with get_db() as db:
        books = db.search_books(
            query=query if query else None,
            language=language if language else None,
            processed=processed,
            limit=per_page,
            offset=offset
        )
        stats = db.get_stats()
        languages = db.get_languages()

    return render_template('books.html',
                          books=books,
                          stats=stats,
                          languages=languages,
                          current_page=page,
                          per_page=per_page,
                          query=query,
                          language=language,
                          status=status)


@app.route('/authors')
def authors_page():
    """Página de listagem de autores."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    query = request.args.get('q', '')
    public_domain = request.args.get('pd', '') == '1'

    offset = (page - 1) * per_page

    with get_db() as db:
        authors = db.get_authors(
            query=query if query else None,
            public_domain_only=public_domain,
            limit=per_page,
            offset=offset
        )
        stats = db.get_stats()

    return render_template('authors.html',
                          authors=authors,
                          stats=stats,
                          current_page=page,
                          query=query,
                          public_domain=public_domain)


@app.route('/book/<book_id>')
def book_detail(book_id):
    """Detalhes de um livro."""
    with get_db() as db:
        book = db.get_book_by_id(book_id)
        if not book:
            flash('Livro não encontrado', 'error')
            return redirect(url_for('books_page'))

    return render_template('book_detail.html', book=book)


@app.route('/book/<book_id>/toggle-processed', methods=['POST'])
def toggle_processed(book_id):
    """Alterna status de processado."""
    with get_db() as db:
        book = db.get_book_by_id(book_id)
        if book:
            if book.get('processado'):
                db.unmark_processed(book_id)
                flash(f'Livro {book_id} desmarcado como processado', 'info')
            else:
                db.mark_as_processed(book_id)
                flash(f'Livro {book_id} marcado como processado', 'success')

    return redirect(request.referrer or url_for('books_page'))

# ============================================================================
# ROTAS - API REST
# ============================================================================

@app.route('/api/stats')
def api_stats():
    """GET /api/stats - Estatísticas do banco."""
    with get_db() as db:
        stats = db.get_stats()
    return json_response(stats)


@app.route('/api/books')
def api_books():
    """GET /api/books - Lista livros com filtros."""
    query = request.args.get('q')
    language = request.args.get('language')
    processed = request.args.get('processed')
    downloaded = request.args.get('downloaded')
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    # Converte strings para bool
    processed_bool = None
    if processed == 'true':
        processed_bool = True
    elif processed == 'false':
        processed_bool = False

    downloaded_bool = None
    if downloaded == 'true':
        downloaded_bool = True
    elif downloaded == 'false':
        downloaded_bool = False

    with get_db() as db:
        books = db.search_books(
            query=query,
            language=language,
            processed=processed_bool,
            downloaded=downloaded_bool,
            limit=min(limit, 500),
            offset=offset
        )

    return json_response({
        'count': len(books),
        'limit': limit,
        'offset': offset,
        'books': books
    })


@app.route('/api/books/<book_id>')
def api_book_detail(book_id):
    """GET /api/books/<id> - Detalhes de um livro."""
    with get_db() as db:
        book = db.get_book_by_id(book_id)

    if not book:
        return json_response({'error': 'Book not found'}, 404)

    return json_response(book)


@app.route('/api/books/<book_id>/processed', methods=['POST'])
def api_mark_processed(book_id):
    """POST /api/books/<id>/processed - Marca como processado."""
    data = request.get_json() or {}
    docx_path = data.get('docx_path')

    with get_db() as db:
        book = db.get_book_by_id(book_id)
        if not book:
            return json_response({'error': 'Book not found'}, 404)

        db.mark_as_processed(book_id, docx_path)

    return json_response({'success': True, 'book_id': book_id})


@app.route('/api/books/<book_id>/processed', methods=['DELETE'])
def api_unmark_processed(book_id):
    """DELETE /api/books/<id>/processed - Desmarca processado."""
    with get_db() as db:
        book = db.get_book_by_id(book_id)
        if not book:
            return json_response({'error': 'Book not found'}, 404)

        db.unmark_processed(book_id)

    return json_response({'success': True, 'book_id': book_id})


@app.route('/api/authors')
def api_authors():
    """GET /api/authors - Lista autores."""
    query = request.args.get('q')
    public_domain = request.args.get('public_domain') == 'true'
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

    with get_db() as db:
        authors = db.get_authors(
            query=query,
            public_domain_only=public_domain,
            limit=min(limit, 500),
            offset=offset
        )

    return json_response({
        'count': len(authors),
        'authors': authors
    })


@app.route('/api/authors/<int:author_id>/books')
def api_author_books(author_id):
    """GET /api/authors/<id>/books - Livros de um autor."""
    limit = request.args.get('limit', 100, type=int)

    with get_db() as db:
        books = db.get_books_by_author(author_id=author_id, limit=limit)

    return json_response({
        'count': len(books),
        'books': books
    })


@app.route('/api/languages')
def api_languages():
    """GET /api/languages - Lista idiomas."""
    with get_db() as db:
        languages = db.get_languages()

    return json_response({'languages': languages})


@app.route('/api/pending')
def api_pending():
    """GET /api/pending - Livros pendentes de processamento."""
    language = request.args.get('language')
    limit = request.args.get('limit', 100, type=int)

    with get_db() as db:
        books = db.get_pending_books(language=language, limit=limit)

    return json_response({
        'count': len(books),
        'books': books
    })

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return json_response({'error': 'Not found'}, 404)
    return render_template('error.html', error='Página não encontrada'), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return json_response({'error': 'Internal server error'}, 500)
    return render_template('error.html', error='Erro interno do servidor'), 500

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="API/Dashboard BooksKDP")
    parser.add_argument('--host', default=API_HOST, help='Host')
    parser.add_argument('--port', '-p', type=int, default=API_PORT, help='Porta')
    parser.add_argument('--debug', '-d', action='store_true', default=API_DEBUG)

    args = parser.parse_args()

    # Garante que banco existe e tem migrations
    with get_db() as db:
        db.create_tables()
        db.migrate_add_processado()

    print(f"""
╔══════════════════════════════════════════════════════════╗
║           BooksKDP - Dashboard & API                     ║
╠══════════════════════════════════════════════════════════╣
║  Dashboard: http://{args.host}:{args.port}/                         ║
║  API:       http://{args.host}:{args.port}/api/                     ║
╚══════════════════════════════════════════════════════════╝
""")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
