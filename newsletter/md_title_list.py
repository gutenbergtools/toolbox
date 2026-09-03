from libgutenberg.Models import Author, Book
from libgutenberg import GutenbergDatabase, DublinCoreMapping
from sqlalchemy import select, and_
ob = GutenbergDatabase.Objectbase(False)
session = ob.get_session()
import datetime
start = datetime.date(2026, 7, 1)
end = datetime.date(2026, 7, 30)
format_string = '%Y-%m-%d'

books = session.query(Book).where(and_(Book.release_date >= start, Book.release_date <= end)).order_by(Book.release_date).all()
day = datetime.date(2000, 1, 1)

with open(f'{start.strftime("%B-%d")}.md', 'w') as titlelist:
    for book in books:
        if day != book.release_date:
            titlelist.write('\n')
            titlelist.write(f"## {book.release_date.strftime('%B %d').replace(' 0', ' ')}" + '\n')
            titlelist.write('\n')
            day = book.release_date
        dc = DublinCoreMapping.DublinCoreObject()
        dc.load_from_database(book.pk, load_files=False)
        titlelist.write(f"* [{dc.title}]({dc.canonical_url}) - {dc.authors_short()}" + '\n')
