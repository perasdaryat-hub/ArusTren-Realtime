#!/usr/bin/env python3
import os, json, sqlite3, hashlib, hmac, base64, secrets, time, uuid
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
PUBLIC=ROOT/'public'
DB=Path(os.environ.get('DB_PATH', ROOT/'arustren.sqlite'))
PORT=int(os.environ.get('PORT','3000'))
SECRET_VALUE=os.environ.get('JWT_SECRET','').strip()
if not SECRET_VALUE:
    SECRET_VALUE=secrets.token_urlsafe(48)
SECRET=SECRET_VALUE.encode()
clients=[]

def now(): return datetime.now(timezone.utc).isoformat()
def uid(p): return p+'_'+str(uuid.uuid4())
def conn():
    c=sqlite3.connect(DB, timeout=10); c.row_factory=sqlite3.Row; c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    c=conn(); c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE COLLATE NOCASE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'publisher',created_at TEXT NOT NULL,last_login_at TEXT);
    CREATE TABLE IF NOT EXISTS articles(id TEXT PRIMARY KEY,owner_id TEXT REFERENCES users(id) ON DELETE SET NULL,title TEXT NOT NULL,category TEXT NOT NULL,author TEXT NOT NULL,tags TEXT,cover TEXT,excerpt TEXT,summary TEXT,content TEXT NOT NULL,read_time TEXT,adsense_slot TEXT,date TEXT,created_at TEXT,updated_at TEXT,status TEXT DEFAULT 'published');
    CREATE TABLE IF NOT EXISTS article_views(id TEXT PRIMARY KEY,article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,visitor_id TEXT NOT NULL,session_id TEXT NOT NULL,viewed_at TEXT NOT NULL,UNIQUE(article_id,visitor_id,session_id));
    CREATE TABLE IF NOT EXISTS reactions(article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,visitor_id TEXT NOT NULL,type TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(article_id,visitor_id,type));
    CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,article_id TEXT NOT NULL REFERENCES articles(id) ON DELETE CASCADE,visitor_id TEXT NOT NULL,name TEXT NOT NULL,city TEXT,text TEXT NOT NULL,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS presence(visitor_id TEXT PRIMARY KEY,last_seen_at INTEGER NOT NULL,page TEXT);
    CREATE INDEX IF NOT EXISTS idx_views_article ON article_views(article_id); CREATE INDEX IF NOT EXISTS idx_presence ON presence(last_seen_at);
    '''); c.commit(); c.close()

def pw_hash(p):
    salt=secrets.token_bytes(16); dk=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,240000); return 'pbkdf2$240000$'+base64.urlsafe_b64encode(salt).decode()+'$'+base64.urlsafe_b64encode(dk).decode()
def pw_ok(p,s):
    try:
        _,it,sa,dk=s.split('$'); salt=base64.urlsafe_b64decode(sa.encode()); got=hashlib.pbkdf2_hmac('sha256',p.encode(),salt,int(it)); return hmac.compare_digest(got,base64.urlsafe_b64decode(dk.encode()))
    except: return False

def token(user_id,email,role):
    head=base64.urlsafe_b64encode(json.dumps({'alg':'HS256','typ':'JWT'},separators=(',',':')).encode()).rstrip(b'=').decode(); body=base64.urlsafe_b64encode(json.dumps({'sub':user_id,'email':email,'role':role,'exp':int(time.time())+7*86400},separators=(',',':')).encode()).rstrip(b'=').decode(); sig=base64.urlsafe_b64encode(hmac.new(SECRET,(head+'.'+body).encode(),hashlib.sha256).digest()).rstrip(b'=').decode(); return head+'.'+body+'.'+sig
def auth(headers):
    h=headers.get('Authorization','');
    if not h.startswith('Bearer '): return None
    try:
        a,b,s=h[7:].split('.'); expected=base64.urlsafe_b64encode(hmac.new(SECRET,(a+'.'+b).encode(),hashlib.sha256).digest()).rstrip(b'=').decode()
        if not hmac.compare_digest(s,expected): return None
        p=json.loads(base64.urlsafe_b64decode(b+'==')); return p if p.get('exp',0)>time.time() else None
    except: return None

def article(row,c):
    d=dict(row); d['views']=c.execute('SELECT COUNT(*) FROM article_views WHERE article_id=?',(d['id'],)).fetchone()[0]; rm={'suka':0,'informatif':0,'kagum':0};
    for x in c.execute('SELECT type,COUNT(*) n FROM reactions WHERE article_id=? GROUP BY type',(d['id'],)): rm[x['type']]=x['n']
    d['reactions']=rm; d['comments']=[dict(x) for x in c.execute('SELECT name,city,text,created_at FROM comments WHERE article_id=? ORDER BY created_at DESC LIMIT 100',(d['id'],))]; d['ownerId']=d.pop('owner_id',None); d['adsenseSlot']=d.pop('adsense_slot','') or ''; return d

def articles(c): return [article(x,c) for x in c.execute("SELECT * FROM articles WHERE status='published' ORDER BY created_at DESC")]
def broadcast(event):
    msg=f'event: {event}\ndata: '+json.dumps({'at':now()})+'\n\n'; dead=[]
    for w in list(clients):
        try: w.write(msg.encode()); w.flush()
        except: dead.append(w)
    for w in dead:
        if w in clients: clients.remove(w)

class H(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def send_json(self,obj,status=200):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def body(self):
        n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        u=urlparse(self.path); p=u.path
        if p=='/health':
            self.send_json({'ok':True,'service':'arustren','database':str(DB),'time':now()}); return
        if p=='/api/realtime':
            self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Cache-Control','no-cache'); self.send_header('Connection','keep-alive'); self.end_headers(); self.wfile.write(b'event: connected\ndata: {}\n\n'); self.wfile.flush(); clients.append(self.wfile)
            try:
                while True: time.sleep(25); self.wfile.write(b': heartbeat\n\n'); self.wfile.flush()
            except: 
                if self.wfile in clients: clients.remove(self.wfile)
            return
        c=conn()
        try:
            if p=='/api/stats':
                online=c.execute('SELECT COUNT(*) FROM presence WHERE last_seen_at>?',(int(time.time()*1000)-45000,)).fetchone()[0]; self.send_json({'users':c.execute('SELECT COUNT(*) FROM users').fetchone()[0],'articles':c.execute("SELECT COUNT(*) FROM articles WHERE status='published'").fetchone()[0],'views':c.execute('SELECT COUNT(*) FROM article_views').fetchone()[0],'online':online}); return
            if p=='/api/articles': self.send_json({'articles':articles(c)}); return
            if p.startswith('/api/articles/') and p.count('/')==3:
                a=c.execute('SELECT * FROM articles WHERE id=?',(p.rsplit('/',1)[1],)).fetchone(); self.send_json({'article':article(a,c)} if a else {'error':'Artikel tidak ditemukan.'},200 if a else 404); return
            if p=='/api/me':
                q=auth(self.headers); u=c.execute('SELECT id,email,role FROM users WHERE id=?',(q['sub'],)).fetchone() if q else None; self.send_json({'user':dict(u)} if u else {'error':'Login diperlukan.'},200 if u else 401); return
            if p=='/api/analytics/dashboard':
                q=auth(self.headers)
                if not q:return self.send_json({'error':'Login diperlukan.'},401)
                mine=c.execute("SELECT * FROM articles WHERE owner_id=? AND status='published' ORDER BY created_at DESC",(q['sub'],)).fetchall(); views=c.execute('SELECT COUNT(*) FROM article_views v JOIN articles a ON a.id=v.article_id WHERE a.owner_id=?',(q['sub'],)).fetchone()[0]; self.send_json({'totalArticles':len(mine),'totalViews':views,'activeSlots':sum(bool(x['adsense_slot']) for x in mine),'articles':[article(x,c) for x in mine],'revenue':None,'revenueStatus':'not_connected_to_adsense_reporting'}); return
            if p.startswith('/api/'):
                self.send_json({'error':'Endpoint tidak ditemukan.'},404); return
            fp=(PUBLIC/p.lstrip('/')).resolve()
            if PUBLIC not in fp.parents and fp!=PUBLIC: raise FileNotFoundError
            if not fp.is_file(): fp=PUBLIC/'index.html'
            data=fp.read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8' if fp.suffix=='.html' else 'application/octet-stream'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        finally: c.close()
    def do_POST(self): self.mutate('POST')
    def do_PUT(self): self.mutate('PUT')
    def do_DELETE(self): self.mutate('DELETE')
    def mutate(self,method):
        p=urlparse(self.path).path; b=self.body(); c=conn()
        try:
            if p=='/api/auth/register':
                email=str(b.get('email','')).strip().lower(); pw=str(b.get('password',''))
                if not email.endswith('@gmail.com') or len(pw)<8:return self.send_json({'error':'Gmail valid dan sandi minimal 8 karakter wajib.'},400)
                if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone():return self.send_json({'error':'Gmail tersebut sudah terdaftar.'},409)
                u={'id':uid('usr'),'email':email,'role':'publisher','created_at':now(),'last_login_at':now()}; c.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(u['id'],email,pw_hash(pw),u['role'],u['created_at'],u['last_login_at'])); c.commit(); broadcast('accounts'); return self.send_json({'token':token(u['id'],u['email'],u['role']),'user':{'id':u['id'],'email':email,'role':u['role']}})
            if p=='/api/auth/login':
                email=str(b.get('email','')).strip().lower(); u=c.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
                if not u or not pw_ok(str(b.get('password','')),u['password_hash']):return self.send_json({'error':'Gmail atau sandi salah.'},401)
                c.execute('UPDATE users SET last_login_at=? WHERE id=?',(now(),u['id']));c.commit();return self.send_json({'token':token(u['id'],u['email'],u['role']),'user':{'id':u['id'],'email':u['email'],'role':u['role']}})
            if p=='/api/bootstrap-samples':
                if c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]>0:return self.send_json({'imported':0})
                items=b.get('articles',[]); stmt='INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'; n=0
                for a in items:
                    if not a.get('title') or not a.get('content'):continue
                    t=now(); vals=(str(a.get('id',uid('art'))),None,str(a['title']),str(a.get('category','Viral & Hot')),str(a.get('author','Redaksi ArusTren')),str(a.get('tags','')),str(a.get('cover','')),str(a.get('excerpt','')),str(a.get('summary','')),str(a['content']),str(a.get('readTime','1 mnt')),str(a.get('adsenseSlot','')),str(a.get('date',datetime.now().strftime('%d/%m/%Y'))),t,t,'published');c.execute(stmt,vals);n+=1
                c.commit();broadcast('articles');return self.send_json({'imported':n})
            q=auth(self.headers)
            if p=='/api/analytics/view':
                if not all(b.get(x) for x in ('articleId','visitorId','sessionId')):return self.send_json({'error':'Identitas kunjungan tidak lengkap.'},400)
                try:c.execute('INSERT INTO article_views VALUES(?,?,?,?,?)',(uid('view'),b['articleId'],b['visitorId'],b['sessionId'],now()));c.commit();broadcast('analytics')
                except sqlite3.IntegrityError:pass
                return self.send_json({'recorded':True,'views':c.execute('SELECT COUNT(*) FROM article_views WHERE article_id=?',(b['articleId'],)).fetchone()[0]})
            if p=='/api/analytics/presence':
                if not b.get('visitorId'):return self.send_json({'error':'visitorId wajib.'},400)
                c.execute('INSERT INTO presence VALUES(?,?,?) ON CONFLICT(visitor_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,page=excluded.page',(b['visitorId'],int(time.time()*1000),b.get('page','portal')));c.commit();return self.send_json({'online':c.execute('SELECT COUNT(*) FROM presence WHERE last_seen_at>?',(int(time.time()*1000)-45000,)).fetchone()[0]})
            if not q:return self.send_json({'error':'Login diperlukan.'},401)
            if p=='/api/articles/import':
                n=0
                for a in b.get('articles',[]):
                    if not a.get('title') or not a.get('content'):continue
                    t=now(); c.execute('INSERT OR IGNORE INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(str(a.get('id',uid('art'))),q['sub'],a['title'],a.get('category','Viral & Hot'),a.get('author','Redaksi ArusTren'),a.get('tags',''),a.get('cover',''),a.get('excerpt',''),a.get('summary',a.get('excerpt','')),a['content'],a.get('readTime','1 mnt'),a.get('adsenseSlot',''),a.get('date',datetime.now().strftime('%d/%m/%Y')),t,t,'published'));n += 1 if c.execute('SELECT changes()').fetchone()[0] > 0 else 0
                c.commit();broadcast('articles');return self.send_json({'imported':n})
            if p.startswith('/api/articles/') and p.endswith('/reactions'):
                aid=p.split('/')[-2]; c.execute('INSERT OR IGNORE INTO reactions VALUES(?,?,?,?)',(aid,b.get('visitorId'),b.get('type'),now()));c.commit();broadcast('engagement');return self.send_json({'article':article(c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone(),c)})
            if p.startswith('/api/articles/') and p.endswith('/comments'):
                aid=p.split('/')[-2];c.execute('INSERT INTO comments VALUES(?,?,?,?,?,?,?)',(uid('com'),aid,b.get('visitorId'),str(b.get('name','Anonim')),str(b.get('city','Indonesia')),str(b.get('text','')),now()));c.commit();broadcast('engagement');return self.send_json({'article':article(c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone(),c)})
            if p=='/api/articles' and method=='POST':
                a=b;t=now();aid=uid('art');vals=(aid,q['sub'],str(a['title']),str(a.get('category','Viral & Hot')),str(a.get('author','Redaksi ArusTren')),str(a.get('tags','')),str(a.get('cover','')),str(a.get('excerpt','')),str(a.get('summary',a.get('excerpt',''))),str(a['content']),str(a.get('readTime','1 mnt')),str(a.get('adsenseSlot','')),datetime.now().strftime('%d/%m/%Y'),t,t,'published');c.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',vals);c.commit();broadcast('articles');return self.send_json({'article':article(c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone(),c)})
            if p.startswith('/api/articles/'):
                aid=p.rsplit('/',1)[1]; a=c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone()
                if not a:return self.send_json({'error':'Artikel tidak ditemukan.'},404)
                if a['owner_id']!=q['sub']:return self.send_json({'error':'Artikel ini bukan milik akunmu.'},403)
                if method=='DELETE':c.execute('DELETE FROM articles WHERE id=?',(aid,));c.commit();broadcast('articles');return self.send_json({'ok':True})
                if method=='PUT':
                    x=b;c.execute('UPDATE articles SET title=?,category=?,author=?,tags=?,cover=?,excerpt=?,summary=?,content=?,read_time=?,adsense_slot=?,updated_at=? WHERE id=?',(x['title'],x.get('category','Viral & Hot'),x.get('author','Redaksi ArusTren'),x.get('tags',''),x.get('cover',''),x.get('excerpt',''),x.get('summary',''),x['content'],x.get('readTime','1 mnt'),x.get('adsenseSlot',''),now(),aid));c.commit();broadcast('articles');return self.send_json({'article':article(c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone(),c)})
            return self.send_json({'error':'Endpoint tidak ditemukan.'},404)
        finally:c.close()

if __name__=='__main__': init_db(); print(f'ArusTren realtime server: http://localhost:{PORT}'); ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()