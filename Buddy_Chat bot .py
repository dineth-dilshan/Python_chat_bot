"""Buddy lecture planner. Run with: python chatbot.py

Python standard library only: Tkinter UI + SQLite persistence.
Data is stored beside this script in lectures.db. Back up both files.
Timetable transcribed from the supplied Year III Semester I photograph.
Choose your subjects and verify the source entries before relying on them.
Weekly recurrence begins 17 August 2026; no semester end/holiday dates supplied.
Queries use Sri Lanka time. Reminders are answers in this app, not background alarms.
"""
import re
import random
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

SL_TIME = timezone(timedelta(hours=5, minutes=30))
DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
DB_PATH = Path(__file__).resolve().with_name('lectures.db')



OPTIONAL = {'Mathematical Programming', 'Numerical Methods', 'Optical Fiber and Telecommunication'}
SEED = [
 (0,'13:00','15:00','PST 31212','Numerical Methods','LT 204'),
 (0,'15:00','17:00','PST 31229','Agile Software Development','LT 202'),
 (1,'08:00','10:00','PST 31211','Mathematical Programming','LT 202'),
 (1,'13:00','15:00','PST 31209','Multimedia and Hypermedia Systems Development','LT 202'),
 (1,'15:00','17:00','PST 31229','Advanced Database Management Systems','LT 102'),
 (2,'08:00','10:00','PST 31227','Object Oriented Analysis and Design','LT 202'),
 (2,'13:00','15:00','PST 31224','Artificial Intelligence and Expert Systems','LT 203'),
 (3,'09:00','12:00','PST 31128','Computer Laboratory 3-I','Computer Lab'),
 (3,'15:00','17:00','PST 31225','Software Project Management','LT 203'),
 (4,'13:00','15:00','PST 31206','Optical Fiber and Telecommunication','LT 202'),
 (4,'13:00','15:00','PST 31226','Software Quality Assurances','LT 203'),
]



JOKES = ['My laptop asked for a holiday. I told it to close its tabs first.', 'I made a timetable for procrastination. I will fill it in tomorrow.', 'My calculator and I had an argument. We just could not count on each other.', 'I asked my database to keep a secret. It said, "Only if nobody queries me."', 'My code went to the gym. It wanted stronger loops.', 'I bought a notebook to organise my thoughts. So far, it is enjoying a very quiet life.', 'My Wi-Fi is studying drama. It always disconnects at the most exciting moment.', 'I told my alarm clock we needed space. It still calls me every morning.', 'My keyboard wanted a promotion. It said it already had plenty of keys to success.', 'I tried to teach my plant Python. It prefers branching.', 'My assignment asked why I was staring at it. I said, "I am waiting for you to explain yourself."', 'My mouse joined a band. It handles all the clicks.', 'I asked my coffee for study advice. It said, "Let us take this one sip at a time."', 'My calendar is very popular. It has a date almost every day.', 'I saved my work in a folder called Finally Finished. It now contains seven versions.', 'My headphones are excellent listeners. They never interrupt my playlist.', 'I asked the printer for one small favour. It replied with a paper jam.', 'My browser has twenty tabs open. Apparently, it is also choosing a career.', 'I gave my code a break. It came back with an extra space and an indentation error.', 'My study group agreed to meet halfway. Now we are all standing in different places.']



COMMAND_WORDS = set("""lecture lectures tomorrow today yesterday next week weekly once
monday tuesday wednesday thursday friday saturday sunday update change reschedule
move postpone shift adjust edit rescheduled changed postponed delete remove drop
add create insert register subject subjects course class list show time date
hello help commands what when where who how are you your name python tkinter
joke jokes tell another please thanks thank tired sleepy exhausted drained bored
stressed overwhelmed sad feeling feel cancel fine good need break listen song
""".split())

SPELLING_ALIASES = {'tommorow':'tomorrow', 'tommorrow':'tomorrow', 'tmrw':'tomorrow',
    'leture':'lecture', 'letures':'lectures', 'lectuer':'lecture', 'lectuers':'lectures',
    'teh':'the', 'waht':'what', 'wht':'what', 'whats':'what is', 'whens':'when is',
    'wat':'what', 'whan':'when', 'tim':'time', 'hw':'how', 'ar':'are', 'u':'you', 'ur':'your', 'pls':'please',
    'plz':'please', 'ad':'add', 'nxt':'next', 'im':'i am', 'tierd':'tired',
    'jok':'joke', 'helo':'hello'}


def edit_distance(a, b):
    """Insertion, deletion, substitution and adjacent letter transposition."""
    grid = [[0]*(len(b)+1) for _ in range(len(a)+1)]
    for i in range(len(a)+1):
        grid[i][0] = i
    for j in range(len(b)+1):
        grid[0][j] = j
    for i in range(1,len(a)+1):
        for j in range(1,len(b)+1):
            grid[i][j] = min(grid[i-1][j]+1,grid[i][j-1]+1,
                             grid[i-1][j-1]+(a[i-1]!=b[j-1]))
            if i>1 and j>1 and a[i-1]==b[j-2] and a[i-2]==b[j-1]:
                grid[i][j] = min(grid[i][j],grid[i-2][j-2]+1)
    return grid[-1][-1]


