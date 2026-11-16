import os, secrets
from functools import wraps
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-local-troque-antes-de-publicar')
url = os.getenv('DATABASE_URL', 'sqlite:///kanban.db')
if url.startswith('postgres://'): url = url.replace('postgres://', 'postgresql+psycopg://', 1)
elif url.startswith('postgresql://'): url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config.update(SQLALCHEMY_DATABASE_URI=url, SQLALCHEMY_TRACK_MODIFICATIONS=False,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                  SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','false').lower() == 'true')
db = SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(160),unique=True,nullable=False,index=True); password_hash=db.Column(db.String(255),nullable=False)
class Board(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(120),nullable=False,default='Meu quadro'); owner_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
class Membership(db.Model):
    id=db.Column(db.Integer,primary_key=True); board_id=db.Column(db.Integer,db.ForeignKey('board.id'),nullable=False); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); role=db.Column(db.String(10),nullable=False,default='EDITOR')
    __table_args__=(UniqueConstraint('board_id','user_id'),)
class Task(db.Model):
    id=db.Column(db.Integer,primary_key=True); board_id=db.Column(db.Integer,db.ForeignKey('board.id'),nullable=False,index=True)
    title=db.Column(db.String(180),nullable=False); description=db.Column(db.Text,default=''); status=db.Column(db.String(20),default='todo',nullable=False)
    responsible=db.Column(db.String(100),default=''); deadline=db.Column(db.String(20),default=''); priority=db.Column(db.String(10),default='medium')
    labels=db.Column(db.String(500),default=''); points=db.Column(db.Integer,default=0); sprint=db.Column(db.String(100),default='')
class Comment(db.Model):
    id=db.Column(db.Integer,primary_key=True); task_id=db.Column(db.Integer,db.ForeignKey('task.id'),nullable=False,index=True); author=db.Column(db.String(100),nullable=False); text=db.Column(db.Text,nullable=False); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
class ChecklistItem(db.Model):
    id=db.Column(db.Integer,primary_key=True); task_id=db.Column(db.Integer,db.ForeignKey('task.id'),nullable=False,index=True); text=db.Column(db.String(240),nullable=False); done=db.Column(db.Boolean,default=False)
class Activity(db.Model):
    id=db.Column(db.Integer,primary_key=True); board_id=db.Column(db.Integer,db.ForeignKey('board.id'),nullable=False,index=True); who=db.Column(db.String(100),nullable=False); message=db.Column(db.String(240),nullable=False); created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))

def me():
    return db.session.get(User,session.get('user_id')) if session.get('user_id') else None