def normalize_command(text):
    text = ' '.join(text.lower().replace('’', "'").split()).rstrip('.!?')
    def correct(match):
        word = match.group()
        if word in SPELLING_ALIASES:
            return SPELLING_ALIASES[word]
        if word in COMMAND_WORDS or len(word)<4 or len(word)>25:
            return word
        limit = 2 if len(word)>=6 else 1
        scores = [(edit_distance(word,c),c) for c in COMMAND_WORDS
                  if abs(len(c)-len(word))<=limit]
        scores = [(d,c) for d,c in scores if d<=limit and 1-d/max(len(word),len(c))>=0.72]
        scores.sort()
        if scores:
            equivalent = {'jokes':'joke', 'lectures':'lecture', 'subjects':'subject'}
            best = {equivalent.get(c,c) for d,c in scores if d==scores[0][0]}
            if len(best)==1:
                return best.pop()
        return word
    return re.sub(r"[a-z]+(?:'[a-z]+)?", correct, text)


def matching_subjects(query, lessons):
    """Match exact names first, then spelling errors in subject-name phrases."""
    query = ' '.join(query.lower().split()).rstrip('.!?')
    if not query:
        return []
    aliases = {'dbms':'advanced database management systems',
               'ooad':'object oriented analysis and design',
               'ai':'artificial intelligence and expert systems',
               'sqa':'software quality assurances'}
    query = aliases.get(query,query)
    exact = [s for s in lessons if query in s['subject'].lower() or query==s['code'].lower()]
    if exact:
        return exact
    if len(query)<4 or len(query)>150 or re.search(r'\d',query):
        return []
    words = re.findall(r'[a-z]+',query)
    ranked = []
    for lesson in lessons:
        subject_words = re.findall(r'[a-z]+',lesson['subject'].lower())
        for start in range(len(subject_words)-len(words)+1):
            phrase = ' '.join(subject_words[start:start+len(words)])
            distance = edit_distance(' '.join(words),phrase)
            if distance<=2 and 1-distance/max(len(query),len(phrase))>=0.75:
                ranked.append((distance,lesson))
                break
    if not ranked:
        return []
    best = min(d for d,_ in ranked)
    return [lesson for d,lesson in ranked if d==best]


def now():
    return datetime.now(SL_TIME)


def parse_date(text, today=None):
    today = today or now().date()
    text = text.strip().lower()
    if text.isalpha():
        corrected = normalize_command(text)
        if corrected in ('today', 'tomorrow'):
            text = corrected
    if text == 'today':
        return today
    if text == 'tomorrow':
        return today + timedelta(days=1)
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError('Use a date such as 2026-10-21 or 21/10/2026, or type today/tomorrow.')


def parse_times(text):
    parts = re.split(r'\s*(?:-|–|—|\bto\b)\s*', text.strip().lower())
    if len(parts) != 2:
        raise ValueError('Enter start and end time, for example 13:00-15:00 or 1 pm-3 pm.')
    result = []
    for part in parts:
        value = part.replace('.', ':').replace(' ', '')
        for fmt in ('%H:%M', '%I:%M%p', '%I%p'):
            try:
                result.append(datetime.strptime(value, fmt).strftime('%H:%M'))
                break
            except ValueError:
                continue
        else:
            raise ValueError('Use 24-hour times (13:00-15:00) or include am/pm on both times.')
    if result[0] >= result[1]:
        raise ValueError('The end time must be later than the start time on the same day.')
    return tuple(result)


def clock(value):
    return datetime.strptime(value, '%H:%M').strftime('%I:%M %p').lstrip('0')


class Schedule:
    def __init__(self, path=DB_PATH):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY, code TEXT, subject TEXT, room TEXT,
                selected INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS patterns (
                lesson_id INTEGER NOT NULL, effective TEXT NOT NULL,
                weekday INTEGER NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
                PRIMARY KEY (lesson_id, effective));
            CREATE TABLE IF NOT EXISTS changes (
                lesson_id INTEGER NOT NULL, original TEXT NOT NULL,
                new_date TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
                PRIMARY KEY (lesson_id, original));
        ''')
        self.db.executescript('\n            CREATE TABLE IF NOT EXISTS jokes (\n                id INTEGER PRIMARY KEY, text TEXT NOT NULL UNIQUE);\n            CREATE TABLE IF NOT EXISTS joke_queue (\n                position INTEGER PRIMARY KEY, joke_id INTEGER NOT NULL UNIQUE);\n            CREATE TABLE IF NOT EXISTS joke_history (\n                sequence INTEGER PRIMARY KEY AUTOINCREMENT, joke_id INTEGER NOT NULL);\n        ')
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO jokes(text) VALUES(?)', [(j,) for j in JOKES])
        self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
        if (not self.db.execute("SELECT 1 FROM metadata WHERE key='initialized'").fetchone()
                and not self.db.execute('SELECT 1 FROM lessons LIMIT 1').fetchone()):
            with self.db:
                for day, start, end, code, subject, room in SEED:
                    cur = self.db.execute('INSERT INTO lessons(code,subject,room,selected) VALUES(?,?,?,?)',
                                          (code, subject, room, int(subject not in OPTIONAL)))
                    self.db.execute('INSERT INTO patterns VALUES(?,?,?,?,?)',
                                    (cur.lastrowid, '2026-08-17', day, start, end))


        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES('initialized','1')")
            if not self.db.execute("SELECT 1 FROM metadata WHERE key='remove_social_v2'").fetchone():
                ids = [r[0] for r in self.db.execute(
                    "SELECT id FROM lessons WHERE lower(subject)=?",
                    ('social and professional issues in computing',))]
                for lesson_id in ids:
                    self.db.execute('DELETE FROM patterns WHERE lesson_id=?', (lesson_id,))
                    self.db.execute('DELETE FROM changes WHERE lesson_id=?', (lesson_id,))
                    self.db.execute('DELETE FROM lessons WHERE id=?', (lesson_id,))
                self.db.execute("INSERT INTO metadata VALUES('remove_social_v2','1')")

    def add_subject(self, subject, code, room, day, start, end, scope):
        with self.db:
            if any(s['subject'].casefold() == subject.casefold() for s in self.lessons()):
                raise ValueError('That subject already exists. Type cancel and use update time instead.')
            cur = self.db.execute('INSERT INTO lessons(code,subject,room,selected) VALUES(?,?,?,1)',
                                  (code,subject,room))
            if scope == 'weekly':
                self.db.execute('INSERT INTO patterns VALUES(?,?,?,?,?)',
                                (cur.lastrowid,day.isoformat(),day.weekday(),start,end))
            else:
                self.db.execute('INSERT INTO changes VALUES(?,?,?,?,?)',
                                (cur.lastrowid,day.isoformat(),day.isoformat(),start,end))
            return cur.lastrowid

    def delete_subject(self, lesson_id):
        with self.db:
            self.db.execute('DELETE FROM changes WHERE lesson_id=?',(lesson_id,))
            self.db.execute('DELETE FROM patterns WHERE lesson_id=?',(lesson_id,))
            self.db.execute('DELETE FROM lessons WHERE id=?',(lesson_id,))

    def lessons(self, selected=False):
        return [dict(r) for r in self.db.execute(
            'SELECT * FROM lessons' + (' WHERE selected=1' if selected else '') + ' ORDER BY id')]

    def choose(self, ids):
        with self.db:
            self.db.execute('UPDATE lessons SET selected=0')
            self.db.executemany('UPDATE lessons SET selected=1 WHERE id=?', [(i,) for i in ids])

    def pattern(self, lesson_id, day):
        row = self.db.execute('''SELECT * FROM patterns WHERE lesson_id=? AND effective<=?
                              ORDER BY effective DESC LIMIT 1''', (lesson_id, day.isoformat())).fetchone()
        return dict(row) if row else None

    def on(self, day):
        output = []
        ds = day.isoformat()
        for lesson in self.lessons(True):
            p = self.pattern(lesson['id'], day)
            changed = self.db.execute('SELECT 1 FROM changes WHERE lesson_id=? AND original=?',
                                      (lesson['id'], ds)).fetchone()
            if p and p['weekday'] == day.weekday() and not changed:
                output.append(dict(lesson, date=ds, original=ds, start=p['start'], end=p['end'], changed=False))
            for change in self.db.execute('SELECT * FROM changes WHERE lesson_id=? AND new_date=?',
                                          (lesson['id'], ds)):
                output.append(dict(lesson, date=ds, original=change['original'], start=change['start'],
                                   end=change['end'], changed=True))
        return sorted(output, key=lambda x: (x['start'], x['subject']))

    def save_once(self, lesson_id, original, new_date, start, end):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO changes VALUES(?,?,?,?,?)',
                            (lesson_id, original, new_date.isoformat(), start, end))

    def save_weekly(self, lesson_id, effective, start, end):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO patterns VALUES(?,?,?,?,?)',
                            (lesson_id, effective.isoformat(), effective.weekday(), start, end))

    def next_joke(self):


        with self.db:
            if not self.db.execute('SELECT 1 FROM joke_queue LIMIT 1').fetchone():
                ids = [r[0] for r in self.db.execute('SELECT id FROM jokes')]
                random.shuffle(ids)
                self.db.executemany('INSERT INTO joke_queue VALUES(?,?)', list(enumerate(ids)))
            recent = {r[0] for r in self.db.execute(
                'SELECT joke_id FROM joke_history ORDER BY sequence DESC LIMIT 5')}
            queue = self.db.execute('SELECT q.position,q.joke_id,j.text FROM joke_queue q '
                                    'JOIN jokes j ON j.id=q.joke_id ORDER BY q.position').fetchall()
            chosen = next((r for r in queue if r['joke_id'] not in recent), queue[0])
            self.db.execute('DELETE FROM joke_queue WHERE position=?', (chosen['position'],))
            self.db.execute('INSERT INTO joke_history(joke_id) VALUES(?)', (chosen['joke_id'],))
            self.db.execute('DELETE FROM joke_history WHERE sequence NOT IN '
                            '(SELECT sequence FROM joke_history ORDER BY sequence DESC LIMIT 20)')
            return chosen['text']

    def close(self):
        self.db.close()


HELP = ("Small spelling mistakes are accepted in supported questions. You can ask:\n"
        "• What are the lectures today?\n• Lectures tomorrow\n• Lectures on Monday\n"
        "• Lectures on 2026-10-21\n• What is my next lecture?\n• This week / next week\n"
        "• When is Software Project Management?\n• Update time / change lecture time\n• Add a subject\n• Delete a subject\n• List subjects\n• I am tired / I need a break\n• Tell me a joke / another one\n\n"
        "Use My subjects to choose your courses. While adding, deleting or updating, type cancel to stop.\n"
        "This is an offline, rule-based assistant. It answers when you ask; it does not send background alerts.")


def event_line(e):
    return (f"{clock(e['start'])}–{clock(e['end'])} | {e['subject']}\n"
            f"   {e['code']} | {e['room']}" + (' | Rescheduled' if e['changed'] else ''))


class Chatbot:
    def __init__(self, schedule, clock_fn=now):
        self.schedule = schedule
        self.clock_fn = clock_fn
        self.name = ''
        self.joke_context = None
        self.state = None
        self.pending = {}

    def day_text(self, day):
        events = self.schedule.on(day)
        result = day.strftime('%A, %d %B %Y') + '\n'
        if not events:
            return result + 'No lectures in your saved timetable.'
        result += '\n\n'.join(event_line(e) for e in events)
        if any(a['start'] < b['end'] and b['start'] < a['end']
               for i,a in enumerate(events) for b in events[i+1:]):
            result += '\n\nSome selected sessions overlap. Check My subjects or your saved changes.'
        return result

    def smalltalk(self, text):

        clean = text.replace("’", "'")
        previous = self.joke_context
        self.joke_context = None
        declines = ("no", "no thanks", "not now", "maybe later", "no thank you")
        refuses_joke = bool(re.search(r"\b(no|not|don't|dont|do not)\b.*\bjokes?\b", clean))
        if previous and (clean in declines or refuses_joke):
            return "No problem. Take your time."
        if refuses_joke:
            return "Okay, no jokes."
        direct = (bool(re.search(r"\bjokes?\b", clean)) or
                  clean in ('make me laugh', 'say something funny', 'tell me something funny'))
        accepts = clean in ('tell', 'tell me', 'tell one', 'yes', 'yes please', 'sure', 'okay', 'ok',
                            'go on', 'go ahead', 'please do', 'yes tell me', 'tell me please', 'please tell me')
        another = clean in ('another', 'another one', 'one more', 'more', 'tell another', 'next one')
        if direct or (previous and (accepts or another)):
            self.joke_context = 'told'
            return self.schedule.next_joke() + "\n\nWant another one?"

        feeling = re.search(r"\b(tired|sleepy|exhausted|drained|bored|stressed|overwhelmed|sad)\b", clean)
        negated = re.search(r"\b(not|never|don't|dont)\b.{0,12}\b(tired|sleepy|exhausted|drained|bored|stressed|overwhelmed|sad)\b", clean)
        expressed = (re.search(r"\b(i'm|im|i am|i feel|feeling)\b", clean) or
                     clean in ('tired','sleepy','exhausted','drained','bored','stressed','overwhelmed','sad'))
        needs_break = clean in ('i need a break', 'need a break', 'what a long day', "i've had a long day", 'i had a long day')
        if (feeling and expressed and not negated) or needs_break:
            if feeling and feeling.group() in ('sad','stressed','overwhelmed'):
                lead = "That sounds like a lot. It is okay to pause for a moment."
            elif feeling and feeling.group() == 'bored':
                lead = "A change of pace might be nice."
            else:
                lead = "Sounds like you could use a break."
            suggestion = random.choice([
                "Maybe put on a favourite relaxing song and take a few minutes for yourself.",
                "You could get some water, stretch a little, and listen to a song you enjoy.",
                "How about stepping away from the screen for a short rest?",
            ])
            self.joke_context = 'offered'
            return lead + " " + suggestion + "\n\nI can also tell you a joke. Want one?"
        return None

    def reply(self, message):
        raw_text = ' '.join(message.lower().split()).rstrip('.!?')
        text = normalize_command(raw_text) if not self.state else raw_text
        if text == 'cancel' or (self.state and raw_text in ('cancle','cancell')):
            self.joke_context = None
            self.state, self.pending = None, {}
            return 'Cancelled. Nothing was changed.'
        chat = self.smalltalk(text)
        if chat is not None:
            if self.state:
                if self.joke_context == 'told':
                    self.joke_context = None
                    chat = chat.replace('\n\nWant another one?', '')
                chat += '\n\nYour unfinished schedule change is still waiting. Say cancel to discard it, or continue with the previous question.'
            return chat
        if self.state:
            try:
                if self.state.startswith(('add_', 'delete_')):
                    return self.subject_flow(message.strip())
                return self.update_flow(message.strip())
            except ValueError as exc:
                return str(exc)
        if text in ('help', 'commands'):
            return HELP
        if text.startswith('my name is '):
            self.name = message.strip()[11:].strip()
            return 'Nice to meet you, ' + self.name + '!'
        if text == 'what is my name':
            return 'Your name is ' + self.name + '.' if self.name else 'Tell me: My name is Alex'
        if text in ('hi','hello','hey'):
            return 'Hello' + (', '+self.name if self.name else '') + '! How are you?'
        if text in ('fine', 'good', 'i am fine', "i'm fine", 'i am good', "i'm good"):
            return 'Glad to hear that!,How can I help you today?...'
        if text == 'how are you':
            return "I'm doing well, thanks! How are you?"
        if text in ('who are you','what is your name'):
            return "I'm Buddy. Nice to meet you!"
        if text in ('thanks','thank you'):
            return "You're welcome!"
        if text in ('bye','quit','exit'):
            return 'Goodbye! Close the window whenever you are finished. Your schedule is saved.'
        if text == 'what is python':
            return 'Python is a programming language used to build apps, websites and more.'
        if text == 'what is tkinter':
            return 'Tkinter provides the windows, buttons and text boxes for this app.'
        current = self.clock_fn()
        today = current.date()
        if text in ('time','what time is it'):
            return 'Sri Lanka time: ' + current.strftime('%I:%M %p')
        if text in ('date','what is the date'):
            return today.strftime('%A, %d %B %Y')
        if text in ('list subjects','show subjects','my subjects','subjects','list subject','show subject','my subject','subject'):
            items = self.schedule.lessons()
            return ('Your subjects:\n' + '\n'.join(s['subject'] + ('' if s['selected'] else ' (not selected)') for s in items)) if items else 'No subjects saved yet. Say add a subject.'
        if re.search(r'\b(add|create|insert|register)\b', text) and re.search(r'\b(subject|course|lecture|class|one)\b', text):
            self.pending = {}
            self.state = 'add_name'
            return 'What is the subject name? You can type cancel at any step.'
        if re.search(r'\b(delete|remove|drop)\b', text):
            if not self.schedule.lessons():
                return 'There are no subjects to delete. Say add a subject to create one.'
            self.pending = {}
            self.state = 'delete_subject'
            return 'Which subject do you want to delete? Enter its name or part of its name.'
        if not self.schedule.lessons(True):
            return 'No subjects are selected. Say add a subject, or choose existing ones in My subjects.'
        if re.search(r'\b(update|change|reschedule|move|postpone|shift|adjust|edit|rescheduled|changed|postponed)\b', text):
            self.pending = {}
            self.state = 'subject'
            return 'Which subject should I update? Type its name or part of its name. Type cancel at any step to stop.'
        if 'next' in text and ('lecture' in text or 'class' in text) and 'week' not in text:
            for offset in range(367):
                day = today + timedelta(days=offset)
                upcoming = [e for e in self.schedule.on(day)
                            if datetime.combine(day, datetime.strptime(e['start'], '%H:%M').time(), SL_TIME) >= current]
                if upcoming:
                    earliest = upcoming[0]['start']
                    return 'Next scheduled lecture(s):\n' + day.strftime('%A, %d %B %Y') + '\n\n' + '\n\n'.join(
                        event_line(e) for e in upcoming if e['start'] == earliest)
            return 'No upcoming lectures found in the next year.'
        if 'week' in text:
            first = today - timedelta(days=today.weekday())
            if 'next' in text:
                first += timedelta(days=7)
            return '\n\n'.join(self.day_text(first+timedelta(days=i)) for i in range(7))
        if 'tomorrow' in text:
            return self.day_text(today+timedelta(days=1))
        if 'today' in text:
            return self.day_text(today)
        match = re.search(r'\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4})\b', text)
        if match:
            try:
                return self.day_text(parse_date(match.group(), today))
            except ValueError as exc:
                return str(exc)
        for index, day_name in enumerate(DAYS):
            if re.search(r'\b'+day_name.lower()+r'\b', text):
                offset = (index-today.weekday()) % 7
                if 'next' in text and offset == 0:
                    offset = 7
                return self.day_text(today+timedelta(days=offset))
        query = re.sub(r'^(when is|when do i have|what time is)\s+', '', text).strip()

        raw_query = re.sub(r'^(when is|when do i have|what time is)\s+', '', raw_text).strip()
        matches = matching_subjects(raw_query, self.schedule.lessons(True))
        if not matches:
            matches = matching_subjects(query, self.schedule.lessons(True))
        if matches:
            ids = {s['id'] for s in matches}
            events = []
            for offset in range(31):
                d = today+timedelta(days=offset)
                events.extend((d,e) for e in self.schedule.on(d) if e['id'] in ids)
            return ('Upcoming matching sessions (next 30 days):\n\n' + '\n\n'.join(
                d.strftime('%a %d %b')+'\n'+event_line(e) for d,e in events)) if events else 'No matching sessions in the next 30 days.'
        return 'Try "lectures today", "lectures tomorrow", "next lecture", or "update time". Type help for more.'

    def subject_flow(self, message):
        text = message.lower().strip()
        p = self.pending
        if self.state == 'add_name':
            name = ' '.join(message.split())
            if len(name) < 2 or len(name) > 150:
                return 'Enter a subject name between 2 and 150 characters.'
            if any(s['subject'].casefold() == name.casefold() for s in self.schedule.lessons()):
                return 'That subject already exists. Enter a different name, or type cancel and use update time.'
            p['name'] = name
            self.state = 'add_code'
            return 'What is the course code? Type skip if you do not have one.'
        if self.state == 'add_code':
            p['code'] = '' if text == 'skip' else message
            self.state = 'add_scope'
            return 'Does this lecture happen once or every week? Reply once or weekly.'
        if self.state == 'add_scope':
            text = normalize_command(text)
            if text not in ('once','weekly','every week'):
                return 'Please type once or weekly.'
            p['scope'] = 'once' if text == 'once' else 'weekly'
            self.state = 'add_date'
            return 'What is the lecture date (or FIRST date for a weekly lecture)? Use YYYY-MM-DD, DD/MM/YYYY, today or tomorrow.'
        if self.state == 'add_date':
            p['date'] = parse_date(message,self.clock_fn().date())
            self.state = 'add_time'
            return 'What are the start and end times? Example: 13:00-15:00 or 1 pm-3 pm.'
        if self.state == 'add_time':
            p['start'],p['end'] = parse_times(message)
            self.state = 'add_room'
            return 'Where is the lecture? Enter the room, online link, or type skip.'
        if self.state == 'add_room':
            p['room'] = 'Not specified' if text == 'skip' else message
            self.state = 'add_confirm'
            conflicts = [e['subject'] for e in self.schedule.on(p['date']) if p['start'] < e['end'] and e['start'] < p['end']]
            warning = ('\nOverlaps on that date: '+', '.join(conflicts)) if conflicts else ''
            return (f"Add this subject?\n{p['name']} | {p['code'] or 'No code'}\n"
                    f"{p['date'].strftime('%A, %d %B %Y')} | {clock(p['start'])}–{clock(p['end'])}\n"
                    f"{p['room']} | {p['scope']}" + warning + '\nReply yes to save, or cancel.')
        if self.state == 'add_confirm':
            if text not in ('yes','save'):
                return 'Reply yes to save, or cancel.'
            self.schedule.add_subject(p['name'],p['code'],p['room'],p['date'],p['start'],p['end'],p['scope'])
            self.state,self.pending = None,{}
            return f"Added {p['name']} and saved its schedule."
        if self.state == 'delete_subject':
            matches = matching_subjects(text, self.schedule.lessons())
            if not matches:
                return 'No matching subject. Try part of its name, or type cancel.'
            p['matches'] = matches
            if len(matches) > 1:
                self.state = 'delete_choice'
                return 'Which one? Reply with its number:\n'+'\n'.join(f"{i}. {s['subject']}" for i,s in enumerate(matches,1))
            p['lesson'] = matches[0]
            self.state = 'delete_confirm'
            return self.delete_prompt()
        if self.state == 'delete_choice':
            if not text.isdigit() or not 1 <= int(text) <= len(p['matches']):
                return 'Enter one of the listed numbers.'
            p['lesson'] = p['matches'][int(text)-1]
            self.state = 'delete_confirm'
            return self.delete_prompt()
        if self.state == 'delete_confirm':
            if text not in ('yes','delete'):
                return 'Reply yes to delete this subject, or cancel to keep it.'
            self.schedule.delete_subject(p['lesson']['id'])
            self.state,self.pending = None,{}
            return f"Deleted {p['lesson']['subject']} and its saved sessions."

    def delete_prompt(self):
        return ('Delete '+self.pending['lesson']['subject']+' and ALL its weekly sessions and date changes?'
                '\nReply yes to delete, or cancel to keep it.')

    def update_flow(self, message):
        text = message.lower().strip()
        if self.state == 'subject':
            matches = matching_subjects(text, self.schedule.lessons(True))
            if not matches:
                return 'No selected subject matches. Try part of the name, or check My subjects.'
            self.pending = {'matches': matches}
            if len(matches) > 1:
                self.state = 'choice'
                return 'Which one? Reply with its number:\n' + '\n'.join(f"{i}. {s['subject']}" for i,s in enumerate(matches,1))
            self.pending['lesson'] = matches[0]
            self.state = 'scope'
            return 'Change '+matches[0]['subject']+' once or every week? Reply once or weekly.'
        if self.state == 'choice':
            if not text.isdigit() or not 1 <= int(text) <= len(self.pending['matches']):
                return 'Enter one of the listed numbers.'
            self.pending['lesson'] = self.pending['matches'][int(text)-1]
            self.state = 'scope'
            return 'Change this lecture once or every week? Reply once or weekly.'
        if self.state == 'scope':
            text = normalize_command(text)
            if text not in ('once','weekly','every week'):
                return 'Please type once or weekly.'
            self.pending['scope'] = 'once' if text == 'once' else 'weekly'
            self.state = 'original' if text == 'once' else 'new_date'
            return ('What is the CURRENT date of the lecture you want to move? Use YYYY-MM-DD or today/tomorrow.'
                    if text == 'once' else 'What is the FIRST date for the new weekly slot? It will repeat on that weekday from this date. Use YYYY-MM-DD.')
        if self.state == 'original':
            d = parse_date(message, self.clock_fn().date())
            matches = [e for e in self.schedule.on(d) if e['id'] == self.pending['lesson']['id']]
            if not matches:
                return 'That subject has no session on that date. Enter its current scheduled date.'
            if len(matches) > 1:
                return 'More than one session of this subject is on that date; use another date or cancel. This simple editor cannot select between duplicate sessions.'
            self.pending['original'] = matches[0]['original']
            self.state = 'new_date'
            return 'What is the NEW date? Use YYYY-MM-DD. Enter the same date if only the time changes.'
        if self.state == 'new_date':
            d = parse_date(message, self.clock_fn().date())
            if d < date(2026,8,17):
                return 'Enter a date on or after the timetable start, 2026-08-17.'
            self.pending['date'] = d
            self.state = 'time'
            return 'What are the new START and END times? Example: 13:00-15:00 or 1 pm-3 pm.'
        if self.state == 'time':
            start,end = parse_times(message)
            self.pending.update(start=start,end=end)
            p = self.pending
            conflicts = [e for e in self.schedule.on(p['date']) if start < e['end'] and e['start'] < end
                         and not (e['id'] == p['lesson']['id'] and
                                  (p['scope'] == 'weekly' or e['original'] == p['original']))]
            warning = ('\nTime overlap on that date: '+', '.join(e['subject'] for e in conflicts)) if conflicts else ''
            self.state = 'confirm'
            return (f"Save this change?\n{p['lesson']['subject']}\n"
                    f"{p['date'].strftime('%A, %d %B %Y')} | {clock(start)}–{clock(end)}\n"
                    + ('Only this occurrence.' if p['scope'] == 'once' else 'Every week from this date. Earlier weeks stay unchanged; existing one-off changes remain.')
                    + warning + '\nReply yes to save, or cancel.')
        if self.state == 'confirm':
            if text not in ('yes','save'):
                return 'Reply yes to save, or cancel to discard this change.'
            p = self.pending
            if p['scope'] == 'once':
                self.schedule.save_once(p['lesson']['id'],p['original'],p['date'],p['start'],p['end'])
            else:
                self.schedule.save_weekly(p['lesson']['id'],p['date'],p['start'],p['end'])
            self.state,self.pending = None,{}
            return 'Saved! I will remember this after you close the app.\n\n'+self.day_text(p['date'])


class MessageBubble(tk.Canvas):
    """Draw text and its rounded background together, with an explicit size."""
    def __init__(self, parent, who, text, timestamp, max_width):
        super().__init__(parent, bg='#171e22', highlightthickness=0, borderwidth=0)
        self.who, self.text, self.timestamp = who, text, timestamp
        self.set_width(max_width)

    def set_width(self, max_width):
        self.delete('all')
        mine = self.who == 'You'
        color = '#30645f' if mine else '#494064'
        muted = '#c0dbd4' if mine else '#d2c8e7'
        max_width = max(180, max_width)
        heading = self.create_text(18, 14, text=self.who, anchor='nw',
                                   fill='#d0e9e1' if mine else '#e4d9f7', font=('Segoe UI', 9, 'bold'))
        body = self.create_text(18, 36, text=self.text, anchor='nw',
                                width=max_width-36, fill='#f0f4f3',
                                font=('Segoe UI', 11), justify='left')
        bounds = self.bbox(body)
        stamp = self.create_text(18, bounds[3]+9, text=self.timestamp,
                                 anchor='nw', fill=muted, font=('Segoe UI', 8))
        boxes = [self.bbox(item) for item in (heading, body, stamp)]
        width = max(box[2]-box[0] for box in boxes)+36
        height = boxes[-1][3]+14
        self.coords(stamp, width-18, bounds[3]+9)
        self.itemconfigure(stamp, anchor='ne')
        radius = 18
        points = [radius, 0, width-radius, 0, width, 0, width, radius,
                  width, height-radius, width, height, width-radius, height,
                  radius, height, 0, height, 0, height-radius, 0, radius, 0, 0]
        background = self.create_polygon(points, smooth=True, splinesteps=24,
                                         fill=color, outline='')
        self.tag_lower(background)
        self.configure(width=width, height=height)


class ChatApp:
    def __init__(self, root, schedule):
        self.root, self.schedule = root, schedule
        self.bot = Chatbot(schedule)
        root.title('Buddy | University Lecture Planner')
        root.geometry('820x780')
        root.minsize(720,560)
        root.configure(bg='#171e22')
        header = tk.Frame(root,bg='#253a3b',padx=22,pady=16)
        header.pack(fill='x')
        tk.Label(header,text='Buddy',font=('Segoe UI',21,'bold'),bg='#253a3b',fg='white').pack(anchor='w')
        tk.Label(header,text='Let’s chat',font=('Segoe UI',11),bg='#253a3b',fg='#a9c7c1').pack(anchor='w')
        footer = tk.Frame(root,bg='#171e22',padx=18,pady=12)
        footer.pack(side='bottom',fill='x')
        tk.Label(footer,text='Message',bg='#171e22',fg='#c2cecd').pack(anchor='w')
        row = tk.Frame(footer,bg='#171e22')
        row.pack(fill='x',pady=5)
        self.entry = tk.Entry(row,font=('Segoe UI',12),relief='flat',
                              bg='#29343a',fg='#f0f4f3',insertbackground='#f0f4f3')
        self.entry.pack(side='left',fill='x',expand=True,ipady=10,padx=(0,10))
        self.entry.bind('<Return>',self.send)
        self.send_button = tk.Canvas(row, width=54, height=46, bg='#30645f',
                                     highlightthickness=1, highlightbackground='#30645f',
                                     highlightcolor='#d0e9e1', takefocus=True, cursor='hand2')
        self.send_button.pack(side='right')
        self.send_button.create_polygon(10, 20, 44, 7, 34, 38, 25, 27,
                                        fill='#d7ece5', outline='#f1faf6', width=1)
        self.send_button.create_polygon(10, 20, 44, 7, 25, 27,
                                        fill='#a5cdbf', outline='')
        self.send_button.create_line(25, 27, 44, 7, fill='#527e71', width=2)
        self.send_button.create_polygon(25, 27, 24, 36, 29, 32,
                                        fill='#86b9ac', outline='')
        self.send_button.bind('<Button-1>', self.send)
        self.send_button.bind('<Return>', self.send)
        self.send_button.bind('<space>', self.send)
        self.send_button.bind('<Enter>', lambda event:self.send_button.configure(bg='#3d7a72'))
        self.send_button.bind('<Leave>', lambda event:self.send_button.configure(bg='#30645f'))
        tk.Label(footer,text='Click the paper plane or press Enter to send • Right-click a message to copy',
                 bg='#171e22',fg='#9aabae',font=('Segoe UI',9)).pack(anchor='w')
        toolbar = tk.Frame(root,bg='#171e22',padx=18,pady=10)
        toolbar.pack(fill='x')
        for title,action in [('Today',lambda:self.ask('lectures today')),('Tomorrow',lambda:self.ask('lectures tomorrow')),
                             ('Next lecture',lambda:self.ask('next lecture')),('Update time',lambda:self.ask('update time')),
                             ('My subjects',self.subjects),('New chat',self.reset)]:
            tk.Button(toolbar,text=title,command=action,relief='flat',bg='#2b3b3f',fg='#deebe7',activebackground='#3b5656',activeforeground='white',padx=8,pady=7).pack(side='left',padx=(0,5))

        area = tk.Frame(root, bg='#171e22')
        area.pack(fill='both', expand=True, padx=18)
        self.canvas = tk.Canvas(area, bg='#171e22', highlightthickness=0)
        scroll = ttk.Scrollbar(area, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.messages = tk.Frame(self.canvas, bg='#171e22')
        self.message_window = self.canvas.create_window((0, 0), window=self.messages, anchor='nw')
        self.bubble_labels = []
        self.messages.bind('<Configure>', self.update_scroll)
        self.canvas.bind('<Configure>', self.resize_chat)

        root.bind('<MouseWheel>', self.scroll_chat)
        root.bind('<Button-4>', self.scroll_chat)
        root.bind('<Button-5>', self.scroll_chat)
        self.reset()
        root.protocol('WM_DELETE_WINDOW',self.close)

    def update_scroll(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def resize_chat(self, event):
        self.canvas.itemconfigure(self.message_window, width=event.width)
        for bubble in self.bubble_labels:
            bubble.set_width(int(event.width * 0.72))

    def scroll_chat(self, event):

        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget != self.canvas:
            widget = getattr(widget, 'master', None)
        if widget != self.canvas:
            return
        if self.canvas.yview() == (0.0, 1.0):
            return 'break'
        if event.num == 4:
            units = -3
        elif event.num == 5:
            units = 3
        else:
            units = -max(1, abs(event.delta) // 120) if event.delta > 0 else max(1, abs(event.delta) // 120)
        self.canvas.yview_scroll(units, 'units')
        return 'break'

    def copy_message(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def add_message(self, who, text):
        mine = who == 'You'
        row = tk.Frame(self.messages, bg='#171e22')
        row.pack(fill='x', pady=(6, 10), padx=6)
        side = 'right' if mine else 'left'
        bubble = MessageBubble(row, who, text,
                               now().strftime('%I:%M %p').lstrip('0'),
                               int(max(400, self.canvas.winfo_width()) * 0.72))
        bubble.pack(side=side, padx=(75, 0) if mine else (0, 75))
        self.bubble_labels.append(bubble)
        def show_menu(event):
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label='Copy message', command=lambda:self.copy_message(text))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()
        bubble.bind('<Button-3>', show_menu)
        self.root.update_idletasks()
        self.update_scroll()
        self.canvas.yview_moveto(1.0)

    def ask(self,text):
        if self.bot.state and text in ('lectures today','lectures tomorrow','next lecture','update time'):
            self.add_message('Buddy','Answer the current question, or type cancel first.')
            return
        self.add_message('You',text)
        try:
            answer = self.bot.reply(text)
        except sqlite3.Error as exc:
            answer = 'Could not save or read the database. Check that this folder is writable. Details: '+str(exc)
        self.add_message('Buddy',answer)
        self.entry.focus_set()

    def send(self,event=None):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0,'end')
            self.ask(text)
        return 'break'

    def reset(self):
        self.bot.joke_context = None
        self.bot.state,self.bot.pending = None,{}
        for widget in self.messages.winfo_children():
            widget.destroy()
        self.bubble_labels.clear()
        self.entry.delete(0,'end')
        self.add_message('Buddy', "Hi! How are you today?")
        self.entry.focus_set()

    def subjects(self):
        if self.bot.state:
            self.add_message('Buddy','Finish the current conversation, or type cancel before changing subjects.')
            return
        dialog = tk.Toplevel(self.root)
        dialog.title('Choose your subjects')
        dialog.geometry('900x620')
        dialog.minsize(660,440)
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog,text='Select ONLY the courses you attend. Use Ctrl-click for several rows.',padding=12).pack(anchor='w')
        ttk.Label(dialog,text='Rows show the current weekly pattern. Duplicate printed course codes are kept; use subject names.',padding=(12,0,12,10)).pack(anchor='w')
        bottom = ttk.Frame(dialog,padding=12)
        bottom.pack(side='bottom',fill='x')
        area = ttk.Frame(dialog)
        area.pack(fill='both',expand=True,padx=12)
        tree = ttk.Treeview(area,columns=('subject','code','slot','room'),show='headings',selectmode='extended')
        for key,title,width in [('subject','Subject',370),('code','Code',100),('slot','Weekly slot',200),('room','Room',110)]:
            tree.heading(key,text=title)
            tree.column(key,width=width,minwidth=60)
        scroll = ttk.Scrollbar(area,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y')
        tree.pack(fill='both',expand=True)
        for lesson in self.schedule.lessons():
            p = self.schedule.pattern(lesson['id'],now().date())
            slot = f"{DAYS[p['weekday']][:3]} {p['start']}-{p['end']}" if p else 'One-off / future session'
            key = str(lesson['id'])
            tree.insert('', 'end', iid=key, values=(lesson['subject'] + (' (optional)' if lesson['subject'] in OPTIONAL else ''),lesson['code'],slot,lesson['room']))
            if lesson['selected']:
                tree.selection_add(key)
        def save():
            try:
                self.schedule.choose([int(i) for i in tree.selection()])
            except sqlite3.Error as exc:
                messagebox.showerror('Could not save',str(exc),parent=dialog)
                return
            count = len(tree.selection())
            dialog.destroy()
            self.add_message('Buddy',f'Saved {count} selected subjects. Ask about today or tomorrow.')
        ttk.Button(bottom,text='Save selection',command=save).pack(side='right')
        ttk.Button(bottom,text='Select all',command=lambda:tree.selection_set(tree.get_children())).pack(side='left')
        ttk.Button(bottom,text='Clear selection',command=lambda:tree.selection_remove(tree.selection())).pack(side='left',padx=8)
        ttk.Button(bottom,text='Cancel',command=dialog.destroy).pack(side='left')

    def close(self):
        self.schedule.close()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    try:
        app = ChatApp(root,Schedule())
    except sqlite3.Error as exc:
        messagebox.showerror('Database error','Keep chatbot.py in a writable folder.\n'+str(exc))
        root.destroy()
    else:
        root.mainloop()