def auth(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not me(): return jsonify(error='Faça login para continuar.'),401
        return fn(*a,**kw)
    return w
def csrf(fn):
    @wraps(fn)
    def w(*a,**kw):
        if request.method in ('POST','PUT','PATCH','DELETE') and request.headers.get('X-CSRF-Token') != session.get('csrf_token'):
            return jsonify(error='Token de segurança inválido. Atualize a página.'),400
        return fn(*a,**kw)
    return w
def board_access(user):
    m=Membership.query.filter_by(user_id=user.id).order_by(Membership.id.desc()).first()
    return (db.session.get(Board,m.board_id),m) if m else (None,None)
def edit_ok(m): return m and m.role in ('OWNER','EDITOR')
def log(b,u,msg): db.session.add(Activity(board_id=b.id,who=u.name,message=msg))
def task_data(t):
    return {'id':t.id,'title':t.title,'description':t.description,'status':t.status,'responsible':t.responsible,'deadline':t.deadline,'priority':t.priority,'labels':[x for x in t.labels.split(',') if x],'points':t.points,'sprint':t.sprint,
      'comments':[{'id':c.id,'author':c.author,'text':c.text,'date':c.created_at.isoformat()} for c in Comment.query.filter_by(task_id=t.id).order_by(Comment.id).all()],
      'checklist':[{'id':c.id,'text':c.text,'done':c.done} for c in ChecklistItem.query.filter_by(task_id=t.id).all()]}
@app.get('/')
def home(): return render_template('index.html')
@app.get('/health')
def health(): return jsonify(status='ok')
@app.get('/api/csrf')
def get_csrf():
    session.setdefault('csrf_token',secrets.token_urlsafe(32)); return jsonify(token=session['csrf_token'])
@app.post('/api/register')
@csrf
def register():
    d=request.get_json(silent=True) or {}; name=(d.get('name') or '').strip(); email=(d.get('email') or '').strip().lower(); password=d.get('password') or ''
    if len(name)<2 or len(email)<5 or len(password)<8: return jsonify(error='Informe nome, e-mail válido e senha com pelo menos 8 caracteres.'),400
    if User.query.filter_by(email=email).first(): return jsonify(error='Este e-mail já está cadastrado.'),409
    u=User(name=name,email=email,password_hash=generate_password_hash(password)); db.session.add(u); db.session.flush()
    b=Board(name='Meu quadro',owner_id=u.id); db.session.add(b); db.session.flush(); db.session.add(Membership(board_id=b.id,user_id=u.id,role='OWNER')); db.session.commit()
    session.clear(); session['user_id']=u.id; session['csrf_token']=secrets.token_urlsafe(32); return jsonify(ok=True),201
@app.post('/api/login')
@csrf
def login():
    d=request.get_json(silent=True) or {}; u=User.query.filter_by(email=(d.get('email') or '').strip().lower()).first()
    if not u or not check_password_hash(u.password_hash,d.get('password') or ''): return jsonify(error='E-mail ou senha incorretos.'),401
    session.clear(); session['user_id']=u.id; session['csrf_token']=secrets.token_urlsafe(32); return jsonify(ok=True)
@app.post('/api/logout')
@auth
@csrf
def logout(): session.clear(); return jsonify(ok=True)
@app.get('/api/board')
@auth
def get_board():
    u=me(); b,m=board_access(u)
    if not b: return jsonify(error='Você não participa de um quadro.'),404
    memberships=Membership.query.filter_by(board_id=b.id).all(); users=[db.session.get(User,x.user_id) for x in memberships]
    ts=Task.query.filter_by(board_id=b.id).order_by(Task.id.desc()).all(); acts=Activity.query.filter_by(board_id=b.id).order_by(Activity.id.desc()).limit(20).all()
    return jsonify(board={'id':b.id,'name':b.name},me={'name':u.name,'email':u.email,'role':m.role},members=[{'name':x.name,'email':x.email,'role':y.role} for x,y in zip(users,memberships)],tasks=[task_data(t) for t in ts],activities=[{'who':a.who,'message':a.message,'date':a.created_at.isoformat()} for a in acts])
@app.put('/api/board')
@auth
@csrf
def rename_board():
    u=me(); b,m=board_access(u); name=((request.get_json(silent=True) or {}).get('name') or '').strip()
    if m.role!='OWNER': return jsonify(error='Somente o dono pode alterar o quadro.'),403
    if not name: return jsonify(error='Informe o nome.'),400
    b.name=name[:120]; db.session.commit(); return jsonify(ok=True)
@app.post('/api/members')
@auth
@csrf
def add_member():
    u=me(); b,m=board_access(u); d=request.get_json(silent=True) or {}; email=(d.get('email') or '').strip().lower(); role=d.get('role','EDITOR'); target=User.query.filter_by(email=email).first()
    if m.role!='OWNER': return jsonify(error='Somente o dono pode compartilhar.'),403
    if not target: return jsonify(error='Esse e-mail ainda não tem cadastro. Peça para a pessoa criar uma conta primeiro.'),404
    if role not in ('EDITOR','VIEWER'): return jsonify(error='Papel inválido.'),400
    if Membership.query.filter_by(board_id=b.id,user_id=target.id).first(): return jsonify(error='Essa pessoa já participa do quadro.'),409
    db.session.add(Membership(board_id=b.id,user_id=target.id,role=role)); log(b,u,f'adicionou {target.name} ao quadro'); db.session.commit(); return jsonify(ok=True),201
@app.delete('/api/members/<path:email>')
@auth
@csrf
def remove_member(email):
    u=me(); b,m=board_access(u); target=User.query.filter_by(email=email.lower()).first(); tm=Membership.query.filter_by(board_id=b.id,user_id=target.id).first() if target else None
    if m.role!='OWNER': return jsonify(error='Somente o dono pode remover participantes.'),403
    if not tm or tm.role=='OWNER': return jsonify(error='Participante não encontrado.'),404
    db.session.delete(tm); log(b,u,f'removeu {target.name} do quadro'); db.session.commit(); return jsonify(ok=True)
@app.post('/api/tasks')
@auth
@csrf
def create_task():
    u=me(); b,m=board_access(u); d=request.get_json(silent=True) or {}; title=(d.get('title') or '').strip()
    if not edit_ok(m): return jsonify(error='Seu perfil não pode criar tarefas.'),403
    if not title: return jsonify(error='O título é obrigatório.'),400
    status=d.get('status','todo'); priority=d.get('priority','medium')
    if status not in ('todo','doing','done') or priority not in ('low','medium','high'): return jsonify(error='Coluna ou prioridade inválida.'),400
    t=Task(board_id=b.id,title=title[:180],description=(d.get('description') or '')[:4000],status=status,responsible=(d.get('responsible') or u.name)[:100],deadline=(d.get('deadline') or '')[:20],priority=priority,labels=','.join(d.get('labels') or [])[:500],points=max(0,min(int(d.get('points') or 0),100)),sprint=(d.get('sprint') or '')[:100])
    db.session.add(t); log(b,u,f'criou a tarefa "{t.title}"'); db.session.commit(); return jsonify(task=task_data(t)),201
@app.put('/api/tasks/<int:tid>')
@auth
@csrf
def edit_task(tid):
    u=me(); b,m=board_access(u); t=Task.query.filter_by(id=tid,board_id=b.id).first_or_404(); d=request.get_json(silent=True) or {}
    if not edit_ok(m): return jsonify(error='Seu perfil não pode editar tarefas.'),403
    for k in ('title','description','status','responsible','deadline','priority','sprint'):
        if k in d: setattr(t,k,d[k])
    if 'labels' in d: t.labels=','.join(d['labels'] or [])
    if 'points' in d: t.points=max(0,min(int(d['points'] or 0),100))
    if t.status not in ('todo','doing','done') or t.priority not in ('low','medium','high'): return jsonify(error='Dados inválidos.'),400
    log(b,u,f'atualizou a tarefa "{t.title}"'); db.session.commit(); return jsonify(task=task_data(t))
@app.delete('/api/tasks/<int:tid>')
@auth
@csrf
def delete_task(tid):
    u=me(); b,m=board_access(u); t=Task.query.filter_by(id=tid,board_id=b.id).first_or_404()
    if not edit_ok(m): return jsonify(error='Seu perfil não pode excluir tarefas.'),403
    Comment.query.filter_by(task_id=t.id).delete(); ChecklistItem.query.filter_by(task_id=t.id).delete(); title=t.title; db.session.delete(t); log(b,u,f'excluiu a tarefa "{title}"'); db.session.commit(); return jsonify(ok=True)
@app.post('/api/tasks/<int:tid>/comments')
@auth
@csrf
def comment(tid):
    u=me(); b,m=board_access(u); t=Task.query.filter_by(id=tid,board_id=b.id).first_or_404(); txt=((request.get_json(silent=True) or {}).get('text') or '').strip()
    if not edit_ok(m): return jsonify(error='Seu perfil não pode comentar.'),403
    if not txt: return jsonify(error='Escreva um comentário.'),400
    db.session.add(Comment(task_id=t.id,author=u.name,text=txt[:2000])); log(b,u,f'comentou na tarefa "{t.title}"'); db.session.commit(); return jsonify(task=task_data(t)),201
@app.post('/api/tasks/<int:tid>/checklist')
@auth
@csrf
def checklist_add(tid):
    u=me(); b,m=board_access(u); t=Task.query.filter_by(id=tid,board_id=b.id).first_or_404(); txt=((request.get_json(silent=True) or {}).get('text') or '').strip()
    if not edit_ok(m): return jsonify(error='Sem permissão.'),403
    if not txt: return jsonify(error='Informe a subtarefa.'),400
    db.session.add(ChecklistItem(task_id=t.id,text=txt[:240])); db.session.commit(); return jsonify(task=task_data(t)),201
@app.patch('/api/checklist/<int:iid>')
@auth
@csrf
def checklist_toggle(iid):
    u=me(); b,m=board_access(u); item=db.session.get(ChecklistItem,iid)
    if not item or not Task.query.filter_by(id=item.task_id,board_id=b.id).first(): return jsonify(error='Subtarefa não encontrada.'),404
    if not edit_ok(m): return jsonify(error='Sem permissão.'),403
    item.done=bool((request.get_json(silent=True) or {}).get('done')); db.session.commit(); return jsonify(ok=True)
with app.app_context(): db.create_all()
if __name__=='__main__': app.run(debug=True)
